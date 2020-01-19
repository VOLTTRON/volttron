#!/usr/bin/env python3
# import module snippets
import base64
from configparser import ConfigParser, NoOptionError
import enum
import json
import ipaddress
import logging
from netifaces import interfaces, ifaddresses, AF_INET
import os
import pwd
import psutil
import shutil
import socket
import re
import subprocess
from time import sleep
from urllib.parse import urlparse

from ansible.module_utils.basic import AnsibleModule
from zmq import curve_keypair
from zmq.utils import z85
import yaml


# region utility functions
def init_logging(filepath, level=logging.DEBUG):
    # if os.path.isfile(filepath):
    #     os.remove(filepath)
    logging.basicConfig(filename=filepath, level=level)


def logger():
    return logging.getLogger(__name__)


def expand_all(path):
    return os.path.expandvars(os.path.expanduser(path))


def wait_for_state(expected_state, vhome, vroot):
    countdown = 5
    current_state = InstanceState.ERROR
    while current_state is not expected_state and countdown > 0:
        sleep(5)
        countdown -= 1
        new_state = get_instance_state()
        if new_state == expected_state:
            current_state = new_state
            break

    return current_state


def encode_key(key):
    """"Base64-encode and return a key in a URL-safe manner."""
    assert len(key) in (32, 40)
    if len(key) == 40:
        key = z85.decode(key)
    return base64.urlsafe_b64encode(key)[:-1].decode("ASCII")


def has_bootstrapped(volttron_path):
    return os.path.exists(os.path.join(volttron_path, 'env/bin/python'))


def python(volttron_path):
    return os.path.join(volttron_path, 'env', 'bin', 'python')


def is_loopback(vip_address):
    ip = vip_address.strip().lower().split("tcp://")[1]
    addr = ipaddress.ip_address(ip)
    return addr.is_loopback


def is_ip_private(vip_address):
    """ Determines if the passed vip_address is a private ip address or not.

    :param vip_address: A valid ip address.
    :return: True if an internal ip address.
    """
    ip = vip_address.strip().lower().split("tcp://")[1]


    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) is not None or priv_24.match(
        ip) is not None or priv_20.match(ip) is not None or priv_16.match(
        ip) is not None


def ip4_addresses():
    ip_list = []
    for interface in interfaces():
        for link in ifaddresses(interface)[AF_INET]:
            ip_list.append(link['addr'])
    return ip_list

# endregion


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


class VolttronContext:
    VOLTTRON_HOME = os.path.abspath(expand_all("~/.volttron"))
    VCTL = os.path.abspath(expand_all("~/volttron/env/bin/vctl"))
    VOLTTRON = os.path.abspath(expand_all("~/volttron/env/bin/volttron"))
    VOLTTRON_ROOT = os.path.abspath(expand_all("~/volttron"))

    def update_volttron_root(self, new_root):
        if new_root != VolttronContext.VOLTTRON_ROOT:
            VolttronContext.VOLTTRON_ROOT = new_root
            VolttronContext.VOLTTRON = os.path.join(new_root, "env/bin/volttron")
            VolttronContext.VCTL = os.path.join(new_root, "env/bin/vctl")


class InstallPhase(enum.Enum):
    AGENT_INSTALL = "AGENT_INSTALL"
    ALLOW_EXTERNAL_CONNECTIONS = "ALLOW_EXTERNAL_CONNECTIONS"
    START_AGENTS = "START_AGENTS"
    UNINSTALL = "UNINSTALL"

# Set up default context for the module
volttron_context = VolttronContext()


