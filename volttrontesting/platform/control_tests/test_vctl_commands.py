import copy
from pathlib import Path
from typing import List
import os

import gevent
import pytest
from gevent import subprocess
import yaml

from volttron.platform import get_examples
from volttron.platform import jsonapi
from volttron.platform.agent.utils import execute_command
from volttrontesting.utils.platformwrapper import with_os_environ, PlatformWrapper, create_volttron_home

listener_agent_dir = get_examples("ListenerAgent")


@pytest.mark.control
def test_needs_connection():
    # Test command that needs instance running
    p = subprocess.Popen(
        ["volttron-ctl", "peerlist"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    try:
        assert "VOLTTRON is not running. This command requires VOLTTRON platform to be running" in stderr.decode("utf-8")
    except AssertionError:
        assert not stderr.decode("utf-8")

@pytest.mark.timeout(600)
@pytest.mark.control
def test_needs_connection_with_connection(volttron_instance: PlatformWrapper):
    # Verify peerlist command works when instance is running
    p = subprocess.Popen(
        ["volttron-ctl", "peerlist"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    try:
        assert "VOLTTRON is not running." in stderr.decode("utf-8")
    except AssertionError:
        assert not stderr.decode("utf-8")


@pytest.mark.control
def test_no_connection(volttron_instance: PlatformWrapper):
    # Test command that doesn't need instance running.
    wrapper = PlatformWrapper(ssl_auth=False,
                              auth_enabled=False
                              )
    p = subprocess.Popen(
        ["volttron-ctl", "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=wrapper.env
    )
    stdout, stderr = p.communicate()
    try:
        assert "No installed Agents found" in stderr.decode("utf-8")
    except AssertionError:
        assert not stderr.decode("utf-8")


@pytest.mark.control
def test_install_same_identity(volttron_instance: PlatformWrapper):
    global listener_agent_dir
    with with_os_environ(volttron_instance.env):
        expected_identity = "listener.1"
        args = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            expected_identity,
            "--start",
        ]
        response = execute_command(args, volttron_instance.env)
        json_response = jsonapi.loads(response)
        agent_uuid = json_response["agent_uuid"]
        response = execute_command(
            ["vctl", "--json", "status", agent_uuid], volttron_instance.env
        )
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        assert "running [" in agent_status_dict.get("status")

        expected_status = agent_status_dict.get("status")
        expected_auuid = agent_status_dict.get("agent_uuid")

        # Attempt to install without force.
        with pytest.raises(RuntimeError):
            execute_command(args, volttron_instance.env)

        # Nothing should have changed the pid should be the same
        response = execute_command(
            ["vctl", "--json", "status", agent_uuid], volttron_instance.env
        )
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]
        assert expected_status == agent_status_dict.get("status")
        assert expected_auuid == agent_status_dict.get("agent_uuid")

        args = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            expected_identity,
            "--start",
            "--force",
        ]

        # Install with force.
        response = execute_command(args, volttron_instance.env)
        json_response = jsonapi.loads(response)
        agent_uuid = json_response["agent_uuid"]
        response = execute_command(
            ["vctl", "--json", "status", agent_uuid], volttron_instance.env
        )
        json_response = jsonapi.loads(response)
        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        assert "running [" in agent_status_dict.get("status")
        assert expected_status != agent_status_dict.get("status")
        assert expected_auuid != agent_status_dict.get("agent_uuid")

        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_install_with_wheel(volttron_instance: PlatformWrapper):
    with with_os_environ(volttron_instance.env):
        global listener_agent_dir
        args = ["volttron-pkg", "package", listener_agent_dir]
        response = execute_command(args, volttron_instance.env)
        assert response.startswith("Package created at: ")
        path = response[len("Package created at: "):]
        assert os.path.exists(path.strip())
        args = ["volttron-ctl", "--json", "install", path.strip()]
        response = execute_command(args, volttron_instance.env)
        response_dict = jsonapi.loads(response)
        assert response_dict.get("agent_uuid")
        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_install_with_wheel_bad_path(volttron_instance: PlatformWrapper):
    with with_os_environ(volttron_instance.env):
        bad_wheel_path = "foo/wheel.whl"
        args = ["volttron-ctl", "--json", "install", bad_wheel_path]
        try:
            response = execute_command(args, volttron_instance.env)
        except RuntimeError as exc:
            assert f"Invalid file {bad_wheel_path}" in exc.args[0]


@pytest.mark.control
@pytest.mark.parametrize(
    "use_config,args",
    (
            (True, ["install", listener_agent_dir, "--tag", "brewster", "--priority", "1"]),
            (
                    True,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "brewster",
                        "--start",
                        "--priority",
                        "1",
                    ],
            ),
            (
                    True,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "brewster",
                        "--start",
                        "--priority",
                        "20",
                    ],
            ),
            (True, ["install", listener_agent_dir, "--tag", "brewster", "--priority", "1"]),
            (
                    True,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "hoppy",
                        "--start",
                        "--priority",
                        "1",
                    ],
            ),
            (True, ["install", listener_agent_dir, "--tag", "brewster", "--priority", "1"]),
            (True, ["install", listener_agent_dir]),
            (
                    False,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "brewster",
                        "--start",
                        "--priority",
                        "1",
                    ],
            ),
            (
                    False,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "brewster",
                        "--start",
                        "--priority",
                        "20",
                    ],
            ),
            (
                    False,
                    ["install", listener_agent_dir, "--tag", "brewster", "--priority", "1"],
            ),
            (
                    False,
                    [
                        "install",
                        listener_agent_dir,
                        "--tag",
                        "hoppy",
                        "--start",
                        "--priority",
                        "1",
                    ],
            ),
            (True, ["install", listener_agent_dir]),
            (True, ["install", listener_agent_dir, "--vip-identity", "ralph"]),
    ),
)
def test_install_arg_matrix(
        volttron_instance: PlatformWrapper, args: List, use_config: bool
):
    listener_config_file = get_examples("ListenerAgent/config")

    with with_os_environ(volttron_instance.env):
        # Don't change the parametrized args that have mutable values. Make copy if changing within test.
        # parameterized args when used with more than 1 .parametrize() or with another parameterized fixture
        # fails to rest values correctly
        # @pytest.mark.parametrize("x,y", (([1, 2], 1), ([3, 4], 1))) - will work fine even if x is changed in test
        # But
        # @pytest.mark.parametrize("x,y", (([1,2],1), ([3,4],1)))
        # @pytest.mark.parametrize("z", [8, 9])
        # will fail to reset value of x correctly if x is changed within test

        vctl_args = copy.copy(args)
        vctl_args.insert(0, "--json")
        vctl_args.insert(0, "volttron-ctl")

        if use_config:
            vctl_args.extend(["--agent-config", listener_config_file])

        response = execute_command(vctl_args, volttron_instance.env)

        json_response = jsonapi.loads(response)

        agent_uuid = json_response["agent_uuid"]
        gevent.sleep(1)

        response = execute_command(
            ["vctl", "--json", "status", agent_uuid], volttron_instance.env
        )
        json_response = jsonapi.loads(response)

        identity = list(json_response.keys())[0]
        agent_status_dict = json_response[identity]

        if "--start" in vctl_args:
            assert agent_status_dict["status"]

        if "--tag" in vctl_args:
            assert agent_status_dict["agent_tag"]
            tag_name = vctl_args[vctl_args.index("--tag") + 1]
            assert tag_name == agent_status_dict["agent_tag"]

        if "--vip-identity" in vctl_args:
            assert agent_status_dict["identity"]
            expected_identity = vctl_args[vctl_args.index("--vip-identity") + 1]
            assert expected_identity == agent_status_dict["identity"]

        if use_config:
            with open(listener_config_file) as fp:
                expected_config = yaml.safe_load(fp.read())
            config_path = Path(volttron_instance.volttron_home).joinpath(
                f"agents/{agent_uuid}/listeneragent-3.3/listeneragent-3.3.dist-info/config"
            )
            with open(config_path) as fp:
                config_data = yaml.safe_load(fp.read())
                assert expected_config == config_data

        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_agent_filters(volttron_instance):
    auuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True
    )
    buuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True
    )

    # Verify all installed agents show up in list
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(
            ["volttron-ctl", "list"],
            env=volttron_instance.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" in str(agent_list)

    # Filter agent based on agent uuid
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(
            ["volttron-ctl", "list", str(auuid)],
            env=volttron_instance.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" not in str(agent_list)

    # Filter agent based on agent name
    with with_os_environ(volttron_instance.env):
        p = subprocess.Popen(
            ["volttron-ctl", "list", "listeneragent-3.3_1"],
            env=volttron_instance.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        agent_list = p.communicate()
        assert "listeneragent-3.3_1" in str(agent_list)
        assert "listeneragent-3.3_2" not in str(agent_list)

    volttron_instance.remove_all_agents()


@pytest.mark.control
def test_vctl_start_stop_restart_by_uuid_should_succeed(volttron_instance: PlatformWrapper):
    global listener_agent_dir
    with with_os_environ(volttron_instance.env):
        identity = "listener"
        install_listener = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            identity
        ]
        # install agent
        agent_uuid = jsonapi.loads(execute_command(install_listener, volttron_instance.env))['agent_uuid']

        # check that agent has not been started
        check_agent_status = ["vctl", "--json", "status", agent_uuid]
        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert not agent_status[identity]['health']
        assert not agent_status[identity]['status']

        # start agent
        start_agent_by_uuid = ["vctl", "start", agent_uuid]
        execute_command(start_agent_by_uuid, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert agent_status[identity]['health']['message'] == 'GOOD'
        assert 'running' in agent_status[identity]['status']

        # stop agent
        stop_tagged_agent = ["vctl", "stop", agent_uuid]
        execute_command(stop_tagged_agent, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert not agent_status[identity]['health']
        assert not int(agent_status[identity]['status'])  # status is a '0' when agent is stopped

        # restart agent
        # start the agent first so that restart agent will go through the entire flow of stopping, then starting an agent
        execute_command(start_agent_by_uuid, volttron_instance.env)
        restart_tagged_agent = ["vctl", "restart", agent_uuid]
        execute_command(restart_tagged_agent, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert agent_status[identity]['health']['message'] == 'GOOD'
        assert 'running' in agent_status[identity]['status']

        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_vctl_start_stop_restart_by_tag_should_succeed(volttron_instance: PlatformWrapper):
    global listener_agent_dir
    with with_os_environ(volttron_instance.env):
        identity = "listener"
        tag_name = "listener"
        install_listener = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            identity,
            "--tag",
            tag_name
        ]
        # install tagged agent
        agent_uuid = jsonapi.loads(execute_command(install_listener, volttron_instance.env))['agent_uuid']
        # check that agent have not been started
        check_agent_status = ["vctl", "--json", "status", agent_uuid]
        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        print(agent_status)
        assert not agent_status[identity]['health']
        assert not agent_status[identity]['status']

        # start tagged agent
        start_tagged_agent = ["vctl", "start", "--tag", tag_name]
        execute_command(start_tagged_agent, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert agent_status[identity]['health']['message'] == 'GOOD'
        assert 'running' in agent_status[identity]['status']

        # stop tagged agent
        stop_tagged_agent = ["vctl", "stop", "--tag", tag_name]
        execute_command(stop_tagged_agent, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert not agent_status[identity]['health']
        assert not int(agent_status[identity]['status'])  # status is a '0' when agent is stopped

        # restart tagged agent
        # start the agent first so that restart agent will go through the entire flow of stopping and then starting an agent
        execute_command(start_tagged_agent, volttron_instance.env)
        restart_tagged_agent = ["vctl", "restart", "--tag", tag_name]
        execute_command(restart_tagged_agent, volttron_instance.env)

        agent_status = jsonapi.loads(execute_command(check_agent_status, volttron_instance.env))
        assert agent_status[identity]['health']['message'] == 'GOOD'
        assert 'running' in agent_status[identity]['status']

        volttron_instance.remove_all_agents()


@pytest.mark.control
def test_vctl_start_stop_restart_by_all_tagged_should_succeed(volttron_instance: PlatformWrapper):
    global listener_agent_dir
    with with_os_environ(volttron_instance.env):
        identity_tag = "listener_tag"
        identity_tag2 = "listener_tag2"
        identity_no_tag = "listener_no_tag"
        tag_name = "listener"
        install_tagged_listener = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            identity_tag,
            "--tag",
            tag_name
        ]
        install_tagged_listener2 = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            identity_tag2,
            "--tag",
            tag_name
        ]
        install_listener_no_tag = [
            "volttron-ctl",
            "--json",
            "install",
            listener_agent_dir,
            "--vip-identity",
            identity_no_tag
        ]

        # install two tagged agents, one untagged agent
        jsonapi.loads(execute_command(install_tagged_listener, volttron_instance.env))
        jsonapi.loads(execute_command(install_tagged_listener2, volttron_instance.env))
        jsonapi.loads(execute_command(install_listener_no_tag, volttron_instance.env))

        check_all_status = ["vctl", "--json", "status"]

        # check that all three agents were installed and were not started
        status = jsonapi.loads(execute_command(check_all_status, volttron_instance.env))
        assert len(status) == 3
        for agent_info in status.values():
            assert not agent_info['health']
            assert not agent_info['status']

        # start all tagged
        start_all_tagged = ["vctl", "start", "--all-tagged"]
        execute_command(start_all_tagged, volttron_instance.env)

        # check that only tagged agents were started
        status = jsonapi.loads(execute_command(check_all_status, volttron_instance.env))

        assert status[identity_tag]['health']
        assert 'running' in status[identity_tag]['status']

        assert status[identity_tag2]['health']
        assert 'running' in status[identity_tag2]['status']

        assert not status[identity_no_tag]['health']
        assert not status[identity_no_tag]['status']

        # stop all tagged
        stop_all_tagged = ["vctl", "stop", "--all-tagged"]
        execute_command(stop_all_tagged, volttron_instance.env)

        # check that all agents were stopped
        status = jsonapi.loads(execute_command(check_all_status, volttron_instance.env))

        assert not status[identity_tag]['health']
        assert not int(status[identity_tag]['status'])  # status is a '0' when agent is started and then stopped

        assert not status[identity_tag2]['health']
        assert not int(status[identity_tag2]['status'])  # status is a '0' when agent is started and then stopped

        assert not status[identity_no_tag]['health']
        assert not status[identity_no_tag]['status']

        # restart all tagged
        # start all tagged agents first so that restart agent will go through the entire flow of stopping and then starting an agent
        execute_command(start_all_tagged, volttron_instance.env)
        restart_all_tagged = ["vctl", "restart", "--all-tagged"]
        execute_command(restart_all_tagged, volttron_instance.env)

        # check that only tagged agents were restarted
        status = jsonapi.loads(execute_command(check_all_status, volttron_instance.env))

        assert status[identity_tag]['health']
        assert 'running' in status[identity_tag]['status']

        assert status[identity_tag2]['health']
        assert 'running' in status[identity_tag2]['status']

        assert not status[identity_no_tag]['health']
        assert not status[identity_no_tag]['status']

        volttron_instance.remove_all_agents()


@pytest.mark.parametrize("subcommand, invalid_option", [
        ("start", "--all-taggeD"), ("stop","--all-taggeD"), ("restart","--all-taggeD"),
        ("start", "--all"), ("stop","--all"), ("restart","--all")
        ]
    )
def test_vctl_start_stop_restart_should_raise_error_on_invalid_options(volttron_instance: PlatformWrapper, subcommand, invalid_option):
    with with_os_environ(volttron_instance.env):        
        with pytest.raises(RuntimeError):
            execute_command(["vctl", subcommand, invalid_option], volttron_instance.env)

@pytest.mark.parametrize("subcommand, valid_option", [("start", "--all-tagged"), ("stop","--all-tagged"), ("restart","--all-tagged")])
def test_vctl_start_stop_restart_should_not_fail_on_when_no_agents_are_installed(volttron_instance: PlatformWrapper, subcommand, valid_option):
    with with_os_environ(volttron_instance.env):            
        execute_command(["vctl", subcommand, valid_option], volttron_instance.env)
        assert not jsonapi.loads(execute_command(["vctl", "--json", "status"], volttron_instance.env))
