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

@pytest.mark.auth
def test_pubsub_not_protected(volttron_instance1_encrypt):
    '''
    Tests pubsub without any topic protection
    '''
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    agent1.last_msg = None
    def got_msg(peer, sender, bus, topic, headers, message):
        agent1.last_msg = message

    agent1.vip.pubsub.subscribe('pubsub', 'foo', callback=got_msg).get(timeout=1)
    agent2.vip.pubsub.publish('pubsub', 'foo', message='hello agent').get(timeout=1)
    gevent.sleep(2)
    assert agent1.last_msg == 'hello agent'

def write_protected_topic_to_file(platform, topic_dict):
    topic_file = os.path.join(platform.volttron_home, 'protected_topics.json')
    with open(topic_file, 'w') as f:
        json.dump(topic_dict, f)

@pytest.mark.auth
def test_pubsub_protected_not_authorized(volttron_instance1_encrypt):
    '''
    Tests pubsub with a protected topic and the agents are not authorized to
    publish to the protected topic.
    '''
    topic_dict = {'protect': [{'topic': 'foo', 'capabilities': ['can_publish_to_foo']}]}

    write_protected_topic_to_file(volttron_instance1_encrypt, topic_dict)
    gevent.sleep(1)

    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    agent1.last_msg = None
    def got_msg(peer, sender, bus, topic, headers, message):
        agent1.last_msg = message

    agent1.vip.pubsub.subscribe('pubsub', 'foo', callback=got_msg).get(timeout=1)

    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.pubsub.publish('pubsub', 'foo', message='hello').get(timeout=1)

@pytest.mark.auth
def test_pubsub_protected_and_authorized(volttron_instance1_encrypt):
    '''
    Tests pubsub with a protected topic and an agents is authorized to
    publish to the protected topic.
    '''
    topic_dict = {'protect': [{'topic': 'foo', 'capabilities': ['can_publish_to_foo']}]}

    write_protected_topic_to_file(volttron_instance1_encrypt, topic_dict)
    gevent.sleep(1)

    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    auth = {'allow':
        [
            {'credentials': 'CURVE:{}'.format(agent1.publickey)},
            {'credentials': 'CURVE:{}'.format(agent2.publickey),
             'capabilities': ['can_publish_to_foo']}
        ]}

    volttron_instance1_encrypt.set_auth_dict(auth)

    agent1.last_msg = None
    def got_msg(peer, sender, bus, topic, headers, message):
        agent1.last_msg = message

    agent1.vip.pubsub.subscribe('pubsub', 'foo', callback=got_msg).get(timeout=1)
    agent2.vip.pubsub.publish('pubsub', 'foo', message='hello agent').get(timeout=1)

    gevent.sleep(2)
    assert agent1.last_msg == 'hello agent'
