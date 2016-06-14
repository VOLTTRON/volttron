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
from gevent import subprocess
from gevent.subprocess import Popen, check_call
from . import get_home

from volttron.platform.auth import AuthEntry, AuthFile


def expandall(string):
    return _os.path.expanduser(_os.path.expandvars(string))


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

    Copies the environment in order to allow modifications in the actual
    callee.
    @:param: list:
        A list of arguments that should be passed to Popen.
    """
    environ = _os.environ.copy()
    process = Popen(cmdargs, env=environ, stdout=subprocess.PIPE,
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
    volttron_home = _os.path.normpath(expandall(
        _os.environ.get('VOLTTRON_HOME', '~/.volttron')))
    _os.environ['VOLTTRON_HOME'] = volttron_home
    if not _os.path.exists(volttron_home):
        _os.makedirs(volttron_home, 0o755)

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
    t = ('\nIs this instance discoverable (Y/N)? [N] ', y_or_n, 'N')
    _explain_discoverable()
    is_discoverable = prompt_response(t) in y

    if is_discoverable:
        t = ('\nWhat is the external ipv4 address for this instance? '
             '[127.0.0.1]: ', None, '127.0.0.1')
        external_ip = prompt_response(t)
        t = ('What is the vip port this instance? [22916] ',)
        vip_port = prompt_response(t)
        if not vip_port:
            vip_port = 22916

        t = ('\nWhat is the port for discovery? [8080] ',)
        external_port = prompt_response(t)
        if not external_port:
            external_port = 8080
        t = (
            '\nWhich IP addresses are allowed to discover this instance? '
            '[/127.*/] ', None, '/127.*/')
        ip_allowed_to_discover = prompt_response(t)
        AuthFile().add(AuthEntry(address=ip_allowed_to_discover,
                                 credentials='/CURVE:.*/'))

        t = ('\nIs this instance a volttron central (Y/N)? [N] ', y_or_n, 'N')
        do_install_vc = prompt_response(t) in y
        do_vc_autostart = True
        do_platform_autostart = True
        if do_install_vc:
            t = ('\nShould volttron central autostart(Y/N)? [Y] ',
                 y_or_n, 'Y')
            do_vc_autostart = prompt_response(t) in y

            t = ('\nInclude volttron central platform agent on '
                 'volttron central? [Y]', y_or_n, 'Y')
            do_install_platform = prompt_response(t) in y
        else:
            do_install_platform = True
            t = ('\nAddress of volttron central? [127.0.0.1]: ', None,
                 '127.0.0.1')
            vc_ipaddress = prompt_response(t)
            should_resolve = True
            first = True
            t = ('Port of volttron central? [8080] ',)
            vc_port = prompt_response(t)
            if not vc_port:
                vc_port = 8080
            while not _resolvable(vc_ipaddress, vc_port) and should_resolve:
                print("Couldn't resolve {}:{}".format(vc_ipaddress, vc_port))
                t2 = (
                    '\nShould volttron central be resolvable now? [Y] ', y_or_n,
                    'Y')
                if first:
                    should_resolve = prompt_response(t2) in ('y', 'Y')
                    first = False

                if should_resolve:
                    t = ('\nAddress of volttron central? ',)
                    vc_ipaddress = prompt_response(t)
                    t = ('\nPort of volttron central? ',)
                    vc_port = prompt_response(t)

        if do_install_platform:
            t = ('\nShould platform agent autostart(Y/N)? [Y] ', y_or_n, 'Y')
            do_platform_autostart = prompt_response(t) in y

        external_uri = "tcp://{}:{}".format(external_ip, vip_port)
        bind_web_address = "http://{}:{}".format(external_ip,
                                                 external_port)
        try:
            vc_web_address = "http://{}:{}".format(vc_ipaddress, vc_port)
            _make_configuration(external_uri, bind_web_address,
                                vc_web_address)

        # if vc_ipaddres isn't defined
        # only happens on volttron central.
        except UnboundLocalError:
            _make_configuration(external_uri, bind_web_address)

        t = ('\nShould install sqlite platform historian? [N]', y_or_n, n)
        do_install_platform_historian = prompt_response(t) in y

        do_historian_autostart = True
        if do_install_platform_historian:
            t = ('\nShould historian agent autostart(Y/N)? [Y] ', y_or_n, 'Y')
            do_historian_autostart = prompt_response(t) in y

        # in order to install agents we need to start the platform.
        _start_platform()
        _install_agents((do_install_vc, do_vc_autostart),
                        (do_install_platform, do_platform_autostart),
                        (do_install_platform_historian,
                         do_historian_autostart))
        _shutdown_platform()
        print('Finished configuration\n')
        print('You can now start you volttron instance.\n')
        print('If you need to change the instance configuration you can edit')
        print('the config file at {}/{}\n'.format(volttron_home, 'config'))
