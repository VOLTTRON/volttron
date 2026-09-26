"""Unit tests for stop_agent_bounded (#3274).

A module-scoped test fixture's finalizer calls agent.core.stop() with no
timeout. When the agent's own core greenlet is already dead, or its
shutdown is wedged (an agentstop send that never returns while the
greenlet stays alive), that call never returns, so the whole test module
hangs in teardown and pytest never writes its JUnit XML. These tests
drive stop_agent_bounded against stubs and, for the wedged-shutdown case,
the real Core class, with no platform needed.
"""
import logging
import time

import gevent
import gevent.event
import pytest

from volttron.platform.vip.agent.core import ZMQCore
from volttrontesting.utils.utils import AgentStopTimeoutError
from volttrontesting.utils.utils import stop_agent_bounded


class _DeadCore:
    """Stands in for a core whose own greenlet has already died: stop()
    blocks forever, since nothing is left to service the request."""

    def __init__(self, identity):
        self.identity = identity
        self._never = gevent.event.Event()

    def stop(self, timeout=None):
        self._never.wait()


class _DeadAgent:
    def __init__(self, identity="dead.agent"):
        self.core = _DeadCore(identity)


class _WatchdogExpired(BaseException):
    """Test-only deadline signal, deliberately not an Exception: Core.stop
    guards its agentstop send with `except Exception`, which would
    otherwise swallow a plain TimeoutError and hide a real hang."""


class _Owner:
    """A minimal agent-like owner for ZMQCore construction."""


class _WedgingConnection:
    """A ZMQConnection stand-in whose send_vip never returns, reproducing
    a wedged agentstop notification with no real network I/O."""

    def __init__(self):
        self.socket = None
        self._forever = gevent.event.Event()

    def send_vip(self, peer, subsystem, args=None, msg_id=b'', user=b'',
                via=None, flags=0, copy=True, track=False):
        self._forever.wait()


class _AgentLike:
    def __init__(self, core):
        self.core = core


def _make_wedged_core(monkeypatch):
    """A real ZMQCore whose agentstop send blocks forever and whose
    greenlet also never exits on its own, driven directly through
    Core.stop without running the full vip_loop machinery.

    core._stop_event.wait(0.01) warms its .hub attribute so Core.stop's
    `gevent.get_hub() is self._stop_event.hub` check takes the inline
    halt() path, the same one a real running agent takes; without this,
    stop() would instead queue onto core._async, which nothing here
    services, which is a different (also real) unbounded path.
    """
    connection = _WedgingConnection()
    monkeypatch.setattr(
        'volttron.platform.vip.agent.core.ZMQConnection',
        lambda *a, **kw: connection)
    core = ZMQCore(_Owner(), address='fake://unittest', identity='wedged.agent',
                   enable_auth=False, messagebus='zmq')
    core.connection = connection
    core.connected = True
    core._stop_event = gevent.event.Event()
    core._stop_event.wait(0.01)
    stuck = gevent.spawn(lambda: gevent.event.Event().wait())
    gevent.sleep(0.05)
    core.greenlet = stuck
    return core, stuck


@pytest.mark.agent
def test_dead_core_stop_hangs_without_a_bound():
    """Control: proves the stub reproduces the hang stop_agent_bounded
    guards against. Bounded by this test's own outer timeout, not the
    helper's, so a regression in the helper cannot mask this failing."""
    agent = _DeadAgent()
    with pytest.raises(gevent.Timeout):
        with gevent.Timeout(1):
            agent.core.stop()


@pytest.mark.agent
def test_stop_agent_bounded_raises_and_logs_on_dead_core(caplog):
    agent = _DeadAgent(identity="dead.agent")
    start = time.time()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(AgentStopTimeoutError):
            stop_agent_bounded(agent, timeout=1)
    elapsed = time.time() - start

    assert elapsed < 5, f"stop_agent_bounded took {elapsed}s, expected ~1s"
    assert "dead.agent" in caplog.text
    assert "did not stop" in caplog.text


@pytest.mark.agent
def test_stop_agent_bounded_returns_on_a_normal_stop():
    class _OkCore:
        def stop(self, timeout=None):
            pass

    class _OkAgent:
        core = _OkCore()

    stop_agent_bounded(_OkAgent(), timeout=1)    # must not raise


@pytest.mark.agent
def test_stop_agent_bounded_logs_something_when_identity_is_missing(caplog):
    # No `identity` attribute at all: the fallback must still produce
    # readable text rather than crashing the log/error call itself.
    class _NoIdentityCore:
        def stop(self, timeout=None):
            gevent.event.Event().wait()

    class _NoIdentityAgent:
        core = _NoIdentityCore()

    agent = _NoIdentityAgent()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(AgentStopTimeoutError) as excinfo:
            stop_agent_bounded(agent, timeout=1)

    assert "did not stop" in caplog.text
    assert "did not stop" in str(excinfo.value)


@pytest.mark.agent
def test_stop_agent_bounded_reraises_a_callers_own_timeout():
    # A caller's own, shorter, outer gevent.Timeout must propagate as
    # itself, not be caught and misreported as this helper's own expiry.
    agent = _DeadAgent(identity="dead.agent")
    outer = gevent.Timeout(0.2)
    with pytest.raises(gevent.Timeout) as excinfo:
        with outer:
            stop_agent_bounded(agent, timeout=30)
    assert excinfo.value is outer


@pytest.mark.agent
def test_stop_agent_bounded_bounds_a_wedged_real_core(monkeypatch):
    # #3274 fix round 1: a single outer gevent.Timeout around a plain
    # core.stop() does not bound Core.stop's own second, internal join,
    # once that join happens inside the finally clause after the outer
    # timer already fired. Reproduced against the real Core class: the
    # agentstop send blocks, and the greenlet stays alive throughout.
    core, stuck = _make_wedged_core(monkeypatch)
    try:
        start = time.time()
        with gevent.Timeout(6, _WatchdogExpired('stop_agent_bounded hung')):
            with pytest.raises(AgentStopTimeoutError):
                stop_agent_bounded(_AgentLike(core), timeout=2)
        elapsed = time.time() - start
        assert elapsed < 6, f"stop_agent_bounded took {elapsed}s"
        assert stuck.ready(), (
            "stop_agent_bounded did not kill the wedged greenlet itself")
    finally:
        stuck.kill(block=True, timeout=3)
