# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
from ConfigParser import ConfigParser
from collections import defaultdict
import hashlib
import os as os
import urlparse
import tempfile

from gevent import subprocess
from gevent.subprocess import Popen, check_call
from zmq.utils import jsonapi
from zmq import green as zmq

from . import get_home
from volttron.platform.auth import AuthEntry, AuthFile

# Global configuration options.  Must be key=value strings.  No cascading
# structure so that we can easily create/load from the volttron config file
# if it exists.
config_opts = {}
agent_config_opts = defaultdict(dict)

# Yes or no answers to questions.
y_or_n = ('Y', 'N', 'y', 'n')
y = ('Y', 'y')
n = ('N', 'n')


def _load_config():
    """ Loads the config file if the path exists.  """
    path = os.path.join(get_home(), "config")
    if os.path.exists(path):
        parser = ConfigParser()
        parser.read(path)
        options = parser.options("volttron")
        for option in options:
            config_opts[option] = parser.get("volttron", option)


def prompt_response(inputs):
    """ Prompt the user for answers.

    The inputs argument is a list or tuple with the following elements:
    [0] - The prompt to the user
    [1] - (Optional) A valid selection of responses
    [2] - (Optional) Default value if the user just types enter.
    """
    while True:
        resp = raw_input(inputs[0])
        if resp == '' and len(inputs) == 3:
            return inputs[2]
        # No validation or the response was in the list of values.
        if len(inputs) == 1 or inputs[1] is None or resp in inputs[1]:
            return resp
        else:
            print('Invalid response proper responses are: ')
            print(inputs[1])


