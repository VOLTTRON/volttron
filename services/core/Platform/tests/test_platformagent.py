import pytest

@pytest.fixture
def platform_uuid(volttron_instance_1):
    import os
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
        os.path.pardir))
    print('AGENT DIR', agent_dir)
    config = os.path.join(agent_dir, "config")
    return volttron_instance_1.build_agentpackage(agent_dir, config)
    #return volttron_instance_1.direct_build_install_run_agent(agent_dir, config)


def test_platform_running(volttron_instance_1, platform_uuid):
    assert platform_uuid is not None
    assert volttron_instance_1.is_running()
    print("THE PLATFORM UUID IS: ", platform_uuid)