# region configuration handling functions
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
    host_config_cpy = {}
    if host_config_dict is not None:
        host_config_cpy = host_config_dict.copy()
    host_config_cpy.pop("participate-in-multiplatform", None)

    logger().debug(f"Building config from:\n{json.dumps(host_config_cpy, indent=2)}")
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
        for k, v in host_config_cpy.items():
            parser.set('volttron', k, v)

    if not had_config:
        if 'volttron_central_addres' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron', 'volttron-central-address')
        else:
            parser.set('volttron', 'volttron-central-address',
                       host_config_cpy['volttron_central_address'])

        if 'volttron_central_serverkey' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron',
                                    'volttron-central-serverkey')
        else:
            parser.set('volttron', 'volttron-central-serverkey',
                       host_config_cpy['volttron_central_serverkey'])

        if 'vip_address' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron', 'vip-address')
        else:
            parser.set('volttron', 'vip-address',
                       host_config_cpy['vip_address'])

        # if not host_config_dict['enable_web']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # elif not host_config_dict['bind_web_address']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # else:
        #     parser.set('volttron', 'bind-web-address',
        #                host_config_dict['bind_web_address'])

    parser.write(open(cfg_loc, 'w'))
    return changed
# endregion


def get_instance_state():
    """
    Determine the state of volttron on target system.  The function determines
    whether or not volttron is running based upon the VOLTTRON_PID file in
    the volttron_home directory.  First of all the function will check to make sure
    that volttron has been bootstrapped.  If it is not the function will return
    `InstanceState.NOT_BOOTSTRAPPED.  If the process id in VOLTTRON_PID is in /proc/ directory
    then the process is alive and the function returns `InstanceState.RUNNING`.  Otherwise, the
    function will return `InstanceState.STOPPED`

    :return:
    """

    PID_FILE = os.path.join(volttron_context.VOLTTRON_HOME, "VOLTTRON_PID")

    if not os.path.exists(volttron_context.VOLTTRON):
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


# region VOLTTRON command functions
def start_volttron():
    cmd = [volttron_context.VOLTTRON, '-L', 'examples/rotatinglog.py']
    logger().debug(f"starting volttron {cmd}")
    proc = subprocess.Popen(cmd,
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'),
                            preexec_fn=os.setpgrp,
                            cwd=volttron_context.VOLTTRON_ROOT)

    logger().debug(proc)


def stop_volttron():
    cmd = [volttron_context.VCTL, 'shutdown', '--platform']
    logger().debug(f"stopping volttron {cmd}")
    proc = subprocess.Popen(cmd,
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'),
                            preexec_fn=os.setpgrp,
                            cwd=volttron_context.VOLTTRON_ROOT)


