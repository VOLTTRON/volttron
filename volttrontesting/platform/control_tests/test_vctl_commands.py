from pathlib import Path
import tempfile
from typing import List

import gevent
import os
import pytest
from gevent import subprocess
import yaml

from volttron.platform import get_examples
import sys

from volttron.platform import jsonapi
from volttron.platform.agent.utils import execute_command
from volttrontesting.utils.platformwrapper import with_os_environ, PlatformWrapper


@pytest.mark.control
def test_install_same_identity(volttron_instance: PlatformWrapper):
    listener_agent_dir = get_examples("ListenerAgent")

    with with_os_environ(volttron_instance.env):
        expected_identity = "listener.1"
        args = ["volttron-ctl", "--json", "install", listener_agent_dir, "--vip-identity", 
                expected_identity, "--start"]
                
        response = execute_command(args, volttron_instance.env)
        json_response = jsonapi.loads(response)
        agent_uuid = json_response['agent_uuid']
        
        response = execute_command(["vctl", "--json", "status", agent_uuid])
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        assert 'running [' in  agent_status_dict.get('status')

        expected_status = agent_status_dict.get('status')
        expected_auuid = agent_status_dict.get('agent_uuid')
        
        # Attempt to install without force.
        with pytest.raises(RuntimeError):
            execute_command(args, volttron_instance.env)
        
        # Nothing should have changed the pid should be the same
        response = execute_command(["vctl", "--json", "status", agent_uuid])
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]
        assert expected_status == agent_status_dict.get('status')
        assert expected_auuid == agent_status_dict.get('agent_uuid')

        args = ["volttron-ctl", "--json", "install", listener_agent_dir, "--vip-identity", 
                expected_identity, "--start", "--force"]

        # Install with force.
        response = execute_command(args, volttron_instance.env)
        json_response = jsonapi.loads(response)
        agent_uuid = json_response['agent_uuid']
        
        response = execute_command(["vctl", "--json", "status", agent_uuid])
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        assert 'running [' in agent_status_dict.get('status')
        assert expected_status != agent_status_dict.get('status')
        assert expected_auuid != agent_status_dict.get('agent_uuid')


@pytest.mark.control
def test_install_with_wheel(volttron_instance:PlatformWrapper):

    with with_os_environ(volttron_instance.env):
        listener_path = "examples/ListenerAgent"

        args = ["volttron-pkg", "package", listener_path]
        response = execute_command(args, volttron_instance.env)
        assert response.startswith("Package created at: ")
        path = response[len("Package created at: "):]
        assert os.path.exists(path.strip())
        args = ["volttron-ctl", "--json", "install", path.strip()]
        response = execute_command(args)
        response_dict = jsonapi.loads(response)
        assert response_dict.get('agent_uuid')
        volttron_instance.remove_all_agents()



@pytest.mark.control
def test_install_with_wheel_bad_path(volttron_instance:PlatformWrapper):

    with with_os_environ(volttron_instance.env):
        bad_wheel_path = "foo/wheel.whl"
        args = ["volttron-ctl", "--json", "install", bad_wheel_path]
        try:
            response = execute_command(args)
        except RuntimeError as exc:          
            assert f'Invalid file {bad_wheel_path}' in exc.args[0]
        

@pytest.mark.control
@pytest.mark.parametrize(
    "use_config,args", (
        (True, ["install", "examples/ListenerAgent", "--tag", "brewster", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent", "--tag", "brewster", "--start", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent", "--tag", "brewster", "--start", "--priority", "20"]),
        (True, ["install", "examples/ListenerAgent", "--tag", "brewster", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent", "--tag", "hoppy", "--start", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent", "--tag", "brewster", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent"]),

        (False, ["install", "examples/ListenerAgent", "--tag", "brewster", "--start", "--priority", "1"]),
        (False, ["install", "examples/ListenerAgent", "--tag", "brewster", "--start", "--priority", "20"]),
        (False, ["install", "examples/ListenerAgent", "--tag", "brewster", "--priority", "1"]),
        (False, ["install", "examples/ListenerAgent", "--tag", "hoppy", "--start", "--priority", "1"]),
        (True, ["install", "examples/ListenerAgent"]),
        (True, ["install", "examples/ListenerAgent", "--vip-identity", "ralph"])
    )
)
def test_install_arg_matrix(volttron_instance:PlatformWrapper, args: List, use_config: bool):
    
    listener_config_file = get_examples("ListenerAgent/config")

    with with_os_environ(volttron_instance.env):

        args.insert(0, "--json")
        args.insert(0, "volttron-ctl")

        if use_config:
            args.extend(["--agent-config", listener_config_file])
        
        response = execute_command(args, volttron_instance.env)

        json_response = jsonapi.loads(response)

        agent_uuid = json_response['agent_uuid']
        gevent.sleep(1)

        response = execute_command(["vctl", "--json", "status", agent_uuid])
        json_response = jsonapi.loads(response)

        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        if "--start" in args:
            assert agent_status_dict["status"]

        if "--tag" in args:
            assert agent_status_dict["agent_tag"]
            tag_name = args[args.index("--tag")+1]
            assert tag_name == agent_status_dict["agent_tag"]

        if "--vip-identity" in args:
            assert agent_status_dict["identity"]
            expected_identity = args[args.index("--vip-identity")+1]
            assert expected_identity == agent_status_dict["identity"]
        
        if use_config:
            with open(listener_config_file) as fp:
                expected_config = yaml.safe_load(fp.read())
            config_path = Path(volttron_instance.volttron_home).joinpath(
                f'agents/{agent_uuid}/listeneragent-3.3/listeneragent-3.3.dist-info/config')
            with open(config_path) as fp:
                config_data = yaml.safe_load(fp.read())
                assert expected_config == config_data

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

