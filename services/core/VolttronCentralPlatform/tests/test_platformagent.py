import logging

import os
import requests
import tempfile

import pytest
import gevent
from zmq.utils import jsonapi

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.keystore import KeyStore
from volttron.platform.web import DiscoveryInfo


def get_new_keypair():
    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()
    return ks.public(), ks.secret()


def add_to_auth(volttron_home, publickey, capabilities=None):
    authfile = AuthFile(os.path.join(volttron_home, 'auth.json'))
    entry = AuthEntry(
        credentials="CURVE:{}".format(publickey), capabilities=capabilities
    )
    authfile.add(entry)


def do_rpc(jsonrpc_address, method, params=None, authentication=None ):

    json_package = {
        'jsonrpc': '2.0',
        'id': '2503402',
        'method': method,
    }

    if authentication:
        json_package['authorization'] = authentication

    if params:
        json_package['params'] = params

    return requests.post(jsonrpc_address, data=jsonapi.dumps(json_package))


def get_auth_token(jsonrpc_address):

    params = {'username': 'admin', 'password': 'admin'}

    return do_rpc(jsonrpc_address, 'get_authorization',
                  params).json()['result']


@pytest.mark.pa
def test_manage_agent(pa_instance):
    """ Test that we can manage a `VolttronCentralPlatform`.

    This test is concerned with managing a `VolttronCentralPlatform` from the
    same platform.  Though in principal that should not matter.  We do this
    from a secondary platform in a diffferent integration test.
    """
    wrapper, agent_uuid = pa_instance
    publickey, secretkey = get_new_keypair()

    agent = wrapper.build_agent(
        serverkey=wrapper.publickey, publickey=publickey, secretkey=secretkey)
    peers = agent.vip.peerlist().get(timeout=2)
    assert VOLTTRON_CENTRAL_PLATFORM in peers

    # Make a call to manage which should return to us the publickey of the
    # platform.agent on the instance.
    papublickey = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, 'manage', wrapper.vip_address,
        wrapper.publickey, agent.core.publickey).get(timeout=2)
    assert papublickey


@pytest.mark.pa
def test_can_get_agentlist(pa_instance):
    """ Test that we can retrieve an agent list from an agent.

    The agent must have the "manager" capability.
    """
    wrapper, agent_uuid = pa_instance
    publickey, secretkey = get_new_keypair()

    agent = wrapper.build_agent(
        serverkey=wrapper.publickey, publickey=publickey, secretkey=secretkey)
    peers = agent.vip.peerlist().get(timeout=2)
    assert VOLTTRON_CENTRAL_PLATFORM in peers

    # Make a call to manage which should return to us the publickey of the
    # platform.agent on the instance.
    papublickey = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, 'manage', wrapper.vip_address,
        wrapper.publickey, agent.core.publickey).get(timeout=2)
    assert papublickey

    agentlist = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, "list_agents"
    ).get(timeout=2)

    assert isinstance(agentlist, list)
    assert len(agentlist) == 1
    retagent = agentlist[0]
    assert retagent['uuid'] == agent_uuid
    checkkeys = ('process_id', 'error_code', 'is_running', 'permissions',
                 'health')
    for k in checkkeys:
        assert k in retagent.keys()

    # make sure can stop is determined to be false
    assert retagent['permissions']['can_stop'] == False

@pytest.mark.pa
def test_agent_can_be_managed(pa_instance):
    wrapper = pa_instance[0]
    publickey, secretkey = get_new_keypair()
    add_to_auth(wrapper.volttron_home, publickey, capabilities=['managed_by'])
    agent = wrapper.build_agent(
        serverkey=wrapper.publickey, publickey=publickey, secretkey=secretkey)
    peers = agent.vip.peerlist().get(timeout=2)
    assert VOLTTRON_CENTRAL_PLATFORM in peers

    # This step is required because internally we are really connecting
    # to the same platform.  If this were two separate installments this
    # transaction would be easier.
    pa_info = DiscoveryInfo.request_discovery_info(wrapper.bind_web_address)
    add_to_auth(wrapper.volttron_home, pa_info.serverkey,
                capabilities=['can_be_managed'])
    print(wrapper.vip_address)
    returnedid = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, 'manage', wrapper.vip_address,
        wrapper.publickey, agent.core.publickey).get(timeout=2)
    assert returnedid


