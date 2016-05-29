import json
import os
import time

import gevent
import pytest

from volttron.platform import jsonrpc
from volttron.platform import keystore
from volttrontesting.utils.utils import poll_gevent_sleep


def build_agent(platform, identity):
    '''Build an agent, configure its keys and return the agent.'''
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
    '''Returns two agents for testing authorization

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    '''
    agent1 = build_agent(platform, 'agent1')
    gevent.sleep(1)
    agent2 = build_agent(platform, 'agent2')

    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    agent1.vip.rpc.export(method=agent1.foo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')

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
    volttron_instance1_encrypt.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)
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

    volttron_instance1_encrypt.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)

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

    volttron_instance1_encrypt.add_capabilities(agent2.publickey,
                                                ['can_call_foo', 'can_call_foo2'])
    gevent.sleep(.1)
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42


def build_two_agents_pubsub_agents(volttron_instance1_encrypt, topic='foo'):
    """ Return two agents for testing protected pubsub

    The first agent is the subscriber.
    The second agent is the publisher.

    :param volttron_instance1_encrypt:
    :param topic:
    :return:
    """
    agent1, agent2 = build_two_test_agents(volttron_instance1_encrypt)

    msgs = []
    def got_msg(peer, sender, bus, topic, headers, message):
        msgs.append(message)

    agent1.vip.pubsub.subscribe('pubsub', topic, callback=got_msg).get(timeout=1)
    return agent1, agent2, topic, msgs


@pytest.mark.auth
def test_pubsub_not_protected(volttron_instance1_encrypt):
    '''Tests pubsub without any topic protection '''
    agent1, agent2, topic, msgs = build_two_agents_pubsub_agents(volttron_instance1_encrypt)
    agent2.vip.pubsub.publish('pubsub', topic, message='hello agent').get(timeout=1)
    assert poll_gevent_sleep(2, lambda: len(msgs) > 0 and msgs[0] == 'hello agent')


def build_protected_pubsub(instance, topic, capabilities, topic_regex=None,
                          add_capabilities=False):
    '''Returns dict that holds configuration for a protected-pubsub test.'''
    agent1, agent2, topic, msgs = build_two_agents_pubsub_agents(instance,
                                                                 topic)
    topic_to_protect = topic_regex if topic_regex else topic
    topic_dict = {'write-protect': [{'topic': topic_to_protect,
                               'capabilities': capabilities}]}

    topic_file = os.path.join(instance.volttron_home, 'protected_topics.json')
    with open(topic_file, 'w') as f:
        json.dump(topic_dict, f)
        gevent.sleep(.1)

    if add_capabilities:
        instance.add_capabilities(agent2.publickey, capabilities)
        gevent.sleep(.1)

    return {'agent1': agent2, 'agent2': agent2, 'topic': topic,
            'instance': instance, 'messages': msgs,
            'capabilities': capabilities}


def pubsub_unauthorized(volttron_instance1_encrypt, topic='foo', regex=None, peer='pubsub'):
    '''
    Tests pubsub with a protected topic and the agents are not authorized to
    publish to the protected topic.
    '''
    setup = build_protected_pubsub(volttron_instance1_encrypt, topic,
                                  'can_publish_to_my_topic', regex)

    agent2 = setup['agent2']
    topic = setup['topic']
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.pubsub.publish(peer, topic, message='hello').get(timeout=1)


def pubsub_authorized(volttron_instance1_encrypt, topic='foo', regex=None, peer='pubsub'):
    '''
    Tests pubsub with a protected topic and an agents is authorized to
    publish to the protected topic.
    '''
    setup = build_protected_pubsub(volttron_instance1_encrypt, topic,
                                  'can_publish_to_my_topic', regex,
                                  add_capabilities=True)
    agent1 = setup['agent1']
    agent2 = setup['agent2']
    topic = setup['topic']
    msgs = setup['messages']
    agent2.vip.pubsub.publish(peer, topic, message='hello agent').get(timeout=1)
    assert poll_gevent_sleep(2, lambda: 'hello agent' in msgs)


@pytest.mark.auth
def test_pubsub_unauthorized(volttron_instance1_encrypt):
    pubsub_unauthorized(volttron_instance1_encrypt)


@pytest.mark.auth
def test_pubsub_authorized(volttron_instance1_encrypt):
    pubsub_authorized(volttron_instance1_encrypt)


@pytest.mark.auth
def test_pubsub_unauthorized_none_peer(volttron_instance1_encrypt):
    pubsub_unauthorized(volttron_instance1_encrypt, peer=None)


@pytest.mark.auth
def test_pubsub_authorized_none_peer(volttron_instance1_encrypt):
    pubsub_authorized(volttron_instance1_encrypt, peer=None)


@pytest.mark.auth
def test_pubsub_unauthorized_regex1(volttron_instance1_encrypt):
    pubsub_unauthorized(volttron_instance1_encrypt,
                        topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_authorized_regex1(volttron_instance1_encrypt):
    pubsub_authorized(volttron_instance1_encrypt,
                      topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_unauthorized_regex2(volttron_instance1_encrypt):
    pubsub_unauthorized(volttron_instance1_encrypt,
                        topic='foo/bar', regex='/foo\/.*/')


@pytest.mark.auth
def test_pubsub_authorized_regex2(volttron_instance1_encrypt):
    pubsub_authorized(volttron_instance1_encrypt,
                      topic='foo/bar', regex='/foo\/.*/')
