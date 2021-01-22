import tempfile

import gevent
import os
import pytest
from gevent import subprocess

from volttron.platform import get_examples
import sys

from volttrontesting.utils.platformwrapper import with_os_environ


@pytest.mark.control
def test_agent_filters(volttron_instance):
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True)
    buuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True)

    # Verify all installed agents show up in list
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(['volttron-ctl', 'list'], env=volttron_instance.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" in str(agent_list)

    # Filter agent based on agent uuid
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(['volttron-ctl', 'list', str(auuid)], env=volttron_instance.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" not in str(agent_list)

    # Filter agent based on agent name
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(['volttron-ctl', 'list', 'listeneragent-3.3_1'], env=volttron_instance.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" not in str(agent_list)

