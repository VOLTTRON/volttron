import os

import pytest

from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.utils.utils import get_rand_tcp_address


@pytest.fixture(scope='module')
def pa_wrapper(request):
    wrapper = PlatformWrapper()
    wrapper.vip_address = get_rand_tcp_address()
    # Requires encryption to install things through the platform.
    wrapper.startup_platform(encrypt=True)
    wrapper.install_agent(agent_dir="services/core/VolttronCentralPlatform")

    def cleanup():
        print('Cleaning now!')
        wrapper.shutdown_platform(cleanup=True)

    request.addfinalizer(cleanup)
    return wrapper


@pytest.mark.pa
def test_can_pa_install_start_stop_restart_listener(pa_wrapper):
    whl_path = pa_wrapper.build_wheel(agent_dir="examples/ListenerAgent")

    assert os.path.exists(whl_path)

    platform = pa_wrapper.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)

    # Local is only used so we don't have to convert to base64 and back.
    files = {'files': [dict(
        file_name=whl_path,
        local=True
    )]}

    print('Calling route_request...')
    installed = platform.call('route_request', 'msgid', 'install', files)
    assert installed
    assert len(installed) == 1
    iuuid = installed[0]
    status = platform.call('route_request', 'msgid1', 'agent_status', iuuid)
    # An agent that hasn't started will have None process id and return code.
    keys = ('process_id', 'return_code')
    for k in keys:
        assert k in status.keys()
        assert status[k] is None

    # An agent that has been started/currently running will have a process_id
    # but not a return_code.
    status = platform.call('route_request', 'msgid2', 'start_agent', iuuid)
    for k in keys:
        assert k in status.keys()
    assert status['return_code'] is None
    pid = status['process_id']

    status = platform.call('route_request', 'msgid3', 'stop_agent', iuuid)
    for k in keys:
        assert k in status.keys()

    #assert status['return_code'] == 0
    #pid = status['process_id']
    print('status is: {}'.format(status))
    assert len(status) == 2

    status = platform.call('route_request', 'msgid4', 'restart_agent', iuuid)
    for k in keys:
        assert k in status.keys()

    print('status is: {}'.format(status))
    # assert status['return_code'] == 0
    pid2 = status['process_id']
    #assert len(status) == 2
    assert pid != pid2


    #platform.inst
    #auuid = pa_wrapper.install_agent(agent_dir="examples/ListenerAgent",
    #                                 start=False)

    # platform = pa_wrapper.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)
    # agent_list = platform.call('route_request', 'foo', 'list_agents', None)
    #
    # print('AGENT LIST: {}'.format(agent_list))
    #
    # print("WRAPPER IS: {}".format(pa_wrapper.vip_address))
    # assert pa_wrapper.vip_address
    # assert pa_wrapper.is_running()
