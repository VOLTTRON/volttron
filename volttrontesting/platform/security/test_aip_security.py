import grp
import pwd
import gevent
import pytest
from mock import MagicMock
from volttron.platform.vip.agent import *
from volttron.platform import get_home, is_rabbitmq_available
from volttrontesting.utils.utils import get_rand_vip
from volttrontesting.fixtures.volttron_platform_fixtures import \
    build_wrapper, cleanup_wrapper

# TODO docs
HAS_RMQ = is_rabbitmq_available()
rmq_skipif = pytest.mark.skipif(not HAS_RMQ, reason='RabbitMQ is not setup')


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



# def get_agent_user_from_dir(agent_uuid):
#     """"""
#     user_id_path =
#     with open(user_id_path, 'r') as id_file:
#         return id_file.readline()


@pytest.fixture(scope="module")
def security_agent(request, secure_volttron_instance):
    agent = secure_volttron_instance.install_agent(
        vip_identity="security_agent",
        agent_dir="volttrontesting/platform/security/SecurityAgent",
        start=True)

    gevent.sleep(2)

    assert secure_volttron_instance.is_agent_running(agent)

    # user_id = get_agent_user_from_dir(agent)
    users = [user[0] for user in list(
        filter(lambda x: x[0].startswith("volttron_"), pwd.getpwall()))]
    # assert user_id in users

    assert grp.getgrnam("volttron_agent")

    def stop_agent():
        print("In teardown method of security agent")
        if secure_volttron_instance.is_running():
            secure_volttron_instance.stop_agent(agent)
            secure_volttron_instance.remove_agent(agent)

            gevent.sleep(2)

            agent_users = [agent_user[0] for agent_user in list(
                filter(lambda x: x[0].startswith("volttron_"), pwd.getpwall()))]
            # assert user_id not in agent_users

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def messagebus_agent(request, secure_volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance2
    agent = secure_volttron_instance.build_agent()
    agent.pubsub_callback = MagicMock(name="pubsub_callback")
    agent.pubsub_callback.reset_mock()
    # subscribe to weather poll results
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix="test/publish",
        callback=agent.pubsub_callback).get()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of messagebus agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.mark.secure
def test_agent_rpc_calls(secure_volttron_instance, security_agent,
                         messagebus_agent):
    """Test if agents are able to send and receive RPC calls, also tests
        if multiple copies of an agent can be installed successfully"""
    # Make sure the security agent can receive an RPC call, and respond
    # assert messagebus_agent.vip.rpc.call(
    #     "security_agent", "can_receive_rpc_calls").get(timeout=5)

    # Temporarily install a second security agent for testing send
    second_agent = secure_volttron_instance.install_agent(
        vip_identity="security_agent2",
        agent_dir="volttrontesting/platform/security/SecurityAgent",
        start=True)

    gevent.sleep(2)

    assert secure_volttron_instance.is_agent_running(second_agent)

    # user_id = get_agent_user_from_dir(second_agent)
    users = [user[0] for user in list(
        filter(lambda x: x[0].startswith("volttron_"), pwd.getpwall()))]
    # assert user_id in users

    # Determine if the security agent can send an RPC call to a peer, receive a
    # response, and respond itself
    # assert messagebus_agent.vip.rpc.call(
    #     "security_agent", "can_make_rpc_calls", "security_agent2").get(
    #     timeout=5)

    # Shutdown the extra security agent
    secure_volttron_instance.stop_agent(second_agent)
    secure_volttron_instance.remove_agent(second_agent)

    gevent.sleep(2)

    agent_users = [agent_user[0] for agent_user in list(
        filter(lambda x: x[0].startswith("volttron_"), pwd.getpwall()))]
    # assert user_id not in agent_users

#
# @pytest.mark.secure
# def test_agent_pubsub(secure_volttron_instance, security_agent,
#                       messagebus_agent):
#     messagebus_agent.vip.pubsub.publish(peer="pubsub", topic="test/read")
#
#     gevent.sleep(2)
#
#     assert messagebus_agent.vip.rpc.call(
#         "security_agent", "can_subscribe_to_messagebus").get(timeout=5) == 1
#
#     messagebus_agent.vip.rpc.call(
#         "security_agent", "can_publish_to_pubsub").get(timeout=5)
#
#     print(messagebus_agent.pubsub_callback.call_args_list)
#     assert messagebus_agent.pubsub_callback.call_count == 1
#     assert "security_agent" == messagebus_agent.pubsub_callback.call_args[0][1]

#
# @pytest.mark.dev
# def test_directory_permissions(secure_volttron_instance, security_agent,
#                                messagebus_agent):
#
#     # Agent should not be able to read/write, but should be able to execute
#     # in its agent directory
#     agent_dir_rwx = messagebus_agent.vip.rpc.call(
#         "security_agent", "can_read_write_execute_agent_dir").get(timeout=5)
#     # assert not agent_dir_rwx["read"]
#     # assert not agent_dir_rwx["write"]
#     # assert agent_dir_rwx["execute"]
#
#     print("Agent dir: {}".format(agent_dir_rwx))
#
#     # Agents should be able to read and write in their data directory, but not
#     # execute
#     data_dir_rwx = messagebus_agent.vip.rpc.call(
#         "security_agent", "can_read_write_execute_agent_data_dir").get(
#         timeout=5)
#     # assert data_dir_rwx["read"]
#     # assert data_dir_rwx["write"]
#     # assert not data_dir_rwx["execute"]
#
#     print("Agent data dir: {}".format(data_dir_rwx))

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

# TODO instance names?

# TODO group names?

# TODO test agent file access

# TODO test agent execution access