def force_kill_volttron():
    logger().debug("Force killing volttron")
    proc = subprocess.Popen(['killall', '-9', 'volttron'],
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'))

    proc = subprocess.Popen(['killall', '-9', 'python'],
                            stdout=open('/dev/null', 'w'),
                            stderr=open('logfile.log', 'a'))
# endregion


def update_agents(agents_config_dict: dict):
    agents_state = get_agents_state(agents_config_dict)
    # all_installed_agents = set(agents_state.keys())
    found_agents = set()
    not_installed = set()

    for identity, v in agents_state.items():
        # If agent hasn't been installed but user wants the agent then go ahead and install it
        if v['state'] == AgentState.NOT_INSTALLED.name and identity in agents_config_dict:
            install_results = install_agent(identity, agents_config_dict[identity])

    agents_state_after = get_agents_state(agents_config_dict)

    # for id, agent_spec in agents_config_dict.items():
    #     logger().debug(f"{id} => {agent_spec}")
    #     if id in agents_state:
    #         found_agents.add(id)
    #         state = AgentState(agents_state[id]['state'])
    #         if state == AgentState.NOT_INSTALLED:
    #             install_agent(id, agent_spec)
    agents_state_after = get_agents_state(agents_config_dict)
    return agents_state, agents_state_after


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
    logger().debug(f"get_agent_status(agent_dir) {agent_dir}")
    base_name = os.path.basename(agent_dir)
    dist_info_dir = None
    for root, dirs, files in os.walk(agent_dir):
        for d in dirs:
            if d.endswith("dist-info"):
                dist_info_dir = os.path.join(root, d)
                break
    agent_data_dir = None
    for root, dirs, files in os.walk(agent_dir):
        for d in dirs:
            if d.endswith("agent-data"):
                agent_data_dir = os.path.join(root, d)
                break

    logger().debug(f"dist-info dir is {dist_info_dir}")
    logger().debug(f"agent-data dir is {agent_data_dir}")

    logger().debug(f"Checking directory exists {dist_info_dir}")
    if not os.path.isdir(dist_info_dir):
        return dict(state=AgentState.NOT_INSTALLED.name)

    tag_file = os.path.join(agent_dir, "TAG")
    priority_file = os.path.join(agent_dir, "AUTOSTART")
    key_file = os.path.join(agent_data_dir, "keystore.json")

    with open(os.path.join(dist_info_dir, 'metadata.json')) as file:
        metadata = json.loads(file.read())
    logger().debug(f"metadata is {metadata}")
    try:
        exports = metadata['exports']
    except KeyError:
        exports = metadata['extensions']['python.exports']
    eggsecutable = exports['setuptools.installation']['eggsecutable']
    found_proc = None
    module, _ = eggsecutable.split(":")
    logger().debug(f"searching for module: {module} using psutils")
    for proc in psutil.process_iter():
        if module in proc.name():
            found_proc = proc
            break

    logger().debug(f"found_proc is: {found_proc}")
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
    if os.path.exists(key_file):
        with open(key_file) as fp:
            data = json.loads(fp.read())
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
            logger().debug(f"file_path is {file_path}")
            identity = open(file_path).read()
            logger().debug(f"Passing dirname ({os.path.dirname(file_path)})")
            results[identity] = get_agent_status(os.path.dirname(file_path))

    return results


def get_agents_state(agents_config_dict):
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
    logger().debug(f"Inside get_agents_state")
    agents_state = find_all_agents(os.path.join(volttron_context.VOLTTRON_HOME, 'agents'))
    logger().debug(f"Inside get_agents_state\n {agents_state}")
    for identity, spec in agents_config_dict.items():

        if identity not in agents_state:
            agents_state[identity] = dict(state=AgentState.NOT_INSTALLED.name)
        elif 'pid' not in agents_state[identity]:
            agents_state[identity]['state'] = AgentState.STOPPED.name
        else:
            agents_state[identity]['state'] = AgentState.RUNNING.name

    return agents_state


def install_agent(identity, agent_spec: dict):
    """
    Installs
    The install_agent function is the main function of the module.  It wraps
    two scripts that are available in the volttron repository under the scripts
    directory.  The instance.py script allows querying of the instance for
    information without having to be activated, and the install-agent.py
    script that has command line arguments for installing the agents on a
    running instance.

    @param: identity: The agent's identity
    @param: agent_spec: The specification for agent installation

    :return:
    """

    cmd = [volttron_context.VCTL, "install", agent_spec['source'], '--start', '--json', '--force',
           '--vip-identity', identity]

    if "priority" in agent_spec:
        cmd.extend(['--priority', str(agent_spec['priority'])])

    logger().debug(f"Commands are {cmd}")

    response = subprocess.run(cmd, cwd=volttron_context.VOLTTRON_ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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


def do_install_agents_phase(agent_config_dict: dict):
    pass


def do_allow_connections(agent_config_dict, volttron_host_dict):
    logger().debug("I AM HERE!")
    for host_facts in volttron_host_dict['results']:
        logger().debug(host_facts['ansible_facts']['my_data']['ansible_local'])
    # with open("/tmp/foofile", 'w') as fp:
    #     fp.write(json.dumps(volttron_host_dict, indent=2))


def do_start_tag_agents(ageent_config_dict):
    pass

def persist_facts():
    instance_state = get_instance_state()
    with open("/etc/ansible/facts.d", "w") as fp:
        fp.write(json.dumps(instance_state, indent=2))




def main():
    init_logging(expand_all("~/ansible_logging.log"))
    logger().debug("Before module instantiation")

    module = AnsibleModule(argument_spec=dict(
        volttron_home=dict(required=False, default=volttron_context.VOLTTRON_HOME),
        volttron_root=dict(required=False, default=volttron_context.VOLTTRON_ROOT),
        config_file=dict(required=True),
        phase=dict(choicesj=InstallPhase.__members__.keys()),
        # instance_name=dict(default=socket.gethostname()),
        # vip_address=dict(default=None),
        # bind_web_address=dict(default=None),
        # volttron_central_address=dict(default=None),
        # volttron_central_serverkey=dict(default=None),
        # Only binds when this flag is set to true.

        state=dict(choices=InstanceState.__members__.keys()),
        volttron_host_facts=dict(required=False, type='dict')
        # started=dict(default=True, type="bool")
    ), supports_check_mode=True)

    # VOLTTRON cannot be ran as root.
    if os.geteuid() == 0:
        module.fail_json(msg="Cannot use this module in root context.")
        return

    # Short cut for params
    p = module.params

    vroot = expand_all(p['volttron_root'])

    # if the volttron path doesn't exist yet then then we know the user
    # hasn't inited this instance yet.
    if not os.path.exists(vroot):
        module.fail_json(msg=f"volttron_path does not exist {vroot}. "
                             f"Please run vctl deploy init on this host.")

    # region host configuration file validation
    host_config_file = expand_all(p['config_file'])

    # The host config file must be present for the script to understand
    # how to configure this instance.
    if not os.path.exists(vroot):
        module.fail_json(msg=f"config_file path does not exist {host_config_file}. "
                             f"Please run vctl deploy init on this host.")

    host_cfg, agent_cfg = _validate_and_build_configuration(host_config_file, module)

    # endregion

    # volttron_context allows the functions to get the main directories
    # without having to pass them along in the arguments of functions.
    volttron_context.update_volttron_root(vroot)

    vhome = expand_all(p['volttron_home'])

    # Check mode allows ansible to run a mininimal commmand that "doesn't change"
    # any state.  In our system, if the serverkey is not created then it will
    # be created during a check mode call.
    check_mode = module.check_mode

    # region create main keystore file that keeps the instance's serverkey

    # Create the volttron_home directory if it doesn't exist and create the main
    # instanc's public and secreate key for the instance.  This is the value that
    # one can retrive when doing a vctl auth serverkey command from the command line.
    os.makedirs(vhome, 0o755, exist_ok=True)

    serverkey_file = os.path.join(vhome, "keystore")

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

    # endregion

    # The main volttron config file will automatically be created when
    # the agent is first started or when this module is run without check_mode
    # set to true.
    main_volttron_config = os.path.join(vhome, "config")

    # region check_mode
    if module.check_mode:
        if not os.path.isfile(main_volttron_config):
            module.exit_json(changed=False,
                             msg="Instance hasn't been started",
                             state={
                                 "instance_state": InstanceState.NEVER_STARTED.name,
                                 "serverkey": publickey,
                                 "agents_state": {},
                                 "vip-address": host_cfg['vip-address'],
                                 "participate-in-multiplatform": host_cfg.get('participate-in-multiplatform', False)
                             })

        instance_state = get_instance_state()
        all_agents_state = get_agents_state(agents_config_dict=agent_cfg)
        module.exit_json(changed=False,
                         state={
                             "instance_state": instance_state.name,
                             "serverkey": publickey,
                             "agents_state": all_agents_state,
                             "vip-address": host_cfg['vip-address'],
                             "participate-in-multiplatform": host_cfg.get('participate-in-multiplatform', False)
                         })

    # endregion

    expected_state = None
    current_phase = None
    volttron_host_facts = None

    # state is required if check_mode is not set
    if 'state' not in p:
        module.exit_json(changed=False, msg="missing required arguments: state",
                         available_states=AgentState.__members__.keys())

    if 'phase' not in p:
        module.exit_json(changed=False, msg="missing required argument: phase",
                         available_phases=InstallPhase.__members__.keys())
    expected_state = InstanceState(p['state'])
    current_phase = InstallPhase(p['phase'])
    volttron_host_facts = None
    if current_phase == InstallPhase.ALLOW_EXTERNAL_CONNECTIONS:
        if 'volttron_host_facts' not in p:
            module.exit_json(changed=False,
                             msg="missing required argument: "
                                 "'volttron_host_facts' for phase 'ALLOW_EXTERNAL_CONNECTIONS")
        else:
            volttron_host_facts = p['volttron_host_facts']
    logger().debug(f"Expected State is {expected_state}")
    logger().debug(f"curren_phase is {current_phase}")

    # Create/update main volttron config file
    config_file_changed = build_volttron_configfile(vhome, host_cfg)
    current_state = get_instance_state()

    if current_state == InstanceState.RUNNING:
        logger().debug("Inside running block")
        if current_phase == InstallPhase.AGENT_INSTALL:
            logger().debug("Before do_install_agents")
            results = do_install_agents_phase(agent_cfg)
        elif current_phase == InstallPhase.ALLOW_EXTERNAL_CONNECTIONS:
            logger().debug("Before do allow")
            results = do_allow_connections(host_cfg['agents'], volttron_host_facts)
        else:
            logger().debug("Before start tag.")
            results = do_start_tag_agents(agent_cfg)

        module.exit_json(changed=True)

    module.exit_json(msg="OUtside!")
    if current_state == expected_state and not config_file_changed:
        agent_state_changed = False
        # if current_state == InstanceState.RUNNING:
        #     module.fail_json(msg="doing check for agents")
        #     agent_state_changed = update_agents(cfg_host['agents'])
        before_agent, after_agent = update_agents(host_cfg['agents'])

        module.exit_json(changed=True, msg="First block here", before_agent=before_agent, after_agent=after_agent)

        module.exit_json(changed=False, msg=f"No Change Required", state=current_state.name,
                         serverkey=publickey,
                         agent_state_changed=agent_state_changed)
    elif expected_state == InstanceState.RUNNING:
        if config_file_changed and current_state == InstanceState.RUNNING:
            logger().debug("Stopping volttron due to restart")
            stop_volttron()
            current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
            if current_state != InstanceState.STOPPED:
                module.fail_json(msg="Failed to stop running volttron in timely manner")
        logger().debug("Starting volttron")
        start_volttron()
        current_state = wait_for_state(InstanceState.RUNNING, vhome, vroot)

        if current_state != InstanceState.RUNNING:
            module.fail_json(msg="Failed to start VOLTTRON")

        before_agent, after_agent = update_agents(host_cfg['agents'])

        module.exit_json(changed=True, before_agent=before_agent, after_agent=after_agent)

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON started", serverkey=publickey,
                         state=current_state.name)
    elif expected_state == InstanceState.STOPPED:
        logger().debug("Stopping volttron")
        stop_volttron()
        current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)

        if current_state != expected_state:
            force_kill_volttron()
            current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)

            if current_state != expected_state:
                module.fail_json(msg="Couldn't shutdown or force kill volttron")

        current_state = get_instance_state()

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON stopped",
                         serverkey=publickey,
                         state=current_state.name)

    module.fail_json(msg="Unknown state found")

    config_file_changed = build_volttron_configfile(vhome, p)

    after_state = get_instance_state()
    changed = after_state != current_state
    module.exit_json(changed=changed,
                     ansible_facts=p,
                     original_state=current_state,
                     after_state=after_state)


