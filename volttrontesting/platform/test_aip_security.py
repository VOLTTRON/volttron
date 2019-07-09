import os
import grp
import pwd
import gevent
import pytest
from mock import MagicMock
from volttron.platform.vip.agent import *
from volttron.platform import get_home, get_services_core, is_rabbitmq_available
from volttrontesting.utils.utils import get_rand_vip
from volttrontesting.fixtures.volttron_platform_fixtures import \
    build_wrapper, cleanup_wrapper

# TODO docs
HAS_RMQ = is_rabbitmq_available()
rmq_skipif = pytest.mark.skipif(not HAS_RMQ, reason='RabbitMQ is not setup')


@pytest.fixture(scope="module", params=(
                    dict(messagebus='zmq', ssl_auth=False),
                    rmq_skipif(dict(messagebus='rmq', ssl_auth=True))
                ))
def secure_volttron_instance(request, volttron_instance):
    """
    Fixture that returns a single instance of volttron platform for testing
    """
    address = get_rand_vip()
    wrapper = build_wrapper(address,
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'],
                            secure_agent_users=True)

    yield wrapper

    cleanup_wrapper(wrapper)


class TestAgent(Agent):

    @RPC.export
    def test_agent(self):
        return True


@pytest.fixture(scope="function")
def cleanup_agents(secure_volttron_instance):
    secure_volttron_instance.remove_all_agents()


def get_agent_user_from_dir(agent_uuid):
    """

    :param agent_uuid:
    :return:
    """
    user_id_path = os.path.join(
        get_home(), "agents", agent_uuid, agent_uuid, "USER_ID")
    with open(user_id_path, 'r') as id_file:
        return id_file.readline()


@pytest.mark.secure
def test_agent_install(secure_volttron_instance):
    """
    Ensures that agents can be installed, removed, started, stopped,
    """
    # Track number of existing users, check if there are agents already running
    existing_users = list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall()))

    # Install a basic agent, then a weather agent - this indicates agents
    # can be installed

    query_agent = secure_volttron_instance.build_agent(
        agent_class=TestAgent,
        identity="query")
    query_agent.poll_callback = MagicMock(name="poll_callback")

    query_agent_id = get_agent_user_from_dir(query_agent.core.agent_uuid)
    current_users = [user for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall())) if user not in existing_users]
    assert query_agent_id in current_users
    assert len(current_users) == 1

    # TODO rather than weather agent, build a custom temporary agent with
    # commands we're going to use
    test_agent = secure_volttron_instance.build_agent(
        agent_class=TestAgent,
        identity="test")

    gevent.sleep(3)
    assert secure_volttron_instance.is_agent_running(test_agent)

    test_agent_id = get_agent_user_from_dir(test_agent)
    current_users = [user for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall())) if user not in existing_users]
    assert test_agent_id in get_agent_user_from_dir(test_agent_id) and \
           query_agent_id in current_users
    assert len(current_users) == 2

    # Perform an rpc call to make sure agents are reachable
    query_results = query_agent.vip.rpc.call(
        "platform.weather", "get_current_weather", [{"station": "KLAX"}]).get(
        timeout=30)

    assert len(query_results) == 1

    # Determine that there are no conflicts installing a second instance of an
    # agent
    test_agent2 = secure_volttron_instance.build_agent(
        agent_class=TestAgent,
        identity="test2")

    gevent.sleep(3)
    assert secure_volttron_instance.is_agent_running(test_agent2)

    test_agent2_id = get_agent_user_from_dir(test_agent2)
    current_users = [user for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall())) if user not in existing_users]
    assert test_agent_id in get_agent_user_from_dir(test_agent2) and \
           query_agent_id in current_users and test_agent2_id in current_users
    assert len(current_users) == 3

    # Stop, then remove agent, check that the user has been removed
    for agent in [query_agent.core.agent_uuid, test_agent, test_agent2]:
        secure_volttron_instance.stop_agent(agent)
        gevent.sleep(2)
        assert not secure_volttron_instance.is_agent_running(agent)

        secure_volttron_instance.remove_agent(agent)
        gevent.sleep(2)

    current_users = [user for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall())) if user not in existing_users]
    assert len(current_users) == 0

    currently_existing_users = list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall()))
    assert set(currently_existing_users) == set(existing_users)

@pytest.mark.secure
def test_agent_user_deleted(secure_volttron_instance):
    pytest.skip()
    # TODO install agent, then delete agent user
    # TODO start security agent, check to make sure users/groups exist
    # TODO remove it again and check that it is successfully removed
    # TODO repeat the previous, deleting group as well
    # TODO adding and removing multiple copies of an agent



# TODO test agent directory permissions

# test agent user sudo perms

# TODO test volttron user add/delete user

# TODO test volttron user add/delete group

# TODO test volttron user add/delete other

# TODO test remove agent secure

# TODO instance names?

# TODO group names?

# TODO test agent file access

# TODO test agent execution access