# @pytest.mark.pa
# def test_agent_data(pa_instance, vc_instance):
#     pa_wrapper = pa_instance['wrapper']
#     agent_uuid = pa_instance['platform-uuid']
#     vc_wrapper = vc_instance['wrapper']
#     jsonrpc_address = vc_instance['jsonrpc']
#
#     assert pa_wrapper
#     assert vc_wrapper
#     assert pa_wrapper.bind_web_address
#
#     authtoken = get_auth_token(jsonrpc_address)
#     assert authtoken
#
#     register = do_rpc(jsonrpc_address, 'register_instance',
#                       authentication=authtoken,
#                       params={
#                           'discovery_address': pa_wrapper.bind_web_address})
#
#     assert register
    #
    # tf = tempfile.NamedTemporaryFile()
    # ks = KeyStore(tf.name)
    # ks.generate()
    #
    # entry = AuthEntry(credentials="CURVE:{}".format(ks.public()))
    # authfile = AuthFile(os.path.join(pa_wrapper.volttron_home, "auth.json"))
    # authfile.add(entry)
    # gevent.sleep(0.1)
    #
    # agent = pa_wrapper.build_agent(
    #     serverkey=pa_wrapper.publickey,
    #     secretkey=ks.secret(),
    #     publickey=ks.public()
    # )
    #
    # peers = agent.vip.peerlist().get(timeout=2)
    # assert PLATFORM_ID in peers
    # assert agent.core.address.startswith('tcp://')
    #
    # print('Calling manage')
    # registered_uuid = agent.vip.rpc.call(
    #     PLATFORM_ID, 'manage', pa_wrapper.vip_address,
    #     pa_wrapper.publickey).get(timeout=2)
    #
    # assert registered_uuid




# def simulated_vc(wrapper, do_manage=False):
#
#     secretkey, publickey = get_new_keypair()
#
#     # This agent will act as a volttron central agent for the purposes
#     # of this test.
#     vc_agent = wrapper.build_agent(serverkey=wrapper.publickey,
#                                    secretkey=secretkey,
#                                    publickey=publickey)
#
#     peers = vc_agent.vip.peerlist().get(timeout=3)
#     assert 'platform.agent' in peers
#
#     if do_manage:
#
#         # Expected to return the platform.agent public key.
#         pk = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
#                                    wrapper.bind_web_address,
#                                    publickey).get(timeout=3)
#         assert pk
#
#         # check the auth file for a can_manage capability in it.
#         auth_path = os.path.join(wrapper.volttron_home, "auth.json")
#         print('ThE AUTH PATH: {}'.format(auth_path))
#         with open(auth_path) as fd:
#             auth_json = fd.read()
#
#         auth_dict = jsonapi.loads(auth_json)
#         print("auth_dict is", auth_dict)
#         found = False
#         for k in auth_dict['allow']:
#             if k['credentials'].endswith(ks.public()):
#                 print('Found vc_publickey:', ks.public())
#                 print("The agent k is: {}".format(k))
#                 capabilities =k.get('capabilities', None)
#                 assert capabilities
#                 assert 'can_manage' in capabilities
#                 found = True
#         assert found, "No vc agent ({}) found with can_manage capability.".format(vc_publickey)
#
#     return vc_agent, secretkey, publickey

