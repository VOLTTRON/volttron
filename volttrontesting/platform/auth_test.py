import json
import os
import time

import gevent
import pytest

from volttron.platform import jsonrpc
from volttron.platform import keystore
from volttrontesting.utils.utils import poll_gevent_sleep
from volttron.platform.vip.agent.errors import VIPError

def build_agent(platform, identity):
    """Build an agent, configure its keys and return the agent."""
    keys = keystore.KeyStore(os.path.join(platform.volttron_home,
                                          identity + '.keys'))
    keys.generate()
    agent = platform.build_agent(identity=identity,
                                 serverkey=platform.serverkey,
                                 publickey=keys.public,
                                 secretkey=keys.secret)
    # Make publickey easily accessible for these tests
    agent.publickey = keys.public
    return agent


def build_two_test_agents(platform):
    """Returns two agents for testing authorization

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    """
    agent1 = build_agent(platform, 'agent1')
    agent2 = build_agent(platform, 'agent2')
    gevent.sleep(1)

    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    agent1.vip.rpc.export(method=agent1.foo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')

    return agent1, agent2


def build_agents_with_capability_args(platform):
    """Returns two agents for testing authorization where one agent has
    rpc call with capability and argument restriction

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    """
    agent1 = build_agent(platform, 'agent1')
    gevent.sleep(1)
    agent2 = build_agent(platform, 'agent2')
    gevent.sleep(1)

    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    agent2.boo = lambda x, y: (x, y)
    agent2.boo.__name__ = 'boo'

    agent1.vip.rpc.export(method=agent1.foo)
    agent2.vip.rpc.export(method=agent2.boo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')
    agent2.vip.rpc.allow(agent2.boo, 'can_call_boo')

    return agent1, agent2


@pytest.mark.auth
def test_unauthorized_rpc_call1(volttron_instance_encrypt):
    """Tests an agent with no capabilities calling a method that
    requires one capability ("can_call_foo")
    """
    agent1, agent2 = build_two_test_agents(volttron_instance_encrypt)

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)


@pytest.mark.auth
def test_authorized_rpc_call1(volttron_instance_encrypt):
    """ Tests an agent with one capability calling a method that
    requires that same capability
    """
    agent1, agent2 = build_two_test_agents(volttron_instance_encrypt)
    volttron_instance_encrypt.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42


@pytest.mark.auth
def test_unauthorized_rpc_call2(volttron_instance_encrypt):
    """Tests an agent with one capability calling a method that
    requires two capabilites
    """
    agent1, agent2 = build_two_test_agents(volttron_instance_encrypt)

    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    volttron_instance_encrypt.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)

@pytest.mark.auth
def test_authorized_rpc_call2(volttron_instance_encrypt):
    """Tests an agent with two capability calling a method that
    requires those same two capabilites
    """
    agent1, agent2 = build_two_test_agents(volttron_instance_encrypt)

    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    volttron_instance_encrypt.add_capabilities(agent2.publickey,
                                                ['can_call_foo', 'can_call_foo2'])
    gevent.sleep(.1)
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42


@pytest.mark.auth
def test_rpc_call_with_capability_and_param_restrictions(volttron_instance_encrypt):
    """Tests an agent with capability and parameter restriction
    """
    agent1, agent2 = build_agents_with_capability_args(volttron_instance_encrypt)

    volttron_instance_encrypt.add_capabilities(agent2.publickey, {'can_call_foo': {'x': 1}})
    gevent.sleep(.1)

    # Attempt calling agent1.foo with invalid parameter value using args
    try:
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method foo only with x=1 but called with x=42"

    # Attempt calling agent1.foo with invalid parameter value using kwargs
    try:
        agent2.vip.rpc.call(agent1.core.identity, 'foo', x=42).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method foo only with x=1 but called with x=42"

    # successful call
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 1).get(timeout=1)
    assert result == 1

    volttron_instance_encrypt.add_capabilities(agent1.publickey, {'can_call_boo': {'x': 1}})
    gevent.sleep(.1)

    # Attempt calling agent2.boo with invalid parameter value for x and any value for y. Call should fail only when
    # x value is wrong
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 42, 43).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method boo only with x=1 but called with x=42"

    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 43).get(timeout=1)
    assert x == 1
    assert y == 43

    # set more than one parameter restriction
    volttron_instance_encrypt.add_capabilities(agent1.publickey, {'can_call_boo': {'x': 1, 'y': 2}})
    gevent.sleep(.1)

    # Attempt calling agent2.boo with valid parameter value for x and invalid value for y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 43).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method boo only with y=2 but called with y=43"

    # Attempt calling agent2.boo with invalid parameter value for x and valid value for y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 22, 2).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method boo only with x=1 but called with x=22"

    # Attempt calling agent2.boo with invalid parameter value for x and y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 22, 23).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User can call method boo only with x=1 but called with x=22" or \
               e.message == "User can call method boo only with y=2 but called with y=23"

    # Attempt calling agent2.boo with valid parameter value for x and y.
    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 2).get(timeout=1)
    assert x == 1
    assert y == 2

    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, y=2).get(timeout=1)
    assert x == 1
    assert y == 2


