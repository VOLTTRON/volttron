import gevent
import pytest

from .. import jsonrpc 

@pytest.mark.auth
def test_unauthorized_rpc_call(volttron_instance1):
    assert volttron_instance1 is not None
    assert volttron_instance1.is_running()
    assert not volttron_instance1.list_agents()
    
    agent1 = volttron_instance1.build_agent(identity='agent1')
    agent2 = volttron_instance1.build_agent(identity='agent2')
    
    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'
    
    agent1.vip.rpc.export(method=agent1.foo) 
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')

    # If the agent is not authorized, then an exception will be raised
    try:
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    except jsonrpc.RemoteError:
        exception_caught = True
    assert exception_caught