# def install_platform(wrapper):
#     agent_uuid = wrapper.install_agent(
#         agent_dir="services/core/VolttronCentralPlatform",
#         config_file="services/core/VolttronCentralPlatform/config")
#     return agent_uuid
#
#
# @pytest.mark.pa
# def test_list_agents(volttron_instance1):
#
#     agent_uuid = install_platform(volttron_instance1)
#
#     caller = volttron_instance1.build_agent()
#
#     results = caller.vip.rpc.call(
#         PLATFORM_ID, "list_agents").get(timeout=10)
#
#     statuses = caller.vip.rpc.call(
#         PLATFORM_ID, "status_agents").get(timeout=10)
#
#     # Note since the vc is simulated the list_agents only should have the
#     # platformagent
#     assert results
#     keys = results[0].keys()
#     assert 'platformagent' in results[0]['name']
#     assert 'process_id' in keys
#     assert 'uuid' in keys
#     assert 'priority' in keys
#     assert 'error_code' in keys
#     assert results[0]['process_id'] > 0
#     assert 'health' in keys
#     assert results[0]['health']['health'] == "GOOD"
#     assert results[0]['health']['context']
#     assert results[0]['health']['last_updated']



# @pytest.mark.pa
# def test_status_agents(pa_instance):
#     pa_wrapper = pa_instance['wrapper']
#
#     vc_agent, secret_key, public_key = simulated_vc(pa_wrapper, do_manage=True)
#
#     assert vc_agent
#
#     results = vc_agent.vip.rpc.call(PLATFORM_ID, "status_agents").get(timeout=10)
#
#     # Note since the vc is simulated the list_agents only should have the
#     # platformagent
#     assert results
#     assert 'platformagent' in results[0]['name']

# @pytest.mark.pa
# def test_platform_health(volttron_instance1):
#     agent_uuid = install_platform(volttron_instance1)
#     assert agent_uuid
#
#     caller = volttron_instance1.build_agent()
#     assert caller
#
#     status = caller.vip.rpc.call('platform.agent',
#                                  'get_health').get(timeout=2)
#
#     assert status['health'] == 'GOOD'
#     assert status['context']
#     assert status['last_updated']
#
#
# @pytest.mark.pa
# def test_startstoprestart_agent(volttron_instance1):
#     agent_uuid = install_platform(volttron_instance1)
#     assert agent_uuid
#
#     caller = volttron_instance1.build_agent()
#     assert caller
#
#     listener_dir = "examples/ListenerAgent"
#     config = "examples/ListenerAgent/config"
#     listener_uuid = volttron_instance1.install_agent(agent_dir=listener_dir,
#                                                      config_file=config,
#                                                      start=False)
#     result = caller.vip.rpc.call(PLATFORM_ID, "agent_status",
#                                  listener_uuid).get(timeout=3)
#     assert result == [None, None]
#     assert listener_uuid
#     caller.vip.rpc.call(PLATFORM_ID, "start_agent",
#                         listener_uuid).get(timeout=3)
#     gevent.sleep(.1)
#     result = caller.vip.rpc.call(PLATFORM_ID, "agent_status",
#                                  listener_uuid).get(timeout=3)
#     assert result[0] > 0
#     assert result[1] is None
#     original_proc = result[0]
#
#     caller.vip.rpc.call(PLATFORM_ID, "restart_agent",
#                         listener_uuid).get(timeout=3)
#     gevent.sleep(0.1)
#     result = caller.vip.rpc.call(PLATFORM_ID, "agent_status",
#                                  listener_uuid).get(timeout=3)
#     assert result[0] > 0
#     assert result[1] is None
#     # TODO: Figure out why the following test fails.
#     #assert result[0] != original_proc
#
#     caller.vip.rpc.call(PLATFORM_ID, "stop_agent",
#                         listener_uuid).get(timeout=3)
#     gevent.sleep(0.1)
#     result = caller.vip.rpc.call(PLATFORM_ID, "agent_status",
#                                  listener_uuid).get(timeout=3)
#     print("the result is: {}".format(result))
#     assert result[0] > 0
#     # TODO: What should the real value be?
#     #assert result[1] == 0


