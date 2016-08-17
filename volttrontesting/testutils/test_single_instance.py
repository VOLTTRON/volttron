import gevent
import pytest

from volttrontesting.utils.core_service_installs import add_volttron_central


@pytest.mark.wrapper
def test_can_install_listeners(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    assert wrapper.is_running()
    uuids = []
    num_listeners = 5

    # TODO Modify so that this is allowable
    jobs = []

    # for x in range(num_listeners):
    #     jobs.append(
    #         gevent.spawn(wrapper.install_agent,
    #                      agent_dir="examples/ListenerAgent",
    #                      config_file={"agentid": "listener",
    #                                   "message": "So Happpy"}))
    #
    # gevent.joinall(jobs, timeout=20)

    for x in range(num_listeners):
        auuid = wrapper.install_agent(agent_dir="examples/ListenerAgent",
                                      config_file={"agentid": "listener",
                                                   "message": "So Happpy"})
        assert auuid
        uuids.append(auuid)

    for u in uuids:
        assert wrapper.is_agent_running(u)

    agent = wrapper.build_agent()
    agent_list = agent.vip.rpc('control', 'list_agents').get(timeout=5)
    print('Agent List: {}'.format(agent_list))
    assert len(agent_list) == num_listeners


@pytest.mark.wrapper
def test_can_install_listener(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    print('WRAPPER IS: {}'.format(wrapper))
    assert wrapper.is_running()
    agent_uuid = wrapper.install_agent(agent_dir="examples/ListenerAgent",
                                       config_file={"agentid": "listener",
                                                    "message": "So Happpy"})
    assert wrapper.is_agent_running(agent_uuid)


@pytest.mark.wrapper
def test_can_add_vc_to_instance(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    print('WRAPPER IS: {}'.format(wrapper))
    if get_volttron_instances.param != 'encrypted':
        pytest.skip('Only available with encryption.')
    assert wrapper.is_running()
    agent_count = len(wrapper.list_agents())
    vc_uuid = add_volttron_central(wrapper)
    assert vc_uuid
    assert agent_count+1 == len(wrapper.list_agents())
    assert wrapper.is_agent_running(vc_uuid)


@pytest.mark.wrapper
def test_can_connect_to_instance(get_volttron_instances):
    wrapper = get_volttron_instances(1)
    print('WRAPPER IS: {}'.format(wrapper))
    assert wrapper is not None
    assert wrapper.is_running()
    assert not wrapper.list_agents()
    message = 'Pinging Hello'
    agent = wrapper.build_agent()
    response = agent.vip.ping('', message).get(timeout=3)
    agent.core.stop()
    assert response[0] == message
