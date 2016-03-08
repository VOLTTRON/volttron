import logging
import os
import tempfile

from zmq.utils import jsonapi
import pytest
import gevent
from volttron.platform.keystore import KeyStore

# The default platform identity
PLATFORM_ID = 'platform.agent'


def simulated_vc(wrapper, do_manage=False):
    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()

    # This agent will act as a volttron central agent for the purposes
    # of this test.
    vc_agent = wrapper.build_agent(serverkey=wrapper.publickey,
                                      secretkey=ks.secret(),
                                      publickey=ks.public())

    peers = vc_agent.vip.peerlist().get(timeout=3)
    assert 'platform.agent' in peers

    if do_manage:
        # Expected to return the platform.agent public key.
        pk = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                   wrapper.bind_web_address,
                                   ks.public()).get(timeout=3)
        assert pk
        # check the auth file for a can_manage capability in it.
        auth_path = os.path.join(wrapper.volttron_home, "auth.json")
        print('ThE AUTH PATH: {}'.format(auth_path))
        with open(auth_path) as fd:
            auth_json = fd.read()

        auth_dict = jsonapi.loads(auth_json)
        print("auth_dict is", auth_dict)
        found = False
        for k in auth_dict['allow']:
            if k['credentials'].endswith(ks.public()):
                print('Found vc_publickey:', ks.public())
                print("The agent k is: {}".format(k))
                capabilities =k.get('capabilities', None)
                assert capabilities
                assert 'can_manage' in capabilities
                found = True
        assert found, "No vc agent ({}) found with can_manage capability.".format(vc_publickey)

    return vc_agent, ks.secret(), ks.public()

@pytest.mark.pa
def test_list_agents(pa_instance):
    pa_wrapper = pa_instance['wrapper']

    vc_agent, secret_key, public_key = simulated_vc(pa_wrapper, do_manage=True)

    assert vc_agent

    results = vc_agent.vip.rpc.call(PLATFORM_ID, "list_agents").get(timeout=10)

    # Note since the vc is simulated the list_agents only should have the
    # platformagent
    assert results
    keys = results[0].keys()
    assert 'platformagent' in results[0]['name']
    assert 'process_id' in keys
    assert 'uuid' in keys
    assert 'priority' in keys
    assert 'error_code' in keys
    assert results[0]['process_id'] > 0




@pytest.mark.pa
def test_start_agent(pa_instance):
    pass

@pytest.mark.pa
def test_end_agent(pa_instance):
    pass

@pytest.mark.pa
def test_restart_agent(pa_instance):
    pass




@pytest.mark.pa
def test_manage_platform(pa_instance):
    """ Test the ability for a platform to be registered from an entity.

    :param pa_instance: {platform_uuid: uuid, wrapper: instance_wrapper}
    :return: None
    """

    pa_wrapper = pa_instance['wrapper']
    vc_agent, vc_secretkey, vc_publickey = simulated_vc(pa_wrapper)

    # Expected to return the platform.agent public key.
    papubkey = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                     pa_wrapper.bind_web_address,
                                     vc_publickey).get(timeout=3)
    assert papubkey

    # Test that once it's registered a new call to manage_platform will
    # return the same result.
    pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                pa_wrapper.bind_web_address,
                                vc_publickey).get(timeout=3)

    # The pakey returned should be the same.
    assert papubkey == pk1

    # Make sure that the error returned is correct when we don't have the
    # the correct public key
    tf = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()

    # if for some reason you can't import the specific exception class,
    # catch it as generic and verify it's in the str(excinfo)
    with pytest.raises(Exception) as excinfo:
        pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                pa_wrapper.bind_web_address,
                                ks.public()).get(timeout=3)
    assert 'AlreadyManagedError' in str(excinfo)

    # check the auth file for a can_manage capability in it.
    auth_json = open(os.path.join(pa_wrapper.volttron_home, "auth.json")).read()
    auth_dict = jsonapi.loads(auth_json)

    found = False
    for k in auth_dict['allow']:
        if k['credentials'].endswith(vc_publickey):
            print('Found vc_publickey')
            capabilities =k.get('capabilities', None)
            assert capabilities
            assert 'can_manage' in capabilities
            found = True
    assert found, "No vc agent ({}) found with can_manage capability.".format(vc_publickey)


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




