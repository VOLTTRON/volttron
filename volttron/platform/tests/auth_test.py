import json
import os

import gevent
import pytest

from .. import jsonrpc
from .. import keystore

def build_agent(platform, identity):
    keys = keystore.KeyStore(os.path.join(platform.volttron_home,
                                          identity + '.keys'))
    keys.generate()
    agent = platform.build_agent(identity=identity,
                                  serverkey=platform.publickey,
                                  publickey=keys.public(),
                                  secretkey=keys.secret())
    # Make publickey easily accessible for these tests
    agent.publickey = keys.public()
    return agent

def build_two_test_agents(platform):
    agent1 = build_agent(platform, 'agent1')
    gevent.sleep(0.1)
    agent2 = build_agent(platform, 'agent2')

    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    auth = {'allow':
        [
            {'credentials': 'CURVE:{}'.format(agent1.publickey)},
            {'credentials': 'CURVE:{}'.format(agent2.publickey)}
        ]}

    platform.set_auth_dict(auth)

    agent1.vip.rpc.export(method=agent1.foo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')

    gevent.sleep(1)
    return agent1, agent2

@pytest.mark.auth
def test_unauthorized_rpc_call1(volttron_instance1_encrypt):
    '''
    Tests an agent with no capabilities calling a method that requires one
    capability ("can_call_foo")
    '''
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)

@pytest.mark.auth
def test_authorized_rpc_call1(volttron_instance1_encrypt):
    '''
    Tests an agent with one capability calling a method that requires that
    same capability
    '''
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    auth = {'allow':
        [
            {'credentials': 'CURVE:{}'.format(agent1.publickey)},
            {'credentials': 'CURVE:{}'.format(agent2.publickey),
             'capabilities': ['can_call_foo']}
        ]}

    volttron_instance1_encrypt.set_auth_dict(auth)

    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42

@pytest.mark.auth
def test_unauthorized_rpc_call2(volttron_instance1_encrypt):
    '''
    Tests an agent with one capability calling a method that requires that
    two capabilites
    '''
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    auth = {'allow':
        [
            {'credentials': 'CURVE:{}'.format(agent1.publickey)},
            {'credentials': 'CURVE:{}'.format(agent2.publickey),
             'capabilities': ['can_call_foo']}
        ]}

    volttron_instance1_encrypt.set_auth_dict(auth)

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)

@pytest.mark.auth
def test_authorized_rpc_call2(volttron_instance1_encrypt):
    '''
    Tests an agent with two capability calling a method that requires those
    same two capabilites
    '''
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)
    
    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    auth = {'allow':
        [
            {'credentials': 'CURVE:{}'.format(agent1.publickey)},
            {'credentials': 'CURVE:{}'.format(agent2.publickey),
             'capabilities': ['can_call_foo', 'can_call_foo2']}
        ]}

    volttron_instance1_encrypt.set_auth_dict(auth)

    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42
