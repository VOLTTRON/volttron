"""build_agent must not leave a running core behind when the connection times out.

An orphaned core can still connect when the router's welcome arrives late and then
holds the identity for the life of the process; the router silently drops every
later connection with that identity (see the forwarder "conflicting identity"
failures that only clear on restart).
"""

import gevent
import pytest

from volttron.platform.vip.agent import utils as agent_utils


class _FakeCore:
    def __init__(self, connects, stop_result):
        self.identity = "remote.forwarder"
        self.connects = connects
        self.stop_result = stop_result
        self.stop_timeouts = []
        self.greenlet = None

    def run(self, event):
        self.greenlet = gevent.getcurrent()
        if self.connects:
            event.set()
        gevent.sleep(3600)

    def stop(self, timeout=None):
        self.stop_timeouts.append(timeout)
        if self.stop_result:
            self.greenlet.kill(block=False)
        return self.stop_result


class _FakeAgent:
    connects = False
    stop_result = True
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.core = _FakeCore(self.connects, self.stop_result)
        _FakeAgent.instances.append(self)


def _build(connects, stop_result=True, timeout=0.05):
    _FakeAgent.connects = connects
    _FakeAgent.stop_result = stop_result
    _FakeAgent.instances = []
    return agent_utils.build_agent(address="tcp://127.0.0.1:1", identity="remote.forwarder",
                                   publickey="pub", secretkey="sec", serverkey="srv",
                                   agent_class=_FakeAgent, timeout=timeout)


def test_timeout_stops_the_unconnected_core():
    with pytest.raises(gevent.Timeout):
        _build(connects=False)
    (agent,) = _FakeAgent.instances
    assert agent.core.stop_timeouts == [0.05]
    gevent.sleep(0)
    assert agent.core.greenlet.dead


def test_timeout_kills_the_core_when_stop_does_not_finish():
    with pytest.raises(gevent.Timeout):
        _build(connects=False, stop_result=False)
    (agent,) = _FakeAgent.instances
    assert agent.core.stop_timeouts == [0.05]
    assert agent.core.greenlet.dead


def test_connected_agent_is_returned_with_its_core_running():
    agent = _build(connects=True)
    assert agent is _FakeAgent.instances[0]
    assert agent.core.stop_timeouts == []
    assert not agent.core.greenlet.dead
    agent.core.greenlet.kill()
