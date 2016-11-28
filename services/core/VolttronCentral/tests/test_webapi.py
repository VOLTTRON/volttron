import json
import os

import gevent
import pytest
import requests
import sys

from volttrontesting.utils.core_service_installs import \
    add_volttron_central_platform, add_volttron_central

from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform
from volttrontesting.utils.utils import poll_gevent_sleep
from zmq.utils import jsonapi
from vctestutils import (APITester, FailedToGetAuthorization,
                         check_multiple_platforms, validate_response,
                         authenticate, do_rpc, validate_at_least_one,
                         each_result_contains)


@pytest.fixture(scope="module")
def vc_vcp_platforms():
    vc = PlatformWrapper()
    vcp = PlatformWrapper()

    # VC is setup to allow all connections
    vc.allow_all_connections()
    start_wrapper_platform(vc, with_http=True)

    start_wrapper_platform(vcp, volttron_central_address=vc.vip_address,
                           volttron_central_serverkey=vc.serverkey)

    vc_uuid = add_volttron_central(vc)
    vcp_uuid = add_volttron_central_platform(vcp)

    # Sleep so we know we are registered
    gevent.sleep(15)
    yield vc, vcp

    vc.shutdown_platform()
    vcp.shutdown_platform()


@pytest.fixture(scope="function")
def web_api_tester(request, vc_instance, pa_instance):
    pa_wrapper, pa_uuid = pa_instance
    vc_wrapper, vc_uuid, vc_jsonrpc = vc_instance
    check_multiple_platforms(vc_wrapper, pa_wrapper)

    tester = APITester(vc_jsonrpc)
    response = tester.register_instance(pa_wrapper.bind_web_address)

    validate_response(response)
    result = response.json()['result']
    assert result['status'] == 'SUCCESS'

    def cleanup():
        for platform in tester.list_platforms().json()['result']:
            tester.unregister_platform(platform['uuid'])

    request.addfinalizer(cleanup)
    return tester


@pytest.mark.vc
def test_auto_register_platform(vc_instance):
    vc, vcuuid, jsonrpc = vc_instance

    adir = "services/core/VolttronCentralPlatform/"
    pauuid = vc.install_agent(agent_dir=adir, config_file=adir+"config")
    assert pauuid
    print(pauuid)

    tester = APITester(jsonrpc)

    def redo_request():
        response = tester.do_rpc("list_platforms")
        print('Response is: {}'.format(response.json()))
        jsonresp = response.json()
        if len(jsonresp['result']) > 0:
            p = jsonresp['result'][0]
            assert p['uuid']
            assert p['name'] == vc.vip_address
            assert isinstance(p['health'], dict)
            assert STATUS_GOOD == p['health']['status']

            return True
        return len(response.json()['result']) > 0

    assert poll_gevent_sleep(6, redo_request)
    response = tester.do_rpc("list_platforms")
    assert len(response.json()['result']) > 0
    jsondata = response.json()
    # Specific platform not the same as vcp on the platform
    platform_uuid = jsondata['result'][0]['uuid']
    # Remove the agent.
    vc.remove_agent(pauuid)
    assert 1 == len(vc.list_agents())
    newpauuid = vc.install_agent(agent_dir=adir, config_file=adir + "config")
    assert newpauuid != pauuid
    assert poll_gevent_sleep(6, redo_request)
    response = tester.do_rpc("list_platforms")
    jsondata = response.json()
    # Specific platform not the same as vcp on the platform
    assert platform_uuid in [result['uuid'] for result in jsondata['result']]


