import hashlib
import os
import tempfile
import uuid

import gevent
import pytest
import requests
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore
from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.web import DiscoveryInfo
from volttrontesting.utils.agent_additions import \
    add_volttron_central_platform
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform
from volttron.platform import jsonapi


def get_new_keypair():
    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()
    return ks.public, ks.secret


def add_to_auth(volttron_home, publickey, capabilities=None):
    authfile = AuthFile(os.path.join(volttron_home, 'auth.json'))
    entry = AuthEntry(
        credentials=publickey, mechanism="CURVE", capabilities=capabilities
    )
    authfile.add(entry, overwrite=True)


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


def values_not_none(keylist, lookup):
    for k in keylist:
        names = k.split('.')
        obj = lookup
        for i in range(len(names)):
            if i == len(names) - 1:
                return names[i] in obj and obj[names[i]] is not None
            try:
                obj = obj[names[i]]
            except KeyError:
                return False
    # passes a None keylist?
    return False


def contains_keys(keylist, lookup):
    for k in keylist:
        names = k.split('.')
        obj = lookup
        for i in range(len(names)):
            if i == len(names) - 1:
                return names[i] in obj
            try:
                obj = obj[names[i]]
            except KeyError:
                return False
    # passes a None keylist?
    return False


class SimulatedVC(Agent):
    def __init__(self, **kwargs):
        super(SimulatedVC, self).__init__(**kwargs)
        self._functioncalls = {}

    def add_method_response(self, method_name, response):
        pass


@pytest.fixture(scope="module")
def vcp_simulated_vc(request):
    """
    This method yields a platform wrapper with a vcp installed and an agent
    connected to it with manager capabilities.

    The parameters are for each of the different identities we want to test
    with.
    """
    p = PlatformWrapper()

    start_wrapper_platform(p, with_tcp=True)
    vcp_uuid = add_volttron_central_platform(p)

    # Build a connection to the just installed vcp agent.
    vc_simulated_agent = p.build_connection("platform.agent",
                                            identity="volttron.central")
    p.add_capabilities(vc_simulated_agent.server.core.publickey, "manager")

    yield p, vc_simulated_agent

    vc_simulated_agent.kill()
    p.shutdown_platform()


@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_pa_uses_correct_address_hash(vcp_simulated_vc):
    p, vc = vcp_simulated_vc

    address_hash_should_be = hashlib.md5(p.vip_address).hexdigest()
    assert address_hash_should_be == vc.call("get_instance_uuid")


@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_get_health(vcp_simulated_vc):
    p, vc = vcp_simulated_vc

    health_from_vcp = vc.call("get_health")
    health = vc.call("health.get_status")

    check = ('status', 'context', 'last_updated')

    for x in check:
        assert health[x] == health_from_vcp[x]

    vc.call('health.set_status', STATUS_GOOD, 'Let the good-times role')

    health_from_vcp = vc.call("get_health")
    health = vc.call("health.get_status")

    for x in check:
        assert health[x] == health_from_vcp[x]

    assert health['status'] == STATUS_GOOD
    assert health['context'] == 'Let the good-times role'

@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_listagents(vcp_simulated_vc):
    try:
        wrapper, vc = vcp_simulated_vc

        os.environ['VOLTTRON_HOME'] = wrapper.volttron_home
        agent_list = vc.call(
            'route_request', 'foo', 'list_agents', None)
        assert 1 <= len(agent_list)
        expected_keys = ['name', 'uuid', 'tag', 'priority', 'process_id', 'health',
                         'health.status', 'heatlh.context', 'health.last_updated',
                         'error_code', 'permissions', 'permissions.can_restart',
                         'permissions.can_remove', 'can_stop', 'can_start',
                         'version']
        expected_key_set = set(expected_keys)
        none_key_set = set(['tag', 'priority', 'health.context', 'error_code'])
        not_none_key_set = expected_key_set.difference(none_key_set)
        for a in agent_list:
            assert contains_keys(expected_keys, a)
            assert values_not_none(not_none_key_set, a)
    finally:
        os.environ.pop('VOLTTRON_HOME')

@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_manage_agent(vcp_instance):
    """ Test that we can manage a `VolttronCentralPlatform`.

    This test is concerned with managing a `VolttronCentralPlatform` from the
    same platform.  Though in principal that should not matter.  We do this
    from a secondary platform in a diffferent integration test.
    """
    wrapper, agent_uuid = vcp_instance
    publickey, secretkey = get_new_keypair()

    agent = wrapper.build_agent(
        serverkey=wrapper.serverkey, publickey=publickey, secretkey=secretkey)
    peers = agent.vip.peerlist().get(timeout=2)
    assert VOLTTRON_CENTRAL_PLATFORM in peers

    # Make a call to manage which should return to us the publickey of the
    # platform.agent on the instance.
    papublickey = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, 'manage', wrapper.vip_address,
        wrapper.serverkey, agent.core.publickey).get(timeout=2)
    assert papublickey


@pytest.mark.pa
@pytest.mark.xfail(reason="Need to upgrade")
def test_can_get_agentlist(vcp_instance):
    """ Test that we can retrieve an agent list from an agent.

    The agent must have the "manager" capability.
    """
    wrapper, agent_uuid = vcp_instance
    publickey, secretkey = get_new_keypair()

    agent = wrapper.build_agent(
        serverkey=wrapper.serverkey, publickey=publickey, secretkey=secretkey)
    peers = agent.vip.peerlist().get(timeout=2)
    assert VOLTTRON_CENTRAL_PLATFORM in peers

    # Make a call to manage which should return to us the publickey of the
    # platform.agent on the instance.
    papublickey = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, 'manage', wrapper.vip_address,
        wrapper.serverkey, agent.core.publickey).get(timeout=2)
    assert papublickey

    agentlist = agent.vip.rpc.call(
        VOLTTRON_CENTRAL_PLATFORM, "list_agents"
    ).get(timeout=2)

    assert isinstance(agentlist, list)
    assert len(agentlist) == 1
    retagent = agentlist[0]
    assert retagent['uuid'] == agent_uuid
    checkkeys = ('process_id', 'error_code', 'is_running', 'permissions',
                 'health', 'version')
    for k in checkkeys:
        assert k in retagent

    # make sure can stop is determined to be false
    assert retagent['permissions']['can_stop'] == False


@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_agent_can_be_managed(vcp_instance):
    wrapper = vcp_instance[0]
    publickey, secretkey = get_new_keypair()
    add_to_auth(wrapper.volttron_home, publickey, capabilities=['managed_by'])
    agent = wrapper.build_agent(
        serverkey=wrapper.serverkey, publickey=publickey, secretkey=secretkey)
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
        wrapper.serverkey, agent.core.publickey).get(timeout=2)
    assert returnedid


@pytest.mark.pa
@pytest.mark.skip(reason="4.1 fixing tests")
def test_status_good_when_agent_starts(vcp_instance):
    wrapper = vcp_instance[0]
    connection = wrapper.build_connection(peer=VOLTTRON_CENTRAL_PLATFORM)

    assert connection.is_connected()
    status = connection.call('health.get_status')
    assert isinstance(status, dict)
    assert status
    assert STATUS_GOOD == status['status']

