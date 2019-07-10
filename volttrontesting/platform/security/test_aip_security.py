import grp
import pwd
import gevent
import pytest
import subprocess
from volttron.platform.vip.agent import *
from volttron.platform import get_home, get_services_core, is_rabbitmq_available
from volttrontesting.utils.utils import get_rand_vip
from volttrontesting.fixtures.volttron_platform_fixtures import \
    build_wrapper, cleanup_wrapper

# TODO docs
HAS_RMQ = is_rabbitmq_available()
rmq_skipif = pytest.mark.skipif(not HAS_RMQ, reason='RabbitMQ is not setup')

test_config = {
    'max_size_gb': None,
    'api_key': None,
    'poll_locations': [],
    'poll_interval': 5
}

@pytest.fixture(scope="module", params=(
        dict(messagebus='zmq', ssl_auth=False),
        # rmq_skipif(dict(messagebus='rmq', ssl_auth=True))
))
def secure_volttron_instance(request):
    """
    Fixture that returns a single instance of volttron platform for testing
    """
    address = get_rand_vip()
    wrapper = build_wrapper(address,
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'],
                            secure_agent_users=True)
    gevent.sleep(3)

    try:
        # TODO replace
        grp.getgrnam("volttron_agent")
    except KeyError:
        pytest.skip("Secure platform requires running "
                    "scripts/security_user_permissions.sh as root "
                    "successfully.")

    yield wrapper

    cleanup_wrapper(wrapper)

@pytest.fixture(scope="function")
def cleanup_agents(secure_volttron_instance):
    """
    Remove all agents from the secure instance before the tests runs
    """
    print("Removing volttron agents...")
    secure_volttron_instance.remove_all_agents()
    gevent.sleep(2)


def get_agent_user_from_dir(agent_uuid):
    """

    :param agent_uuid:
    :return:
    """
    user_id_path = os.path.join(
        get_home(), "agents", agent_uuid, "USER_ID")
    with open(user_id_path, 'r') as id_file:
        return id_file.readline()

# TODO see if this can be accomplished with built agents rather than installed?
# TODO may need to implement secure users for built agents
@pytest.mark.secure
def test_agent_install(secure_volttron_instance, query_agent):
    """
    Ensures that agents can be installed, removed, started, stopped,
    """
    # Install a basic agent, then a weather agent - this indicates agents
    # can be installed

    gevent.sleep(2)

    test_agent = secure_volttron_instance.install_agent(
        vip_identity="test",
        agent_dir=get_services_core("WeatherDotGov"),
        config_file=test_config)

    gevent.sleep(2)
    assert secure_volttron_instance.is_agent_running(test_agent)

    test_agent_id = get_agent_user_from_dir(test_agent)
    current_users = [user[0] for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall()))]
    assert test_agent_id in current_users

    # Perform an rpc call to make sure agents are reachable
    query_results = query_agent.vip.rpc.call(
        "test", "get_current_weather", [{"station": "KLAX"}]).get(
        timeout=30)

    assert len(query_results) == 1

    # Determine that there are no conflicts installing a second instance of an
    # agent
    test_agent2 = secure_volttron_instance.install_agent(
        vip_identity="test2",
        agent_dir=get_services_core("WeatherDotGov"),
        config_file=test_config)

    gevent.sleep(3)
    assert secure_volttron_instance.is_agent_running(test_agent2)

    test_agent2_id = get_agent_user_from_dir(test_agent2)
    current_users = [user[0] for user in list(filter(lambda x: x[0].startswith(
        "volttron_"), pwd.getpwall()))]
    assert test_agent_id in current_users and test_agent2_id in current_users

    # Stop, then remove agent, check that the user has been removed
    for agent in [test_agent, test_agent2]:
        secure_volttron_instance.stop_agent(agent)
        gevent.sleep(2)
        assert not secure_volttron_instance.is_agent_running(agent)

        secure_volttron_instance.remove_agent(agent)
        gevent.sleep(2)

        current_users = [user for user in list(filter(lambda x: x[0].startswith(
            "volttron_"), pwd.getpwall()))]
        assert agent not in current_users

# @pytest.mark.secure
# def test_agent_user_deleted(secure_volttron_instance, query_agent):
#     """"""
#     # create an agent for testing
#     test_agent = secure_volttron_instance.install_agent(
#         vip_identity="test",
#         agent_dir=get_services_core("WeatherDotGov"),
#         config_file=test_config)
#
#     gevent.sleep(2)
#     assert secure_volttron_instance.is_agent_running(test_agent)
#
#     # Shut it down
#     secure_volttron_instance.stop_agent(test_agent)
#     assert not secure_volttron_instance.is_agent_running(test_agent)
#
#     test_agent_user = get_agent_user_from_dir(test_agent)
#
#     # make sure its user exists
#     try:
#         pwd.getpwnam(test_agent_user)
#     except KeyError:
#         pytest.fail("Agent user not found")
#
#     # remove the user, make sure it no longer exists
#     userdel = ['sudo', 'userdel', test_agent_user]
#     userdel_process = subprocess.Popen(
#         userdel, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     stdout, stderr = userdel_process.communicate()
#     if stderr:
#         pytest.fail("Unable to remove test agent user")
#
#     current_users = [user[0] for user in list(filter(lambda x: x[0].startswith(
#         "volttron_"), pwd.getpwall()))]
#
#     assert test_agent_user not in current_users
#
#     # Attempt to start the agent
#     try:
#         secure_volttron_instance.start_agent(test_agent)
#         gevent.sleep(2)
#     except Exception as e:
#         print(e)
#
#     assert not secure_volttron_instance.is_agent_running(test_agent)

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