# @pytest.mark.pa
# def test_automanage(volttron_instance1):
#
#     install_platform(volttron_instance1)
#     volttron_instance1.install_agent(
#         agent_dir='services/core/VolttronCentral',
#         config_file='services/core/VolttronCentral/config')
#
#     caller = volttron_instance1.build_agent()
#     assert caller
#
#     managed = caller.vip.rpc(PLATFORM_ID,'is_managed').get(timeout=10)
#     assert managed


# @pytest.mark.pa
# def test_manage_platform(volttron_instance1):
#     """ Test the ability for a platform to be registered from an entity.
#
#     :param pa_instance: {platform_uuid: uuid, wrapper: instance_wrapper}
#     :return: None
#     """
#
#     # Platform installed on volttron_instance2
#     install_platform(volttron_instance1)
#
#     caller = volttron_instance1.build_agent()
#     assert caller
#
#     caller.vip.rpc.call(PLATFORM_ID, 'manage_platform')
#
#
#
#
#     pa_wrapper = pa_instance['wrapper']
#     vc_agent, vc_secretkey, vc_publickey = simulated_vc(pa_wrapper)
#
#     # Expected to return the platform.agent public key.
#     papubkey = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
#                                      pa_wrapper.bind_web_address,
#                                      vc_publickey).get(timeout=3)
#     assert papubkey
#
#     # Test that once it's registered a new call to manage_platform will
#     # return the same result.
#     pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
#                                 pa_wrapper.bind_web_address,
#                                 vc_publickey).get(timeout=3)
#
#     # The pakey returned should be the same.
#     assert papubkey == pk1
#
#     # Make sure that the error returned is correct when we don't have the
#     # the correct public key
#     tf = tempfile.NamedTemporaryFile()
#     ks = KeyStore(tf.name)
#     ks.generate()
#
#     # if for some reason you can't import the specific exception class,
#     # catch it as generic and verify it's in the str(excinfo)
#     with pytest.raises(Exception) as excinfo:
#         pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
#                                 pa_wrapper.bind_web_address,
#                                 ks.public()).get(timeout=3)
#     assert 'AlreadyManagedError' in str(excinfo)
#
#     # check the auth file for a can_manage capability in it.
#     auth_json = open(os.path.join(pa_wrapper.volttron_home, "auth.json")).read()
#     auth_dict = jsonapi.loads(auth_json)
#
#     found = False
#     for k in auth_dict['allow']:
#         if k['credentials'].endswith(vc_publickey):
#             print('Found vc_publickey')
#             capabilities =k.get('capabilities', None)
#             assert capabilities
#             assert 'can_manage' in capabilities
#             found = True
#     assert found, "No vc agent ({}) found with can_manage capability.".format(vc_publickey)


# def test_setting_creation(volttron_instance1, platform_uuid):
#     """ Tests setting and retrieval of settings.
#
#     * The test will stop and start the agent to test the
#     persistence of the settings.
#
#     * The test will test the ability to overwrite an existing setting with
#     a new value.
#
#     :param volttron_instance1:
#     :param platform_uuid:
#     :return:
#     """
#
#     agent = volttron_instance1.build_agent()
#     agent.vip.rpc.call(PLATFORM_ID, "set_setting", key="las",
#                        value="vegas").get(timeout=3)
#
#     res = agent.vip.rpc.call(PLATFORM_ID, "get_setting",
#                              key="las").get(timeout=3)
#     assert res == "vegas"
#
#     agent.vip.rpc.call(PLATFORM_ID, "set_setting", key="las",
#                        value="Palmas de Gran Canaria")
#     res = agent.vip.rpc.call(PLATFORM_ID, "get_setting",
#                              key="las").get(timeout=3)
#     assert res == "Palmas de Gran Canaria"
#
#     volttron_instance1.stop_agent(platform_uuid)
#     volttron_instance1.start_agent(platform_uuid)
#
#     res = agent.vip.rpc.call(PLATFORM_ID, "get_setting",
#                              key="las").get(timeout=3)
#     assert res == "Palmas de Gran Canaria"




