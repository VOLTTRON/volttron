"""Unit tests for stop_agent_bounded (#3274).

A module-scoped test fixture's finalizer calls agent.core.stop() with no
timeout. When the agent's own core greenlet is already dead, that call
never returns, so the whole test module hangs in teardown and pytest never
writes its JUnit XML. These tests drive stop_agent_bounded against a stub
whose stop() never returns, with no real platform needed.
"""
import logging
import time

import gevent
import gevent.event
import pytest

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
def test_stop_agent_bounded_returns_and_logs_on_dead_core(caplog):
    agent = _DeadAgent(identity="dead.agent")
    start = time.time()
    with caplog.at_level(logging.WARNING):
        result = stop_agent_bounded(agent, timeout=1)
    elapsed = time.time() - start

    assert result is False
    assert elapsed < 5, f"stop_agent_bounded took {elapsed}s, expected ~1s"
    assert "dead.agent" in caplog.text
    assert "did not stop" in caplog.text


@pytest.mark.agent
def test_stop_agent_bounded_returns_true_on_a_normal_stop():
    class _OkCore:
        def stop(self, timeout=None):
            pass

    class _OkAgent:
        core = _OkCore()

    assert stop_agent_bounded(_OkAgent(), timeout=1) is True
