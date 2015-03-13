# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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
#}}}


'''Main VOLTTRON™ script.

Becomes the volttron executable used to start the supervisory platform.
'''


from __future__ import print_function, absolute_import

import argparse
import logging
import logging.handlers
import logging.config
import os
import sys

#from . import aip
from . import __version__
from . import config
from . import vip
from .agent import utils

#HAVE_RESTRICTED = False


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)
_vip_log = logging.getLogger('volttron.vip.router')


def log_to_file(file_, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file_)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
        '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def configure_logging(conf_path):
    '''Load logging configuration from a file.

    Several formats are possible: ini, JSON, Python, and YAML. The ini
    format uses the standard Windows ini file format and is read in
    using logging.config.fileConfig(). The remaining formats will be
    read in according to the serialization format and the resulting
    dictionary will be passed to logging.config.dictConfig(). See the
    logging.config module for specifics on the two file and dict
    formats. Returns None on success, (path, exception) on error.

    The default format is ini. Other formats will be selected based on
    the file extension. Each format can be forced, regardless of file
    extension, by prepending the path with the format name followed by a
    colon:

      Examples:
        config.json        is loaded as JSON
        config.conf        is loaded as ini
        json:config.conf   is loaded as JSON

    YAML formatted configuration files require the PyYAML package.
    '''

    conf_format = 'ini'
    if conf_path.startswith('ini:'):
        conf_format, conf_path = 'ini', conf_path[4:]
    elif conf_path.startswith('json:'):
        conf_format, conf_path = 'json', conf_path[5:]
    elif conf_path.startswith('py:'):
        conf_format, conf_path = 'py', conf_path[3:]
    elif conf_path.startswith('yaml:'):
        conf_format, conf_path = 'yaml', conf_path[5:]
    elif conf_path.endswith('.json'):
        conf_format = 'json'
    elif conf_path.endswith('.py'):
        conf_format = 'py'
    elif conf_path.endswith('.yaml'):
        conf_format = 'yaml'

    if conf_format == 'ini':
        try:
            logging.config.fileConfig(conf_path)
        except (ValueError, TypeError, AttributeError, ImportError) as exc:
            return conf_path, exc
        return

    with open(conf_path) as conf_file:
        if conf_format == 'json':
            import json
            try:
                conf_dict = json.load(conf_file)
            except ValueError as exc:
                return conf_path, exc
        elif conf_format == 'py':
            import ast
            try:
                conf_dict = ast.literal_eval(conf_file.read())
            except ValueError as exc:
                return conf_path, exc
        else:
            try:
                import yaml
            except ImportError:
                return (conf_path, 'PyYAML must be installed before '
                        'loading logging configuration from a YAML file.')
            try:
                conf_dict = yaml.load(conf_file)
            except yaml.YAMLError as exc:
                return conf_path, exc
    try:
        logging.config.dictConfig(conf_dict)
    except (ValueError, TypeError, AttributeError, ImportError) as exc:
        return conf_path, exc


class Router(vip.BaseRouter):
    '''Concrete VIP router.'''
    def __init__(self, address, context=None):
        super(Router, self).__init__(context=context)
        self.address = address
    def setup(self):
        self.socket.bind(self.address)
    def log(self, level, message, frames):
        _vip_log.log(level, '%s: %s', message,
                     frames and [bytes(f) for f in frames])
    def run(self):
        self.start()
        _vip_log.info('VIP router started')
        try:
            while self.poll():
                self.route()
        finally:
            _vip_log.info('VIP router stopped')
            self.stop()


def main(argv=sys.argv):
    '''Parse the command-line given in argv and run volttron.'''
    volttron_home = config.expandall(
        os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = volttron_home

    # Setup option parser
    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]), add_help=False,
        argument_default=argparse.SUPPRESS,
        description='VOLTTRON platform service',
        usage='%(prog)s [OPTION]...',
        epilog='Boolean options, which take no argument, may be inversed by '
               'prefixing the option with no- (e.g. --autostart may be '
               'inversed using --no-autostart).'
    )
    parser.add_argument(
        '-c', '--config', metavar='FILE', action='parse_config',
        ignore_unknown=True, sections=[None, 'volttron'],
        help='read configuration from FILE')
    parser.add_argument(
        '-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument(
        '-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument(
        '-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument(
        '-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument(
        '--verboseness', type=int, metavar='LEVEL', default=logging.WARNING,
        help='set logger verboseness')
    parser.add_argument(
        '--show-config', action='store_true',
        help=argparse.SUPPRESS)
    parser.add_help_argument()
    parser.add_version_argument(version='%(prog)s ' + __version__)

    agents = parser.add_argument_group('agent options')
    agents.add_argument(
        '--autostart', action='store_true', inverse='--no-autostart',
        help='automatically start enabled agents and services')
    agents.add_argument(
        '--no-autostart', action='store_false', dest='autostart',
        help=argparse.SUPPRESS)

    control = parser.add_argument_group('control options')
    control.add_argument(
        '--allow-root', action='store_true', inverse='--no-allow-root',
        help='allow root to connect to control socket')
    control.add_argument(
        '--no-allow-root', action='store_false', dest='allow_root',
        help=argparse.SUPPRESS)
    control.add_argument(
        '--allow-users', action='store_list', metavar='LIST',
        help='users allowed to connect to control socket')
    control.add_argument(
        '--allow-groups', action='store_list', metavar='LIST',
        help='user groups allowed to connect to control socket')

