# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
from ConfigParser import ConfigParser
import argparse
import getpass
import hashlib
import os
import sys
import urlparse
import tempfile

from gevent import subprocess
from gevent.subprocess import Popen
from volttron.platform.agent import json as jsonapi
from zmq import green as zmq

from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.utils.prompt import prompt_response, y, n, y_or_n

from . import get_home, get_services_core

# Global configuration options.  Must be key=value strings.  No cascading
# structure so that we can easily create/load from the volttron config file
# if it exists.
config_opts = {}

# Dictionary of tags to config functions.
# Populated by the `installs` decorator.
available_agents = {}

def _load_config():
    """Loads the config file if the path exists."""
    path = os.path.join(get_home(), 'config')
    if os.path.exists(path):
        parser = ConfigParser()
        parser.read(path)
        options = parser.options('volttron')
        for option in options:
            config_opts[option] = parser.get('volttron', option)


def _install_config_file():
    home = get_home()

    if not os.path.exists(home):
        os.makedirs(home, 0o755)

    path = os.path.join(home, 'config')

    config = ConfigParser()
    config.add_section('volttron')

    for k, v in config_opts.items():
        config.set('volttron', k, v)

    with open(path, 'w') as configfile:
        config.write(configfile)


def _cmd(cmdargs):
    """Executes the passed command.

    :param cmdargs: A list of arguments that should be passed to Popen.
    :type cmdargs: [str]
    """
    if verbose:
        print(cmdargs)
    process = Popen(cmdargs, env=os.environ, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
    process.wait()


def _is_bound_already(address):
    context = zmq.Context()
    dealer_sock = context.socket(zmq.DEALER)
    already_bound = False
    try:
        dealer_sock.bind(address)
    except zmq.ZMQError:
        already_bound = True
    finally:
        dealer_sock.close()
    return already_bound


def fail_if_instance_running():

    home = get_home()
    ipc_address = 'ipc://@{}/run/vip.socket'.format(home)

    if os.path.exists(home) and\
       _is_bound_already(ipc_address):
        print("""
The current instance is running.  In order to configure an instance it cannot
be running.  Please execute:

    volttron-ctl shutdown --platform

to stop the instance.
""")
        sys.exit()


def fail_if_not_in_src_root():
    in_src_root = os.path.exists("./volttron")
    if not in_src_root:
        print """
volttron-cfg needs to be run from the volttron top level source directory.
"""
        sys.exit()


def _start_platform():
    cmd = ['volttron', '-vv',
           '-l', os.path.join(get_home(), 'volttron.cfg.log')]
    if verbose:
        print('Starting platform...')
    pid = Popen(cmd, env=os.environ.copy(), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)


def _shutdown_platform():
    if verbose:
        print('Shutting down platform...')
    _cmd(['volttron-ctl', 'shutdown', '--platform'])


def _install_agent(agent_dir, config, tag):
    if not isinstance(config, dict):
        config_file = config
    else:
        cfg = tempfile.NamedTemporaryFile()
        with open(cfg.name, 'w') as fout:
            fout.write(jsonapi.dumps(config))
        config_file = cfg.name
    _cmd(['volttron-ctl', 'remove', '--tag', tag, '--force'])
    _cmd(['scripts/core/pack_install.sh',
          agent_dir, config_file, tag])


# Decorator to handle installing agents
# Decorated functions need to return a config
# file for the target agent.
def installs(agent_dir, tag, identity=None, post_install_func=None):
    def wrap(config_func):
        global available_agents

        def func(*args, **kwargs):
            if identity is not None:
                os.environ['AGENT_VIP_IDENTITY'] = identity

            print 'Configuring {}'.format(agent_dir)
            config = config_func(*args, **kwargs)
            _install_config_file()
            _start_platform()
            _install_agent(agent_dir, config, tag)
            if post_install_func:
                post_install_func()

            autostart = prompt_response('Should agent autostart?',
                                        valid_answers=y_or_n,
                                        default='N')
            if autostart in y:
                _cmd(['volttron-ctl', 'enable', '--tag', tag])

            _shutdown_platform()

            if identity is not None:
                os.environ.pop('AGENT_VIP_IDENTITY')

        available_agents[tag] = func
        return func
    return wrap


def is_valid_url(url, accepted_schemes):
    if url is None:
        return False
    parsed = urlparse.urlparse(url)
    if parsed.scheme not in accepted_schemes:
        return False
    if not parsed.hostname:
        return False

    return True


def is_valid_port(port):
    try:
        port = int(port)
    except ValueError:
        return False

    return 0 < port < 65535


def do_vip():
    global config_opts

    parsed = urlparse.urlparse(config_opts.get('vip-address',
                                               'tcp://127.0.0.1:22916'))
    vip_address = None
    if parsed.hostname is not None and parsed.scheme is not None:
        vip_address = parsed.scheme + '://' + parsed.hostname
        vip_port = parsed.port
    else:
        vip_address = 'tcp://127.0.0.1'
        vip_port = 22916

    available = False
    while not available:
        valid_address = False
        while not valid_address:
            prompt = 'What is the external instance ipv4 address?'

            new_vip_address = prompt_response(prompt, default=vip_address)
            valid_address = is_valid_url(new_vip_address, ['tcp'])
            if valid_address:
                vip_address = new_vip_address
            else:
                print("Address is not valid")

        valid_port = False
        while not valid_port:
            prompt = 'What is the instance port for the vip address?'
            new_vip_port = prompt_response(prompt, default=vip_port)
            valid_port = is_valid_port(new_vip_port)
            if valid_port:
                vip_port = new_vip_port
            else:
                print("Port is not valid")

        while vip_address.endswith('/'):
            vip_address = vip_address[:-1]

        attempted_address = '{}:{}'.format(vip_address, vip_port)
        if not _is_bound_already(attempted_address):
            available = True
        else:
            print('\nERROR: That address has already been bound to.')
    config_opts['vip-address'] = '{}:{}'.format(vip_address, vip_port)


@installs(get_services_core("VolttronCentral"), 'vc')
def do_vc():
    global config_opts

    # Full implies that it will have a port on it as well.  Though if it's
    # not in the address that means that we haven't set it up before.
    full_bind_web_address = config_opts.get('bind-web-address',
                                            'http://127.0.0.1')

    parsed = urlparse.urlparse(full_bind_web_address)

    address_only = full_bind_web_address
    port_only = None
    if parsed.port is not None:
        address_only = parsed.scheme + '://' + parsed.hostname
        port_only = parsed.port
    else:
        port_only = 8080

    print("""
In order for external clients to connect to volttron central or the instance
itself, the instance must bind to a tcp address.  If testing this can be an
internal address such as 127.0.0.1.
""")
    valid_address = False
    external_ip = None
    while not valid_address:
        prompt = 'Please enter the external ipv4 address for this instance? '
        new_external_ip = prompt_response(prompt, default=address_only)
        valid_address = is_valid_url(new_external_ip, ['http', 'https'])
        if valid_address:
            external_ip = new_external_ip

    valid_port = False
    vc_port = None
    while not valid_port:
        prompt = 'What is the port for volttron central?'
        new_vc_port = prompt_response(prompt, default=port_only)
        valid_port = is_valid_port(new_vc_port)
        if valid_port:
            vc_port = new_vc_port

    while external_ip.endswith("/"):
        external_ip = external_ip[:-1]

    config_opts['bind-web-address'] = '{}:{}'.format(external_ip, vc_port)

    resp = vc_config()
    print('Installing volttron central')
    return resp


def vc_config():
    username = ''
    while not username:
        username = prompt_response('Enter volttron central admin user name:')
        if not username:
            print('ERROR Invalid username')
    password = ''
    password2 = ''
    while not password:
        password = prompt_response('Enter volttron central admin password:',
                                   echo=False)
        if not password:
            print('ERROR: Invalid password')
            continue

        password2 = prompt_response('Retype password:',
                                    echo=False)
        if password2 != password:
            print("ERROR: Passwords don't match")

            password = ''

    config = {
        'users': {
            username: {
                'password': hashlib.sha512(password).hexdigest(),
                'groups': ['admin']
            }
        }
    }

    return config


@installs(get_services_core("VolttronCentralPlatform"), 'vcp')
def do_vcp():
    global config_opts

    # Default instance name to the vip address.
    instance_name = config_opts.get('instance-name',
                                    config_opts.get('vip-address'))
    instance_name = instance_name.strip('"')

    valid_name = False
    while not valid_name:
        prompt = 'Enter the name of this instance.'
        new_instance_name = prompt_response(prompt, default=instance_name)
        if new_instance_name:
            valid_name = True
            instance_name = new_instance_name
    config_opts['instance-name'] = '"{}"'.format(instance_name)

    vc_address = config_opts.get('volttron-central-address',
                                 config_opts.get('bind-web-address',
                                                 'http://127.0.0.1'))

    parsed = urlparse.urlparse(vc_address)
    address_only = vc_address
    port_only = None
    if parsed.port is not None:
        address_only = parsed.scheme + '://' + parsed.hostname
        port_only = parsed.port
    else:
        port_only = 8080

    valid_vc = False
    while not valid_vc:
        prompt = "Enter volttron central's web address"
        new_vc_address = prompt_response(prompt, default=address_only)
        valid_vc = is_valid_url(new_vc_address, ['http', 'https'])
        if valid_vc:
            vc_address = new_vc_address

    vc_port = None
    while True:
        prompt = 'What is the port for volttron central?'
        new_vc_port = prompt_response(prompt, default=port_only)
        if is_valid_port(new_vc_port):
            vc_port = new_vc_port
            break

    new_address = '{}:{}'.format(vc_address, vc_port)
    config_opts['volttron-central-address'] = new_address

    return {}


@installs(get_services_core("SQLHistorian"), 'platform_historian',
          identity='platform.historian')
def do_platform_historian():
    datafile = os.path.join(get_home(), 'data', 'platform.historian.sqlite')
    config = {
        'agentid': 'sqlhistorian-sqlite',
        'connection': {
            'type': 'sqlite',
            'params': {
                'database': datafile
            }
        }
    }
    return config


def add_fake_device_to_configstore():
    prompt = 'Install a fake device on the master driver?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        _cmd(['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
              'fake.csv', 'examples/configurations/drivers/fake.csv', '--csv'])
        _cmd(['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
              'devices/fake-campus/fake-building/fake-device',
              'examples/configurations/drivers/fake.config'])


