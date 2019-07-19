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


# TODO do this a better way
def get_agent_user_from_dir(agent_name, agent_uuid):
    """
    :param agent_uuid:
    :return: Unix user ID if installed Volttron agent
    """
    user_id_path = os.path.join(get_home(), "agents", agent_uuid,
                                agent_name, "{}.agent-data".format(agent_name),
                                "USER_ID")
    with open(user_id_path, 'r') as id_file:
        return id_file.readline()


@pytest.fixture(scope="module", params=(
                    dict(messagebus='zmq', ssl_auth=False,
                         instance_name="volttron_security"),
                    # TODO work out how to make a good platform level failure case
                    # dict(messagebus='zmq', ssl_auth=False,
                    #                          instance_name="volttron_fail"),
                    # rmq_skipif(dict(messagebus='rmq', ssl_auth=True))
                ))
def secure_volttron_instance(request):
    """
    Fixture that returns a single instance of volttron platform for testing
    """
    address = get_rand_vip()
    wrapper = build_wrapper(address,
                            instance_name=request.param['instance_name'],
                            messagebus=request.param['messagebus'],
                            ssl_auth=request.param['ssl_auth'],
                            secure_agent_users=True)

    gevent.sleep(3)

    yield wrapper

    cleanup_wrapper(wrapper)


@pytest.fixture(scope="module")
def query_agent(request, secure_volttron_instance):
    # Start a fake agent to query the security agent
    agent = secure_volttron_instance.build_agent()

    agent.publish_callback = MagicMock(name="publish_callback")
    # subscribe to weather poll results
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix="test/publish",
        callback=agent.publish_callback).get()

    # Add a tear down method to stop the fake agent
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def security_agent(request, secure_volttron_instance):
    agent = secure_volttron_instance.install_agent(
        vip_identity="security_agent",
        agent_dir="volttrontesting/platform/security/SecurityAgent",
        start=False,
        config_file=None)

    secure_volttron_instance.start_agent(agent)
    gevent.sleep(3)
    assert secure_volttron_instance.is_agent_running(agent)

    users = [user[0] for user in pwd.getpwall()]
    # TODO find an alternative for the agent name here
    agent_user = get_agent_user_from_dir("securityagent-0.1", agent)
    assert agent_user in users

    def stop_agent():
        print("stopping security agent")
        if secure_volttron_instance.is_running():
            secure_volttron_instance.stop_agent(agent)

    request.addfinalizer(stop_agent)
    return agent


@pytest.mark.secure
def test_agent_rpc(secure_volttron_instance, security_agent, query_agent):
    """if multiple copies of an agent can be installed successfully"""
    # Make sure the security agent can receive an RPC call, and respond
    assert query_agent.vip.rpc.call( "security_agent", "can_receive_rpc_calls")\
        .get(timeout=5)

    # Try installing a second copy of the agent
    agent2 = secure_volttron_instance.install_agent(
        vip_identity="security_agent2",
        agent_dir="volttrontesting/platform/security/SecurityAgent",
        start=False,
        config_file=None)

    secure_volttron_instance.start_agent(agent2)
    gevent.sleep(3)
    assert secure_volttron_instance.is_agent_running(agent2)

    assert query_agent.vip.rpc.call("security_agent", "can_make_rpc_calls",
                                    "security_agent2").get(timeout=5)


# TODO sometimes fails?
@pytest.mark.dev
def test_agent_pubsub(secure_volttron_instance, security_agent,
                      query_agent):
    query_agent.vip.rpc.call("security_agent", "can_publish_to_pubsub")

    gevent.sleep(3)
    assert "security_agent" == query_agent.publish_callback.call_args[0][1]
    assert "Security agent test message" == \
           query_agent.publish_callback.call_args[0][5]

    assert 0 == query_agent.vip.rpc.call(
        "security_agent", "can_subscribe_to_messagebus").get(timeout=5)

    query_agent.vip.pubsub.publish(peer='pubsub', topic="test/read",
                                   message="test message")

    gevent.sleep(3)

    assert 1 == query_agent.vip.rpc.call(
        "security_agent", "can_subscribe_to_messagebus").get(timeout=5)


@pytest.mark.dev
def test_agent_perms_install_dir(secure_volttron_instance, security_agent,
                                 query_agent):
    print(query_agent.vip.rpc.call(
        "security_agent", "can_execute_only_agent_dir").get(timeout=5))


@pytest.mark.skip
@pytest.mark.secure
def test_agent_perms_data_dir():
    pass


@pytest.mark.skip
@pytest.mark.secure
def test_agent_perms_agentdata_dir():
    pass


@pytest.mark.skip
@pytest.mark.secure
def test_agent_perms_distinfo_dir():
    pass


@pytest.mark.skip
@pytest.mark.secure
def test_agent_perms_out_of_agent_dir():
    pass

# TODO test if user is removed during execution
# TODO test if agent is removed after installation
# TODO test if USER_ID file is removed after installation
# TODO test if USER_ID file is removed during execution
# TODO test user group removed after installation
# TODO test user group removed during execution
# TODO test sudo permissions for user
# TODO test volttron user add/delete other users