def _cmd(cmdargs):
    """ Executes the passed command.
.
    @:param: list:
        A list of arguments that should be passed to Popen.
    """
    print(cmdargs)
    process = Popen(cmdargs, env=os.environ, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
    process.wait()


def _install_agents(install_vc, install_platform, install_historian):
    if install_vc[0]:
        print('Installing volttron central')
        cfg_file = 'services/core/VolttronCentral/config'
        _cmd(['volttron-ctl', 'remove', '--tag', 'vc', '--force'])
        _cmd(['scripts/core/pack_install.sh',
              'services/core/VolttronCentral', cfg_file, 'vc'])
        if install_vc[1]:
            _cmd(['volttron-ctl', 'enable', '--tag', 'vc'])

    if install_platform[0]:
        print('Installing platform...')
        cfg_file = 'services/core/VolttronCentralPlatform/config'
        _cmd(['volttron-ctl', 'remove', '--tag', 'platform', '--force'])
        _cmd(['scripts/core/pack_install.sh',
           'services/core/VolttronCentralPlatform', cfg_file, 'platform'])
        if install_platform[1]:
            _cmd(['volttron-ctl', 'enable', '--tag', 'platform'])

    if install_historian[0]:
        print('Installing historian...')
        cfg_file = 'services/core/SQLHistorian/config.sqlite.platform.historian'
        _cmd(['volttron-ctl', 'remove', '--tag', 'historian', '--force'])
        _cmd(['scripts/core/pack_install.sh',
          'services/core/SQLHistorian', cfg_file, 'historian'])
        if install_historian[1]:
            _cmd(['volttron-ctl', 'enable', '--tag', 'historian'])
        
def _is_bound_already(address):
    # Create a UDS socket
    context = zmq.Context()
    dealer_sck = context.socket(zmq.DEALER)
    already_bound = False
    try:
        dealer_sck.bind(address)
    except zmq.ZMQError:
        already_bound = True
    finally:
        dealer_sck.close()
    return already_bound


def _is_instance_running():

    instance_running = False
    if os.path.exists(get_home()):
        # Create a UDS socket
        context = zmq.Context()
        dealer_sck = context.socket(zmq.DEALER)

        ipc_address = "ipc://@{}/run/vip.socket".format(get_home())
        try:
            dealer_sck.bind(ipc_address)
        except zmq.ZMQError:
            instance_running = True
        finally:
            dealer_sck.close()

    return instance_running


def _start_platform():
    cmd = ['volttron', '--developer-mode', '-vv']

    pid = Popen(cmd, env=os.environ.copy(), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
    print('Configuring instance...')
    return pid


def _shutdown_platform():
    print('Shutting down platform...')
    _cmd(['volttron-ctl', 'shutdown', '--platform'])


def _make_configuration(external_uri, bind_web_address,
                        volttron_central=None):
    import ConfigParser as configparser  # python3 has configparser

    config = configparser.ConfigParser()
    config.add_section('volttron')
    config.set('volttron', 'vip-address', external_uri)
    config.set('volttron', 'bind-web-address', bind_web_address)
    if volttron_central:
        config.set('volttron', 'volttron-central-address',
                   volttron_central)
    cfgfile = os.path.join(get_home(), 'config')
    with open(cfgfile, 'w') as cf:
        config.write(cf)


def _resolvable(uri, port):
    import requests
    try:
        uri_and_port = "{}:{}".format(uri, port)
        discovery_uri = "http://" + uri_and_port + "/discovery/"
        req = requests.request('GET', discovery_uri)
    except:
        return False
    return True


def _install_agent(autostart, agent_dir, config, tag):
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
    if autostart:
         _cmd(['volttron-ctl', 'enable', '--tag', tag])


def _install_vc(autostart):
    username = ""
    while not username:
        t = ("Enter volttron central admin user name: ",)
        username = prompt_response(t)
        if not username:
            print("ERROR Invalid username")
    password = ""
    while not password:
        t = ("Enter volttron central admin password: ",)
        password = prompt_response(t)
        if not password:
            print("ERROR: Invalid password")

    config = {
        "users": {
            username: {
                "password": hashlib.sha512(password).hexdigest(),
                "groups": [
                    "admin"
                ]
            }
        }
    }

    print("Installing volttron central(VC)")
    _install_agent(autostart, "services/core/VolttronCentral", config, 'vc')


def _install_vcp(autostart):
    config = {}

    print("Installing volttron central platform(VCP)")
    _install_agent(autostart, "services/core/VolttronCentralPlatform", config,
                   'vcp')


def _install_platform_historian(autostart):
    os.environ["AGENT_VIP_IDENTITY"]="platform.historian"
    datafile = os.path.join(get_home(), "data", "platform.historian.sqlite")
    config = {
        "agentid": "sqlhistorian-sqlite",
        "connection": {
            "type": "sqlite",
            "params": {
                "database": datafile
            }
        }
    }
    _install_agent(autostart, "services/core/SQLHistorian", config,
                   "platform_historian")
    os.environ.pop("AGENT_VIP_IDENTITY")

def _install_config_file():
    path = os.path.join(get_home(), "config")

    config = ConfigParser()
    config.add_section("volttron")

    for k, v in config_opts.items():
        config.set('volttron', k, v)

    with open(path, 'w') as configfile:
        config.write(configfile)


def is_valid_url(test, accepted_schemes):
    if test is None:
        return False
    parsed = urlparse.urlparse(test)
    if parsed.scheme not in accepted_schemes:
        return False
    if not parsed.hostname:
        return False

    return True


def is_valid_port(test):
    try:
        value = int(test)
    except ValueError:
        return False

    return test > 0 and test < 65535


def do_platform_historian():
    prompt = "Would you like to install a platform historian? [N]: "
    resp = prompt_response((prompt, y_or_n, 'N'))

    if resp in n:
        return False
    return False, _install_platform_historian


def do_vip():
    global config_opts

    parsed = urlparse.urlparse(config_opts.get("volttron", "vip-address"))
    vip_address = None
    if parsed.hostname is not None and parsed.scheme is not None:
        vip_address = parsed.scheme + "://" + parsed.hostname
        vip_port = parsed.port
    else:
        vip_address = "tcp://127.0.0.1"
        vip_port = 22916

    available = False
    while not available:
        valid_address = False
        while not valid_address:
            prompt = 'What is the external instance ipv4 address? '
            prompt += '[{}]: '.format(
                vip_address
            )

            new_vip_address = prompt_response((prompt, None, vip_address))
            valid_address = is_valid_url(new_vip_address, ['tcp'])
            if valid_address:
                vip_address = new_vip_address

        valid_port = False
        while not valid_port:
            prompt = 'What is the instance port for the vip address? [{}]: '.format(
                vip_port
            )
            new_vip_port = prompt_response((prompt, None, vip_port))
            valid_port = is_valid_port(new_vip_port)
            if valid_port:
                vip_port = new_vip_port

        while vip_address.endswith("/"):
            vip_address = vip_address[:-1]

        attempted_address = "{}:{}".format(vip_address, vip_port)
        if not _is_bound_already(attempted_address):
            available = True
        else:
            print('\nERROR: That address has already been bound to.')
    config_opts['vip-address'] = "{}:{}".format(vip_address, vip_port)
    _install_config_file()


def do_vc():
    global config_opts

    # Install volttron central?
    t = ('Is this instance a volttron central? [N]: ', y_or_n, 'N')
    is_vc = prompt_response(t) in y

    if not is_vc:
        return False

    # Full implies that it will have a port on it as well.  Though if it's
    # not in the address that means that we haven't set it up before.
    full_bind_web_address = config_opts.get(
        'bind-web-address', "http://127.0.0.1")

    parsed = urlparse.urlparse(full_bind_web_address)

    address_only = full_bind_web_address
    port_only = None
    if parsed.port is not None:
        address_only = parsed.scheme + "://" + parsed.hostname
        port_only = parsed.port
    else:
        port_only = 8080


    prompt = '''
In order for external clients to connect to volttron central or the instance
itself, the instance must bind to a tcp address.  If testing this can be an
internal address such as 127.0.0.1.
'''
    print(prompt)
    valid_address = False
    external_ip = None
    while not valid_address:
        prompt = "Please enter the external ipv4 address for this instance? "
        prompt += "[{}]: ".format(address_only)
        t = (prompt, None, address_only)
        new_external_ip = prompt_response(t)
        valid_address = is_valid_url(new_external_ip, ["http", "https"])
        if valid_address:
            external_ip = new_external_ip

    valid_port = False
    vc_port = None
    while not valid_port:
        vc_port = None

        prompt = 'What is the port for volttron central? [{}]: '.format(
            port_only
        )
        t = (prompt, None, port_only)
        new_vc_port = prompt_response(t)
        valid_port = is_valid_port(new_vc_port)
        if valid_port:
            vc_port = new_vc_port

    while external_ip.endswith("/"):
        external_ip = external_ip[:-1]

    config_opts['bind-web-address'] = "{}:{}".format(external_ip, vc_port)

    # TODO Add protecction of vc here.

    return False, _install_vc


def do_vcp():
    global config_opts

    prompt = "Will this instance be controlled by volttron central? [Y]: "
    resp = prompt_response((prompt, y_or_n, 'Y'))
    has_vcp = resp in y
    if not has_vcp:
        return

    # Default instance name to the vip address.
    instance_name = config_opts.get("instance-name",
                                    config_opts.get('vip-address'))

    valid_name = False
    while not valid_name:
        prompt = 'Enter the name of this instance. [{}]: '.format(
            instance_name
        )
        t = (prompt, None, instance_name)
        new_instance_name = prompt_response(t)
        if new_instance_name:
            valid_name = True
            instance_name = new_instance_name
    config_opts['instance-name'] = instance_name

    vc_address = config_opts.get("volttron-central-address",
                                 config_opts.get("bind-web-address"))

    valid_vc = False
    while not valid_vc:
        prompt = "Enter volttron central's web address [{}]: ".format(
            vc_address
        )
        new_vc_address = prompt_response((prompt, None, vc_address))
        valid_vc = is_valid_url(new_vc_address, ['http', 'https'])
        if valid_vc:
            vc_address = new_vc_address
    config_opts['volttron-central-address'] = vc_address

    return False, _install_vcp

    # TODO Add protecction of vc here.
#
#     t = ('Which IP addresses are allowed to discover this instance? '
#          '[/127.*/] ', None, '/127.*/')
#     ip_allowed_to_discover = prompt_response(t)
#     AuthFile().add(AuthEntry(address=external_ip,
#                              credentials='/CURVE:.*/'))
#
# do_vc_autostart = False
# if is_vc:
#     t = ('Should volttron central autostart (Y/N)? [Y]: ', y_or_n, 'Y')
#     do_vc_autostart = prompt_response(t) in y
#
# do_platform_autostart = False
# other_vc_address = None
# other_vc_port = None
# if connect_to_vc:
#     t = ('Should volttron central platform autostart (Y/N)? [Y]: ',
#          y_or_n, 'Y')
#     do_platform_autostart = prompt_response(t) in y
#
#     if not is_vc:
#         t = ('Address of the volttron central to connect to? '
#              '[127.0.0.1]: ',
#              None, '127.0.0.1')
#
#         other_vc_address = prompt_response(t)
#         should_resolve = True
#         first = True
#         t = ('Port of volttron central? [8080]: ', None, '8080')
#         other_vc_port = prompt_response(t)
#
#         while not _resolvable(other_vc_address, other_vc_port) \
#                 and should_resolve:
#             print("Couldn't resolve {}:{}".format(other_vc_address,
#                                                   other_vc_port))
#             t2 = (
#                 '\nShould volttron central be resolvable now? [Y]: ',
#                 y_or_n, 'Y')
#             if first:
#                 should_resolve = prompt_response(t2) in ('y', 'Y')
#                 first = False
#
#             if should_resolve:
#                 t = ('\nAddress of volttron central? []: ',)
#                 other_vc_address = prompt_response(t)
#                 t = ('\nPort of volttron central? []: ',)
#                 other_vc_port = prompt_response(t)
#
# external_vip_address = "tcp://{}:{}".format(external_ip,
#                                             instance_port)


def _explain_discoverable():
    discoverability = """
A platform is discoverable if it responds to an http request /discovery/.
The ip address and port are used to hook up a volttron central instance and
instances in the field.  Though this is not required to register a field
instance with volttron central, it does make adding additional platforms
easier.

NOTE: The instances does not have to be discoverable after the instance is
      registered with volttron central.
"""
    print(discoverability)


def setup_instance():
    """ Routine for configuring an insalled volttron instance.

    The function interactively sets up the instance for working with volttron
    central and the discovery service.
    """
    if _is_instance_running():
        print("""
The current instance is running.  In order to configure an instance it cannot
be running.  Please execute:

    volttron-ctl shutdown --platform

to stop the instance.
""")
        return

    # Start true configuration here.
    volttron_home = get_home()

    # Load config if it exists.
    _load_config()

    print('\nYour VOLTTRON_HOME currently set to: {}'.format(volttron_home))
    t = ('\nIs this the volttron you are attempting to setup? [Y]: ',
         y_or_n,
         'Y')
    if not prompt_response(t) in y:
        print(
            '\nPlease execute with VOLTRON_HOME=/your/path volttron-cfg to '
            'modify VOLTTRON_HOME.\n')
        return

    os.environ['VOLTTRON_HOME'] = volttron_home
    first_time = False
    if not os.path.exists(volttron_home):
        first_time = True
        os.makedirs(volttron_home, 0o755)


#     prompt = """
# volttron-cfg has two modes a wizard mode that walks you through settup of an
# instance or a menu mode where you can pick what to install on the instance.
# """
#     p = "Would you like to go through the setup wizard? [Y]: "
#     wizardmode = prompt_response(p, y_or_n, 'Y')

    wizardmode = 'Y'
    if wizardmode in y:
        # no installation required with vip so just do the setup of that
        # address first.
        do_vip()

        # Returns either a function or False
        vc_response = do_vc()

        # Function or False
        vcp_response = do_vcp()

        historian_response = do_platform_historian()

        stack = [vc_response, vcp_response, historian_response]

        _install_config_file()
        _start_platform()
        # Loop over the returned values and call them one by one.
        for function in stack:
            if function:
                # All functions are should have a autostart as the only
                # parameter to install.
                function[1](function[0])
        _shutdown_platform()


    # instance_port = prompt_response(t)
    #
    #
    # bind_web_address = None
    # if is_vc:
    #     bind_web_address = "http://{}:{}".format(external_ip,
    #                                              vc_port)
    #
    # vc_web_address = None
    # if connect_to_vc and not is_vc:
    #     vc_web_address = "http://{}:{}".format(other_vc_address,
    #                                            other_vc_port)
    #
    # with open(os.path.join(volttron_home, 'config'), 'w') as fout:
    #     fout.write('[volttron]\n')
    #     fout.write('vip-address={}\n'.format(external_vip_address))
    #     if is_vc:
    #         fout.write('bind-web-address={}\n'.format(bind_web_address))
    #     if connect_to_vc and not is_vc:
    #         fout.write('volttron-central-address={}|{}\n'.format(
    #             instance_name,
    #             vc_web_address
    #         ))
    #
    # _start_platform()
    #
    # if is_vc:
    #     _install_vc(do_vc_autostart)
    #
    # if connect_to_vc:
    #     print('Installing volttron central platform (VCP)')
    #     _install_agent(do_platform_autostart,
    #                    'services/core/VolttronCentralPlatform',
    #                    {"agentid": "volttroncentralplatform"}, "vcp")
    #
    # t = ('\nShould install SQLITE platform historian? [N]: ', y_or_n, n)
    # install_platform_historian = prompt_response(t) in y
    #
    # historian_autostart = False
    # if install_platform_historian:
    #     t = ('\nShould historian agent autostart(Y/N)? [Y]: ', y_or_n, 'Y')
    #     historian_autostart = prompt_response(t) in y
    #     _install_platform_historian(historian_autostart)
    #
    # _shutdown_platform()
    print('Finished configuration\n')
    print('You can now start you volttron instance.\n')
    print('If you need to change the instance configuration you can edit')
    print('the config file at {}/{}\n'.format(volttron_home, 'config'))