#    if HAVE_RESTRICTED:
#        class RestrictedAction(argparse.Action):
#            def __init__(self, option_strings, dest,
#                         const=True, help=None, **kwargs):
#                super(RestrictedAction, self).__init__(
#                    option_strings, dest=argparse.SUPPRESS, nargs=0,
#                    const=const, help=help)
#            def __call__(self, parser, namespace, values, option_string=None):
#                namespace.verify_agents = self.const
#                namespace.resource_monitor = self.const
#                namespace.mobility = self.const
#        restrict = parser.add_argument_group('restricted options')
#        restrict.add_argument(
#            '--restricted', action=RestrictedAction, inverse='--no-restricted',
#            help='shortcut to enable all restricted features')
#        restrict.add_argument(
#            '--no-restricted', action=RestrictedAction, const=False,
#            help=argparse.SUPPRESS)
#        restrict.add_argument(
#            '--verify', action='store_true', inverse='--no-verify',
#            help='verify agent integrity before execution')
#        restrict.add_argument(
#            '--no-verify', action='store_false', dest='verify_agents',
#            help=argparse.SUPPRESS)
#        restrict.add_argument(
#            '--resource-monitor', action='store_true',
#            inverse='--no-resource-monitor',
#            help='enable agent resource management')
#        restrict.add_argument(
#            '--no-resource-monitor', action='store_false',
#            dest='resource_monitor', help=argparse.SUPPRESS)
#        restrict.add_argument(
#            '--mobility', action='store_true', inverse='--no-mobility',
#            help='enable agent mobility')
#        restrict.add_argument(
#            '--no-mobility', action='store_false', dest='mobility',
#            help=argparse.SUPPRESS)
#        restrict.add_argument(
#            '--mobility-address', metavar='ADDRESS',
#            help='specify the address on which to listen')
#        restrict.add_argument(
#            '--mobility-port', type=int, metavar='NUMBER',
#            help='specify the port on which to listen')

    parser.set_defaults(
        log=None,
        log_config=None,
        verboseness=logging.WARNING,
        volttron_home=volttron_home,
        vip_address='ipc://{}{}/run/vip.socket'.format(
            '@' if sys.platform.startswith('linux') else '', volttron_home),
        autostart=True,
        allow_root=False,
        allow_users=None,
        allow_groups=None,
#        verify_agents=True,
#        resource_monitor=True,
#        mobility=True,
#        mobility_address=None,
#        mobility_port=2522
    )

    # Parse and expand options
    argv = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'VOLTTRON_NO_CONFIG' not in os.environ:
        argv[:0] = ['--config', conf]
    opts = parser.parse_args(argv)
#    if HAVE_RESTRICTED:
#        # Set mobility defaults
#        if opts.mobility_address is None:
#            info = socket.getaddrinfo(
#                None, 0, 0, socket.SOCK_STREAM, 0, socket.AI_NUMERICHOST)
#            family = info[0][0] if info else ''
#            opts.mobility_address = '::' if family == socket.AF_INET6 else ''
    if getattr(opts, 'show_config', False):
        for name, value in sorted(vars(opts).iteritems()):
            print(name, repr(value))
        return

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(
            opts.log, level, handler_class=logging.handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        error = configure_logging(opts.log_config)
        if error:
            parser.error('{}: {}'.format(*error))

    # Log configuration
    _log.debug('Configuration:')
    for name, value in sorted(vars(opts).iteritems()):
        _log.debug('  %s = %s', name, repr(value))

#    # Setup mobility server
#    if HAVE_RESTRICTED and opts.mobility:
#        ssh_dir = os.path.join(opts.volttron_home, 'ssh')
#        try:
#            priv_key = RSAKey(filename=os.path.join(ssh_dir, 'id_rsa'))
#            authorized_keys = comms.load_authorized_keys(
#                os.path.join(ssh_dir, 'authorized_keys'))
#        except (OSError, IOError,
#                PasswordRequiredException, SSHException) as exc:
#            parser.error(exc)
#
#    # Set configuration
#    if HAVE_RESTRICTED:
#        if opts.verify_agents:
#            _log.info('Agent integrity verification enabled')
#        if opts.resource_monitor:
#            _log.info('Resource monitor enabled')
#            opts.resmon = resmon.ResourceMonitor()
#    opts.aip = aip.AIPplatform(opts)
#    opts.aip.setup()
#    if opts.autostart:
#        for name, error in opts.aip.autostart():
#            _log.error('error starting {!r}: {}\n'.format(name, error))

    # Main loop
    router = Router(opts.vip_address)
    router.run()

#    try:
#        if HAVE_RESTRICTED and opts.mobility:
#            address = (opts.mobility_address, opts.mobility_port)
#            mobility_in = comms_server.ThreadedServer(
#                address, priv_key, authorized_keys, opts.aip)
#            mobility_in.start()
#            mobility_out = MobilityAgent(
#                opts.aip,
#                subscribe_address=opts.subscribe_address,
#                publish_address=opts.publish_address)
#            gevent.spawn(mobility_out.run)
#        router.run()
#    finally:
#        opts.aip.finish()


def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()
