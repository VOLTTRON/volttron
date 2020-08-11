# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
import argparse
import hashlib
import os
import sys
import tempfile
import atexit
import time
from configparser import ConfigParser
from shutil import copy
from urllib.parse import urlparse

from gevent import subprocess
from gevent.subprocess import Popen
from zmq import green as zmq

from bootstrap import install_rabbit, default_rmq_dir
from requirements import extras_require
from volttron.platform import certs, is_rabbitmq_available
from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import MASTER_WEB, PLATFORM_DRIVER, VOLTTRON_CENTRAL
from volttron.platform.agent.utils import get_platform_instance_name, wait_for_volttron_startup, \
    is_volttron_running, wait_for_volttron_shutdown
from volttron.utils import get_hostname
from volttron.utils.prompt import prompt_response, y, n, y_or_n
from volttron.utils.rmq_config_params import RMQConfig
from volttron.utils.rmq_setup import setup_rabbitmq_volttron
from . import get_home, get_services_core, set_home

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


def _update_config_file(instance_name=None, web_secret_key=None):
    if not config_opts:
        _load_config()
    home = get_home()

    if not os.path.exists(home):
        os.makedirs(home, 0o755)

    path = os.path.join(home, 'config')

    config = ConfigParser()

    config.add_section('volttron')

    for k, v in config_opts.items():
        config.set('volttron', k, v)

    # if instance_name is not None:

    if 'instance-name' in config_opts:
        # Overwrite existing if instance name was passed
        if instance_name is not None:
            config.set('volttron', 'instance-name', instance_name)
    else:
        if instance_name is None:
            instance_name = 'volttron1'
        config.set('volttron', 'instance-name', instance_name)

    if web_secret_key is not None:
        config.set('volttron', 'web-secret-key', web_secret_key)

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
    out, error = process.communicate()
    if process.returncode != 0:
        print("Error executing command: {} \nSTDOUT: {}\nSTDERR: {}".format(cmdargs, out, error))
        sys.exit(10)


def _is_bound_already(address):
    context = zmq.Context()
    dealer_sock = context.socket(zmq.DEALER)
    already_bound = False
    try:
        dealer_sock.bind(address)
    except zmq.ZMQError as e:
        print(e)
        already_bound = True
    finally:
        dealer_sock.close()
    return already_bound


def fail_if_instance_running():

    home = get_home()

    if os.path.exists(home) and\
       is_volttron_running(home):
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
        print("""
volttron-cfg needs to be run from the volttron top level source directory.
""")
        sys.exit()