@pytest.mark.vc
def test_vc_settings_store(vc_instance):
    """ Test the reading and writing of data through the get_setting,
        set_setting and get_all_key json-rpc calls.
    """
    vc, vcuuid, jsonrpc = vc_instance

    kv = dict(key='test.user', value='is.good')
    kv2 = dict(key='test.user', value='othervalue')
    kv3 = dict(key='other.user', value='tough stuff')
    tester = APITester(jsonrpc)

    # Creating setting replies with SUCCESS.
    resp = tester.do_rpc('set_setting', **kv)
    print("THE RESPONSE")
    print(resp.json())
    assert 'SUCCESS' == resp.json()['result']

    # Get setting should respond with the same  value.
    resp = tester.do_rpc('get_setting', key=kv['key'])
    assert kv['value'] == resp.json()['result']

    # Make sure keys are returned.
    resp = tester.do_rpc('get_setting_keys')
    assert kv['key'] in resp.json()['result']

    # Test overwrite
    resp = tester.do_rpc('set_setting', **kv2)
    assert 'SUCCESS' == resp.json()['result']

    # Test that the data was overwritten
    resp = tester.do_rpc('get_setting', key=kv['key'])
    assert kv2['value'] == resp.json()['result']

    # add secondary key/value
    resp = tester.do_rpc('set_setting', **kv3)
    assert 'SUCCESS' == resp.json()['result']

    # test both keys are in the store
    resp = tester.do_rpc('get_setting_keys')
    assert kv['key'] in resp.json()['result']
    assert kv3['key'] in resp.json()['result']

    # A None(null) value passed to set_setting should remove the key
    resp = tester.do_rpc('set_setting', key=kv['key'], value=None)
    assert 'SUCCESS' == resp.json()['result']
    resp = tester.do_rpc('get_setting_keys')
    assert kv['key'] not in resp.json()['result']


@pytest.mark.vc
def test_unregister_platform(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    orig_platform_count = len(platforms)
    assert orig_platform_count > 0

    uuid_to_remove = platforms[0]['uuid']
    response = web_api_tester.unregister_platform(uuid_to_remove)
    validate_response(response)
    platforms = web_api_tester.list_platforms().json()['result']
    assert len(platforms) == orig_platform_count - 1


@pytest.mark.vc
def test_login_rejected_for_foo(vc_instance):
    vc_jsonrpc = vc_instance[2]
    with pytest.raises(FailedToGetAuthorization):
        tester = APITester(vc_jsonrpc, "foo", "")


@pytest.mark.vc
def test_store_list_get_configuration(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    data = dict(
        bim=50,
        baz="foo",
        bar="lambda"
    )
    str_data = jsonapi.dumps(data)
    identity = "foo.bar"
    config_name = "fuzzywidgets"
    api = APITester(vc.jsonrpc_endpoint)

    platforms = api.list_platforms().json()['result']
    platform_uuid = platforms[0]["uuid"]

    json = api.store_agent_config(platform_uuid, identity, config_name,
                                  str_data).json()
    assert json['result'] is None

    json = api.list_agent_configs(platform_uuid, identity).json()
    assert json['result']
    assert config_name == json['result'][0]

    json = api.get_agent_config(platform_uuid, identity, config_name).json()
    assert str_data == json['result']


@pytest.mark.vc
def test_listagent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint)

    platform = api.get_result(api.list_platforms)[0]
    print('The platform is {}'.format(platform))

    agent_list = api.get_result(api.list_agents, platform_uuid=platform['uuid'])
    print('The agent list is: {}'.format(agent_list))
    assert len(agent_list) == 1


@pytest.mark.vc
def test_installagent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    # To install the agent we need to simulate the browser's interface
    # for passing files.  This means we have to have a base-64 representation
    # of the wheel file to send across as well as the correct structure
    # of parameters.

    # params['files'] must exist as a list of files
    # each file must have a file_name and file entry
    # the file name is the name of the agent wheel file the file is the base64
    # encoded wheel file.
    #   f['file_name']
    #   f['file

    agent_wheel = vc.build_agentpackage('examples/ListenerAgent')
    assert os.path.exists(agent_wheel)

    import base64
    import random

    with open(agent_wheel, 'r+b') as f:
        # From the web this is what is added to the file.
        filestr = "base64,"+base64.b64encode(f.read())

    file = dict(
        file_name=os.path.basename(agent_wheel),
        file=filestr,
        vip_identity='bar.full.{}'.format(random.randint(1, 100000))
    )

    api = APITester(vc.jsonrpc_endpoint)

    platform = api.get_result(api.list_platforms)[0]

    agents = api.get_result(api.list_agents, platform['uuid'])
    assert agents

    agent = api.get_result(api.install_agent, platform['uuid'], file)

    assert agent
    assert agent.get('uuid')

    agents_after = api.get_result(api.list_agents, platform['uuid'])
    assert len(agents) + 1 == len(agents_after)





