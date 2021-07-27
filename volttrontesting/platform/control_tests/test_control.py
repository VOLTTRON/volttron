import tempfile

import gevent
import os
import pytest
from gevent import subprocess

from volttron.platform import get_examples
import sys


@pytest.mark.control
def test_agent_versions(volttron_instance):
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True)
    assert auuid is not None

    agent = volttron_instance.dynamic_agent
    version = agent.vip.rpc.call('control', 'agent_version',
                                  auuid).get(timeout=2)
    assert version == "3.3"

    versions = agent.vip.rpc.call('control', 'agent_versions').get(timeout=2)
    assert isinstance(versions, dict)
    assert len(versions) == 1
    k = list(versions.keys())[0]
    versions = versions[k]
    assert versions[0] == 'listeneragent-3.3'
    assert versions[1] == '3.3'
    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_identity_is_uuid(volttron_instance):
    """ The identity is uuid for an agent that doesn't include a specific
    identity.

    @param volttron_instance:
    @return:
    """
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True)
    assert auuid is not None

    agent = volttron_instance.dynamic_agent
    identity = agent.vip.rpc.call('control', 'agent_vip_identity',
                                  auuid).get(timeout=2)
    assert identity == "listeneragent-3.3_1"
    volttron_instance.remove_all_agents()

@pytest.mark.control
def test_can_get_identity(volttron_instance):
    """ Based upon the agent uuid retrieve the IDENTITY.  Use the
    VolttronCentralPlatform as the test agent.

    @param volttron_instance:
    """
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True,
        vip_identity="test_can_get_identity")
    assert auuid is not None

    cn = volttron_instance.build_connection(peer='control')
    identity = cn.call('agent_vip_identity', auuid)
    assert identity == 'test_can_get_identity'
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
    message_bus = os.environ.get('MESSAGEBUS', 'zmq')

    cn = volttron_instance.build_connection(peer='control')
    assert cn.is_peer_connected()
    id_serverkey_map = cn.call('get_all_agent_publickeys')

    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True,
        vip_identity=listener_identity)
    assert auuid is not None

    id_serverkey_map = cn.call('get_all_agent_publickeys')
    assert listener_identity in id_serverkey_map
    assert id_serverkey_map.get(listener_identity) is not None


@pytest.mark.control
def test_recover_from_crash(get_volttron_instances):
    """
    Test if control agent periodically monitors and restarts any crashed agents
    :param volttron_instance:
    :return:
    """

    volttron_instance = get_volttron_instances(1, True,
                                               agent_monitor_frequency=10)
    tmpdir = tempfile.mkdtemp()

    os.chdir(tmpdir)
    os.mkdir('crashtest')
    with open(os.path.join('crashtest', '__init__.py'), 'w') as file:
        pass
    with open(os.path.join('crashtest', 'crashtest.py'), 'w') as file:
        file.write('''
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
import gevent

class CrashTestAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(CrashTestAgent, self).__init__(**kwargs)

    @Core.receiver('onstart')
    def crash_after_five_seconds(self, sender, **kwargs):
        print("crash test agent on start")
        gevent.sleep(5)
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

        ''')
        with open(os.path.join('setup.py'), 'w') as file:
            file.write('''
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
    ''')
    p = subprocess.Popen([sys.executable, 'setup.py', 'bdist_wheel'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    # print("out {}".format(stdout))
    # print("err {}".format(stderr))

    wheel = os.path.join(tmpdir, 'dist', 'crashtest-0.1-py3-none-any.whl')
    assert os.path.exists(wheel)
    agent_uuid = volttron_instance.install_agent(agent_wheel=wheel,
                                                 start=True)
    assert agent_uuid
    query_agent = volttron_instance.dynamic_agent
    status = query_agent.vip.rpc.call('control', 'agent_status',
                                      agent_uuid).get(timeout=2)
    assert status
    crashed = False
    restarted = False
    wait_time = 0
    # wait till it has not crashed and once crashed
    # wait till we detect a restart or 20 seconds.
    # have to do this since the test agent is hardcoded to crash 5
    # seconds after start
    while not crashed or (not restarted and wait_time < 30):
        status = query_agent.vip.rpc.call('control', 'agent_status',
                                          agent_uuid).get(timeout=2)
        if crashed and status[0] and status[1] is None:
            restarted = True
        elif status[0] and status[1] == 5:
            crashed = True
        gevent.sleep(1)
        wait_time += 1
    assert crashed and restarted



