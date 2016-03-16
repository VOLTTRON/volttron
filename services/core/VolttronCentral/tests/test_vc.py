import os
import tempfile

import gevent
import pytest
import requests
from zmq.utils import jsonapi

from volttron.platform.keystore import KeyStore
from volttrontesting.fixtures.vc_fixtures import PLATFORM_AGENT_CONFIG


def validate_instances(wrapper1, wrapper2):
    assert wrapper1.bind_web_address
    assert wrapper2.bind_web_address
    assert wrapper1.bind_web_address != wrapper2.bind_web_address
    assert wrapper1.volttron_home
    assert wrapper2.volttron_home
    assert wrapper1.volttron_home != wrapper2.volttron_home

@pytest.mark.vc
def test_publickey_retrieval(vc_instance, pa_instance):
    """ This method tests that the /discovery addresses.

    The discovery now should return the server key for the bus as well as
    for the volttron.central and platform.agent public keys if they are
    available.

    :param vc_instance:
    :param pa_instance:
    :return:
    """
    vc_discovery = vc_instance['wrapper'].bind_web_address+"/discovery/"
    pa_discovery = pa_instance['wrapper'].bind_web_address+"/discovery/"
    response = requests.get(vc_discovery)
    assert response.json()['serverkey']
    assert response.json()['vcpublickey']
    assert response.json()['vcpublickey'] != response.json()['serverkey']

    response2 = requests.get(pa_discovery)
    assert response2.json()['serverkey']
    assert response2.json()['papublickey']
    assert response2.json()['papublickey'] != response.json()['serverkey']

    assert response2.json()['serverkey'] != response.json()['serverkey']
    assert response2.json()['papublickey'] != response.json()['vcpublickey']

    vc_wrapper = vc_instance['wrapper']
    vc_wrapper.install_agent(
        agent_dir='services/core/Platform',
        config_file=PLATFORM_AGENT_CONFIG)
    response3 = requests.get(vc_discovery)
    assert response3.json()['serverkey'] == response.json()['serverkey']
    assert response3.json()['vcpublickey'] == response.json()['vcpublickey']
    assert response3.json()['papublickey']
    assert response3.json()['vcpublickey'] != response2.json()['papublickey']


@pytest.mark.vc
def test_autoregistered_peer_platform(vc_instance):
    vc_wrapper = vc_instance['wrapper']

    caller_agent = vc_wrapper.build_agent(
        address=vc_wrapper.local_vip_address)
    assert caller_agent

    platforms = caller_agent.vip.rpc.call(
        'volttron.central', 'get_platforms').get(timeout=2)

    assert not platforms # no platforms should be registered.

    platform_uuid = vc_wrapper.install_agent(
        agent_dir="services/core/Platform", config_file=PLATFORM_AGENT_CONFIG)

    # must wait for the registration to be added.
    gevent.sleep(6)
    platforms = caller_agent.vip.rpc.call(
        'volttron.central', 'list_platforms').get(timeout=2)

    assert platforms
    p = platforms[0]
    print('A PLATFORM IS: {}'.format(p))
    assert p['is_local']
    assert p['tags']['available']
    assert p['tags']['created']
    assert p['vip_address'] == vc_wrapper.local_vip_address


@pytest.mark.vc
def test_discovery(vc_instance, pa_instance):
    vc_wrapper = vc_instance['wrapper']
    pa_wrapper = pa_instance['wrapper']

    paurl = "http://{}/discovery/".format(pa_wrapper.bind_web_address)
    vcurl = "http://{}/discovery/".format(vc_wrapper.bind_web_address)

    pares = requests.get(paurl)
    assert pares.ok
    data = pares.json()
    assert data['serverkey']
    assert data['vip-address']

    vcres = requests.get(vcurl)
    assert vcres.ok
    data = vcres.json()
    assert data['serverkey']
    assert data['vip-address']


