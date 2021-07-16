import os

import gevent
import pytest

from volttron.platform import jsonrpc
from volttron.platform import keystore
from volttron.platform.agent.known_identities import AUTH
from volttrontesting.utils.utils import poll_gevent_sleep
from volttron.platform.vip.agent.errors import VIPError
from volttron.platform import jsonapi
from volttron.platform.auth import AuthFile


@pytest.fixture
def build_two_test_agents(volttron_instance):
    """Returns two agents for testing authorization

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    """
    agent1 = volttron_instance.build_agent(identity='agent1')
    gevent.sleep(4)
    agent2 = volttron_instance.build_agent(identity='agent2')
    gevent.sleep(4)

    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    agent1.vip.rpc.export(method=agent1.foo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')

    try:
        yield agent1, agent2
    finally:
        agent1.core.stop()
        agent2.core.stop()
        auth_file = AuthFile(os.path.join(volttron_instance.volttron_home, 'auth.json'))
        allow_entries = auth_file.read_allow_entries()
        auth_file.remove_by_indices(list(range(3, len(allow_entries))))
        # TODO if we have to wait for auth propagation anyways why do we create new agents for each test case
        #  we should just update capabilities, at least we will save on agent creation and tear down time
        gevent.sleep(3)


@pytest.fixture
def build_agents_with_capability_args(volttron_instance):
    """Returns two agents for testing authorization where one agent has
    rpc call with capability and argument restriction

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    """
    # Can't call the fixture directly so build our own agent here.
    agent1 = volttron_instance.build_agent(identity='agent1')
    gevent.sleep(4)
    agent2 = volttron_instance.build_agent(identity='agent2')
    gevent.sleep(4)


    agent1.foo = lambda x: x
    agent1.foo.__name__ = 'foo'

    agent2.boo = lambda x, y: (x, y)
    agent2.boo.__name__ = 'boo'

    agent1.vip.rpc.export(method=agent1.foo)
    agent2.vip.rpc.export(method=agent2.boo)
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo')
    agent2.vip.rpc.allow(agent2.boo, 'can_call_boo')

    yield agent1, agent2

    agent1.core.stop()
    agent2.core.stop()
    auth_file = AuthFile(os.path.join(volttron_instance.volttron_home, 'auth.json'))
    allow_entries = auth_file.read_allow_entries()
    auth_file.remove_by_indices(list(range(3, len(allow_entries))))
    gevent.sleep(0.5)


@pytest.fixture
def build_protected_pubsub(volttron_instance, build_two_agents_pubsub_agents):

    def protected_pubsub_fn(topic, capabilities, topic_regex=None,
                          add_capabilities=False):
        """Returns dict that holds configuration for a protected-pubsub test."""
        agent1, agent2, topic, msgs = build_two_agents_pubsub_agents(topic)
        topic_to_protect = topic_regex if topic_regex else topic
        topic_dict = {'write-protect': [{'topic': topic_to_protect,
                                         'capabilities': capabilities}]}

        topic_file = os.path.join(volttron_instance.volttron_home, 'protected_topics.json')
        with open(topic_file, 'w') as f:
            jsonapi.dump(topic_dict, f)
            gevent.sleep(1)

        if add_capabilities:
            volttron_instance.add_capabilities(agent2.publickey, capabilities)
            gevent.sleep(2)

        return {'agent1': agent2, 'agent2': agent2, 'topic': topic,
                'instance': volttron_instance, 'messages': msgs,
                'capabilities': capabilities}
    yield protected_pubsub_fn

    os.remove(os.path.join(volttron_instance.volttron_home, 'protected_topics.json'))


@pytest.fixture
def build_two_agents_pubsub_agents(build_two_test_agents):
    """ Return two agents for testing protected pubsub

    The first agent is the subscriber.
    The second agent is the publisher.

    :param volttron_instance:
    :param topic:
    :return:
    """
    agent1, agent2 = build_two_test_agents
    gevent.sleep(1)
    msgs = []

    def build_pubsub_agent_fn(topic='foo'):
        def got_msg(peer, sender, bus, topic, headers, message):
            print("Got message: {}".format(message))
            msgs.append(message)

        agent1.vip.pubsub.subscribe('pubsub', topic, callback=got_msg).get(timeout=1)
        gevent.sleep(1)
        return agent1, agent2, topic, msgs
    yield build_pubsub_agent_fn


# utility method for pubsub tests
def pubsub_unauthorized(build_protected_pubsub, topic='foo', regex=None, peer='pubsub'):
    """Tests pubsub with a protected topic and the agents are not
    authorized to publish to the protected topic.
    """
    setup = build_protected_pubsub(topic, 'can_publish_to_my_topic', regex)
    gevent.sleep(0.5)
    agent1 = setup['agent1']
    agent2 = setup['agent2']
    topic = setup['topic']
    try:
        agent2.vip.pubsub.publish(peer, topic, message='hello').get(timeout=2)
    except VIPError as e:
        assert e.msg == "to publish to topic \"{}\" requires ".format(topic) + \
            "capabilities ['can_publish_to_my_topic'], but capability list " \
            "{'edit_config_store': {'identity': 'agent2'}} was provided"


# utility method for pubsub tests
def pubsub_authorized(build_protected_pubsub, topic='foo', regex=None, peer='pubsub'):
    """Tests pubsub with a protected topic and an agents is
    authorized to publish to the protected topic.
    """
    setup = build_protected_pubsub(topic, 'can_publish_to_my_topic', regex, add_capabilities=True)
    agent1 = setup['agent1']
    agent2 = setup['agent2']
    topic = setup['topic']
    msgs = setup['messages']
    agent2.vip.pubsub.publish(peer, topic, message='hello agent').get(timeout=2)
    assert poll_gevent_sleep(2, lambda: 'hello agent' in msgs)


@pytest.mark.auth
def test_unauthorized_rpc_call1(volttron_instance, build_two_test_agents):
    """Tests an agent with no capabilities calling a method that
    requires one capability ("can_call_foo")
    """
    (agent1, agent2) = build_two_test_agents

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)


