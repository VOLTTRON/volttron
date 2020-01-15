#!/usr/bin/env python3
# import module snippets
import base64
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
from zmq import curve_keypair
from zmq.utils import z85
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
    NEVER_STARTED = 'NEVER_STARTED'
    ERROR = "ERROR"


class AgentState(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERRORED = "ERRORED"
    NOT_INSTALLED = "NOT_INSTALLED"
    UNKNOWN = "UNKNOWN"


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


def update_agents(vctl, volttron_home, agents_config_dict: dict):
    agents_state = get_agents_state(volttron_home, agents_config_dict)
    # all_installed_agents = set(agents_state.keys())
    found_agents = set()

    for id, agent_spec in agents_config_dict.items():
        logger().debug(f"{id} => {agent_spec}")
        if id in agents_state:
            found_agents.add(id)
            state = AgentState(agents_state[id]['state'])
            if state == AgentState.NOT_INSTALLED:
                install_agent(vctl, id, agent_spec)


def check_install_agents(agents: dict):
    for id, item in agents.items():
        logger().debug(f"{id} => {item}")


def get_agent_status(agent_dir):
    """
    Retrieve the agent status from the installed directory in VOLTTRON_HOME.

    This method uses the metadata.json file in the agent's .dist-info folder
    to load information about the agent.  In addition it uses psutil to
    verify whether an agent is running or not.

    The function will return a dictionary with the following keys:
     - pid          - PID of the agent if running
     - public_key   - public_key of the agent if available
     - priority     - startup order if available
     - tag          - agent tag if available

    :param agent_dir: The installed agent directory
    :return:
    """
    base_name = os.path.basename(agent_dir)
    dist_info_dir = os.path.join(agent_dir, f"{base_name}.dist-info")
    if not os.path.isdir(dist_info_dir):
        return dict(state=AgentState.NOT_INSTALLED.name)

    tag_file = os.path.join(agent_dir, "TAG")
    priority_file = os.path.join(agent_dir, "AUTOSTART")
    secret_key_file = os.path.join(agent_dir, f"{base_name}.agent-data/keystore.json")

    with open(os.path.join(dist_info_dir, 'metadata.json')) as file:
        metadata = json.loads(file.read())

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
    """
    Find all of the agents in the specified `path`.  The path should
    be the VOLTTRON_HOME/agents directory.

    The function uses the each agent's IDENTITY file to create a
    dictionary of agent identities mapped onto the agent state.

    This function requires using `get_agent_status` to determine the
    state of the agent.

    :param path:
        Path of the search for agents.
    :return:
        dictionary of identity -> agent status
    """
    results = {}
    name = "IDENTITY"
    for root, dirs, files in os.walk(path):
        if name in files:
            file_path = os.path.join(root, name)
            identity = open(file_path).read()
            results[identity] = get_agent_status(os.path.dirname(file_path))

    return results


def get_agents_state(volttron_home, agents_config_dict):
    """
    Uses all found agents (from `find_all_agents` function) to provide an
    agent state key.  The function compares expected agents to the currently
    installed and runnning agents to provide the state.

    This function will return a dictionary such as the following:

    {
      "identity1":
        {
          "state": "RUNNING",
          "pid": 4234
        },
      "identity2":
        {
          "state": "NOT_INSTALLED"
        }
    }

    :param volttron_home:
    :param agents_config_dict:
    :return:
        dictionary identity -> state with pid
    """
    agents_state = find_all_agents(os.path.join(volttron_home, 'agents'))

    for identity, spec in agents_config_dict.items():

        if identity not in agents_state:
            agents_state[identity] = dict(state=AgentState.NOT_INSTALLED.name)
        elif agents_state[identity]['pid'] is not None:
            agents_state[identity]['state'] = AgentState.STOPPED.name
        else:
            agents_state[identity]['state'] = AgentState.RUNNING.name

    return agents_state


def install_agent(vctl, identity, agent_spec: dict):
    """
    Installs
    The install_agent function is the main function of the module.  It wraps
    two scripts that are available in the volttron repository under the scripts
    directory.  The instance.py script allows querying of the instance for
    information without having to be activated, and the install-agent.py
    script that has command line arguments for installing the agents on a
    running instance.

    :param python:
    :param scripts_dir:
    :param params:
    :return:
    """

    cmd = [vctl, "install", agent_spec['source'], '--json', '--force', '--vip-identity', identity]

    response = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if response.returncode != 0:
        logger().debug(f"Something failed spectacularly during install for idenitity {identity}")
        logger().debug(f"STDOUT\n{response.stdout}")
        logger().debug(f"STDERR\n{response.stdout}")
        return

    logger().debug(f"Installed {identity}")
    logger().debug(f"STDOUT\n{response.stdout}")
    logger().debug(f"STDERR\n{response.stdout}")
        
    #
    # params = module.params
    # # First we need to verify that the instance is currently running or we
    # # cannot install anything.
    # args = [python, os.path.join(scripts_dir, 'instance.py'), '--volttron-home',
    #         params['volttron_home']]
    #
    # (rc, out, err) = module.run_command(args)
    #
    # if rc != 0:
    #     return True, False, dict(msg="instance not running", out=out, err=err)
    #
    # if int(out.strip()) == 0:
    #     err = "Instance {} is not running.".format(params['volttron_home'])
    #     return (True, False,
    #             dict(msg=err))
    #
    # # Next we need to customize the installation script parameters based upon
    # # the input from the caller.
    # script = os.path.join(scripts_dir, "install-agent.py")
    #
    # args = [python, script]
    # args.extend(['--volttron-home', params['volttron_home']])
    # args.extend(['--volttron-root', params['volttron_root']])
    # args.extend(['--agent-source', params['source']])
    #
    # if params['identity']:
    #     args.extend(['--vip-identity', params['identity']])
    #
    # # Always use force because we can't find a reason not to upgrade if
    # # possible.
    # args.extend(['--force'])
    #
    # # If a priority is specified that implies the agent will be enabled.
    # if params['priority']:
    #     args.extend(['--enable', '--priority', str(params['priority'])])
    # elif params['enable']:
    #     args.extend(['--enable'])
    #
    # # When a config_objecct is sent as a parameter we use a temp file to write
    # # the content to before using it within the installation.  We do this so
    # # that we don't have to deal with passing json on the commmand line, though
    # # it will work it is frought with perils
    # #
    # # We serialize the json (config_object) and stuff it into the temp file.
    # tmpfilename = '/tmp/tmp-{}'.format(random.randint(10, 1000))
    # #module.fail_json(msg=tmpfilename + str(params['config_object']))
    # if params['config_object']:
    # #    module.exit_json(msg=params['config_object'])
    #     # Dump to to tmp file and then add the --config param to the arguments.
    #     data = json.dumps(params['config_object'])
    #     with open(tmpfilename, 'w') as f:
    #         f.write(data)
    #
    #     args.extend(['--config', tmpfilename])
    # elif params['config']:
    #     args.extend(['--config', params['config']])
    #
    # if params['state'] == 'started':
    #     args.extend(['--start'])
    #
    # if params['tag']:
    #     args.extend(['--tag', params['tag']])
    #
    # (rc, stdout, stderr) = module.run_command(args)
    #
    # retvalues = {}
    # is_error = int(rc) != 0
    # if is_error:
    #     retvalues['msg'] = "rc code from install-agent.py invalid."
    #
    # # Cleanup temp file if necessary.
    # if os.path.exists(tmpfilename):
    #     os.remove(tmpfilename)
    #
    # install_return = None
    # if not is_error:
    #     # Now there is a lot of cruf in the stdout, however it is split by \n
    #     # and after the word RECORD at the end of a line is json data
    #     pos = stdout.rindex('RECORD') + len('RECORD') + 1
    #     jsondata = stdout[pos:]
    #     #return is_error, False, dict(stdout=jsondata)
    #     install_return = json.loads(jsondata.replace("\n", " "))
    #     if params['state'] == 'started':
    #         is_error = 'started' in install_return and not install_return['started']
    #         if is_error:
    #             retvalues['msg'] = "Agent wasn't able to reach started state."
    #
    # retvalues['params'] = params
    # retvalues['args'] = args
    # retvalues['install_agent_ret'] = install_return
    # if is_error:
    #     return is_error, False, retvalues
    #
    # retvalues['result'] = "installed {} agent.".format(params['source'])
    # return is_error, True, retvalues


def encode_key(key):
    """"Base64-encode and return a key in a URL-safe manner."""
    assert len(key) in (32, 40)
    if len(key) == 40:
        key = z85.decode(key)
    return base64.urlsafe_b64encode(key)[:-1].decode("ASCII")


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

    # VOLTTRON cannot be ran as root.
    if os.geteuid() == 0:
        module.fail_json(msg="Cannot use this module in root context.")
        return

    p = module.params

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

    serverkey_file = os.path.join(vhome, "keystore")
    host_config = expand_all(p['config_file'])
    volttronbin = os.path.join(vroot, "env/bin/volttron")
    vctlbin = os.path.join(vroot, "env/bin/vctl")

    check_mode = module.check_mode

    if not os.path.exists(vroot):
        module.fail_json(msg=f"volttron_path does not exist {vroot}. "
                             f"Please run vctl deploy init on this host.")

    os.makedirs(vhome, 0o755, exist_ok=True)

    if not os.path.exists(serverkey_file):
        public, secret = curve_keypair()
        with open(serverkey_file, 'w') as fp:
            fp.write(
                json.dumps(
                    {'public': encode_key(public), 'secret': encode_key(secret)},
                    indent=2))

    with open(serverkey_file) as fp:
        keypair = json.loads(fp.read())
        publickey = keypair['public']

    if not os.path.isfile(host_config):
        if module.check_mode:
            module.exit_json(chande=False,
                             msg="Instance hasn't been started",
                             instance_state=InstanceState.NEVER_STARTED.name,
                             serverkey=publickey,
                             agents_state={})
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

    expected_state = None
    # Check mode allows us to get the state of the instance in its current form without doing
    # anything else.
    if check_mode:
        instance_state = get_instance_state(volttron_home=vhome, volttron_path=vroot)
        all_agents_state = get_agents_state(volttron_home=vhome, agents_config_dict=cfg_host['agents'])
        module.exit_json(changed=False, instance_state=instance_state.name, serverkey=publickey,
                         agents_state=all_agents_state)
    else:
        # state is required if check_mode is not set
        if 'state' not in p:
            module.exit_json(changed=False, msg="missing required arguments: state")

        expected_state = InstanceState(p['state'])

        logger().debug(f"Expected State is {expected_state}")

    # _validate_agent_config will exit if the agent's configurations are not valid.
    # validity means the paths to config files are valid json/yaml and that
    # their paths are correct
    _validate_agent_config(cfg_host['agents'])

    # Create/update main volttron config file
    config_file_changed = build_volttron_configfile(vhome, cfg_host['config'])
    current_state = get_instance_state(vhome, vroot)

    if current_state == expected_state and not config_file_changed:
        agent_state_changed = False
        if current_state == InstanceState.RUNNING:
            agent_state_changed = check_install_agents(cfg_host['agents'])
        module.exit_json(changed=False, msg=f"No Change Required", state=current_state.name,
                         serverkey=publickey,
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

        if current_state != InstanceState.RUNNING:
            module.fail_json(msg="Failed to start VOLTTRON")

        update_agents(cfg_host['agents'])

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON started", serverkey=publickey,
                         state=current_state.name)
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
                         msg="VOLTTRON stopped",
                         serverkey=publickey,
                         state=current_state.name)

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
