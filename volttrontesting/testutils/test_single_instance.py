import pytest

from volttrontesting.utils.core_service_installs import add_volttron_central


@pytest.mark.wrapper
def test_can_install_listener(get_volttron_instances):
    wrapper = get_volttron_instances(1)

    agent_uuid = wrapper.install_agent(agent_dir="examples/ListenerAgent",
                                       config_file={"agentid": "listener",
                                                    "message": "So Happpy"})
    assert wrapper.is_agent_running(agent_uuid)


@pytest.mark.wrapper
def test_can_add_vc_to_instance(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    if get_volttron_instances.param != 'encrypted':
        pytest.skip('Only available with encryption.')

    agent_count = len(wrapper.list_agents())
    vc_uuid = add_volttron_central(wrapper)
    assert vc_uuid
    assert agent_count+1 == len(wrapper.list_agents())
    assert wrapper.is_agent_running(vc_uuid)


@pytest.mark.wrapper
def test_can_connect_to_instance(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    assert wrapper is not None
    assert wrapper.is_running()
    assert not wrapper.list_agents()
    message = 'Pinging Hello'
    agent = wrapper.build_agent()
    response = agent.vip.ping('', message).get(timeout=3)
    agent.core.stop()
    assert response[0] == message