@pytest.mark.vc
def test_vc_started(vc_instance):
    vc_wrapper = vc_instance['wrapper']
    vc_uuid = vc_instance['vc_uuid']

    assert vc_wrapper.is_agent_running(vc_uuid)
    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()  #needed because using a temp file!!!!
    print('Checking peers on vc using:\nserverkey: {}\npublickey: {}\n'
          'secretkey: {}'.format(
        vc_wrapper.publickey,
        ks.public(),
        ks.secret()
    ))
    paagent = vc_wrapper.build_agent(serverkey=vc_wrapper.publickey,
                                     publickey=ks.public(),
                                     secretkey=ks.secret())
    peers = paagent.vip.peerlist().get(timeout=3)
    print(peers)
    assert "volttron.central" in peers
    paagent.core.stop()
    del paagent


@pytest.mark.vc
@pytest.mark.parametrize("display_name", [None, "happydays"])
def test_register_instance(vc_instance, pa_instance, display_name):
    vc_wrapper = vc_instance['wrapper']
    pa_wrapper = pa_instance['wrapper']

    validate_instances(vc_wrapper, pa_wrapper)

    print("connecting to vc instance with vip_adddress: {}".format(
        pa_wrapper.vip_address)
    )

    authfile = os.path.join(vc_wrapper.volttron_home, "auth.json")
    with open(authfile) as f:
        print("vc authfile: {}".format(f.read()))

    tf = tempfile.NamedTemporaryFile()
    paks = KeyStore(tf.name)
    paks.generate()  #needed because using a temp file!!!!
    print('Checking peers on pa using:\nserverkey: {}\npublickey: {}\n'
          'secretkey: {}'.format(
        pa_wrapper.publickey,
        paks.public(),
        paks.secret()
    ))
    paagent = pa_wrapper.build_agent(serverkey=pa_wrapper.publickey,
                                     publickey=paks.public(),
                                     secretkey=paks.secret())
    peers = paagent.vip.peerlist().get(timeout=3)
    assert "platform.agent" in peers
    paagent.core.stop()
    del paagent

    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()  #needed because using a temp file!!!!!
    print('Checking peers on vc using:\nserverkey: {}\npublickey: {}\n'
          'secretkey: {}'.format(
        vc_wrapper.publickey,
        ks.public(),
        ks.secret()
    ))

    # Create an agent to use for calling rpc methods on volttron.central.
    controlagent = vc_wrapper.build_agent(serverkey=vc_wrapper.publickey,
                                          publickey=ks.public(),
                                          secretkey=ks.secret())
    plist = controlagent.vip.peerlist().get(timeout=2)
    assert "volttron.central" in plist

    print('Attempting to manage platform now.')
    print('display_name is now: ', display_name)
    dct = dict(peer="volttron.central", method="register_instance",
                                        discovery_address=pa_wrapper.bind_web_address,
                                        display_name=display_name)
    print(jsonapi.dumps(dct))
    if display_name:
        retval = controlagent.vip.rpc.call("volttron.central", "register_instance",
                                        discovery_address=pa_wrapper.bind_web_address,
                                        display_name=display_name).get(timeout=10)
    else:
        
        retval = controlagent.vip.rpc.call("volttron.central", "register_instance",
                                        discovery_address=pa_wrapper.bind_web_address).get(timeout=10)

    assert retval
    if display_name:
        assert display_name == retval['display_name']
    else:
        assert pa_wrapper.bind_web_address == retval['display_name']
    assert retval['success']

    print('Testing that we now have a single entry in the platform_details')
    retval = controlagent.vip.rpc.call("volttron.central",
                                       "list_platform_details").get(timeout=10)
    print("From vc list_platform_details: {}".format(retval))

    assert len(retval) == 1
    assert 'hushpuppy' == retval[0]['display_name']
    assert retval[0]['vip_address']
    assert not retval[0]['tags']
    assert retval[0]['serverkey']

    controlagent.core.stop()

    # # build agent to interact with the vc agent on the vc_wrapper instance.
    # #agent = vc_wrapper.build_agent(**params)
    # # serverkey=vc_wrapper.publickey,
    # #                                publickey=ks.public(),
    # #                                secretkey=ks.secret())
    # with open(authfile) as f:
    #     print("vc authfile: {}".format(f.read()))
    # peers = agent.vip.peerlist().get(timeout=2)
    # assert "volttron.central" in peers


