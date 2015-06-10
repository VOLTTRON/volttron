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

from __future__ import print_function, absolute_import

import argparse
import logging
from logging import handlers
import logging.config
import os
import sys
import threading

import gevent

from . import aip
from . import __version__
from . import config
from . import vip
from .control import ControlService
from .agent import utils
from .vipagent import Agent, Core
from .vipagent.compat import CompatPubSub

try:
    import volttron.restricted
except ImportError:
    HAVE_RESTRICTED = False
else:
    from volttron.restricted import resmon
    HAVE_RESTRICTED = True


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


def log_to_file(file_, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file_)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter())
    root = logging.getLogger()
    if root.level < level:
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


class LogLevelAction(argparse.Action):
    '''Action to set the log level of individual modules.'''

    def __call__(self, parser, namespace, values, option_string=None):
        for pair in values.split(','):
            if not pair.strip():
                continue
            try:
                logger_name, level_name = pair.rsplit(':', 1)
            except (ValueError, TypeError):
                raise argparse.ArgumentError(
                    self, 'invalid log level pair: {}'.format(values))
            try:
                level = int(level_name)
            except (ValueError, TypeError):
                try:
                    level = getattr(logging, level_name)
                except AttributeError:
                    raise argparse.ArgumentError(
                        self, 'invalid log level {!r}'.format(level_name))
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)


class Router(vip.BaseRouter):
    '''Concrete VIP router.'''
    def __init__(self, addresses, context=None):
        super(Router, self).__init__(context=context)
        self.addresses = addresses
        self.logger = logging.getLogger('vip.router')
        if self.logger.level == logging.NOTSET:
            self.logger.setLevel(logging.INFO)

    def setup(self):
        self.socket.bind('inproc://vip')
        for address in self.addresses:
            self.socket.bind(address)

    def log(self, level, message, frames):
        self.logger.log(level, '%s: %s', message,
                        frames and [bytes(f) for f in frames])

    def run(self):
        self.start()
        try:
            while self.poll():
                self.route()
        finally:
            self.stop()

    def handle_subsystem(self, frames, user_id):
        subsystem = bytes(frames[5])
        if subsystem == b'quit':
            sender = bytes(frames[0])
            if sender == b'control' and not user_id:
                raise KeyboardInterrupt()
        elif subsystem == 'query.addresses':
            frames[6:] = self.addresses
            frames[3] = ''
            frames[5] = 'query.addresses.result'
            return frames


class PubSubService(Agent):
    @Core.receiver('onstart')
    def setup_agent(self, sender, **kwargs):
        self.vip.pubsub.add_bus('')