def _start_platform():
    vhome = get_home()
    cmd = ['volttron', '-vv',
           '-l', os.path.join(vhome, 'volttron.cfg.log')]
    print(cmd)
    if verbose:
        print('Starting platform...')
    pid = Popen(cmd, env=os.environ.copy(), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
    wait_for_volttron_startup(vhome, 45)


def _shutdown_platform():
    vhome = get_home()
    if is_volttron_running(vhome):
        if verbose:
            print('Shutting down platform...')
        _cmd(['volttron-ctl', 'shutdown', '--platform'])
        wait_for_volttron_shutdown(vhome, 45)


def _cleanup_on_exit():
    vhome = get_home()
    retry_attempt = 30
    while retry_attempt > 0:
        if is_volttron_running(vhome):
            time.sleep(1)
            retry_attempt -= 1
        else:
            return
    _shutdown_platform()

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


def _is_agent_installed(tag):
    installed_list_process = Popen(['vctl','list'], env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    installed_list = installed_list_process.communicate()
    installed = b"".join(installed_list)
    if tag.encode('utf-8') in installed:
        return True
    else:
        return False


# Decorator to handle installing agents
# Decorated functions need to return a config
# file for the target agent.
def installs(agent_dir, tag, identity=None, post_install_func=None):
    def wrap(config_func):
        global available_agents

        def func(*args, **kwargs):
            if identity is not None:
                os.environ['AGENT_VIP_IDENTITY'] = identity

            print('Configuring {}.'.format(agent_dir))
            config = config_func(*args, **kwargs)
            _update_config_file()
            #TODO: Optimize long vcfg install times
            #TODO: (potentially only starting the platform once per vcfg)
            _start_platform()

            _install_agent(agent_dir, config, tag)

            if not _is_agent_installed(tag):
                print(tag + ' not installed correctly!')
                _shutdown_platform()
                return

            if post_install_func:
                post_install_func()

            autostart = prompt_response('Should the agent autostart?',
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
    parsed = urlparse(url)
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


def is_valid_bus(bus_type):
    return bus_type in ['zmq', 'rmq']


def _get_dependencies():
    reqs = subprocess.check_output([sys.executable, "-m", "pip", "freeze"])
    dependencies = [r.decode() for r in reqs.split()]
    return dependencies


def _check_dependencies_met(requirement):
    try:
        dependencies_needed = extras_require[requirement]
    except KeyError:
        print(f"ERROR: Requirement {requirement} was not found in requirements.py")
        return False
    current_dependencies = _get_dependencies()
    for dependency in dependencies_needed:
        if "==" in dependency:
            if dependency in current_dependencies:
                pass
            else:
                return False
        else:
            if dependency.split("==")[0] in [r.split("==")[0] for r in current_dependencies]:
                pass
            else:
                return False
    return True


def set_dependencies(requirement):
    try:
        dependencies_needed = extras_require[requirement]
    except KeyError:
        print("ERROR: Incorrect requirement chosen")
        return
    cmds = [sys.executable, "-m", "pip", "install"]
    for dependency in dependencies_needed:
        cmds.append(dependency)
    subprocess.check_call(cmds)
    return


def set_dependencies_rmq():
    install_rabbit(default_rmq_dir)


def _create_web_certs():
    global config_opts
    """
    Utility to create web server certificates
    Designed to be used in conjecture with get_cert_and_key
    As such, it assumes that the program has already checked
    for existing certs, and prompted the user to enter in 
    certificates that they have generated separately.
    """
    crts = certs.Certs()
    try:
        crts.ca_cert()
    except certs.CertError:
        print("WARNING! CA certificate does not exist.")
        prompt_str = "Create new root CA?"
        prompt = prompt_response(prompt_str, valid_answers=y_or_n, default='Y')
        if prompt in y:
            cert_data = {}
            print("\nPlease enter the following details for web server certificate:")
            prompt = '\tCountry:'
            cert_data['country'] = prompt_response(prompt, default='US')
            prompt = '\tState:'
            cert_data['state'] = prompt_response(prompt, mandatory=True)
            prompt = '\tLocation:'
            cert_data['location'] = prompt_response(prompt, mandatory=True)
            prompt = '\tOrganization:'
            cert_data['organization'] = prompt_response(prompt, mandatory=True)
            prompt = '\tOrganization Unit:'
            cert_data['organization-unit'] = prompt_response(prompt,mandatory=True)
            cert_data['common-name'] = get_platform_instance_name() + '-root-ca'
            data = {'C': cert_data.get('country'),
                    'ST': cert_data.get('state'),
                    'L': cert_data.get('location'),
                    'O': cert_data.get('organization'),
                    'OU': cert_data.get('organization-unit'),
                    'CN': cert_data.get('common-name')}
            crts.create_root_ca(overwrite=False, **data)
            copy(crts.cert_file(crts.root_ca_name),crts.cert_file(crts.trusted_ca_name))
        else:
            return 1
    
    print("Creating new web server certificate.")
    crts.create_signed_cert_files(name=MASTER_WEB + "-server", cert_type='server', ca_name=crts.root_ca_name, fqdn=get_hostname())
    return 0


def check_rmq_setup():
    global config_opts
    rmq_config = RMQConfig()
    if not os.path.exists(rmq_config.volttron_rmq_config):
        setup_rabbitmq_volttron('single', verbose, prompt=True, instance_name=None)
    _load_config()


def do_message_bus():
    global config_opts
    bus_type = None
    valid_bus = False
    while not valid_bus:
        prompt = 'What type of message bus (rmq/zmq)?'
        new_bus = prompt_response(prompt, default='zmq')
        valid_bus = is_valid_bus(new_bus)
        if valid_bus:
            bus_type = new_bus
        else:
            print("Message type is not valid. Valid entries are zmq or rmq.")

    if bus_type == 'rmq':
        if not is_rabbitmq_available():
            print("RabbitMQ has not been set up!")
            print("Please run scripts/rabbit_dependencies.sh and bootstrap --rabbitmq before running vcfg.")
            sys.exit()
            # print("Setting up now...")
            # set_dependencies_rmq()
            # print("Done!")

        # if not _check_dependencies_met('rabbitmq'):
        #     print("Rabbitmq dependencies not installed. Installing now...")
        #     set_dependencies("rabbitmq")
        #     print("Done!")
        check_rmq_setup()

    config_opts['message-bus'] = bus_type


def do_vip():
    global config_opts

    parsed = urlparse(config_opts.get('vip-address', 'tcp://127.0.0.1:22916'))
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
            if config_opts['message-bus'] == 'rmq':
                prompt = """
The rmq message bus has a backward compatibility 
layer with current zmq instances. What is the 
zmq bus's vip address?"""
            else:
                prompt = "What is the vip address?"

            new_vip_address = prompt_response(prompt, default=vip_address)
            valid_address = is_valid_url(new_vip_address, ['tcp'])
            if valid_address:
                vip_address = new_vip_address
            else:
                print("Address is not valid.")

        valid_port = False
        while not valid_port:
            prompt = 'What is the port for the vip address?'
            new_vip_port = prompt_response(prompt, default=vip_port)
            valid_port = is_valid_port(new_vip_port)
            if valid_port:
                vip_port = new_vip_port
            else:
                print("Port is not valid.")

        while vip_address.endswith('/'):
            vip_address = vip_address[:-1]

        attempted_address = '{}:{}'.format(vip_address, vip_port)
        if not _is_bound_already(attempted_address):
            available = True
        else:
            print('\nERROR: That address has already been bound to.')
    config_opts['vip-address'] = '{}:{}'.format(vip_address, vip_port)

def do_web_enabled_rmq(vhome):
    global config_opts

    # Full implies that it will have a port on it as well.  Though if it's
    # not in the address that means that we haven't set it up before.
    full_bind_web_address = config_opts.get('bind-web-address',
            'https://' + get_hostname())

    parsed = urlparse(full_bind_web_address)

    address_only = full_bind_web_address
    port_only = None
    if parsed.port is not None:
        address_only = parsed.scheme + '://' + parsed.hostname
        port_only = parsed.port
    else:
        port_only = 8443

    valid_address = False
    external_ip = None

    while not valid_address:
        new_external_ip = address_only
        valid_address = is_valid_url(new_external_ip, ['https'])
        if valid_address:
            external_ip = new_external_ip
    print("Web address set to: {}".format(external_ip))

    valid_port = False
    vc_port = None
    while not valid_port:
        prompt = 'What is the port for this instance?'
        new_vc_port = prompt_response(prompt, default=port_only)
        valid_port = is_valid_port(new_vc_port)
        if valid_port:
            vc_port = new_vc_port

    while external_ip.endswith("/"):
        external_ip = external_ip[:-1]

    parsed = urlparse(external_ip)

    config_opts['bind-web-address'] = '{}:{}'.format(external_ip, vc_port)


def do_web_enabled_zmq(vhome):
    global config_opts


    # Full implies that it will have a port on it as well.  Though if it's
    # not in the address that means that we haven't set it up before.
    full_bind_web_address = config_opts.get('bind-web-address',
            'https://' + get_hostname())

    parsed = urlparse(full_bind_web_address)

    address_only = full_bind_web_address
    port_only = None
    if parsed.port is not None:
        address_only = parsed.scheme + '://' + parsed.hostname
        port_only = parsed.port
    else:
        port_only = 8443

    valid_address = False
    external_ip = None

    while not valid_address:
        prompt = 'What is the protocol for this instance?'
        new_scheme = prompt_response(prompt, default=parsed.scheme)
        new_external_ip = new_scheme + '://' + parsed.hostname
        valid_address = is_valid_url(new_external_ip, ['http', 'https'])
        if valid_address:
            external_ip = new_external_ip
    print("Web address set to: {}".format(external_ip))

    valid_port = False
    vc_port = None
    while not valid_port:
        prompt = 'What is the port for this instance?'
        if new_scheme == 'http' and port_only == 8443:
            port_only = 8080
        new_vc_port = prompt_response(prompt, default=port_only)
        valid_port = is_valid_port(new_vc_port)
        if valid_port:
            vc_port = new_vc_port

    while external_ip.endswith("/"):
        external_ip = external_ip[:-1]

    parsed = urlparse(external_ip)

    config_opts['bind-web-address'] = '{}:{}'.format(external_ip, vc_port)

    if config_opts['message-bus'] == 'zmq' and parsed.scheme == "https":
        get_cert_and_key(vhome)


def do_web_agent():
    global config_opts
    volttron_home = get_home()
    _load_config()
    _update_config_file()
    if 'message-bus' not in config_opts:
        do_message_bus()
    if 'vip-address' not in config_opts:
        do_vip()
    _update_config_file()
    if 'bind-web-address' not in config_opts:
        if config_opts['message-bus'] == 'rmq':
            do_web_enabled_rmq(volttron_home)
        elif config_opts['message-bus'] == 'zmq':
            do_web_enabled_zmq(volttron_home)
    _update_config_file()


@installs(get_services_core("VolttronCentral"), 'vc')
def do_vc():
    do_web_agent()
    # resp = vc_config()

    print('Installing volttron central.')
    return {}


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
                'password': hashlib.sha512(password.encode('utf-8')).hexdigest(),
                'groups': ['admin']
            }
        }
    }

    return config