def to_bool(arg):
    abool = None
    try:
        abool = bool(arg)
    except TypeError:
        if isinstance(arg, str):
            if arg.upper() in ('YES', 'TRUE'):
                abool = True
            elif arg.upper() in ('NO', 'FALSE'):
                abool = False
    if abool is None:
        raise TypeError(f'Invalid type for value {arg} should be a boolean value')

    return abool


def valid_local_public_vip_address(vip_address):
    if vip_address is None:
        return False
    parsed = urlparse(vip_address)

    if parsed.scheme != 'tcp':
        return False

    if parsed.port is None:
        return False

    if parsed.port <= 1024 or parsed.port > 65535:
        return False

    try:
        addr = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    else:
        if addr not in ip4_addresses():
            return False

        return not addr.is_loopback


def dertimine_vip_address(should_be_public, vip_address, custom_port=22916):
    vip_addr = None
    if vip_address is None:
        if should_be_public:
            public_addr = None
            for addr in ip4_addresses():
                if not ipaddress.ip_address(addr).is_loopback:
                    public_addr = addr
                    break
            vip_addr = f"tcp://{public_addr}:{custom_port}"
        else:
            vip_addr = f"tcp://127.0.0.1:22916"
    elif should_be_public and not valid_local_public_vip_address(vip_address):
        raise ValueError(f"Invalid vip address specified {vip_address} can not be loopback")
    elif not should_be_public and valid_local_public_vip_address(vip_address):
        raise ValueError(f"Invalid vip address specified {vip_address} should be loopback address")

    if vip_addr is None:
        raise ValueError("Couldn't determine vip-address for this host!")

    return vip_addr


