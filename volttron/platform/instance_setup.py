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

import os as _os
import hashlib
import tempfile

from gevent import subprocess
from gevent.subprocess import Popen, check_call
from zmq.utils import jsonapi

from . import get_home
from volttron.platform.auth import AuthEntry, AuthFile


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
        # No validation or tthe response was in the list of values.
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
    process = Popen(cmdargs, env=_os.environ, stdout=subprocess.PIPE,
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

#
# def _enable_discovery(address_port):
#     """ Enable discovery will autostart when the volttron instance starts.
#
#     Puts the port and binding ip address that should be bound to in the root
#     directory of VOLTTRON_HOME.
#     """
#     discovery_file = _os.path.join(_os.environ['VOLTTRON_HOME'], 'DISCOVERY')
#     with open(discovery_file, 'w') as df:
#         df.write(address_port)






def _start_platform():
    cmd = ['volttron', '--developer-mode']

    pid = Popen(cmd, env=_os.environ.copy(), stdout=subprocess.PIPE,
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
    cfgfile = _os.path.join(get_home(), 'config')
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
    t = ("Enter volttron central admin user name:",)
    username = prompt_response(t)
    t = ("Enter volttron central admin password:",)
    password = prompt_response(t)
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


def _install_platform_historian(autostart):
    datafile = _os.path.join(get_home(), "data", "platform.historian.sqlite")
    config = {
        "agentid": "sqlhistorian-sqlite",
        "identity": "platform.historian",
        "connection": {
            "type": "sqlite",
            "params": {
                "database": datafile
            }
        }
    }
    _install_agent(autostart, "services/core/SQLHistorian", config,
                   "platform_historian")



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
    volttron_home = get_home()

    y_or_n = ('Y', 'N', 'y', 'n')
    y = ('Y', 'y')
    n = ('N', 'n')
    print('\nYour VOLTTRON_HOME currently set to: {}'.format(volttron_home))
    t = ('\nIs this the volttron you are attempting to setup? [Y]',
         y_or_n,
         'Y')
    if not prompt_response(t) in y:
        print(
            '\nPlease execute with VOLTRON_HOME=/your/path volttron-cfg to '
            'modify VOLTTRON_HOME.\n')
        return

    _os.environ['VOLTTRON_HOME'] = volttron_home
    if not _os.path.exists(volttron_home):
        _os.makedirs(volttron_home, 0o755)

    # If yes then we know we at least want the platform agent installed.
    t = ('Will this instance register with a volttron central? ('
         'either locally or remotely) [Y]: ', y_or_n, 'Y')
    connect_to_vc = prompt_response(t) in y

    # Install volttron central?
    t = ('Is this instance a volttron central? [N]: ', y_or_n, 'N')
    is_vc = prompt_response(t) in y

    if is_vc:
        prompt = '''
In order for external clients to connect to volttron central or the instance
itself, the instance must bind to a tcp address.  If testing this can be an
internal address such as 127.0.0.1.

Note: the assumption is that the discovery address for volttron central and
      the vip address will be the same.  If not one can change the address
      in the config file after competing this configuration.

Please enter the external ipv4 address for this instance? [127.0.0.1]: '''
        t = (prompt, None, '127.0.0.1')
        external_ip = prompt_response(t)
    else:
        prompt = 'Please enter the external ipv4 address for this instance? '\
                 '[127.0.0.1]: '
        t = (prompt, None, '127.0.0.1')
        external_ip = prompt_response(t)

    vc_port = None
    if is_vc:
        t = ('What is the port for volttron central? [8080]: ', None, '8080')
        vc_port = prompt_response(t)

    t = ('What is the instance port for the vip address? [22916]: ', None,
         '22916')
    instance_port = prompt_response(t)

    instance_name = 'Unnamed Instance'
    if connect_to_vc:
        t = ('Enter the name of this instance: ',)
        instance_name = prompt_response(t)

        t = ('Which IP addresses are allowed to discover this instance? '
             '[/127.*/] ', None, '/127.*/')
        ip_allowed_to_discover = prompt_response(t)
        AuthFile().add(AuthEntry(address=external_ip,
                                 credentials='/CURVE:.*/'))

    do_vc_autostart = False
    if is_vc:
        t = ('Should volttron central autostart (Y/N)? [Y]: ', y_or_n, 'Y')
        do_vc_autostart = prompt_response(t) in y

    do_platform_autostart = False
    other_vc_address = None
    other_vc_port = None
    if connect_to_vc:
        t = ('Should volttron central platform autostart (Y/N)? [Y]: ',
             y_or_n, 'Y')
        do_platform_autostart = prompt_response(t) in y

        if not is_vc:
            t = ('Address of the volttron central to connect to? '
                 '[127.0.0.1]: ',
                 None, '127.0.0.1')

            other_vc_address = prompt_response(t)
            should_resolve = True
            first = True
            t = ('Port of volttron central? [8080] ', None, '8080')
            other_vc_port = prompt_response(t)

            while not _resolvable(other_vc_address, other_vc_port) \
                    and should_resolve:
                print("Couldn't resolve {}:{}".format(other_vc_address,
                                                      other_vc_port))
                t2 = (
                    '\nShould volttron central be resolvable now? [Y] ',
                    y_or_n, 'Y')
                if first:
                    should_resolve = prompt_response(t2) in ('y', 'Y')
                    first = False

                if should_resolve:
                    t = ('\nAddress of volttron central? ',)
                    other_vc_address = prompt_response(t)
                    t = ('\nPort of volttron central? ',)
                    other_vc_port = prompt_response(t)

    external_vip_address = "tcp://{}:{}".format(external_ip,
                                                instance_port)

    bind_web_address = None
    if is_vc:
        bind_web_address = "http://{}:{}".format(external_ip,
                                                 vc_port)

    vc_web_address = None
    if connect_to_vc and not is_vc:
        vc_web_address = "http://{}:{}".format(other_vc_address,
                                               other_vc_port)

    with open(_os.path.join(volttron_home, 'config'), 'w') as fout:
        fout.write('[volttron]\n')
        fout.write('vip-address={}\n'.format(external_vip_address))
        if is_vc:
            fout.write('bind-web-address={}\n'.format(bind_web_address))
        if connect_to_vc and not is_vc:
            fout.write('volttron-central-address={}|{}\n'.format(
                instance_name,
                vc_web_address
            ))

    _start_platform()

    if is_vc:
        _install_vc(do_vc_autostart)

    if connect_to_vc:
        print('Installing volttron central platform (VCP)')
        _install_agent(do_platform_autostart,
                       'services/core/VolttronCentralPlatform',
                       {"agentid": "volttroncentralplatform"}, "vcp")

    t = ('\nShould install SQLITE platform historian? [N]', y_or_n, n)
    install_platform_historian = prompt_response(t) in y

    historian_autostart = False
    if install_platform_historian:
        t = ('\nShould historian agent autostart(Y/N)? [Y] ', y_or_n, 'Y')
        historian_autostart = prompt_response(t) in y
        _install_platform_historian(historian_autostart)

    _shutdown_platform()
    print('Finished configuration\n')
    print('You can now start you volttron instance.\n')
    print('If you need to change the instance configuration you can edit')
    print('the config file at {}/{}\n'.format(volttron_home, 'config'))

