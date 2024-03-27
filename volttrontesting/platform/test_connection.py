import gevent
import pytest
from volttron.platform.agent.known_identities import CONTROL, PLATFORM_WEB, AUTH, CONFIGURATION_STORE
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.vip.agent.utils import build_connection
import os


@pytest.fixture(scope="module")
def setup_control_connection(request, volttron_instance):
    """ Creates a single instance of VOLTTRON for testing purposes
    """
    global wrapper, control_connection

    wrapper = volttron_instance

    request.addfinalizer(wrapper.shutdown_platform)

    assert wrapper
    assert wrapper.is_running()

    wrapper.allow_all_connections()
    gevent.sleep(1)

    # Connect using keys
    ks = KeyStore()
    ks.generate()

    control_connection = wrapper.build_connection(identity="foo",
                                                  address=wrapper.vip_address,
                                                  peer=CONTROL,
                                                  serverkey=wrapper.serverkey,
                                                  publickey=ks.public,
                                                  secretkey=ks.secret,
                                                  instance_name=wrapper.instance_name,
                                                  message_bus=wrapper.messagebus)

    # Sleep a couple seconds to wait for things to startup
    gevent.sleep(2)
    return wrapper, control_connection


@pytest.mark.control
def test_can_connect_to_control(setup_control_connection):
    wrapper, connection = setup_control_connection
    assert connection
    assert connection.is_connected(3)


@pytest.mark.control
def test_can_get_peers(setup_control_connection, volttron_instance):
    wrapper, connection = setup_control_connection
    peers = connection.peers()
    assert CONTROL in peers
    if volttron_instance.auth_enabled:
        assert AUTH in peers
    assert CONFIGURATION_STORE in peers


@pytest.mark.control
def test_can_get_serverkey(setup_control_connection):
    wrapper, connection = setup_control_connection
    assert wrapper.serverkey == control_connection.serverkey


@pytest.mark.control
def test_can_call_rpc(setup_control_connection):
    wrapper, connection = setup_control_connection
    assert connection.call('list_agents') == []
