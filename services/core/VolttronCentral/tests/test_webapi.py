import json
import os

import gevent
import pytest
import requests
import sys

from volttron.platform import get_examples
from volttrontesting.utils.agent_additions import \
    add_volttron_central_platform, add_volttron_central, add_listener

from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform
from volttrontesting.utils.utils import poll_gevent_sleep
from zmq.utils import jsonapi
from vctestutils import (APITester,
                         check_multiple_platforms,
                         validate_response)


@pytest.fixture(scope="module")
def vc_vcp_platforms():
    """
    This method returns two distinct platforms one vc and one vcp.  When they
    are returned they should be registered together.

    This method will yield the two platforms as a tuple and then after the
    module is finished executing the cleanup of both will happen.

    """
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
    resp = tester.set_setting(**kv)
    assert 'SUCCESS' == resp

    # Get setting should respond with the same  value.
    resp = tester.get_setting(key=kv['key'])
    assert kv['value'] == resp

    # Make sure keys are returned.
    resp = tester.get_setting_keys()
    assert kv['key'] in resp

    # Test overwrite
    resp = tester.set_setting(**kv2)
    assert 'SUCCESS' == resp

    # Test that the data was overwritten
    resp = tester.get_setting(key=kv['key'])
    assert kv2['value'] == resp

    # add secondary key/value
    resp = tester.set_setting(**kv3)
    assert 'SUCCESS' == resp

    # test both keys are in the store
    resp = tester.get_setting_keys()
    assert kv['key'] in resp
    assert kv3['key'] in resp

    # A None(null) value passed to set_setting should remove the key
    resp = tester.set_setting(key=kv['key'], value=None)
    assert 'SUCCESS' == resp
    resp = tester.get_setting_keys()
    assert kv['key'] not in resp


@pytest.mark.vc
@pytest.mark.skip(reason="Must reimplement unregister.")
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
    with pytest.raises(AssertionError):
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

    platforms = api.list_platforms()
    platform_uuid = platforms[0]["uuid"]

    resp = api.store_agent_config(platform_uuid, identity, config_name,
                                  str_data)
    assert resp is None

    resp = api.list_agent_configs(platform_uuid, identity)
    assert config_name == resp[0]

    resp = api.get_agent_config(platform_uuid, identity, config_name)
    assert str_data == resp


@pytest.mark.vc
def test_correct_reader_permissions_on_vcp_vc_and_listener_agent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint, username="reader", password="reader")

    platform = api.list_platforms()[0]
    print('The platform is {}'.format(platform))

    agent_list = api.list_agents(platform_uuid=platform['uuid'])
    print('The agent list is: {}'.format(agent_list))
    assert len(agent_list) == 1
    assert agent_list[0]['version']

    add_listener(vcp, {"log-level": "DEBUG"})
    agent_list = api.list_agents(platform_uuid=platform['uuid'])
    assert len(agent_list) == 2

    permissions = ('can_restart', 'can_remove', 'can_stop', 'can_start')

    for agent in agent_list:
        for p in permissions:
            assert p in agent['permissions']
            # for reader all should be false.
            assert not agent['permissions'][p]


@pytest.mark.vc
def test_correct_admin_permissions_on_vcp_vc_and_listener_agent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint)

    platform = api.list_platforms()[0]

    len_before_new_listener = len(
        api.list_agents(platform_uuid=platform['uuid']))

    add_listener(vcp, {"log-level": "DEBUG"})
    agent_list = api.list_agents(platform_uuid=platform['uuid'])
    assert len_before_new_listener + 1 == len(agent_list)

    permissions = ('can_restart', 'can_remove', 'can_stop', 'can_start')

    for agent in agent_list:
        for p in permissions:
            assert p in agent['permissions']
            # for admin all should be true.
            assert agent['permissions'][p]


@pytest.mark.vc
def test_correct_admin_permissions_on_vcp_vc_and_listener_agent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint)

    platform = api.list_platforms()[0]
    print('The platform is {}'.format(platform))

    len_before_new_listener = len(api.list_agents(platform_uuid=platform['uuid']))

    add_listener(vcp, {"log-level": "DEBUG"})
    agent_list = api.list_agents(platform_uuid=platform['uuid'])
    assert len_before_new_listener + 1 == len(agent_list)

    permissions = ('can_restart', 'can_remove', 'can_stop', 'can_start')

    for agent in agent_list:
        for p in permissions:
            assert p in agent['permissions']

            if agent['identity'] in ('platform.agent', 'volttron.central'):
                if p in ('can_restart', 'can_start'):
                    assert agent['permissions'][p]
                else:
                    assert not agent['permissions'][p]
            else:
                # for admin all should be true if not vcp or vc.
                assert agent['permissions'][p]


@pytest.mark.vc
def test_listagent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc.jsonrpc_endpoint)

    platform = api.list_platforms()[0]
    print('The platform is {}'.format(platform))

    agent_list = api.list_agents(platform_uuid=platform['uuid'])
    print('The agent list is: {}'.format(agent_list))
    assert len(agent_list) > 1
    assert agent_list[0]['version']


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

    agent_wheel = vc.build_agentpackage(get_examples("ListenerAgent"))
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

    platform = api.list_platforms()[0]

    agents = api.list_agents(platform['uuid'])
    assert agents

    agent = api.install_agent(platform['uuid'], fileargs=file)

    assert agent
    assert agent.get('uuid')

    agents_after = api.list_agents(platform['uuid'])
    assert len(agents) + 1 == len(agents_after)