@installs(get_services_core("MasterDriverAgent"), 'master_driver',
          post_install_func=add_fake_device_to_configstore)
def do_master_driver():
    return {}


@installs('examples/ListenerAgent', 'listener')
def do_listener():
    return {}


def wizard():
    """Routine for configuring an insalled volttron instance.

    The function interactively sets up the instance for working with volttron
    central and the discovery service.
    """

    # Start true configuration here.
    volttron_home = get_home()

    print('\nYour VOLTTRON_HOME currently set to: {}'.format(volttron_home))
    prompt = '\nIs this the volttron you are attempting to setup? '
    if not prompt_response(prompt, valid_answers=y_or_n, default='Y') in y:
        print(
            '\nPlease execute with VOLTRON_HOME=/your/path volttron-cfg to '
            'modify VOLTTRON_HOME.\n')
        return

    _load_config()
    do_vip()
    _install_config_file()

    prompt = 'Is this instance a volttron central?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_vc()

    prompt = 'Will this instance be controlled by volttron central?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='Y')
    if response in y:
        do_vcp()

    prompt = 'Would you like to install a platform historian?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_platform_historian()

    prompt = 'Would you like to install a master driver?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_master_driver()

    prompt = 'Would you like to install a listener agent?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_listener()

    print('Finished configuration\n')
    print('You can now start the volttron instance.\n')
    print('If you need to change the instance configuration you can edit')
    print('the config file at {}/config\n'.format(volttron_home))


def main():
    global verbose

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--verbose', action='store_true')

    group = parser.add_mutually_exclusive_group()

    agent_list = '\n\t' + '\n\t'.join(sorted(available_agents.keys()))
    group.add_argument('--list-agents', action='store_true', dest='list_agents',
                       help='list configurable agents{}'.format(agent_list))

    group.add_argument('--agent', nargs='+',
                        help='configure listed agents')

    args = parser.parse_args()
    verbose = args.verbose

    fail_if_instance_running()
    fail_if_not_in_src_root()

    _load_config()

    if args.list_agents:
        print "Agents available to configure:{}".format(agent_list)

    elif not args.agent:
        wizard()

    else:
        # Warn about unknown agents
        for agent in args.agent:
            if agent not in available_agents:
                print '"{}" not configurable with this tool'.format(agent)

        # Configure agents
        for agent in args.agent:
            try:
                available_agents[agent]()
            except KeyError:
                pass
