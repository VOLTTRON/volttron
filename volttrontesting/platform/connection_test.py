import gevent
from volttron.platform.agent.known_identities import CONTROL, MASTER_WEB, AUTH
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.connection import Connection

import pytest


@pytest.fixture(scope="module")
def setup_control_connection(request, get_volttron_instances):
    """ Creates a single instance of VOLTTRON for testing purposes
    """
    global wrapper, control_connection

    wrapper = get_volttron_instances(1)

    request.addfinalizer(wrapper.shutdown_platform)

    assert wrapper
    assert wrapper.is_running()

    if get_volttron_instances.param == 'encrypted':
        if wrapper.encrypt:
            wrapper.allow_all_connections()
        # Connect using keys
        ks = KeyStore()
        ks.generate()

        control_connection = Connection(address=wrapper.vip_address,
                                        peer=CONTROL,
                                        serverkey=wrapper.serverkey,
                                        publickey=ks.public(),
                                        secretkey=ks.secret())
    else:
        control_connection = Connection(address=wrapper.local_vip_address,
                                        peer=CONTROL, developer_mode=True)
    # Sleep a couple seconds to wait for things to startup
    gevent.sleep(2)
    return wrapper, control_connection


@pytest.mark.control
def test_can_connect_to_control(setup_control_connection):
    wrapper, connection = setup_control_connection
    assert connection
    assert connection.is_connected(3)


@pytest.mark.control
def test_can_get_peers(setup_control_connection):
    wrapper, connection = setup_control_connection
    peers = connection.peers()
    assert MASTER_WEB in peers
    # assert CONTROL in peers
    assert AUTH in peers


@pytest.mark.control
def test_can_get_serverkey(setup_control_connection):
    wrapper, connection = setup_control_connection

    if wrapper.encrypt:
        assert wrapper.serverkey == control_connection.serverkey
    else:
        assert control_connection.serverkey is None


@pytest.mark.control
def test_can_call_rpc(setup_control_connection):
    wrapper, connection = setup_control_connection
    assert connection.call('list_agents') == []
