import tempfile

import gevent
import os
import pytest
from gevent import subprocess

from volttron.platform import get_examples
from volttron.platform.jsonrpc import RemoteError
import sys

@pytest.mark.timeout(600)
@pytest.mark.control
def test_agent_versions(volttron_instance):
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True
    )
    assert auuid is not None

    agent = volttron_instance.dynamic_agent
    version = agent.vip.rpc.call("control", "agent_version", auuid).get(timeout=2)
    assert version == "3.3"

    versions = agent.vip.rpc.call("control", "agent_versions").get(timeout=2)
    assert isinstance(versions, dict)
    assert len(versions) == 1
    k = list(versions.keys())[0]
    versions = versions[k]
    assert versions[0] == "listeneragent-3.3"
    assert versions[1] == "3.3"
    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_identity_is_uuid(volttron_instance):
    """The identity is uuid for an agent that doesn't include a specific
    identity.

    @param volttron_instance:
    @return:
    """
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True
    )
    assert auuid is not None

    agent = volttron_instance.dynamic_agent
    identity = agent.vip.rpc.call("control", "agent_vip_identity", auuid).get(timeout=2)
    assert identity == "listeneragent-3.3_1"
    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_can_get_identity(volttron_instance):
    """Based upon the agent uuid retrieve the IDENTITY.  Use the
    VolttronCentralPlatform as the test agent.

    @param volttron_instance:
    """
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        start=True,
        vip_identity="test_can_get_identity",
    )
    assert auuid is not None

    identity = volttron_instance.dynamic_agent.vip.rpc.call(
        "control", "agent_vip_identity", auuid
    ).get(5)
    assert identity == "test_can_get_identity"
    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_can_get_publickey(volttron_instance):
    """
    Test the control rpc method for retrieving agent publickeys from the
    :class:`ControlService`

    @param volttron_instance:
    """
    listener_identity = "listener_test"
    volttron_instance.is_running()
    message_bus = os.environ.get("MESSAGEBUS", "zmq")

    cn = volttron_instance.dynamic_agent
    id_serverkey_map = cn.vip.rpc.call("control", "get_all_agent_publickeys").get(timeout=5)

    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        start=True,
        vip_identity=listener_identity,
    )
    assert auuid is not None

    id_serverkey_map = cn.vip.rpc.call("control", "get_all_agent_publickeys").get(timeout=5)
    assert listener_identity in id_serverkey_map
    assert id_serverkey_map.get(listener_identity) is not None
    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_prioritize_agent_valid_input(volttron_instance):
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True
    )
    assert auuid is not None

    cn = volttron_instance.dynamic_agent
    assert cn.vip.rpc.call('control', 'prioritize_agent', auuid, '0').get(timeout=2) is None
    assert cn.vip.rpc.call('control', 'prioritize_agent', auuid, '99').get(timeout=2) is None


@pytest.mark.xfail(reason="bytes() calls (control.py:390|398) raise: TypeError('string argument without an encoding').")
@pytest.mark.parametrize('uuid, priority, expected', [
    (34, '50', "expected a string for 'uuid'"),
    ('34/7', '50', 'invalid agent'),
    ('.', '50', 'invalid agent'),
    ('..', '50', 'invalid agent'),
    ('foo', 2, "expected a string or null for 'priority'"),
    ('foo', '-1', 'Priority must be an integer from 0 - 99.'),
    ('foo', '4.5', 'Priority must be an integer from 0 - 99.'),
    ('foo', '100', 'Priority must be an integer from 0 - 99.'),
    ('foo', 'foo', 'Priority must be an integer from 0 - 99.')
])
def test_prioritize_agent_invalid_input(volttron_instance, uuid, priority, expected):
    cn = volttron_instance.dynamic_agent
    with pytest.raises(RemoteError) as e:
        cn.vip.rpc.call('control', 'prioritize_agent', uuid, priority).get(timeout=2)
    assert expected in e.value.message


@pytest.mark.timeout(600)
@pytest.mark.control
def test_recover_from_crash(volttron_instance):
    """
    Test if control agent periodically monitors and restarts any crashed agents
    :param volttron_instance:
    :return:
    """
    volttron_instance.stop_platform()
    volttron_instance.startup_platform(volttron_instance.vip_address, agent_monitor_frequency=20)
    tmpdir = tempfile.mkdtemp()

    os.chdir(tmpdir)
    os.mkdir("crashtest")
    with open(os.path.join("crashtest", "__init__.py"), "w") as file:
        pass
    with open(os.path.join("crashtest", "crashtest.py"), "w") as file:
        file.write(
            """
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
import gevent

class CrashTestAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(CrashTestAgent, self).__init__(**kwargs)

    @Core.receiver('onstart')
    def crash_after_test_seconds(self, sender, **kwargs):
        print("crash test agent on start")
        gevent.sleep(15)
        print("crash test agent quitting")
        sys.exit(5)

def main(argv=sys.argv):
    try:
        utils.vip_main(CrashTestAgent, version='0.1')
    except Exception as e:
        print('unhandled exception: {}'.format(e))

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())

        """
        )
        with open(os.path.join("setup.py"), "w") as file:
            file.write(
                """
from setuptools import setup
setup(
    name='crashtest',
    version='0.1',
    install_requires=['volttron'],
    packages=['crashtest'],
    entry_points={
        'setuptools.installation': [
            'eggsecutable=crashtest.crashtest:main',
        ]
    }
)
    """
            )
    p = subprocess.Popen(
        [sys.executable, "setup.py", "bdist_wheel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    # print("out {}".format(stdout))
    # print("err {}".format(stderr))

    wheel = os.path.join(tmpdir, "dist", "crashtest-0.1-py3-none-any.whl")
    assert os.path.exists(wheel)
    agent_uuid = volttron_instance.install_agent(agent_wheel=wheel)
    assert agent_uuid
    gevent.sleep(1)
    volttron_instance.start_agent(agent_uuid)
    query_agent = volttron_instance.dynamic_agent
    status = query_agent.vip.rpc.call("control", "agent_status", agent_uuid).get(
        timeout=2
    )
    assert status
    crashed = False
    restarted = False
    wait_time = 0
    # wait till it has not crashed and once crashed
    # wait till we detect a restart or 20 seconds.
    # have to do this since the test agent is hardcoded to crash 15
    # seconds after start
    while not crashed or (not restarted and wait_time < 50):
        status = query_agent.vip.rpc.call("control", "agent_status", agent_uuid).get(
            timeout=2
        )
        if crashed and status[0] and status[1] is None:
            restarted = True
        elif status[0] and status[1] == 5:
            crashed = True
        gevent.sleep(1)
        wait_time += 1
    assert crashed and restarted