def _validate_and_build_configuration(host_config_file, module: AnsibleModule):

    if not os.path.isfile(host_config_file):
        module.fail_json(msg=f"The host config file ({host_config_file} does not exist.")
    with open(host_config_file) as fp:
        host_cfg_loaded = yaml.safe_load(fp)
    if 'config' not in host_cfg_loaded:
        module.fail_json(msg="Must have config section in host configuration file.")
    if 'agents' not in host_cfg_loaded:
        module.fail_json(msg="Must have agents section in host configuration file.")
    logger().debug(f"host config loaded: {host_cfg_loaded}")
    host_config = host_cfg_loaded.get('config', {})
    agents_config = host_cfg_loaded.get('agents', {})

    # If no configuration paraementers are passed that's ok
    if host_config is None:
        host_config = {}

    # No agent configuration means that we have a platform just sitting there doing nothing.
    if agents_config is None:
        agents_config = {}

    # region verify and create vip-address for volttron config file
    multiplatform_participant = False
    try:
        logger().debug(f"host config is {host_config}")
        a_bool = to_bool(host_config.get('participate-in-multiplatform', False))
        multiplatform_participant = a_bool # to_bool(host_config.get('participate-in-multiplatform', False))
    except TypeError:
        module.fail_json(msg=f"Invalid value for participate-in-multiplatform")

    allow_external_connections = False
    try:
        allow_external_connections = to_bool(host_config.pop('allow-external-connections', multiplatform_participant))
    except TypeError:
        module.fail_json(msg=f"Invalid value for 'allow-external-connections'")

    custom_vip_ip = host_config.pop("custom-vip-ip", None)
    custom_vip_port = int(host_config.get("custom-vip-port", 22916))
    if custom_vip_port <= 1024 or custom_vip_port > 65535:
        module.fail_json(msg="Invalid custom-vip-port must be between 1024 and 65535")

    if custom_vip_ip:
        vip_address = f"tcp://{custom_vip_ip}:{custom_vip_port}"
    else:
        vip_address = None

    if multiplatform_participant and not allow_external_connections:
        module.fail_json(msg="Mismatch between allow-external-connections and participate-in-multiplatform")

    if multiplatform_participant or allow_external_connections:
        try:
            vip_address = dertimine_vip_address(should_be_public=True, vip_address=vip_address)
        except ValueError as ex:
            module.fail_json(msg=ex)
        else:
            host_config['vip-address'] = vip_address
    else:
        try:
            vip_address = dertimine_vip_address(should_be_public=False, vip_address=vip_address)
        except ValueError as ex:
            module.fail_json(msg=ex)
        else:
            host_config['vip-address'] = vip_address
    # endregion

    return host_config, agents_config


if __name__ == '__main__':
    main()