def get_cert_and_key(vhome):

    # Check for existing files first. If present and are valid ask if we are to use that

    master_web_cert = os.path.join(vhome, 'certificates/certs/', MASTER_WEB+"-server.crt")
    master_web_key = os.path.join(vhome, 'certificates/private/', MASTER_WEB + "-server.pem")
    cert_error = True

    if is_file_readable(master_web_cert, False) and is_file_readable(master_web_key, False):
        try:
            if certs.Certs.validate_key_pair(master_web_cert, master_web_key):
                print('\nThe following certificate and keyfile exists for web access over https: \n{}\n{}'.format(
                    master_web_cert,master_web_key))
                prompt = '\nDo you want to use these certificates for the web server?'
                if prompt_response(prompt, valid_answers=y_or_n, default='Y') in y:
                    config_opts['web-ssl-cert'] = master_web_cert
                    config_opts['web-ssl-key'] = master_web_key
                    cert_error = False
                else:
                    print('\nPlease provide the path to cert and key files. '
                          'This will overwrite existing files: \n{} and {}'.format(master_web_cert, master_web_key))
            else:
                print("Existing key pair is not valid.")
        except RuntimeError as e:
            print(e)
            pass



    # Either are there no valid existing certs or user decided to overwrite the existing file.
    # Prompt for new files
    while cert_error:
        prompt = "Would you like to generate a new web certificate?"
        if prompt_response(prompt, valid_answers=y_or_n, default='Y') in n:
            while True:
                prompt = 'Enter the SSL certificate public key file:'
                cert_file = prompt_response(prompt, mandatory=True)
                if is_file_readable(cert_file):
                    break
                else:
                    print("Unable to read file {}".format(cert_file))
            while True:
                prompt = \
                    'Enter the SSL certificate private key file:'
                key_file = prompt_response(prompt, mandatory=True)
                if is_file_readable(key_file):
                    break
                else:
                    print("Unable to read file {}".format(key_file))
            try:
                if certs.Certs.validate_key_pair(cert_file, key_file):
                    cert_error = False
                    config_opts['web-ssl-cert'] = cert_file
                    config_opts['web-ssl-key'] = key_file
                else:
                    print("ERROR:\n Given public key and private key do not "
                          "match or is invalid. public and private key "
                          "files should be PEM encoded and private key "
                          "should use RSA encryption")
            except RuntimeError:
                print("ERROR:\n Given public key and private key do not "
                      "match or is invalid. public and private key "
                      "files should be PEM encoded and private key "
                      "should use RSA encryption")
        else:
            cert_error = _create_web_certs()
            if not cert_error:
                master_web_cert = os.path.join(vhome, 'certificates/certs/',
                        MASTER_WEB+"-server.crt")
                master_web_key = os.path.join(vhome, 'certificates/private/', 
                        MASTER_WEB + "-server.pem")
                config_opts['web-ssl-cert'] = master_web_cert
                config_opts['web-ssl-key'] = master_web_key