@pytest.mark.auth
def test_authorized_rpc_call1(volttron_instance, build_two_test_agents):
    """ Tests an agent with one capability calling a method that
    requires that same capability
    """
    agent1, agent2 = build_two_test_agents
    volttron_instance.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42


@pytest.mark.auth
def test_unauthorized_rpc_call2(volttron_instance, build_two_test_agents):
    """Tests an agent with one capability calling a method that
    requires two capabilites
    """
    agent1, agent2 = build_two_test_agents

    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    volttron_instance.add_capabilities(agent2.publickey, 'can_call_foo')
    gevent.sleep(.1)

    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)

@pytest.mark.auth
def test_authorized_rpc_call2(volttron_instance, build_two_test_agents):
    """Tests an agent with two capability calling a method that
    requires those same two capabilites
    """
    agent1, agent2 = build_two_test_agents

    # Add another required capability
    agent1.vip.rpc.allow(agent1.foo, 'can_call_foo2')

    volttron_instance.add_capabilities(agent2.publickey,
                                                ['can_call_foo', 'can_call_foo2'])
    gevent.sleep(.1)
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=2)
    assert result == 42


@pytest.mark.auth
def test_get_rpc_method_authorizations(volttron_instance, build_two_test_agents):
    (agent1, agent2) = build_two_test_agents
    volttron_instance.add_capabilities(agent2.publickey, 'modify_rpc_method_allowance')
    gevent.sleep(1)
    agent1_rpc_authorizations = agent2.vip.rpc.call(AUTH, 'auth.get_rpc_authorizations', 'approve_authorization_failure').get(timeout=2)
    assert len(agent1_rpc_authorizations) == 1


@pytest.mark.auth
def test_set_rpc_method_authorizations(volttron_instance, build_two_test_agents):
    (agent1, agent2) = build_two_test_agents
    volttron_instance.add_capabilities(agent2.publickey, 'modify_rpc_method_allowance')
    volttron_instance.add_capabilities(agent2.publickey, 'test_authorization_1')
    # If the agent is not authorized, then an exception will be raised
    with pytest.raises(jsonrpc.RemoteError):
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)

    agent2.vip.rpc.call(agent1.core.identity, 'auth.set_rpc_authorizations', 'foo', 'test_authorization_1')

    return_val = agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)
    assert return_val == 42


