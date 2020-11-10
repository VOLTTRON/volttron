import os

import gevent
import pytest

from volttron.platform import get_examples, jsonapi
from volttrontesting.utils.agent_additions import \
    add_volttron_central_platform, add_volttron_central, add_listener

from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform

from vctestutils import APITester
from services.core.VolttronCentral.tests.vc_fixtures import \
    vc_and_vcp_together, vc_instance, vcp_instance


@pytest.fixture(scope="module")
def auto_registered_local(vc_and_vcp_together):
    webapi = APITester(vc_and_vcp_together)

    yield webapi


def test_platform_list(auto_registered_local):
    webapi = auto_registered_local

    assert len(webapi.list_platforms()) == 1


def test_platform_inspect(auto_registered_local):
    webapi = auto_registered_local
    platforms = webapi.list_platforms()
    platform_uuid = platforms[0]["uuid"]

    agents = webapi.list_agents(platform_uuid)

    for agent in agents:
        agent_uuid = agent['uuid']
        result = webapi.inspect(platform_uuid, agent_uuid)
        print(result)
        method = 'health.get_status'
        assert method in result['methods']


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


@pytest.mark.vc
def test_vc_settings_store(auto_registered_local):
    """ Test the reading and writing of data through the get_setting,
        set_setting and get_all_key json-rpc calls.
    """
    webapi = auto_registered_local

    kv = dict(key='test.user', value='is.good')
    kv2 = dict(key='test.user', value='othervalue')
    kv3 = dict(key='other.user', value='tough stuff')

    # Creating setting replies with SUCCESS.
    resp = webapi.set_setting(**kv)
    assert 'SUCCESS' == resp

    # Get setting should respond with the same  value.
    resp = webapi.get_setting(key=kv['key'])
    assert kv['value'] == resp

    # Make sure keys are returned.
    resp = webapi.get_setting_keys()
    assert kv['key'] in resp

    # Test overwrite
    resp = webapi.set_setting(**kv2)
    assert 'SUCCESS' == resp

    # Test that the data was overwritten
    resp = webapi.get_setting(key=kv['key'])
    assert kv2['value'] == resp

    # add secondary key/value
    resp = webapi.set_setting(**kv3)
    assert 'SUCCESS' == resp

    # test both keys are in the store
    resp = webapi.get_setting_keys()
    assert kv['key'] in resp
    assert kv3['key'] in resp

    # A None(null) value passed to set_setting should remove the key
    resp = webapi.set_setting(key=kv['key'], value=None)
    assert 'SUCCESS' == resp
    resp = webapi.get_setting_keys()
    assert kv['key'] not in resp


@pytest.mark.vc
def test_store_list_get_configuration(auto_registered_local):

    data = dict(
        bim=50,
        baz="foo",
        bar="lambda"
    )
    str_data = jsonapi.dumps(data)
    identity = "foo.bar"
    config_name = "fuzzywidgets"

    webapi = auto_registered_local

    platforms = webapi.list_platforms()
    platform_uuid = platforms[0]["uuid"]

    resp = webapi.store_agent_config(platform_uuid, identity, config_name,
                                     str_data)
    assert resp is None

    resp = webapi.list_agent_configs(platform_uuid, identity)
    assert config_name == resp[0]

    resp = webapi.get_agent_config(platform_uuid, identity, config_name)
    assert str_data == resp


@pytest.mark.vc
def test_store_delete_configuration(auto_registered_local):

    data = dict(
        bim=50,
        baz="foo",
        bar="lambda"
    )
    str_data = jsonapi.dumps(data)
    identity = "foo.bar"
    config_name = "fuzzywidgets"

    webapi = auto_registered_local

    platforms = webapi.list_platforms()
    platform_uuid = platforms[0]["uuid"]

    resp = webapi.store_agent_config(platform_uuid, identity, config_name,
                                     str_data)
    assert resp is None

    resp = webapi.list_agent_configs(platform_uuid, identity)
    assert config_name == resp[0]

    resp = webapi.get_agent_config(platform_uuid, identity, config_name)
    assert str_data == resp

    resp = webapi.delete_agent_config(platform_uuid, identity, config_name)
    assert '' == resp

    resp = webapi.list_agent_configs(platform_uuid, identity)
    for res in resp:
        assert config_name != resp[0]


