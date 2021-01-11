import pytest

from volttron.platform import get_examples


@pytest.mark.wrapper
def test_can_install_listeners_on_different_instances(get_volttron_instances):

    num_instances = 3
    wrappers = get_volttron_instances(num_instances, True)

    wrapper_uuid = []
    assert num_instances == len(wrappers)
    for w in wrappers:
        assert w.is_running()
        auuid = w.install_agent(
            agent_dir=get_examples("ListenerAgent"), config_file={"message": "So Happpy"},
            start=True
        )
        assert auuid
        assert w.is_agent_running(auuid)
        wrapper_uuid.append((w, auuid))

    # Make sure that the installed agents are for different instances
    for w, aid in wrapper_uuid:
        for w1, aid1 in wrapper_uuid:
            if id(w1) == id(w):
                assert w1.is_agent_running(aid)
            else:
                # Note using w to compare the installed agent on w to the agent installed on w1
                with pytest.raises(FileNotFoundError):
                    w.get_agent_identity(aid1)
