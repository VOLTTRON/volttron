import pytest


@pytest.fixture(scope="module")
def single_instance(request, get_volttron_instances):
    wrapper = get_volttron_instances(1, True)
    request.addfinalizer(wrapper.shutdown_platform)
    return wrapper


@pytest.mark.wrapper
def test_can_install_listeners(single_instance):
    assert single_instance.is_running()
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
    try:
        for x in range(num_listeners):
            auuid = single_instance.install_agent(
                agent_dir="examples/ListenerAgent", config_file={
                    "agentid": "listener",
                    "message": "So Happpy"})
            assert auuid
            uuids.append(auuid)

        for u in uuids:
            assert single_instance.is_agent_running(u)

        agent = single_instance.build_agent()
        agent_list = agent.vip.rpc('control', 'list_agents').get(timeout=5)
        print('Agent List: {}'.format(agent_list))
        assert len(agent_list) == num_listeners
    finally:
        for x in uuids:
            try:
                single_instance.remove_agent(x)
            except:
                print('COULDN"T REMOVE AGENT')
