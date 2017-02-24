from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.jsonrpc import RemoteError, UNAUTHORIZED
from volttron.platform.messaging.health import STATUS_GOOD

import pytest
from volttrontesting.utils.core_service_installs import add_volttron_central, \
    add_volttron_central_platform, add_listener
from volttrontesting.utils.platformwrapper import start_wrapper_platform

vcp = None


@pytest.fixture(scope="module")
def setup_platform(get_volttron_instances):
    """ Creates a single instance of VOLTTRON with a VOLTTRON Central Platform

    The VOLTTRON Central Platform agent is not registered with a VOLTTRON
    Central Platform.
    """
    global vcp
    vcp = get_volttron_instances(1, False)

    start_wrapper_platform(vcp, with_http=True)

    assert vcp
    assert vcp.is_running()
    vcp_uuid = add_volttron_central_platform(vcp)

    assert vcp_uuid, "Invalid vcp uuid returned"
    assert vcp.is_agent_running(vcp_uuid), "vcp wasn't running!"

    yield vcp

    vcp.shutdown_platform()


@pytest.fixture
def vcp_conn_as_manager(setup_platform):
    assert setup_platform.is_running()

    conn = setup_platform.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM,
                                           capabilities=['manager'])
    yield conn
    conn.kill()


@pytest.fixture
def vcp_conn(setup_platform):
    assert setup_platform.is_running()

    conn = setup_platform.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)
    yield conn
    conn.kill()


@pytest.mark.vcp
@pytest.mark.skip(reason="4.1 fixing tests")
def test_list_agents(vcp_conn_as_manager):

    assert VOLTTRON_CENTRAL_PLATFORM in vcp_conn_as_manager.peers()

    agent_list = vcp_conn_as_manager.call("list_agents")
    assert agent_list and len(agent_list) == 1

    try:
        listener_uuid = add_listener(vcp)
        agent_list = vcp_conn_as_manager.call("list_agents")
        assert agent_list and len(agent_list) == 2

    finally:
        if listener_uuid:
            vcp.remove_agent(listener_uuid)


@pytest.mark.vcp
@pytest.mark.skip(reason="4.1 fixing tests")
def test_can_inspect_agent(vcp_conn_as_manager):

    output = vcp_conn_as_manager.call('inspect')
    methods = output['methods']
    assert 'list_agents' in methods
    assert 'start_agent' in methods
    assert 'stop_agent' in methods
    assert 'restart_agent' in methods
    assert 'agent_status' in methods
    assert 'get_devices' in methods
    assert 'route_request' in methods
    assert 'manage' in methods
    assert 'unmanage' in methods
    assert 'get_health' in methods
    assert 'get_instance_uuid' in methods
    assert 'status_agents' in methods


@pytest.mark.vcp
@pytest.mark.skip(reason="4.1 fixing tests")
def test_can_call_rpc_method(vcp_conn):
    health = vcp_conn.call('get_health', timeout=2)
    assert health['status'] == STATUS_GOOD


@pytest.mark.vcp
def test_can_get_version(vcp_conn):
    version = vcp_conn.call('agent.version', timeout=2)
    assert version is not None
    assert version == '4.0'


@pytest.mark.vcp
@pytest.mark.skip(reason="4.1 fixing tests")
def test_manager_required(vcp_conn):

    # These are the rpc methods that require management.  We can test
    # all of them through a loop because the verification of the capability
    # happens before the execution of the rpc method.
    #
    # However if there is not a manager capability required then we must
    # check to make sure that the RemoteError is the UNAUTHORIZED rather
    # than a parameter issue.
    retrieval_methods = (
        'get_publickey', 'list_agents', 'status_agents', 'get_devices',
        'get_instance_uuid', 'start_agent', 'stop_agent', 'agent_status',
        'restart_agent', 'route_request', 'get_agent_config',
        'list_agent_configs', 'store_agent_config'
    )

    for method in retrieval_methods:
        with pytest.raises(RemoteError) as einfo:
            output = vcp_conn.call(method)
        assert str(UNAUTHORIZED) in str(einfo.value)