def main(argv=sys.argv):
    volttron_home = config.expandall(
        os.environ.get('VOLTTRON_HOME', '~/.volttron'))
    os.environ['VOLTTRON_HOME'] = volttron_home

    # Setup option parser
    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]), add_help=False,
        description='VOLTTRON platform service',
        usage='%(prog)s [OPTION]...',
        argument_default=argparse.SUPPRESS,
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
        '--log-level', metavar='LOGGER:LEVEL', action=LogLevelAction,
        help='override default logger logging level')
    parser.add_argument(
        '-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument(
        '-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument(
        '--verboseness', type=int, metavar='LEVEL', default=logging.WARNING,
        help='set logger verboseness')
    #parser.add_argument(
    #    '--volttron-home', env_var='VOLTTRON_HOME', metavar='PATH',
    #    help='VOLTTRON configuration directory')
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
    agents.add_argument(
        '--publish-address', metavar='ZMQADDR',
        help='ZeroMQ URL used for pre-3.x agent publishing (deprecated)')
    agents.add_argument(
        '--subscribe-address', metavar='ZMQADDR',
        help='ZeroMQ URL used for pre-3.x agent subscriptions (deprecated)')
    agents.add_argument(
        '--vip-address', metavar='ZMQADDR', action='append', default=[],
        help='ZeroMQ URL to bind for VIP connections')

    # XXX: re-implement control options
    #on
    #control.add_argument(
    #    '--allow-root', action='store_true', inverse='--no-allow-root',
    #    help='allow root to connect to control socket')
    #control.add_argument(
    #    '--no-allow-root', action='store_false', dest='allow_root',
    #    help=argparse.SUPPRESS)
    #control.add_argument(
    #    '--allow-users', action='store_list', metavar='LIST',
    #    help='users allowed to connect to control socket')
    #control.add_argument(
    #    '--allow-groups', action='store_list', metavar='LIST',
    #    help='user groups allowed to connect to control socket')

    if HAVE_RESTRICTED:
        class RestrictedAction(argparse.Action):
            def __init__(self, option_strings, dest,
                         const=True, help=None, **kwargs):
                super(RestrictedAction, self).__init__(
                    option_strings, dest=argparse.SUPPRESS, nargs=0,
                    const=const, help=help)
            def __call__(self, parser, namespace, values, option_string=None):
                namespace.verify_agents = self.const
                namespace.resource_monitor = self.const
                #namespace.mobility = self.const
        restrict = parser.add_argument_group('restricted options')
        restrict.add_argument(
            '--restricted', action=RestrictedAction, inverse='--no-restricted',
            help='shortcut to enable all restricted features')
        restrict.add_argument(
            '--no-restricted', action=RestrictedAction, const=False,
            help=argparse.SUPPRESS)
        restrict.add_argument(
            '--verify', action='store_true', inverse='--no-verify',
            help='verify agent integrity before execution')
        restrict.add_argument(
            '--no-verify', action='store_false', dest='verify_agents',
            help=argparse.SUPPRESS)
        restrict.add_argument(
            '--resource-monitor', action='store_true',
            inverse='--no-resource-monitor',
            help='enable agent resource management')
        restrict.add_argument(
            '--no-resource-monitor', action='store_false',
            dest='resource_monitor', help=argparse.SUPPRESS)
        #restrict.add_argument(
        #    '--mobility', action='store_true', inverse='--no-mobility',
        #    help='enable agent mobility')
        #restrict.add_argument(
        #    '--no-mobility', action='store_false', dest='mobility',
        #    help=argparse.SUPPRESS)

    vip_path = '$VOLTTRON_HOME/run/vip.socket'
    if sys.platform.startswith('linux'):
        vip_path = '@' + vip_path
    parser.set_defaults(
        log=None,
        log_config=None,
        verboseness=logging.WARNING,
        volttron_home=volttron_home,
        autostart=True,
        publish_address='ipc://$VOLTTRON_HOME/run/publish',
        subscribe_address='ipc://$VOLTTRON_HOME/run/subscribe',
        vip_address=['ipc://' + vip_path],
        #allow_root=False,
        #allow_users=None,
        #allow_groups=None,
        verify_agents=True,
        resource_monitor=True,
        #mobility=True,
    )

    # Parse and expand options
    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        args = ['--config', conf] + args
    logging.getLogger().setLevel(logging.NOTSET)
    opts = parser.parse_args(args)
    if opts.log:
        opts.log = config.expandall(opts.log)
    if opts.log_config:
        opts.log_config = config.expandall(opts.log_config)
    opts.publish_address = config.expandall(opts.publish_address)
    opts.subscribe_address = config.expandall(opts.subscribe_address)
    opts.vip_address = [config.expandall(addr) for addr in opts.vip_address]
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
        log_to_file(opts.log, level, handler_class=handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        error = configure_logging(opts.log_config)
        if error:
            parser.error('{}: {}'.format(*error))

    # Set configuration
    if HAVE_RESTRICTED:
        if opts.verify_agents:
            _log.info('Agent integrity verification enabled')
        if opts.resource_monitor:
            _log.info('Resource monitor enabled')
            opts.resmon = resmon.ResourceMonitor()
    opts.aip = aip.AIPplatform(opts)
    opts.aip.setup()
    if opts.autostart:
        for name, error in opts.aip.autostart():
            _log.error('error starting {!r}: {}\n'.format(name, error))

    # Main loops
    def services():
        control = gevent.spawn(ControlService(
            opts.aip, address='inproc://vip', identity='control').core.run)
        pubsub = gevent.spawn(PubSubService(
            address='inproc://vip', identity='pubsub').core.run)
        exchange = gevent.spawn(CompatPubSub(
            address='inproc://vip', identity='pubsub.compat',
            publish_address=opts.publish_address,
            subscribe_address=opts.subscribe_address).core.run)
        gevent.wait()
    try:
        router = Router(opts.vip_address)
        thread = threading.Thread(target=services)
        thread.daemon = True
        thread.start()
        router.run()
    finally:
        opts.aip.finish()


def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    _main()
