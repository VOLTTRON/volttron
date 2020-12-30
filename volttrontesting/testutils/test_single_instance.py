import pytest
import gevent

from volttron.platform import get_examples


@pytest.mark.wrapper
def test_can_install_listeners(volttron_instance):
    assert volttron_instance.is_running()
    uuids = []
    num_listeners = 5

    try:
        for x in range(num_listeners):
            identity = "listener_" + str(x)
            auuid = volttron_instance.install_agent(
                agent_dir=get_examples("ListenerAgent"), config_file={
                    "agentid": identity,
                    "message": "So Happpy"})
            assert auuid
            uuids.append(auuid)
            gevent.sleep(4)

        for u in uuids:
            assert volttron_instance.is_agent_running(u)

        agent = volttron_instance.build_agent()
        agent_list = agent.vip.rpc('control', 'list_agents').get(timeout=5)
        print('Agent List: {}'.format(agent_list))
        assert len(agent_list) == num_listeners
    finally:
        for x in uuids:
            try:
                volttron_instance.remove_agent(x)
            except:
                print('COULDN"T REMOVE AGENT')
