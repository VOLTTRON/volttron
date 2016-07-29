import hashlib

import gevent
import pytest
import requests

from volttron.platform.jsonrpc import json_validate_response
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.utils.servicepaths import (
    VOLTTRON_CENTRAL_PLATFORM_PATH, VOLTTRON_CENTRAL_PATH)
from volttrontesting.utils.utils import (
    poll_gevent_sleep, get_rand_http_address, get_rand_tcp_address)
from volttrontesting.utils.webapi import (
    WebAPI, FailedToGetAuthorization, check_multiple_platforms,
    validate_response, validate_at_least_one, each_result_contains)

# Default configuration dictionary.  To modify make a deep copy of this
# dictionary and then use that reference rather than modifying here.
VC_DEFAULT_CONFIG = {
    "users": {
        "admin": {
            "password": hashlib.sha512("admin").hexdigest(),
            "groups": [
                "admin"
            ]
        }
    }
}


def jsonrpcurl(bind_web_address):
    return "{}/jsonrpc".format(bind_web_address)


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
            wrapper = PlatformWrapper()
            print("VOLTTRON_HOME is set to: {}".format(wrapper.volttron_home))
            instances.append(wrapper)
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


@pytest.fixture(scope="module")
def get_platform_wrappers_module(request):
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


@pytest.fixture
def vc_and_registered_platform(get_platform_wrappers):
    vc_wrapper, pa_wrapper = get_platform_wrappers(2)

    # Both sides have a web server for this one to work properly.
    start_wrapper_platform(vc_wrapper, with_http=True)
    start_wrapper_platform(pa_wrapper,
                           volttron_central_address=vc_wrapper.bind_web_address)

    install_volttron_central(vc_wrapper)
    install_volttron_central_platform(pa_wrapper)

    api = WebAPI(url="{}/jsonrpc".format(vc_wrapper.bind_web_address),
                 username="admin", password="admin")

    # Verify we have the first platform registered.
    poll_gevent_sleep(max_seconds=6,
                      condition=lambda: len(
                          api.list_platforms().json()['result']) == 1)

    # Now we should have more than a single result.
    jsonresp = api.list_platforms().json()

    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)

    # Now we should have an instance running
    assert len(jsonresp['result']) == 1

    return vc_wrapper, pa_wrapper



def build_webapi(wrapper):
    jsonrpc = "{}/jsonrpc".format(wrapper.bind_web_address)
    response = requests.get(jsonrpc)
    assert response.ok, "You must install a volttron central."
    api = WebAPI(url=jsonrpc, username="admin", password="admin")
    return api


def install_volttron_central(wrapper):
    assert wrapper.is_running()
    # Install the volttron central agent.
    vcuuid = wrapper.install_agent(agent_dir=VOLTTRON_CENTRAL_PATH,
                                   config_file=VC_DEFAULT_CONFIG)
    assert vcuuid
    response = requests.get("{}/jsonrpc".format(wrapper.bind_web_address))
    assert response.ok
    return vcuuid


def install_volttron_central_platform(wrapper, config_dict={}):
    assert wrapper.is_running()
    # Install the volttron central agent.
    vcpuuid = wrapper.install_agent(agent_dir=VOLTTRON_CENTRAL_PLATFORM_PATH,
                                    config_file=config_dict)
    assert vcpuuid
    return vcpuuid


def start_wrapper_platform(wrapper, with_http=False, with_tcp=True,
                           volttron_central_address=None):
    assert not wrapper.is_running()

    vc_http = get_rand_http_address() if with_http else None
    vc_tcp = get_rand_tcp_address() if with_tcp else None
    wrapper.startup_platform(encrypt=True, vip_address=vc_tcp,
                             bind_web_address=vc_http,
                             volttron_central_address=volttron_central_address)
    if with_http:
        discovery = "{}/discovery/".format(vc_http)
        response = requests.get(discovery)
        assert response.ok

    assert wrapper.is_running()


@pytest.mark.vc
def test_register_instance_using_discovery(get_platform_wrappers):
    vc_wrapper, pa_wrapper = get_platform_wrappers(2)

    # Both sides have a web server for this one to work properly.
    start_wrapper_platform(vc_wrapper, with_http=True)
    start_wrapper_platform(pa_wrapper, with_http=True)

    install_volttron_central(vc_wrapper)
    install_volttron_central_platform(pa_wrapper)

    api = build_webapi(vc_wrapper)

    jsonresp = api.list_platforms().json()
    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)
    # No platforms are registered with vc yet.
    assert len(jsonresp['result']) == 0

    jsonresp = api.register_instance(pa_wrapper.bind_web_address, "foo")
    assert jsonresp['result']['status'] == 'SUCCESS'
    assert jsonresp['result']['context'] == 'Registered instance foo'

    jsonresp = api.list_platforms().json()

    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)

    print("RESULT IS: {}".format(jsonresp['result']))

    # Now we should have an instance running
    assert len(jsonresp['result']) == 1

    # check_multiple_platforms(vc_wrapper, pa_wrapper)
    #
    # username, auth = authenticate(vc_jsonrpc, "admin", "admin")
    # assert auth
    #
    # print("vip address of pa_agent: {}".format(pa_wrapper.vip_address))
    # print("vip address of vc_agent: {}".format(vc_wrapper.vip_address))
    #
    # # Call register_instance rpc method on vc
    # response = do_rpc("register_instance",
    #                   dict(discovery_address=pa_wrapper.bind_web_address),
    #                   auth, vc_jsonrpc)
    #
    # validate_response(response)
    # result = response.json()['result']
    # assert result['status'] == 'SUCCESS'
    #
    # # list platforms
    # response = do_rpc("list_platforms", None, auth, vc_jsonrpc)
    # validate_response(response)
    # platforms = response.json()['result']
    # assert len(platforms) == 1
    # uuid = platforms[0]['uuid']


