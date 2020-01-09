#!/usr/bin/env python3
# import module snippets
from configparser import ConfigParser, NoOptionError
import enum
import json
import logging
import os
import pwd
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


class StateEnum(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    INVALID_PATH = "INVALID_PATH"
    NOT_BOOTSTRAPPED = "NOT_BOOTSTRAPPED"
    ERROR = "ERROR"


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


def build_volttron_configfile(volttron_home, host_config_dict):
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

        if not host_config_dict['enable_web']:
            _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        elif not host_config_dict['bind_web_address']:
            _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        else:
            parser.set('volttron', 'bind-web-address',
                       host_config_dict['bind_web_address'])

    parser.write(open(cfg_loc, 'w'))
    return changed


def get_current_state(volttron_home, volttron_path):
    """
    Determine the state of volttron on target system.

    :param volttron_home:
    :param volttron_path:
    :return:
    """

    PID_FILE = os.path.join(volttron_home, "VOLTTRON_PID")

    state = None
    if not os.path.exists(python(volttron_path)):
        state = StateEnum.NOT_BOOTSTRAPPED
    else:
        if os.path.exists(PID_FILE):
            pid = open(PID_FILE).read()
            if os.path.isdir(f"/proc/{pid}"):
                state = StateEnum.RUNNING
            else:
                state = StateEnum.STOPPED
        else:
            state = StateEnum.STOPPED

    logger().debug(f"get_current_state() returning {state}")
    return state


def check_agent_status(agents):
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

        state=dict(required=True, choices=StateEnum.__members__.keys())
        #started=dict(default=True, type="bool")
    ))

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

    if p['state'] not in StateEnum.__members__.keys():
        module.fail_json(msg=f"Invalid state for enum {StateEnum.__members__}")

    expected_state = StateEnum(p['state'])

    logger().debug(f"Expected State is {expected_state}")

    if not os.path.exists(vroot):
        module.fail_json(msg="Invalid VOLTTRON path (%s)" % vroot)

    with open(host_config) as fp:
        cfg_host = yaml.safe_load(fp)

    if 'config' not in cfg_host:
        module.fail_json(msg="Must have config section in host configuration file.")

    #module.exit_json(changed=True, msg=cfg_host) # f"{json.dumps(cfg_host, indent=2)}")
    #
    # bind_web = p['bind_web_address']
    # if bind_web and p['enable_web']:
    #     parsed = urlparse(bind_web)
    #
    #     if parsed.scheme not in ('http', 'https'):
    #         module.fail_json(
    #             "Invalid bind_web_address must be http or https scheme")
    #         return
    #
    #     if parsed.port < 4000:
    #         module.fail_json(
    #             "bind_web_address port shuould be larger than 4000 or "
    #             "cannot bind to it without root."
    #         )
    #         return
    #
    # vip_address = p['vip_address']
    # if vip_address:
    #     parsed = urlparse(vip_address)
    #
    #     if parsed.scheme not in ('tcp',):
    #         module.fail_json(
    #             "vip address should start with tcp://"
    #         )
    #     if parsed.port <= 4000:
    #         module.fail_json(
    #             "http port shuould be larger than 4000 or cannot bind "
    #             "to it without root."
    #         )

    config_file_changed = build_volttron_configfile(vhome, cfg_host['config'])
    current_state = get_current_state(vhome, vroot)

    if current_state == expected_state and not config_file_changed:
        module.exit_json(changed=False, msg=f"No Change Required", state=current_state.name)
    elif expected_state == StateEnum.RUNNING:
        if config_file_changed and current_state == StateEnum.RUNNING:
            logger().debug("Stopping volttron due to restart")
            stop_volttron(vroot, vctlbin)
            current_state = wait_for_state(StateEnum.STOPPED, vhome, vroot)
            if current_state != StateEnum.STOPPED:
                module.fail_json(msg="Failed to stop running volttron in timely manner")
        logger().debug("Starting volttron")
        start_volttron(vroot, volttronbin)
        current_state = wait_for_state(StateEnum.RUNNING, vhome, vroot)

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON started", state=current_state.name)
    elif expected_state == StateEnum.STOPPED:
        logger().debug("Stopping volttron")
        stop_volttron(vroot, vctlbin)
        current_state = wait_for_state(StateEnum.STOPPED, vhome, vroot)

        if current_state != expected_state:
            force_kill_volttron()
            current_state = wait_for_state(StateEnum.STOPPED, vhome, vroot)

            if current_state != expected_state:
                module.fail_json(msg="Couldn't shutdown or force kill volttron")

        current_state = get_current_state(vhome, vroot)

        module.exit_json(changed=True, failed=current_state != expected_state,
                         msg="VOLTTRON stopped", state=current_state.name)

    module.fail_json(msg="Unknown state found")


    config_file_changed = build_volttron_configfile(vhome, p)

    after_state = get_current_state(vhome, vroot)
    changed = after_state != current_state
    module.exit_json(changed=changed,
                     ansible_facts=p,
                     original_state=current_state,
                     after_state=after_state)


def wait_for_state(expected_state, vhome, vroot):
    countdown = 5
    current_state = StateEnum.ERROR
    while current_state is not expected_state and countdown > 0:
        sleep(5)
        countdown -= 1
        new_state = get_current_state(vhome, vroot)
        if new_state == expected_state:
            current_state = new_state
            break

    return current_state


if __name__ == '__main__':
    main()
