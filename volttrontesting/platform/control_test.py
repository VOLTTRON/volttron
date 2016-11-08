import os
import pytest


@pytest.mark.control
def test_identity_is_uuid(volttron_instance):
    """ The identity is uuid for an agent that doesn't include a specific
    identity.

    @param volttron_instance:
    @return:
    """
    auuid = volttron_instance.install_agent(
        agent_dir="examples/ListenerAgent", start=True)
    assert auuid is not None

    agent = volttron_instance.build_agent()
    identity = agent.vip.rpc.call('control', 'agent_vip_identity',
                                  auuid).get(timeout=2)
    assert identity == "listeneragent-3.2_1"


@pytest.mark.control
def test_can_get_identity(volttron_instance):
    """ Based upon the agent uuid retrieve the IDENTITY.  Use the
    VolttronCentralPlatform as the test agent.

    @param volttron_instance:
    """
    auuid = volttron_instance.install_agent(
        agent_dir="examples/ListenerAgent", start=True,
        vip_identity="test_can_get_identity")
    assert auuid is not None

    cn = volttron_instance.build_connection(peer='control')
    identity = cn.call('agent_vip_identity', auuid)
    assert identity == 'test_can_get_identity'


@pytest.mark.control
def test_can_get_publickey(volttron_instance):
    """
    Test the control rpc method for retrieving agent publickeys from the
    :class:`ControlService`

    @param volttron_instance:
    """
    if not volttron_instance.encrypt:
        pytest.skip("Keys aren't used in developer-mode")

    listener_identity = "listener_test"
    volttron_instance.is_running()

    cn = volttron_instance.build_connection(peer='control')
    assert cn.is_peer_connected()
    id_serverkey_map = cn.call('get_all_agent_publickeys')
    assert id_serverkey_map == {}

    auuid = volttron_instance.install_agent(
        agent_dir="examples/ListenerAgent", start=True,
        vip_identity=listener_identity)
    assert auuid is not None

    id_serverkey_map = cn.call('get_all_agent_publickeys')
    assert len(id_serverkey_map) == 1
    assert listener_identity in id_serverkey_map
    assert id_serverkey_map.get(listener_identity) is not None
