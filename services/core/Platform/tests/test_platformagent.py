import os

import logging
import pytest
import gevent
from volttron.platform.keystore import KeyStore
from volttron.platform.auth import AuthFile, AuthEntry
# The default platform identity
PLATFORM_ID = 'platform.agent'

PLATFORM_AGENT_CONFIG = {
    # Agent id is used in the display on volttron central.
    "agentid": "Platform Agent",

    # Set the Platform agents identity
    #
    # Default "identity": "platform.agent"
    "identity": PLATFORM_ID,

    # Configuration parameters.
    #
    # The period of time to go between attempting to report status to the
    # platform.historian.
    #
    # Default "report_status_period": 30
    "report_status_period": 15
}

#wk2BXQdHkAlMIoXthOPhFOqWpapD1eWsBQYY7h4-bXw", "domain": "vip", "address": "/192\\.168\\.1\\..*/"}
INITIAL_AUTH_DICT = {
    "allow": [
        {"credentials": "CURVE:.*"}
    ]
}

_log = logging.getLogger(__name__)


@pytest.fixture
def platform_uuid(volttron_instance1_web):
    """ Installs the platform agent and returns the uuuid of the agent.

    :param volttron_instance1:
    :return:
    """

    agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
        os.path.pardir))

    return volttron_instance1_web.install_agent(agent_dir=agent_dir,
                                            config_file=PLATFORM_AGENT_CONFIG)


# def test_platform_running(volttron_instance1, platform_uuid):
#     assert platform_uuid is not None
#     assert volttron_instance1.is_running()

@pytest.mark.vc
def test_registration_creation(volttron_instance1_web, platform_uuid):
    """ Test the ability for a platform to be registered from an entity.

    :param volttron_instance1_encrypt:
    :param platform_uuid:
    :return: The public key for the agent (currently the platform key)
    """

    vi1 = volttron_instance1_web
    vi1.set_auth_dict(INITIAL_AUTH_DICT)
    print("addresses are: ", vi1.vip_address)
    # authfile = AuthFile(os.path.join(vi1.volttron_home, "auth.json"))
    # ae = AuthEntry(credentials=".*")
    # with open(os.path.join(vi1.volttron_home, "auth.json")) as fin:
    #     print(fin.read())
    # authfile.add(ae)
    # gevent.sleep(2)
    # authfile= AuthFile(os.path.join(vi1.volttron_home, "auth.json"))
    # gevent.sleep(.2)
    # print("AUTHS ARE:",authfile.read())

    #print("AUTHS ARE:",authfile.read())
    # authfile.
    # vi1.set_auth_dict(INITIAL_AUTH_DICT)
    # gevent.sleep(.5)

    ks = KeyStore(os.path.join(vi1.volttron_home, 'keystore'))
    ks.generate()

    print("SECRET:",ks.secret())
    print("PUBLIC:",ks.public())
    print("SERVER:",vi1.publickey)

    # This agent will act as a volttron central agent for the purposes
    # of this test.
    vc_agent = vi1.build_agent(#identity="volttron.central",
                                serverkey=vi1.publickey,
                                secretkey=ks.secret(), publickey=ks.public())
    print(vc_agent.vip.hello().get(timeout=.3))
    print(vc_agent.core.identity)

    # Expected to return the platform.agent public key.
    pk = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                vi1.bind_web_address,
                                vi1.publickey).get(timeout=3)
    assert pk

    # Test that once it's registered a new call to manage_platform will
    # return the same result.
    pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                vi1.bind_web_address,
                                vi1.publickey).get(timeout=3)
    assert pk == pk1

    # Make sure that the error returned is correct when we don't have the
    # the correct public key
    ks = KeyStore('test.keystore')
    ks.generate()

    # if for some reason you can't import the specific exception class,
    # catch it as generic and verify it's in the str(excinfo)
    with pytest.raises(Exception) as excinfo:
        pk1 = vc_agent.vip.rpc.call(PLATFORM_ID, "manage_platform",
                                vi1.bind_web_address,
                                ks.public()).get(timeout=3)
    assert 'AlreadyManagedError' in str(excinfo)

    # check the auth file for a can_manage capability in it.
    auth_json = open(os.path.join(vi1.volttron_home, "auth.json")).read()
    assert "can_manage" in auth_json


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




