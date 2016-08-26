from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.messaging.health import STATUS_GOOD

import pytest
from volttrontesting.utils.core_service_installs import add_volttron_central, \
    add_volttron_central_platform, add_listener
from volttrontesting.utils.platformwrapper import start_wrapper_platform

vcp = None


@pytest.fixture(scope="module")
def setup_platform(request, get_volttron_instances):
    """ Creates a single instance of VOLTTRON with a VOLTTRON Central Platform

    The VOLTTRON Central Platform agent is not registered with a VOLTTRON
    Central Platform.
    """
    global vcp
    vcp = get_volttron_instances(1, False)

    if get_volttron_instances.param == "encrypted":
        start_wrapper_platform(vcp, with_http=True)
    else:
        pytest.skip("Only testing encrypted")
        start_wrapper_platform(vcp, with_http=False, with_tcp=False)

    assert vcp
    assert vcp.is_running()
    vcp_uuid = add_volttron_central_platform(vcp)

    assert vcp_uuid, "Invalid vcp uuid returned"
    assert vcp.is_agent_running(vcp_uuid), "vcp wasn't running!"

    return vcp


@pytest.mark.vcp
def test_list_agents(setup_platform):
    assert vcp.is_running()

    connection = vcp.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)

    assert VOLTTRON_CENTRAL_PLATFORM in connection.peers()

    agent_list = connection.call("list_agents")
    assert agent_list and len(agent_list) == 1

    try:
        listener_uuid = add_listener(vcp)
        agent_list = connection.call("list_agents")
        assert agent_list and len(agent_list) == 2

    finally:
        if listener_uuid:
            vcp.remove_agent(listener_uuid)


@pytest.mark.vcp
def test_can_inspect_agent(setup_platform):
    connection = vcp.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)

    output = connection.call('inspect')
    methods = output['methods']
    assert 'list_agents' in methods
    assert 'start_agent' in methods
    assert 'stop_agent' in methods
    assert 'restart_agent' in methods
    assert 'agent_status' in methods
    assert 'get_device' in methods
    assert 'get_devices' in methods
    assert 'route_request' in methods
    assert 'manage' in methods
    assert 'unmanage' in methods
    assert 'get_health' in methods
    assert 'reconfigure' in methods
    assert 'get_instance_uuid' in methods
    assert 'get_manager_key' in methods
    assert 'list_agent_methods' in methods


@pytest.mark.vcp
def test_can_call_rpc_method(setup_platform):
    connection = vcp.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)

    health = connection.call('get_health', timeout=2)
    assert health['status'] == STATUS_GOOD
