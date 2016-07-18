import hashlib
import pytest

from volttron.platform.jsonrpc import json_validate_response

from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.utils.servicepaths import VOLTTRON_CENTRAL_PLATFORM_PATH, \
    VOLTTRON_CENTRAL_PATH
from volttrontesting.utils.utils import poll_gevent_sleep, get_rand_http_address, \
    get_rand_tcp_address
from volttrontesting.utils.webapi import (
    WebAPI, FailedToGetAuthorization, check_multiple_platforms,
    validate_response, authenticate, do_rpc, validate_at_least_one,
    each_result_contains)


@pytest.fixture(scope="function")
def web_api_tester(request, vc_instance, pa_instance):
    pa_wrapper, pa_uuid = pa_instance
    vc_wrapper, vc_uuid, vc_jsonrpc = vc_instance
    check_multiple_platforms(vc_wrapper, pa_wrapper)

    tester = WebAPI(vc_jsonrpc)
    response = tester.register_instance(pa_wrapper.bind_web_address)

    validate_response(response)
    result = response.json()['result']
    assert result['status'] == 'SUCCESS'

    def cleanup():
        for platform in tester.list_platforms().json()['result']:
            tester.unregister_platform(platform['uuid'])

    request.addfinalizer(cleanup)
    return tester


@pytest.fixture
def get_platform_wrappers(request):
    def get_n_wrappers(n, **kwargs):
        get_n_wrappers.count = n
        instances = []
        for i in range(0, n):
            instances.append(PlatformWrapper())
        get_n_wrappers.wrappers = instances
        return instances

    def cleanup():
        for i in range(0, get_n_wrappers.count):
            print('Shutting down instance: {}'.format(
                get_n_wrappers.wrappers[i].volttron_home
            ))
            get_n_wrappers.wrappers[i].shutdown_platform()
    request.addfinalizer(cleanup)
    return get_n_wrappers


@pytest.mark.vc
def test_autoreg_with_local_platform(get_platform_wrappers):
    # Create a wrapper object that we can install both the VOLTTRON_CENTRAL
    # and the VOLTTRON_CENTRL_PLATFORM on.
    wrapper = get_platform_wrappers(1)[0]
    # Build an http address that we can start serving during platform startup.
    vc_http = get_rand_http_address()
    vc_tcp = get_rand_tcp_address()
    wrapper.startup_platform(vip_address=vc_tcp, bind_web_address=vc_http,
                             encrypt=True)

    vc_config = {
        "users": {
            "admin":{
                "password": hashlib.sha512("admin").hexdigest(),
                "groups": [
                    "admin"
                ]
            }
        }
    }

    # Install the volttron central agent.
    vcuuid = wrapper.install_agent(agent_dir=VOLTTRON_CENTRAL_PATH,
                                   config_file=vc_config)
    assert vcuuid

    api = WebAPI(url="{}/jsonrpc".format(vc_http),
                 username="admin", password="admin")
    jsonresp = api.list_platforms().json()
    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)
    # No platforms are registered with vc yet.
    assert len(jsonresp['result']) == 0

    # Install the volttron central platform agent.
    vcpuuid = wrapper.install_agent(agent_dir=VOLTTRON_CENTRAL_PLATFORM_PATH,
                                    config_file={})
    assert vcpuuid

    poll_gevent_sleep(max_seconds=2,
                      condition=lambda: len(api.list_platforms().json()['result']) == 1)

    # Now we should have more than a single result.
    jsonresp = api.list_platforms().json()
    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)
    # Now we should have an instance running
    assert len(jsonresp['result']) == 1


@pytest.mark.vc
def test_auto_register_platform(vc_instance):
    vc, vcuuid, jsonrpc = vc_instance

    adir = VOLTTRON_CENTRAL_PLATFORM_PATH
    print("VCP IS: " + adir)
    pauuid = vc.install_agent(agent_dir=adir, config_file={})
    assert pauuid

    webtest = WebAPI(jsonrpc)
    resp = webtest.call('list_platforms').json()
    assert len(resp['result']) == 1

    def redo_request():
        response = webtest.call("list_platforms")
        print('Response is: {}'.format(response.json()))
        jsonresp = response.json()
        if len(jsonresp['result']) > 0:
            p = jsonresp['result'][0]
            assert p['uuid']
            assert p['name'] == 'local'
            assert isinstance(p['health'], dict)
            # assert STATUS_GOOD == p['health']['status']

            return True
        return len(response.json()['result']) > 0

    assert poll_gevent_sleep(6, redo_request)
    response = webtest.call("list_platforms")
    assert len(response.json()['result']) > 0
    jsondata = response.json()
    # Specific platform not the same as vcp on the platform
    platform_uuid = jsondata['result'][0]['uuid']
    # Remove the agent.
    vc.remove_agent(pauuid)
    assert len(vc.list_agents()) == 1
    newpauuid = vc.install_agent(agent_dir=adir, config_file=adir + "config")
    assert newpauuid != pauuid
    assert poll_gevent_sleep(6, redo_request)
    response = webtest.call("list_platforms")
    jsondata = response.json()
    # Specific platform not the same as vcp on the platform
    platform_uuid2 = jsondata['result'][0]['uuid']
    assert platform_uuid == platform_uuid2


@pytest.mark.vc
def test_get_setting_keys_first_returns_empty(vc_instance):
    vc, vcuuid, jsonrpc = vc_instance
    tester = WebAPI(jsonrpc)
    resp = tester.do_rpc('get_setting_keys')
    assert resp.json()['result'] is not None
    assert [] == resp.json()['result']


@pytest.mark.vc
def test_vc_settings_store(vc_instance):
    """ Test the reading and writing of data through the get_setting,
        set_setting and get_all_key json-rpc calls.
    """
    vc, vcuuid, jsonrpc = vc_instance

    kv = dict(key='test.user', value='is.good')
    kv2 = dict(key='test.user', value='othervalue')
    kv3 = dict(key='other.user', value='tough stuff')
    tester = WebAPI(jsonrpc)

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
    response = do_rpc("register_instance",
                      dict(discovery_address=pa_wrapper.bind_web_address),
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
        tester = WebAPI(vc_jsonrpc, "foo", "")
