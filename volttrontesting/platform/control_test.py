import pytest


@pytest.mark.control
def test_identity_is_uuid(volttron_instance1):
    """ The identity is uuid for an agent that doesn't include a specific
    identity.

    @param volttron_instance1:
    @return:
    """
    auuid = volttron_instance1.install_agent(
        agent_dir="examples/ListenerAgent", start=True)
    assert auuid is not None

    agent = volttron_instance1.build_agent()
    identity = agent.vip.rpc.call('control', 'agent_vip_identity',
                                  auuid).get(timeout=2)
    assert identity == auuid


@pytest.mark.control
def test_can_get_identity(volttron_instance1):
    """ Based upon the agent uuid retrieve the IDENTITY.  Use the
    VolttronCentralPlatform as the test agent.

    @param volttron_instance1:
    @return:
    """
    auuid = volttron_instance1.install_agent(
        agent_dir="services/core/VolttronCentralPlatform", start=True)
    assert auuid is not None

    agent = volttron_instance1.build_agent()
    identity = agent.vip.rpc.call('control', 'agent_vip_identity',
                                  auuid).get(timeout=2)
    assert identity == 'platform.agent'
