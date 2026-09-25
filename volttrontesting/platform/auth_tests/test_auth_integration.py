import logging
import os
import subprocess
import sys
import tempfile
import gevent
import pytest
from volttron.platform.agent.known_identities import AUTH
from volttron.platform import jsonrpc
from volttron.platform.messaging.health import STATUS_BAD

_log = logging.getLogger(__name__)

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
    
    # installed_uuids tracks what actually got installed so far, so the
    # finally block can remove it even when a later step in this fixture
    # (the second install, or anything between the two) fails before the
    # try ever reaches yield (#3261 fix round 2).
    installed_uuids = []
    try:
        # CI reruns a failing test against this same fixture and
        # volttron_home (see #3261), so directory creation here must
        # tolerate a path that already exists from the first attempt.
        tmpdir = volttron_instance.volttron_home+"/tmpdir"
        os.makedirs(tmpdir, exist_ok=True)
        tmpdir = volttron_instance.volttron_home+"/tmpdir" + "/called"
        os.makedirs(tmpdir, exist_ok=True)
        os.chdir(tmpdir)

        os.makedirs("calledagent", exist_ok=True)
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
        installed_uuids.append(called_uuid)
        gevent.sleep(1)


        tmpdir = volttron_instance.volttron_home+"/tmpdir" + "/caller"
        os.makedirs(tmpdir, exist_ok=True)
        os.chdir(tmpdir)
        os.makedirs("calleragent", exist_ok=True)
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
        installed_uuids.append(caller_uuid)
        gevent.sleep(1)

        # Fixed VIP identities (called_agent, caller_agent): a rerun of a
        # failing test reinstalls onto the same platform instance and needs
        # the prior install gone first, or it errors on "Identity already
        # exists" (#3261).
        yield caller_uuid, called_uuid
    finally:
        # Remove whatever got installed, even if a later step failed before
        # yielding (#3261 fix round 2). Attempt every removal regardless of
        # an earlier one raising, and never let a removal error replace the
        # test's own failure/error: log it instead of swallowing it or
        # letting it propagate from finally (#3261 fix round 1).
        for uuid in installed_uuids:
            try:
                volttron_instance.remove_agent(uuid)
            except Exception:
                _log.exception("Failed to remove agent %s during teardown", uuid)
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

    volttron_instance.start_agent(called_agent_uuid)
    gevent.sleep(1)
    volttron_instance.start_agent(caller_agent_uuid)

    # If the agent is not authorized health status is updated
    health =  volttron_instance.dynamic_agent.vip.rpc.call(
        "caller_agent", "health.get_status").get(timeout=2)

    assert health.get('status') == STATUS_BAD
    # The granted capability set (volttron/platform/aip.py,
    # _authorize_agent_keys) is not part of what this test proves, and it
    # has grown before (#3260). Assert the refusal itself: the JSON-RPC
    # unauthorized code, the required capability, the method, and the
    # caller identity, not the full rendered capability dict.
    context = health.get('context')
    assert context is not None
    assert str(jsonrpc.UNAUTHORIZED) in context
    assert "method 'restricted_method' requires capabilities {'can_call_method'}, but capability " in context
    assert context.endswith('was provided for user caller_agent")')
    
    
        