@pytest.mark.vc
def test_autoreg_local_platform(get_platform_wrappers):
    # Create a wrapper object that we can install both the VOLTTRON_CENTRAL
    # and the VOLTTRON_CENTRL_PLATFORM on.
    wrapper = get_platform_wrappers(1)[0]

    start_wrapper_platform(wrapper, with_http=True, with_tcp=True)

    # Create a volttron central instance.
    install_volttron_central(wrapper)

    api = WebAPI(url="{}/jsonrpc".format(wrapper.bind_web_address),
                 username="admin", password="admin")
    jsonresp = api.list_platforms().json()
    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)
    # No platforms are registered with vc yet.
    assert len(jsonresp['result']) == 0

    install_volttron_central_platform(wrapper)

    poll_gevent_sleep(max_seconds=10,
                      condition=lambda: len(
                          api.list_platforms().json()['result']) == 1)

    # Now we should have more than a single result.
    jsonresp = api.list_platforms().json()

    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)

    # Now we should have an instance running
    assert len(jsonresp['result']) == 1


@pytest.mark.vc
def test_autoreg_remote_platforms(get_platform_wrappers):
    vc_wrapper, pa_wrapper1, pa_wrapper2 = get_platform_wrappers(3)

    # Build an http address that we can start serving during platform startup.
    vc_http = get_rand_http_address()
    vc_tcp = get_rand_tcp_address()
    vc_wrapper.startup_platform(vip_address=vc_tcp, bind_web_address=vc_http,
                                encrypt=True)

    install_volttron_central(vc_wrapper)

    # Connect to the web api
    api = WebAPI(url="{}/jsonrpc".format(vc_http),
                 username="admin", password="admin")

    jsonresp = api.list_platforms().json()
    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)
    # No platforms are registered with vc yet.
    assert len(jsonresp['result']) == 0

    # Create First Remote Platform
    start_wrapper_platform(pa_wrapper1,
                           volttron_central_address=vc_wrapper.bind_web_address)
    install_volttron_central_platform(pa_wrapper1)

    # Verify we have the first platform registered.
    poll_gevent_sleep(max_seconds=6,
                      condition=lambda: len(
                          api.list_platforms().json()['result']) == 1)

    # Now we should have more than a single result.
    jsonresp = api.list_platforms().json()

    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)

    # Now we should have an instance running
    assert len(jsonresp['result']) == 1

    # Create Second Remote Platform
    start_wrapper_platform(pa_wrapper2,
                           volttron_central_address=vc_wrapper.bind_web_address)
    install_volttron_central_platform(pa_wrapper2)

    poll_gevent_sleep(max_seconds=6,
                      condition=lambda: len(
                          api.list_platforms().json()['result']) == 2)

    # Now we should have more than a single result.
    jsonresp = api.list_platforms().json()

    # make sure we get back a valid json-rpc response.
    json_validate_response(jsonresp)

    # Now we should have an instance running
    assert len(jsonresp['result']) == 2


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
@pytest.mark.xfail(reason='Hmmmm')
def test_list_exported_methods(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    agents = web_api_tester.list_agents(platforms[0]['uuid']).json()['result']
    for agent in agents:
        response = web_api_tester.inspect(platforms[0]['uuid'], agent['uuid'])
        validate_response(response)


@pytest.mark.vc
def test_list_agents(vc_and_registered_platform):
    vcwrap, pawrap = vc_and_registered_platform
    api = WebAPI(jsonrpcurl(vcwrap.bind_web_address))
    gevent.sleep(5)
    platforms = api.list_platforms().json()['result']
    assert len(platforms) > 0
    response = api.list_agents(platforms[0]['uuid'])
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


@pytest.mark.vc
def test_list_platforms(vc_and_registered_platform):
    vcwrap, pawrap = vc_and_registered_platform
    api = WebAPI(jsonrpcurl(vcwrap.bind_web_address))
    response = api.list_platforms()
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


@pytest.mark.vc
@pytest.mark.xfail
def test_unregister_platform(vc_and_registered_platform):
    vcwrap, pawrap = vc_and_registered_platform
    api = WebAPI(jsonrpcurl(vcwrap.bind_web_address))
    # TODO figure out why the registration isn't immediate.
    gevent.sleep(5)
    platforms = api.list_platforms().json()['result']
    orig_platform_count = len(platforms)
    assert orig_platform_count > 0

    uuid_to_remove = platforms[0]['uuid']
    response = web_api_tester.unregister_platform(uuid_to_remove)
    validate_response(response)
    platforms = api.list_platforms().json()['result']
    assert len(platforms) == orig_platform_count - 1


@pytest.mark.web
def test_login_rejected_for_foo(vc_instance):
    vc_jsonrpc = vc_instance[2]
    with pytest.raises(FailedToGetAuthorization):
        tester = WebAPI(vc_jsonrpc, "foo", "")