@pytest.mark.vc
@pytest.mark.skipif(True, reason='Permissions always admin presently')
def test_correct_reader_permissions_on_vcp_vc_and_listener_agent(vc_vcp_platforms):
    vc, vcp = vc_vcp_platforms

    api = APITester(vc, username="reader", password="reader")

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
def test_correct_admin_permissions_on_vcp_vc_and_listener_agent(auto_registered_local):

    apitester = auto_registered_local

    platform = apitester.list_platforms()[0]
    print('The platform is {}'.format(platform))

    len_before_new_listener = len(apitester.list_agents(platform_uuid=platform['uuid']))

    listener_uuid = add_listener(apitester._wrapper, {"log-level": "DEBUG"})
    agent_list = apitester.list_agents(platform_uuid=platform['uuid'])
    assert len_before_new_listener + 1 == len(agent_list)

    permissions = ('can_restart', 'can_remove', 'can_stop', 'can_start')

    for agent in agent_list:
        for p in permissions:
            assert p in agent['permissions']
            permissions = agent['permissions']

            if agent['identity'] in ('platform.agent', 'volttron.central') or \
                    agent['identity'].endswith('.platform.agent'):
                if p in ('can_restart', 'can_start'):
                    assert permissions[p]
                else:
                    assert not permissions[p]
            else:
                # for admin all should be true if not vcp or vc.
                assert permissions[p]

    apitester.remove_agent(platform['uuid'], listener_uuid)
    agent_list = apitester.list_agents(platform_uuid=platform['uuid'])
    assert len_before_new_listener == len(agent_list)


@pytest.mark.vc
def test_listagent(auto_registered_local):

    webapi = auto_registered_local

    platform = webapi.list_platforms()[0]
    print('The platform is {}'.format(platform))

    agent_list = webapi.list_agents(platform_uuid=platform['uuid'])
    print('The agent list is: {}'.format(agent_list))
    assert len(agent_list) > 1
    assert agent_list[0]['version']


@pytest.mark.vc
def test_installagent(auto_registered_local):

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

    webapi = auto_registered_local
    agent_wheel = webapi._wrapper.build_agentpackage(get_examples("ListenerAgent"))
    assert os.path.exists(agent_wheel)

    import base64
    import random

    # with open(agent_wheel, 'r+b') as f:
    #     hold = f.read()
    #     file_str = str(hold).encode('utf-8')
    #     decoded_str = str(base64.decodestring(hold))
    #     # From the web this is what is added to the file.
    #     filestr = "base64," + file_str
    #     # filestr = "base64,"+str(base64.b64encode(hold))

    with open(agent_wheel, 'r+b') as f:
        # From the web this is what is added to the file.
        hold = f.read()
        print(f"Package is {hold}")
        filestr = "base64,"+base64.b64encode(hold).decode('utf-8')
        print(f"file string is {filestr}")
    file_props = dict(
        file_name=os.path.basename(agent_wheel),
        file=filestr,
        vip_identity='bar.full.{}'.format(random.randint(1, 100000))
    )

    platform = webapi.list_platforms()[0]

    agents = webapi.list_agents(platform['uuid'])
    assert agents

    agent = webapi.install_agent(platform['uuid'], fileargs=file_props)

    assert agent
    assert agent.get('uuid')

    agents_after = webapi.list_agents(platform['uuid'])
    assert len(agents) + 1 == len(agents_after)

    webapi.remove_agent(platform['uuid'], agent.get('uuid'))
    agents_after = webapi.list_agents(agent.get('uuid'))
    assert len(agents) == len(agents_after)


# @pytest.mark.vc
# def test_login_rejected_for_foo(vc_instance):
#     vc_jsonrpc = vc_instance[2]
#     with pytest.raises(AssertionError):
#         tester = APITester(vc_jsonrpc, "foo", "")