def build_two_agents_pubsub_agents(volttron_instance_encrypt, topic='foo'):
    """ Return two agents for testing protected pubsub

    The first agent is the subscriber.
    The second agent is the publisher.

    :param volttron_instance_encrypt:
    :param topic:
    :return:
    """
    agent1, agent2 = build_two_test_agents(volttron_instance_encrypt)
    gevent.sleep(1)
    msgs = []
    def got_msg(peer, sender, bus, topic, headers, message):
        print("Got message: {}".format(message))
        msgs.append(message)

    agent1.vip.pubsub.subscribe('pubsub', topic, callback=got_msg).get(timeout=1)
    return agent1, agent2, topic, msgs


@pytest.mark.auth
def test_pubsub_not_protected(volttron_instance_encrypt):
    """Tests pubsub without any topic protection """
    agent1, agent2, topic, msgs = build_two_agents_pubsub_agents(volttron_instance_encrypt)
    agent2.vip.pubsub.publish('pubsub', topic, message='hello agent').get(timeout=1)
    gevent.sleep(2.0)
    assert len(msgs) > 0
    assert msgs[0] == 'hello agent'
    #This was the old method for checking for the results. Not sure which method is better.
    #assert poll_gevent_sleep(2, lambda: len(msgs) > 0 and msgs[0] == 'hello agent')


def build_protected_pubsub(instance, topic, capabilities, topic_regex=None,
                          add_capabilities=False):
    """Returns dict that holds configuration for a protected-pubsub test."""
    agent1, agent2, topic, msgs = build_two_agents_pubsub_agents(instance,
                                                                 topic)
    topic_to_protect = topic_regex if topic_regex else topic
    topic_dict = {'write-protect': [{'topic': topic_to_protect,
                               'capabilities': capabilities}]}

    topic_file = os.path.join(instance.volttron_home, 'protected_topics.json')
    with open(topic_file, 'w') as f:
        json.dump(topic_dict, f)
        gevent.sleep(.5)

    if add_capabilities:
        instance.add_capabilities(agent2.publickey, capabilities)
        gevent.sleep(.2)

    return {'agent1': agent2, 'agent2': agent2, 'topic': topic,
            'instance': instance, 'messages': msgs,
            'capabilities': capabilities}


def pubsub_unauthorized(volttron_instance_encrypt, topic='foo', regex=None, peer='pubsub'):
    """Tests pubsub with a protected topic and the agents are not
    authorized to publish to the protected topic.
    """
    setup = build_protected_pubsub(volttron_instance_encrypt, topic,
                                  'can_publish_to_my_topic', regex)
    gevent.sleep(0.1)
    agent1 = setup['agent1']
    agent2 = setup['agent2']
    topic = setup['topic']
    try:
        agent2.vip.pubsub.publish(peer, topic, message='hello').get(timeout=2)
    except VIPError as e:
        assert e.msg == "to publish to topic \"{}\" requires ".format(topic) + \
            "capabilities ['can_publish_to_my_topic'], but capability list " \
            "{'edit_config_store': {'identity': 'agent2'}} was provided"


def pubsub_authorized(volttron_instance_encrypt, topic='foo', regex=None, peer='pubsub'):
    """Tests pubsub with a protected topic and an agents is
    authorized to publish to the protected topic.
    """
    setup = build_protected_pubsub(volttron_instance_encrypt, topic,
                                  'can_publish_to_my_topic', regex,
                                  add_capabilities=True)
    agent1 = setup['agent1']
    agent2 = setup['agent2']
    topic = setup['topic']
    msgs = setup['messages']
    agent2.vip.pubsub.publish(peer, topic, message='hello agent').get(timeout=2)
    assert poll_gevent_sleep(2, lambda: 'hello agent' in msgs)


@pytest.mark.auth
def test_pubsub_unauthorized(volttron_instance_encrypt):
    pubsub_unauthorized(volttron_instance_encrypt)


@pytest.mark.auth
def test_pubsub_authorized(volttron_instance_encrypt):
    pubsub_authorized(volttron_instance_encrypt)


@pytest.mark.auth
def test_pubsub_unauthorized_none_peer(volttron_instance_encrypt):
    pubsub_unauthorized(volttron_instance_encrypt, peer=None)


@pytest.mark.auth
def test_pubsub_authorized_none_peer(volttron_instance_encrypt):
    pubsub_authorized(volttron_instance_encrypt, peer=None)


@pytest.mark.auth
def test_pubsub_unauthorized_regex1(volttron_instance_encrypt):
    pubsub_unauthorized(volttron_instance_encrypt,
                        topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_authorized_regex1(volttron_instance_encrypt):
    pubsub_authorized(volttron_instance_encrypt,
                      topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_unauthorized_regex2(volttron_instance_encrypt):
    pubsub_unauthorized(volttron_instance_encrypt,
                        topic='foo/bar', regex='/foo\/.*/')


@pytest.mark.auth
def test_pubsub_authorized_regex2(volttron_instance_encrypt):
    pubsub_authorized(volttron_instance_encrypt,
                      topic='foo/bar', regex='/foo\/.*/')
