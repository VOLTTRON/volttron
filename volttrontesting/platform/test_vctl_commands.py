from pathlib import Path
import tempfile

import gevent
import os
import pytest
from gevent import subprocess

from volttron.platform import get_examples
import sys

from volttron.platform import jsonapi
from volttron.platform.agent.utils import execute_command
from volttrontesting.utils.platformwrapper import with_os_environ


@pytest.mark.control
def test_install_agent_config_not_empty(volttron_instance):
    listener_agent_dir = get_examples("ListenerAgent")
    listener_agent_config = Path(listener_agent_dir).joinpath("config")
    with with_os_environ(volttron_instance.env):
        cmds = ["vctl", '--json', 'install', listener_agent_dir, '--agent-config',
                listener_agent_config]
        response = execute_command(cmds, volttron_instance.env)

        json_response = jsonapi.loads(response)

        agent_uuid = json_response['agent_uuid']
        config_path = Path(volttron_instance.volttron_home).joinpath(
            f'agents/{agent_uuid}/listeneragent-3.3/listeneragent-3.3.dist-info/config')
        with open(config_path) as fp:
            with open(listener_agent_config) as fp2:
                assert fp2.read() == fp.read()

        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_install_agent_config_empty(volttron_instance):
    listener_agent_dir = get_examples("ListenerAgent")

    with with_os_environ(volttron_instance.env):
        cmds = ["vctl", '--json', 'install', listener_agent_dir]

        response = execute_command(cmds, volttron_instance.env)

        json_response = jsonapi.loads(response)

        agent_uuid = json_response['agent_uuid']
        config_path = Path(volttron_instance.volttron_home).joinpath(
            f'agents/{agent_uuid}/listeneragent-3.3/listeneragent-3.3.dist-info/config')
        with open(config_path) as fp:
            config_data = jsonapi.loads(fp.read())
            assert {} == config_data

        volttron_instance.remove_all_agents()


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