@pytest.mark.auth
def test_rpc_call_with_capability_and_param_restrictions(volttron_instance, build_agents_with_capability_args):
    """Tests an agent with capability and parameter restriction
    """
    agent1, agent2 = build_agents_with_capability_args

    volttron_instance.add_capabilities(agent2.publickey, {'can_call_foo': {'x': 1}})
    gevent.sleep(.1)

    # Attempt calling agent1.foo with invalid parameter value using args
    try:
        agent2.vip.rpc.call(agent1.core.identity, 'foo', 42).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent2 can call method foo only with x=1 but called with x=42"

    # Attempt calling agent1.foo with invalid parameter value using kwargs
    try:
        agent2.vip.rpc.call(agent1.core.identity, 'foo', x=42).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent2 can call method foo only with x=1 but called with x=42"

    # successful call
    result = agent2.vip.rpc.call(agent1.core.identity, 'foo', 1).get(timeout=1)
    assert result == 1

    volttron_instance.add_capabilities(agent1.publickey, {'can_call_boo': {'x': 1}})
    gevent.sleep(.1)

    # Attempt calling agent2.boo with invalid parameter value for x and any value for y. Call should fail only when
    # x value is wrong
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 42, 43).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent1 can call method boo only with x=1 but called with x=42"

    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 43).get(timeout=1)
    assert x == 1
    assert y == 43

    # set more than one parameter restriction
    volttron_instance.add_capabilities(agent1.publickey, {'can_call_boo': {'x': 1, 'y': 2}})
    gevent.sleep(.1)

    # Attempt calling agent2.boo with valid parameter value for x and invalid value for y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 43).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent1 can call method boo only with y=2 but called with y=43"

    # Attempt calling agent2.boo with invalid parameter value for x and valid value for y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 22, 2).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent1 can call method boo only with x=1 but called with x=22"

    # Attempt calling agent2.boo with invalid parameter value for x and y.
    try:
        agent1.vip.rpc.call(agent2.core.identity, 'boo', 22, 23).get(timeout=1)
        assert False
    except jsonrpc.RemoteError as e:
        assert e.message == "User agent1 can call method boo only with x=1 but called with x=22" or \
               e.message == "User agent1 can call method boo only with y=2 but called with y=23"

    # Attempt calling agent2.boo with valid parameter value for x and y.
    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, 2).get(timeout=1)
    assert x == 1
    assert y == 2

    x, y = agent1.vip.rpc.call(agent2.core.identity, 'boo', 1, y=2).get(timeout=1)
    assert x == 1
    assert y == 2

#fails
@pytest.mark.auth
def test_pubsub_not_protected(build_two_agents_pubsub_agents):
    """Tests pubsub without any topic protection """
    agent1, agent2, topic, msgs = build_two_agents_pubsub_agents()
    agent2.vip.pubsub.publish('pubsub', topic, message='hello agent').get(timeout=1)
    gevent.sleep(2.0)
    assert len(msgs) > 0
    assert msgs[0] == 'hello agent'
    #This was the old method for checking for the results. Not sure which method is better.
    #assert poll_gevent_sleep(2, lambda: len(msgs) > 0 and msgs[0] == 'hello agent')


@pytest.mark.auth
def test_pubsub_unauthorized(build_protected_pubsub):
    pubsub_unauthorized(build_protected_pubsub)


@pytest.mark.auth
def test_pubsub_authorized(build_protected_pubsub):
    pubsub_authorized(build_protected_pubsub)


@pytest.mark.auth
def test_pubsub_unauthorized_none_peer(build_protected_pubsub):
    pubsub_unauthorized(build_protected_pubsub, peer=None)


@pytest.mark.auth
def test_pubsub_authorized_none_peer(build_protected_pubsub):
    pubsub_authorized(build_protected_pubsub, peer=None)

@pytest.mark.auth
def test_pubsub_unauthorized_regex1(build_protected_pubsub):
    pubsub_unauthorized(build_protected_pubsub,
                        topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_authorized_regex1(build_protected_pubsub):
    pubsub_authorized(build_protected_pubsub,
                      topic='foo', regex='/foo*/')


@pytest.mark.auth
def test_pubsub_unauthorized_regex2(build_protected_pubsub):
    pubsub_unauthorized(build_protected_pubsub,
                        topic='foo/bar', regex=r'/foo\/.*/')


@pytest.mark.auth
def test_pubsub_authorized_regex2(build_protected_pubsub):
    pubsub_authorized(build_protected_pubsub,
                      topic='foo/bar', regex=r'/foo\/.*/')
