#!/usr/bin/env python3
# import module snippets
from configparser import ConfigParser, NoOptionError
import enum
import json
import logging
import os
import pwd
import psutil
import shutil
import socket
import subprocess
from time import sleep
from urllib.parse import urlparse

from ansible.module_utils.basic import AnsibleModule
import yaml


def init_logging(filepath, level=logging.DEBUG):
    logging.basicConfig(filename=filepath, level=level)


def logger():
    return logging.getLogger(__name__)


class InstanceState(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    INVALID_PATH = "INVALID_PATH"
    NOT_BOOTSTRAPPED = "NOT_BOOTSTRAPPED"
    ERROR = "ERROR"


class AgentState(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERRORED = "ERRORED"
    NOT_INSTALLED = "NOT_INSTALLED"


def has_bootstrapped(volttron_path):
    return os.path.exists(os.path.join(volttron_path, 'env/bin/python'))


def expand_all(path):
    return os.path.expandvars(os.path.expanduser(path))


def python(volttron_path):
    return os.path.join(volttron_path, 'env', 'bin', 'python')


def _get_option_no_error(inst, section, option, default=None):
    try:
        value = inst.get(section, option)
    except NoOptionError:
        value = default
    return value


def _remove_option_no_error(inst, section, option):
    try:
        inst.remove_option(section, option)
        return True
    except NoOptionError:
        return False


def _validate_agent_config(agent_dict: dict):

    agent_keys = ['source', 'config', 'config_store']
    for id, item in agent_dict.items():

        logger().debug(f"{json.dumps(os.environ.copy(), indent=2)}")


def build_volttron_configfile(volttron_home, host_config_dict:dict):
    """
    :param volttron_home:
    :param params:
    :return:
    """
    logger().debug(f"Building config from:\n{json.dumps(host_config_dict, indent=2)}")
    cfg_loc = os.path.join(volttron_home, 'config')
    had_config = False
    changed = False
    if not os.path.isdir(volttron_home):
        os.makedirs(volttron_home)
    else:
        if os.path.isfile(cfg_loc):
            had_config = True

    parser = ConfigParser()

    if had_config:
        parser.read(cfg_loc)

    if host_config_dict is None:
        host_config_dict = {}
    vc_address = None
    vc_serverkey = None
    vip_address = None
    bind_web_address = None

    if had_config:
        vc_address = _get_option_no_error(parser,
                                          'volttron',
                                          'voltttron-central-address')
        vc_serverkey = _get_option_no_error(parser,
                                            'volttron',
                                            'voltttron-central-serverkey')
        vip_address = _get_option_no_error(parser, 'volttron', 'vip-address')
        bind_web_address = _get_option_no_error(parser,
                                                'volttron', 'bind-web-address')
    else:
        changed = True
        parser.add_section('volttron')
        for k, v in host_config_dict.items():
            parser.set('volttron', k, v)

    if not had_config:
        if 'volttron_central_addres' not in host_config_dict:
            _remove_option_no_error(parser, 'volttron', 'volttron-central-address')
        else:
            parser.set('volttron', 'volttron-central-address',
                       host_config_dict['volttron_central_address'])

        if 'volttron_central_serverkey' not in host_config_dict:
            _remove_option_no_error(parser, 'volttron',
                                    'volttron-central-serverkey')
        else:
            parser.set('volttron', 'volttron-central-serverkey',
                       host_config_dict['volttron_central_serverkey'])

        if 'vip_address' not in host_config_dict:
            _remove_option_no_error(parser, 'volttron', 'vip-address')
        else:
            parser.set('volttron', 'vip-address',
                       host_config_dict['vip_address'])

        # if not host_config_dict['enable_web']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # elif not host_config_dict['bind_web_address']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # else:
        #     parser.set('volttron', 'bind-web-address',
        #                host_config_dict['bind_web_address'])

    parser.write(open(cfg_loc, 'w'))
    return changed


def get_instance_state(volttron_home, volttron_path):
    """
    Determine the state of volttron on target system.  The function determines
    whether or not volttron is running based upon the VOLTTRON_PID file in
    the volttron_home directory.  First of all the function will check to make sure
    that volttron has been bootstrapped.  If it is not the function will return
    `InstanceState.NOT_BOOTSTRAPPED.  If the process id in VOLTTRON_PID is in /proc/ directory
    then the process is alive and the function returns `InstanceState.RUNNING`.  Otherwise, the
    function will return `InstanceState.STOPPED`

    :param volttron_home:
    :param volttron_path:
    :return:
    """

    PID_FILE = os.path.join(volttron_home, "VOLTTRON_PID")

    if not os.path.exists(python(volttron_path)):
        state = InstanceState.NOT_BOOTSTRAPPED
    else:
        if os.path.exists(PID_FILE):
            pid = open(PID_FILE).read()
            if os.path.isdir(f"/proc/{pid}"):
                state = InstanceState.RUNNING
            else:
                state = InstanceState.STOPPED
        else:
            state = InstanceState.STOPPED

    logger().debug(f"get_current_state() returning {state}")
    return state


def check_agent_status(agents: dict):
    for id, item in agents.items():
        pass


def start_volttron(volttron_path, volttron_bin):
    cmd = [volttron_bin, '-L', 'examples/rotatinglog.py']
    logger().debug(f"starting volttron {cmd}")
    proc = subprocess.Popen(cmd,
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'),
                            preexec_fn=os.setpgrp,
                            cwd=volttron_path)

    logger().debug(proc)


def stop_volttron(volttron_path, vctl_bin):
    cmd = [vctl_bin, 'shutdown', '--platform']
    logger().debug(f"stopping volttron {cmd}")
    proc = subprocess.Popen(cmd,
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'),
                            preexec_fn=os.setpgrp,
                            cwd=volttron_path)


def force_kill_volttron():
    logger().debug("Force killing volttron")
    proc = subprocess.Popen(['killall', '-9', 'volttron'],
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'))

    proc = subprocess.Popen(['killall', '-9', 'python'],
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'))


def update_agents(agents: dict):
    for id, agent in agents.items():
        logger().debug(f"{id} => {agent}")


def check_install_agents(agents: dict):
    for id, item in agents.items():
        logger().debug(f"{id} => {item}")

def get_agent_status(agent_dir):
    base_name = os.path.basename(agent_dir)
    dist_info_dir = os.path.join(agent_dir, f"{base_name}.dist-info")
    if not os.path.isdir(dist_info_dir):
        return dict(state=AgentState.NOT_INSTALLED.name)

    tag_file = os.path.join(agent_dir, "TAG")
    priority_file = os.path.join(agent_dir, "AUTOSTART")
    secret_key_file = os.path.join(agent_dir, f"{base_name}.agent-data/keystore.json")

    with open(os.path.join(dist_info_dir, 'metadata.json')) as file:
        metadata = json.loads(file.read())
        # wheelmeta = {
        #     key.strip().lower(): value.strip()
        #     for key, value in
        #     (parts for line in file if line
        #      for parts in [line.split(':', 1)] if len(parts) == 2)
        # }
    exports = metadata['exports']
    module = exports['setuptools.installation']['eggsecutable']
    found_proc = None
    for proc in psutil.process_iter():
        if module in proc.name:
            found_proc = proc
    pid = None
    if found_proc:
        pid = found_proc.pid
    tag = None
    if os.path.exists(tag_file):
        tag = open(tag_file).read()
    priority = None
    if os.path.exists(priority_file):
        priority = open(priority_file).read()
    public_key = None
    if os.path.exists(secret_key_file):
        with open(secret_key_file) as fp:
            data = json.loads(fp)
            public_key = data['public']
    return {
        "pid": pid,
        "public_key": public_key,
        "priority": priority,
        "tag": tag
    }


def find_all_agents(path):
    results = {}
    name = "IDENTITY"
    for root, dirs, files in os.walk(path):
        if name in files:
            file_path = os.path.join(root, name)
            identity = open(file_path).read()
            results[identity] =  get_agent_status(os.path.dirname(file_path))

    return results


def get_agents_state(volttron_home, agents_config_dict):
    agents_state = find_all_agents(volttron_home)

    for identity, spec in agents_config_dict.items():

        if identity not in agents_state:
            agents_state[identity] = dict(state=AgentState.NOT_INSTALLED.name)
        elif agents_state[identity]['pid'] is not None:
            agents_state[identity]['state'] = AgentState.STOPPED.name
        else:
            agents_state[identity]['state'] = AgentState.RUNNING.name

    return agents_state


def main():
    init_logging(expand_all("~/ansible_logging.log"))
    logger().debug("Before module instantiation")

    module = AnsibleModule(argument_spec=dict(
        volttron_home=dict(required=False, default="~/.volttron"),
        volttron_root=dict(required=False, default="~/volttron"),
        config_file=dict(required=True),
        # instance_name=dict(default=socket.gethostname()),
        # vip_address=dict(default=None),
        # bind_web_address=dict(default=None),
        # volttron_central_address=dict(default=None),
        # volttron_central_serverkey=dict(default=None),
        # Only binds when this flag is set to true.

        state=dict(choices=InstanceState.__members__.keys()),
        # started=dict(default=True, type="bool")
    ), supports_check_mode=True)

    p = module.params

    # # VOLTTRON cannot be ran as root.
    # if os.geteuid() == 0:
    #     module.fail_json(msg="Cannot use this module in root context.")
    #     return
    #
    # # Make sure we are running under the correct user for VOLTTRON
    # if pwd.getpwuid(os.getuid()).pw_name != p['volttron_user']:
    #     module.fail_json(
    #         msg="Must run as the passed volttron_user use become=yes and "
    #             "specify the correct user {}".format(p['volttron_user']))
    #
    # if p['volttron_home'] is None:
    #     p['volttron_home'] = "/home/{}/.volttron".format(p['volttron_user'])

    vhome = expand_all(p['volttron_home'])
    vroot = expand_all(p['volttron_root'])
    host_config = expand_all(p['config_file'])
    volttronbin = os.path.join(vroot, "env/bin/volttron")
    vctlbin = os.path.join(vroot, "env/bin/vctl")

    check_mode = module.check_mode

    if not os.path.exists(vroot):
        module.fail_json(msg=f"volttron_path does not exist {vroot}. "
                             f"Please run vctl deploy up.")

    if not os.path.isfile(host_config):
        module.fail_json(msg=f"File not found {host_config}.")

    with open(host_config) as fp:
        cfg_host = yaml.safe_load(fp)

    if 'config' not in cfg_host:
        module.fail_json(msg="Must have config section in host configuration file.")

    if 'agents' not in cfg_host:
        module.fail_json(msg="Must have agents section in host configuration file.")

    if not cfg_host['config']:
        cfg_host['config'] = {}

    if not cfg_host['agents']:
        cfg_host['agents'] = {}

    if check_mode:
        instance_state = get_instance_state(volttron_home=vhome, volttron_path=vroot)
        all_agents_state = get_agents_state(volttron_home=vhome, agents_config_dict=cfg_host['agents'])
        module.exit_json(changed=False, instance_state=instance_state.name, agents_state=all_agents_state)
    else:
        if 'state' not in p:
            module.exit_json(changed=False, msg="missing required arguments: state")

        expected_state = InstanceState(p['state'])

        logger().debug(f"Expected State is {expected_state}")

    _validate_agent_config(cfg_host['agents'])

    config_file_changed = build_volttron_configfile(vhome, cfg_host['config'])
    current_state = get_instance_state(vhome, vroot)

    if current_state == expected_state and not config_file_changed:
        agent_state_changed = False
        if current_state == InstanceState.RUNNING:
            agent_state_changed = check_install_agents(cfg_host['agents'])
        module.exit_json(changed=False, msg=f"No Change Required", state=current_state.name,
                         agent_state_changed=agent_state_changed)
    elif expected_state == InstanceState.RUNNING:
        if config_file_changed and current_state == InstanceState.RUNNING:
            logger().debug("Stopping volttron due to restart")
            stop_volttron(vroot, vctlbin)
            current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
            if current_state != InstanceState.STOPPED:
                module.fail_json(msg="Failed to stop running volttron in timely manner")
        logger().debug("Starting volttron")
        start_volttron(vroot, volttronbin)
        current_state = wait_for_state(InstanceState.RUNNING, vhome, vroot)

        update_agents(cfg_host['agents'])

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON started", state=current_state.name)
    elif expected_state == InstanceState.STOPPED:
        logger().debug("Stopping volttron")
        stop_volttron(vroot, vctlbin)
        current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)

        if current_state != expected_state:
            force_kill_volttron()
            current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)

            if current_state != expected_state:
                module.fail_json(msg="Couldn't shutdown or force kill volttron")

        current_state = get_instance_state(vhome, vroot)

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON stopped", state=current_state.name)

    module.fail_json(msg="Unknown state found")


    config_file_changed = build_volttron_configfile(vhome, p)

    after_state = get_instance_state(vhome, vroot)
    changed = after_state != current_state
    module.exit_json(changed=changed,
                     ansible_facts=p,
                     original_state=current_state,
                     after_state=after_state)


def wait_for_state(expected_state, vhome, vroot):
    countdown = 5
    current_state = InstanceState.ERROR
    while current_state is not expected_state and countdown > 0:
        sleep(5)
        countdown -= 1
        new_state = get_instance_state(vhome, vroot)
        if new_state == expected_state:
            current_state = new_state
            break

    return current_state


if __name__ == '__main__':
    main()
