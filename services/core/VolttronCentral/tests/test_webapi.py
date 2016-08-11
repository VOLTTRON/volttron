import json
import pytest
import requests
import sys

from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.utils import poll_gevent_sleep
from zmq.utils import jsonapi
from vctestutils import (APITester, FailedToGetAuthorization,
                         check_multiple_platforms, validate_response,
                         authenticate, do_rpc, validate_at_least_one,
                         each_result_contains)


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
@pytest.mark.xfail(reason='Not sure why this is failing.')
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
            assert p['name'] == 'local'
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
    assert vc.list_agents() == 1
    newpauuid = vc.install_agent(agent_dir=adir, config_file=adir + "config")
    assert newpauuid != pauuid
    assert poll_gevent_sleep(6, redo_request)
    response = tester.do_rpc("list_platforms")
    jsondata = response.json()
    # Specific platform not the same as vcp on the platform
    platform_uuid2= jsondata['result'][0]['uuid']
    assert platform_uuid == platform_uuid2





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
def test_register_instance(vc_instance, pa_instance):

    pa_wrapper, pa_uuid = pa_instance
    vc_wrapper, vc_uuid, vc_jsonrpc = vc_instance

    check_multiple_platforms(vc_wrapper, pa_wrapper)

    username, auth = authenticate(vc_jsonrpc, "admin", "admin")
    assert auth

    print("vip address of pa_agent: {}".format(pa_wrapper.vip_address))
    print("vip address of vc_agent: {}".format(vc_wrapper.vip_address))

    # Call register_instance rpc method on vc
    response = do_rpc("register_instance", [pa_wrapper.bind_web_address],
                      auth, vc_jsonrpc)

    validate_response(response)
    result = response.json()['result']
    assert result['status'] == 'SUCCESS'

    # list platforms
    response = do_rpc("list_platforms", None, auth, vc_jsonrpc)
    validate_response(response)
    platforms = response.json()['result']
    assert len(platforms) == 1
    uuid = platforms[0]['uuid']


@pytest.mark.vc
@pytest.mark.xfail(reason='Hmmmm')
def test_list_exported_methods(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    agents = web_api_tester.list_agents(platforms[0]['uuid']).json()['result']
    for agent in agents:
        response = web_api_tester.inspect(platforms[0]['uuid'], agent['uuid'])
        validate_response(response)


@pytest.mark.vc
@pytest.mark.xfail(reason='Platforms now have static uuids that are not the same as the installed platform uuid.')
def test_list_agents(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    assert len(platforms) > 0
    response = web_api_tester.list_agents(platforms[0]['uuid'])
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


@pytest.mark.vc
def test_list_platforms(web_api_tester):
    response = web_api_tester.list_platforms()
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


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


@pytest.mark.web
def test_login_rejected_for_foo(vc_instance):
    vc_jsonrpc = vc_instance[2]
    with pytest.raises(FailedToGetAuthorization):
        tester = APITester(vc_jsonrpc, "foo", "")
