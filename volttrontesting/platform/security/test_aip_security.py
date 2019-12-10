import pwd
from datetime import datetime

import gevent
import pytest
from mock import MagicMock

from volttron.platform import get_home, is_rabbitmq_available
from volttron.platform import get_services_core, get_examples
from volttron.platform.agent import utils
from volttron.platform.agent.utils import execute_command
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import *
from volttrontesting.fixtures.volttron_platform_fixtures import \
    build_wrapper, cleanup_wrapper, volttron_multi_messagebus
from volttrontesting.utils.utils import get_hostname_and_random_port, get_rand_vip, get_rand_ip_and_port


HAS_RMQ = is_rabbitmq_available()
rmq_skipif = pytest.mark.skipif(not HAS_RMQ, reason='RabbitMQ is not setup')

# skip if running on travis because initial secure_user_permissions scripts needs to be run as root/sudo
# TODO: Should we spin a separate docker image just to test this one test case alone?
#  May be we can do this along with testing for remote RMQ instance setup for which we need sudo access too.
pytestmark = pytest.mark.skipif(os.environ.get("CI") is not None,
                                reason="Can't run on travis as this test needs root to run "
                                       "setup script before running test case")

INSTANCE_NAME1 = "volttron1"
INSTANCE_NAME2 = "volttron2"

# TODO do this a better way
def get_agent_user_from_dir(agent_name, agent_uuid):
    """
    :param agent_uuid:
    :return: Unix user ID if installed Volttron agent
    """
    user_id_path = os.path.join(get_home(), "agents", agent_uuid, "USER_ID")
    with open(user_id_path, 'r') as id_file:
        return id_file.readline()