def is_file_readable(file_path, log=True):
    file_path = os.path.expanduser(os.path.expandvars(file_path))
    if os.path.exists(file_path) and os.access(file_path, os.R_OK):
        return True
    else:
        if log:
            print("\nInvalid file path. Path does not exists or is not readable.")
        return False


@installs(get_services_core("VolttronCentralPlatform"), 'vcp')
def do_vcp():
    global config_opts
    is_vc = False
    vctl_list_process = Popen(['vctl', 'list'], env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    vctl_list = vctl_list_process.communicate()
    vctl_list_output = ''.join([v.decode('utf-8') for v in vctl_list])

    # Default instance name to the vip address.
    instance_name = config_opts.get('instance-name',
                                    'volttron1')
    instance_name = instance_name.strip('"')

    valid_name = False
    while not valid_name:
        prompt = 'What is the name of this instance?'
        new_instance_name = prompt_response(prompt, default=instance_name)
        if new_instance_name:
            valid_name = True
            instance_name = new_instance_name
    config_opts['instance-name'] = '"{}"'.format(instance_name)

    try:
        vc_address = config_opts['volttron-central-address']
        no_vc_address = False
    except KeyError:
        no_vc_address = True

    try:
        if no_vc_address:
            vc_address = config_opts['bind-web-address']
        if VOLTTRON_CENTRAL in vctl_list_output:
            is_vc = True
        
    except KeyError:
        vc_address = config_opts.get('volttron-central-address',
                                     config_opts.get('bind-web-address',
                                     'https://' + get_hostname()))
    if not is_vc:
        parsed = urlparse(vc_address)
        address_only = vc_address
        port_only = None
        if parsed.port is not None:
            address_only = parsed.scheme + '://' + parsed.hostname
            port_only = parsed.port
        else:
            port_only = 8443

        valid_vc = False
        while not valid_vc:
            prompt = "What is the hostname for volttron central?"
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

    else:
        new_address = vc_address
        print('Volttron central address set to {}'.format(new_address))

    config_opts['volttron-central-address'] = new_address

    return {}


@installs(get_services_core("SQLHistorian"), 'platform_historian',
          identity='platform.historian')
def do_platform_historian():
    datafile = 'platform.historian.sqlite'
    config = {
        'connection': {
            'type': 'sqlite',
            'params': {
                'database': datafile
            }
        }
    }
    return config


def add_fake_device_to_configstore():
    prompt = 'Would you like to install a fake device on the master driver?'
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


def confirm_volttron_home():
    global prompt_vhome
    volttron_home = get_home()
    if prompt_vhome:
        print('\nYour VOLTTRON_HOME currently set to: {}'.format(volttron_home))
        prompt = '\nIs this the volttron you are attempting to setup?'
        if not prompt_response(prompt, valid_answers=y_or_n, default='Y') in y:
            print(
                '\nPlease execute with VOLTRON_HOME=/your/path volttron-cfg to '
                'modify VOLTTRON_HOME.\n')
            sys.exit(1)


def wizard():
    global config_opts
    """Routine for configuring an installed volttron instance.

    The function interactively sets up the instance for working with volttron
    central and the discovery service.
    """

    # Start true configuration here.
    volttron_home = get_home()
    confirm_volttron_home()
    _load_config()
    _update_config_file()
    do_message_bus()
    do_vip()
    _update_config_file()

    prompt = 'Is this instance web enabled?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        if not _check_dependencies_met('web'):
            print("Web dependencies not installed. Installing now...")
            set_dependencies('web')
            print("Done!")
        if config_opts['message-bus'] == 'rmq':
            do_web_enabled_rmq(volttron_home)
        elif config_opts['message-bus'] == 'zmq':
            do_web_enabled_zmq(volttron_home)
        _update_config_file()
        # TODO: Commented out so we don't prompt for installing vc or vcp until they
        # have been figured out totally for python3

        prompt = 'Is this an instance of volttron central?'
        response = prompt_response(prompt, valid_answers=y_or_n, default='N')
        if response in y:
            do_vc()
            if _is_agent_installed('vc'):
                print("VC admin and password are set up using the admin web interface.\n"
                      "After starting VOLTTRON, please go to {} to complete the setup.".format(
                        os.path.join(config_opts['bind-web-address'], "admin", "login.html")
                        ))
    # TODO: Commented out so we don't prompt for installing vc or vcp until they
    # have been figured out totally for python3

    prompt = 'Will this instance be controlled by volttron central?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='Y')
    if response in y:
        if not _check_dependencies_met("drivers") or not _check_dependencies_met("web"):
            print("VCP dependencies not installed. Installing now...")
            if not _check_dependencies_met("drivers"):
                set_dependencies("drivers")
            if not _check_dependencies_met("web"):
                set_dependencies("web")
            print("Done!")
        do_vcp()

    prompt = 'Would you like to install a platform historian?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_platform_historian()
    prompt = 'Would you like to install a master driver?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        if not _check_dependencies_met("drivers"):
            print("Driver dependencies not installed. Installing now...")
            set_dependencies("drivers")
            print("Done!")
        do_master_driver()

    prompt = 'Would you like to install a listener agent?'
    response = prompt_response(prompt, valid_answers=y_or_n, default='N')
    if response in y:
        do_listener()

    print('Finished configuration!\n')
    print('You can now start the volttron instance.\n')
    print('If you need to change the instance configuration you can edit')
    print('the config file is at {}/config\n'.format(volttron_home))


def process_rmq_inputs(args, instance_name=None):
    if not is_rabbitmq_available():
        raise RuntimeError("Rabbitmq Dependencies not installed please run python bootstrap.py --rabbitmq")
    confirm_volttron_home()
    if len(args) == 2:
        vhome = get_home()
        if args[0] == 'single':
            vhome_config = os.path.join(vhome, 'rabbitmq_config.yml')
        elif args[0] == 'federation':
            vhome_config = os.path.join(vhome, 'rabbitmq_federation_config.yml')
        elif args[0] == 'shovel':
            vhome_config = os.path.join(vhome, 'rabbitmq_shovel_config.yml')
        else:
            print("Invalid argument. \nUsage: vcf --rabbitmq single|federation|shovel "
                  "[optional path to rabbitmq config yml]")
            sys.exit(1)
        if args[1] != vhome_config:
            if not os.path.exists(vhome):
                os.makedirs(vhome, 0o755)
            copy(args[1], vhome_config)
        setup_rabbitmq_volttron(args[0], verbose, instance_name=instance_name)
    else:
        setup_rabbitmq_volttron(args[0], verbose, prompt=True, instance_name=instance_name)


def main():
    global verbose, prompt_vhome
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--vhome', help="Path to volttron home")
    parser.add_argument('--instance-name', dest='instance_name', help="Name of this volttron instance")

    group = parser.add_mutually_exclusive_group()

    agent_list = '\n\t' + '\n\t'.join(sorted(available_agents.keys()))
    group.add_argument('--list-agents', action='store_true', dest='list_agents',
                       help='list configurable agents{}'.format(agent_list))

    group.add_argument('--agent', nargs='+',
                        help='configure listed agents')
    group.add_argument('--rabbitmq', nargs='+',
                       help='Configure rabbitmq for single instance, '
                            'federation, or shovel either based on '
                            'configuration file in yml format or providing '
                            'details when prompted. \nUsage: vcfg --rabbitmq '
                            'single|federation|shovel [rabbitmq config '
                            'file]')
    group.add_argument('--secure-agent-users', action='store_true', dest='secure_agent_users',
                       help='Require that agents run with their own users (this requires running '
                            'scripts/secure_user_permissions.sh as sudo)')

    args = parser.parse_args()
    verbose = args.verbose
    prompt_vhome = True
    if args.vhome:
        set_home(args.vhome)
        prompt_vhome = False
    # if not args.rabbitmq or args.rabbitmq[0] in ["single"]:
    fail_if_instance_running()
    fail_if_not_in_src_root()
    atexit.register(_cleanup_on_exit)
    _load_config()
    if args.instance_name:
        _update_config_file(instance_name=args.instance_name)
    if args.list_agents:
        print("Agents available to configure:{}".format(agent_list))
    elif args.rabbitmq:
        if len(args.rabbitmq) > 2:
            print("vcfg --rabbitmq can at most accept 2 arguments")
            parser.print_help()
            sys.exit(1)
        elif args.rabbitmq[0] not in ['single', 'federation', 'shovel']:
            print("Usage: vcf --rabbitmq single|federation|shovel "
                  "[optional path to rabbitmq config yml]")
            parser.print_help()
            sys.exit(1)
        elif len(args.rabbitmq) == 2 and not os.path.exists(args.rabbitmq[1]):
            print("Invalid rabbitmq configuration file path.")
            parser.print_help()
            sys.exit(1)
        else:
            process_rmq_inputs(args.rabbitmq, args.instance_name)
    elif args.secure_agent_users:
        config_opts['secure-agent-users'] = args.secure_agent_users
        _update_config_file()
    elif not args.agent:
        wizard()

    else:
        # Warn about unknown agents
        valid_agents = False
        for agent in args.agent:
            if agent not in available_agents:
                print('"{}" not configurable with this tool'.format(agent))
            else:
                valid_agents = True
        if valid_agents:
            confirm_volttron_home()

        # Configure agents
        for agent in args.agent:
            try:
                available_agents[agent]()
            except KeyError:
                pass
