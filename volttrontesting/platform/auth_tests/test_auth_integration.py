import os
import subprocess
import sys
import tempfile
import gevent
import pytest
from volttron.platform.agent.known_identities import AUTH
from volttron.platform import jsonrpc
from volttron.platform.messaging.health import STATUS_BAD

called_agent_src = """
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.vip.agent.subsystems import RPC
import gevent
class CalledAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(CalledAgent, self).__init__(**kwargs)
    @RPC.export
    @RPC.allow("can_call_method")
    def restricted_method(self, sender, **kwargs):
        print("test")
def main(argv=sys.argv):
    try:
        utils.vip_main(CalledAgent, version='0.1')
    except Exception as e:
        print('unhandled exception: {}'.format(e))
if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
"""

called_agent_setup = """
from setuptools import setup
setup(
    name='calledagent',
    version='0.1',
    install_requires=['volttron'],
    packages=['calledagent'],
    entry_points={
        'setuptools.installation': [
            'eggsecutable=calledagent.calledagent:main',
        ]
    }
)
"""

caller_agent_src = """
import sys
import gevent
import logging
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.vip.agent.subsystems import RPC
from volttron.platform.scheduling import periodic
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD, Status)
from volttron.platform.agent.known_identities import AUTH
from volttron.platform import jsonrpc
from volttron.platform.messaging.health import STATUS_BAD

_log = logging.getLogger(__name__)
class CallerAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(CallerAgent, self).__init__(**kwargs)
    
    # @Core.schedule(periodic(3))
    # def call_rpc_method(self):
    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        try:
            self.vip.rpc.call('called_agent', 'restricted_method').get(timeout=3)
        except Exception as e:
            self.vip.health.set_status(STATUS_BAD, f"{e}")
def main(argv=sys.argv):
    try:
        utils.vip_main(CallerAgent, version='0.1')
    except Exception as e:
        print('unhandled exception: {}'.format(e))
if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
"""
      
caller_agent_setup = """
from setuptools import setup
setup(
    name='calleragent',
    version='0.1',
    install_requires=['volttron'],
    packages=['calleragent'],
    entry_points={
        'setuptools.installation': [
            'eggsecutable=calleragent.calleragent:main',
        ]
    }
)
"""  

@pytest.fixture
def install_two_agents(volttron_instance):
    """Returns two agents for testing authorization

    The first agent is the "RPC callee."
    The second agent is the unauthorized "RPC caller."
    """
    """
    Test if control agent periodically monitors and restarts any crashed agents
    :param volttron_instance:
    :return:
    """
    
    tmpdir = volttron_instance.volttron_home+"/tmpdir"
    os.mkdir(tmpdir)
    tmpdir = volttron_instance.volttron_home+"/tmpdir" + "/called"
    os.mkdir(tmpdir)
    os.chdir(tmpdir)
    
    os.mkdir("calledagent")
    with open(os.path.join("calledagent", "__init__.py"), "w") as file:
        pass
    with open(os.path.join("calledagent", "calledagent.py"), "w") as file:
        file.write(called_agent_src)
        with open(os.path.join("setup.py"), "w") as file:
            file.write(called_agent_setup)
    p = subprocess.Popen(
        [sys.executable, "setup.py", "bdist_wheel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    # print("out {}".format(stdout))
    # print("err {}".format(stderr))

    wheel = os.path.join(tmpdir, "dist", "calledagent-0.1-py3-none-any.whl")
    assert os.path.exists(wheel)
    called_uuid = volttron_instance.install_agent(agent_wheel=wheel, 
                                                 vip_identity="called_agent",
                                                 start=False)
    assert called_uuid
    gevent.sleep(1)
    
    
    tmpdir = volttron_instance.volttron_home+"/tmpdir" + "/caller"
    os.mkdir(tmpdir)
    os.chdir(tmpdir)
    os.mkdir("calleragent")
    with open(os.path.join("calleragent", "__init__.py"), "w") as file:
        pass
    with open(os.path.join("calleragent", "calleragent.py"), "w") as file:
        file.write(caller_agent_src)
        with open(os.path.join("setup.py"), "w") as file:
            file.write(caller_agent_setup)
    p = subprocess.Popen(
        [sys.executable, "setup.py", "bdist_wheel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    # print("out {}".format(stdout))
    # print("err {}".format(stderr))

    wheel = os.path.join(tmpdir, "dist", "calleragent-0.1-py3-none-any.whl")
    assert os.path.exists(wheel)
    caller_uuid = volttron_instance.install_agent(agent_wheel=wheel, 
                                                 vip_identity="caller_agent",
                                                 start=False)
    assert caller_uuid
    gevent.sleep(1)

    try:
        yield caller_uuid, called_uuid
    finally:
        #volttron_instance.remove_agent(caller_uuid)
        #volttron_instance.remove_agent(called_uuid)
        # TODO if we have to wait for auth propagation anyways why do we create new agents for each test case
        #  we should just update capabilities, at least we will save on agent creation and tear down time
        gevent.sleep(1)


@pytest.fixture(autouse=True)
def build_volttron_instance(volttron_instance):
    if not volttron_instance.auth_enabled:
        pytest.skip("AUTH tests are not applicable if auth is disabled")


@pytest.mark.auth
def test_unauthorized_rpc_call(volttron_instance, install_two_agents):
    """Tests an agent with no capabilities calling a method that
    requires one capability ("can_call_foo")
    """
    (caller_agent_uuid, called_agent_uuid) = install_two_agents
    
    # check auth error for newly installed agents
    check_auth_error(volttron_instance, caller_agent_uuid, called_agent_uuid)
    
    volttron_instance.restart_platform()
    gevent.sleep(3)
    
    # check auth error for already installed agent
    check_auth_error(volttron_instance, caller_agent_uuid, called_agent_uuid)

def check_auth_error(volttron_instance, caller_agent_uuid, called_agent_uuid):
    
    expected_auth_err = ('volttron.platform.jsonrpc.Error('
    '-32001, "method \'restricted_method\' '  
    'requires capabilities {\'can_call_method\'}, ' 
    'but capability {\'edit_config_store\': {\'identity\': \'caller_agent\'}}' 
    ' was provided for user caller_agent")')
    volttron_instance.start_agent(called_agent_uuid)
    gevent.sleep(1)
    volttron_instance.start_agent(caller_agent_uuid)
    
    # If the agent is not authorized health status is updated
    health =  volttron_instance.dynamic_agent.vip.rpc.call(
        "caller_agent", "health.get_status").get(timeout=2)
    
    assert health.get('status') == STATUS_BAD
    assert health.get('context') == expected_auth_err
    
    
        