@pytest.fixture(scope="module", params=(
                    dict(messagebus='zmq', ssl_auth=False, instance_name=INSTANCE_NAME1),
                    rmq_skipif(dict(messagebus='rmq', ssl_auth=True, instance_name=INSTANCE_NAME1)),
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
            secure_volttron_instance.remove_agent(agent)

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def multi_messagebus_forwarder(volttron_multi_messagebus):
    from_instance, to_instance = volttron_multi_messagebus(INSTANCE_NAME1, INSTANCE_NAME2)
    to_instance.allow_all_connections()
    forwarder_config = {"custom_topic_list": ["foo"]}

    if to_instance.messagebus == 'rmq':
        remote_address = to_instance.bind_web_address
        to_instance.enable_auto_csr()
        print("REQUEST CA: {}".format(os.environ.get('REQUESTS_CA_BUNDLE')))
        os.environ['REQUESTS_CA_BUNDLE'] = to_instance.requests_ca_bundle

        forwarder_config['destination-address'] = remote_address
    else:
        remote_address = to_instance.vip_address
        forwarder_config['destination-vip'] = remote_address
        forwarder_config['destination-serverkey'] = to_instance.serverkey

    forwarder_uuid = from_instance.install_agent(
        agent_dir=get_services_core("ForwardHistorian"),
        config_file=forwarder_config,
        start=True
    )
    gevent.sleep(1)
    assert from_instance.is_agent_running(forwarder_uuid)

    yield from_instance, to_instance

    from_instance.stop_agent(forwarder_uuid)

def publish(publish_agent, topic, header, message):
    publish_agent.vip.pubsub.publish('pubsub',
                                     topic,
                                     headers=header,
                                     message=message).get(timeout=10)

@pytest.mark.secure
def test_agent_rpc(secure_volttron_instance, security_agent, query_agent):
    """
    Test agent running in secure mode can make RPC calls without any errors
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    """if multiple copies of an agent can be installed successfully"""
    # Make sure the security agent can receive an RPC call, and respond
    assert query_agent.vip.rpc.call(
        "security_agent", "can_receive_rpc_calls").get(timeout=5)

    # Try installing a second copy of the agent
    agent2 = None
    try:
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
    except BaseException as e:
        print("Exception {}".format(e))
        assert False
    finally:
        if agent2:
            secure_volttron_instance.remove_agent(agent2)


@pytest.mark.secure
def test_agent_pubsub(secure_volttron_instance, security_agent,
                      query_agent):
    """
    Test agent running in secure mode can publish and subscribe to message bus without any errors
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
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



@pytest.mark.secure
def test_install_dir_permissions(secure_volttron_instance, security_agent, query_agent):
    """
    Test to make sure agent user only has read and execute permissions for all sub folders of agent install directory
    except <agent>.agent-data directory. Agent user should have rwx to agent-data directory
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    assert secure_volttron_instance.is_agent_running(security_agent)
    results = query_agent.vip.rpc.call("security_agent", "verify_install_dir_permissions").get(timeout=10)
    print(results)
    assert results is None

@pytest.mark.secure
def test_install_dir_file_permissions(secure_volttron_instance, security_agent, query_agent):
    """
    Test to make sure agent user only has read access to all files in install-directory except for files in
    <agent>.agent-data directory. Agent user will be the owner of files in agent-data directory and hence we
    need not check files in this dir
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    results = query_agent.vip.rpc.call("security_agent", "verify_install_dir_file_permissions").get(timeout=5)
    assert results is None

@pytest.mark.secure
def test_vhome_dir_permissions(secure_volttron_instance, security_agent, query_agent):
    """
    Test to make sure we have read and execute access to relevant folder outside of agent's install dir.

    Agent should have read access to the below directories other than its own agent install dir. Read access to other
    folder are based on default settings in the machine.  We restrict only file access when necessary.
        - vhome
        - vhome/certificates and its subfolders
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    assert secure_volttron_instance.is_agent_running(security_agent)
    results = query_agent.vip.rpc.call("security_agent", "verify_vhome_dir_permissions").get(timeout=10)
    print(results)
    assert results is None

@pytest.mark.secure
def test_vhome_file_permissions(secure_volttron_instance, security_agent, query_agent):
    """
    Test to make sure agent does not have any permissions on files outside agent's directory but for the following
    exceptions.
    Agent user should have read access to
        - vhome/config
        - vhome/known_hosts
        - vhome/rabbitmq_config.yml
        - vhome/certificates/certs/<agent_vip_id>.<instance_name>.crt
        - vhome/certificates/private/<agent_vip_id>.<instance_name>.pem

    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    assert secure_volttron_instance.is_agent_running(security_agent)
    # Try installing a second copy of the agent. First agent should not have read/write/execute access to any
    # of the files of agent2. rpc call checks all files in vhome
    agent2 = None
    try:
        agent2 = secure_volttron_instance.install_agent(
            vip_identity="security_agent2",
            agent_dir="volttrontesting/platform/security/SecurityAgent",
            start=False,
            config_file=None)

        secure_volttron_instance.start_agent(agent2)
        gevent.sleep(3)
        assert secure_volttron_instance.is_agent_running(agent2)

        # Now verify that security_agent has read access to only its own files
        results = query_agent.vip.rpc.call("security_agent",
                                           "verify_vhome_file_permissions",
                                           INSTANCE_NAME1).get(timeout=10)
        print(results)
        assert results is None
    except BaseException as e:
        print("Exception {}".format(e))
        assert False
    finally:
        if agent2:
            secure_volttron_instance.remove_agent(agent2)


@pytest.mark.secure
def test_config_store_access(secure_volttron_instance, security_agent, query_agent):
    """
    Test to make sure agent does not have any permissions on files outside agent's directory but for the following
    exceptions.
    Agent user should have read access to
        - vhome/config
        - vhome/known_hosts
        - vhome/certificates/certs/<agent_vip_id>.<instance_name>.crt
        - vhome/certificates/private/<agent_vip_id>.<instance_name>.pem
    :param secure_volttron_instance: secure volttron instance
    :param security_agent: Test agent which runs secure mode as a user other than platform user
    :param query_agent: Fake agent to do rpc calls to test agent
    """
    assert secure_volttron_instance.is_agent_running(security_agent)
    # Try installing a second copy of the agent. First agent should not have read/write/execute access to any
    # of the files of agent2. rpc call checks all files in vhome
    agent2 = None
    try:
        agent2 = secure_volttron_instance.install_agent(
            vip_identity="security_agent2",
            agent_dir="volttrontesting/platform/security/SecurityAgent",
            start=False,
            config_file=None)

        secure_volttron_instance.start_agent(agent2)
        gevent.sleep(3)
        assert secure_volttron_instance.is_agent_running(agent2)

        # make initial entry in config store for both agents
        config_path = os.path.join(secure_volttron_instance.volttron_home, "test_secure_agent_config")
        with open(config_path, "w+") as f:
            f.write('{"test":"value"}')

        gevent.sleep(1)

        execute_command(['volttron-ctl', 'config', 'store', "security_agent", "config", config_path, "--json"],
                                 cwd=secure_volttron_instance.volttron_home, env=secure_volttron_instance.env)
        execute_command(['volttron-ctl', 'config', 'store', "security_agent2", "config", config_path, "--json"],
                                 cwd=secure_volttron_instance.volttron_home, env=secure_volttron_instance.env)

        execute_command(['volttron-ctl', 'config', 'store', "security_agent", "config", config_path, "--json"],
                        cwd=secure_volttron_instance.volttron_home, env=secure_volttron_instance.env)

        # this rpc method will check agents own config store and access and agent's access to other agent's config store
        results = query_agent.vip.rpc.call("security_agent",
                                           "verify_config_store_access", "security_agent2").get(timeout=30)
        print("RESULTS :::: {}".format(results))
    except BaseException as e:
        print("Exception {}".format(e))
        assert False
    finally:
        if agent2:
            secure_volttron_instance.remove_agent(agent2)


def test_multi_messagebus_forwarder(multi_messagebus_forwarder):
    """
    Forward Historian test with multi message bus combinations
    :return:
    """
    from_instance, to_instance = multi_messagebus_forwarder
    publish_agent = from_instance.dynamic_agent
    subscriber_agent = to_instance.dynamic_agent

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='devices',
                               callback=subscriber_agent.callback).get()

    subscriber_agent.analysis_callback = MagicMock(name="analysis_callback")
    subscriber_agent.analysis_callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                                          prefix='analysis',
                                          callback=subscriber_agent.analysis_callback).get()
    sub_list = subscriber_agent.vip.pubsub.list('pubsub').get()
    gevent.sleep(3)

    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }

    for i in range(0, 5):
        topic = "devices/PNNL/BUILDING1/HP{}/CoolingTemperature".format(i)
        value = 35
        publish(publish_agent, topic, headers, value)
        topic = "analysis/PNNL/BUILDING1/WATERHEATER{}/ILCResults".format(i)
        value = {'result': 'passed'}
        publish(publish_agent, topic, headers, value)
        gevent.sleep(0.5)

    gevent.sleep(1)

    assert subscriber_agent.callback.call_count == 5
    assert subscriber_agent.analysis_callback.call_count == 5
