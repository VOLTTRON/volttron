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

# pylint: disable=W0142,W0403
#}}}

import gevent.monkey
gevent.monkey.patch_all()

import argparse
from contextlib import closing
import logging
from logging import handlers
import os
import socket
import sys

import gevent
from pkg_resources import load_entry_point
from zmq import green as zmq
# Override zmq to use greenlets with mobility agent
zmq.green = zmq
sys.modules['zmq'] = zmq

from . import aip
from . import __version__
from . import config
from .control.server import control_loop
from .agent import utils

try:
    import volttron.restricted
except ImportError:
    have_restricted = False
else:
    from volttron.restricted import comms, comms_server, resmon
    from volttron.restricted.mobility import MobilityAgent
    from paramiko import RSAKey, PasswordRequiredException, SSHException
    have_restricted = True


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler, **kwargs):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file, **kwargs)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
            '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def agent_exchange(in_addr, out_addr, logger_name=None):
    '''Agent message publish/subscribe exchange loop

    Accept multi-part messages from sockets connected to in_addr, which
    is a PULL socket, and forward them to sockets connected to out_addr,
    which is a XPUB socket. When subscriptions are added or removed, a
    message of the form 'subscriptions/<OP>/<TOPIC>' is broadcast to the
    PUB socket where <OP> is either 'add' or 'remove' and <TOPIC> is the
    topic being subscribed or unsubscribed. When a message is received
    of the form 'subscriptions/list/<PREFIX>', a multipart message will
    be broadcast with the first two received frames (topic and headers)
    sent unchanged and with the remainder of the message containing
    currently subscribed topics which start with <PREFIX>, each frame
    containing exactly one topic.

    If logger_name is given, a new logger will be created with the given
    name. Otherwise, the module logger will be used.
    '''
    log = _log if logger_name is None else logging.getLogger(logger_name)
    ctx = zmq.Context.instance()
    with closing(ctx.socket(zmq.PULL)) as in_sock, \
            closing(ctx.socket(zmq.XPUB)) as out_sock:
        in_sock.bind(in_addr)
        out_sock.bind(out_addr)
        poller = zmq.Poller()
        poller.register(in_sock, zmq.POLLIN)
        poller.register(out_sock, zmq.POLLIN)
        subscriptions = set()
        while True:
            for sock, event in poller.poll():
                if sock is in_sock:
                    message = in_sock.recv_multipart()
                    log.debug('incoming message: {!r}'.format(message))
                    topic = message[0]
                    if (topic.startswith('subscriptions/list') and
                            topic[18:19] in ['/', '']):
                        if len(message) > 2:
                            del message[2:]
                        elif len(message) == 1:
                            message.append('')
                        prefix = topic[19:]
                        message.extend([t for t in subscriptions
                                        if t.startswith(prefix)])
                    out_sock.send_multipart(message)
                elif sock is out_sock:
                    message = out_sock.recv()
                    if message:
                        add = bool(ord(message[0]))
                        topic = message[1:]
                        if add:
                            subscriptions.add(topic)
                        else:
                            subscriptions.discard(topic)
                        log.debug('incoming subscription: {} {!r}'.format(
                                ('add' if add else 'remove'), topic))
                        out_sock.send('subscriptions/{}{}{}'.format(
                                ('add' if add else 'remove'),
                                ('' if topic[:1] == '/' else '/'), topic))


def get_volttron_parser(*args, **kwargs):
    '''Return standard parser for VOLTTRON tools.'''
    kwargs.setdefault('add_help', False)
    parser = ArgumentParser(*args, **kwargs)
    parser.add_argument('-c', '--config', metavar='FILE',
        action='parse_config', ignore_unknown=True,
        help='read configuration from FILE')
    parser.add_argument('-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument('-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument('-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument('-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument('--verboseness', type=int, metavar='LEVEL',
        default=logging.WARNING,
        help='set logger verboseness')
    return parser


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
    parser.add_argument('-c', '--config', metavar='FILE',
        action='parse_config', ignore_unknown=True, sections=[None, 'volttron'],
        help='read configuration from FILE')
    parser.add_argument('-l', '--log', metavar='FILE', default=None,
        help='send log output to FILE instead of stderr')
    parser.add_argument('-L', '--log-config', metavar='FILE',
        help='read logging configuration from FILE')
    parser.add_argument('--log-backupcount', metavar='COUNT', default=7, type=int, 
        help='set number of backup log files')
    parser.add_argument('-q', '--quiet', action='add_const', const=10, dest='verboseness',
        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument('-v', '--verbose', action='add_const', const=-10, dest='verboseness',
        help='increase logger verboseness; may be used multiple times')
    parser.add_argument('--verboseness', type=int, metavar='LEVEL',
        default=logging.WARNING,
        help='set logger verboseness')
    #parser.add_argument('--volttron-home', env_var='VOLTTRON_HOME', metavar='PATH',
    #    help='VOLTTRON configuration directory')
    parser.add_argument('--show-config', action='store_true',
        help=argparse.SUPPRESS)
    parser.add_help_argument()
    parser.add_version_argument(version='%(prog)s ' + __version__)

    agents = parser.add_argument_group('agent options')
    agents.add_argument('--autostart', action='store_true', inverse='--no-autostart',
        help='automatically start enabled agents and services')
    agents.add_argument('--no-autostart', action='store_false', dest='autostart',
        help=argparse.SUPPRESS)
    agents.add_argument('--publish-address', metavar='ZMQADDR',
        help='ZeroMQ URL for used for agent publishing')
    agents.add_argument('--subscribe-address', metavar='ZMQADDR',
        help='ZeroMQ URL for used for agent subscriptions')

    control = parser.add_argument_group('control options')
    control.add_argument('--control-socket', metavar='FILE',
        help='path to socket used for control messages')
    control.add_argument('--allow-root', action='store_true', inverse='--no-allow-root',
        help='allow root to connect to control socket')
    control.add_argument('--no-allow-root', action='store_false', dest='allow_root',
        help=argparse.SUPPRESS)
    control.add_argument('--allow-users', action='store_list', metavar='LIST',
        help='users allowed to connect to control socket')
    control.add_argument('--allow-groups', action='store_list', metavar='LIST',
        help='user groups allowed to connect to control socket')

    if have_restricted:
        class RestrictedAction(argparse.Action):
            def __init__(self, option_strings, dest, const=True, help=None, **kwargs):
                super(RestrictedAction, self).__init__(option_strings,
                    dest=argparse.SUPPRESS, nargs=0, const=const, help=help)
            def __call__(self, parser, namespace, values, option_string=None):
                namespace.verify_agents = self.const
                namespace.resource_monitor = self.const
                namespace.mobility = self.const
        restrict = parser.add_argument_group('restricted options')
        restrict.add_argument('--restricted', action=RestrictedAction,
            inverse='--no-restricted',
            help='shortcut to enable all restricted features')
        restrict.add_argument('--no-restricted', action=RestrictedAction,
            const=False, help=argparse.SUPPRESS)
        restrict.add_argument('--verify', action='store_true',
            inverse='--no-verify',
            help='verify agent integrity before execution')
        restrict.add_argument('--no-verify', action='store_false',
            dest='verify_agents', help=argparse.SUPPRESS)
        restrict.add_argument('--resource-monitor', action='store_true',
            inverse='--no-resource-monitor',
            help='enable agent resource management')
        restrict.add_argument('--no-resource-monitor', action='store_false',
            dest='resource_monitor', help=argparse.SUPPRESS)
        restrict.add_argument('--mobility', action='store_true',
            inverse='--no-mobility',
            help='enable agent mobility')
        restrict.add_argument('--no-mobility', action='store_false',
            dest='mobility', help=argparse.SUPPRESS)
        restrict.add_argument('--mobility-address', metavar='ADDRESS',
            help='specify the address on which to listen')
        restrict.add_argument('--mobility-port', type=int, metavar='NUMBER',
            help='specify the port on which to listen')

    parser.set_defaults(
        log = None,
        log_config = None,
        log_backupcount = 7,
        verboseness = logging.WARNING,
        volttron_home = volttron_home,
        autostart = True,
        publish_address = 'ipc://$VOLTTRON_HOME/run/publish',
        subscribe_address = 'ipc://$VOLTTRON_HOME/run/subscribe',
        control_socket = '@$VOLTTRON_HOME/run/control',
        allow_root = False,
        allow_users = None,
        allow_groups = None,
        verify_agents = True,
        resource_monitor = True,
        mobility = True,
        mobility_address = None,
        mobility_port = 2522
    )

    # Parse and expand options
    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        args = ['--config', conf] + args
    opts = parser.parse_args(args)
    opts.control_socket = config.expandall(opts.control_socket)
    opts.publish_address = config.expandall(opts.publish_address)
    opts.subscribe_address = config.expandall(opts.subscribe_address)
    if have_restricted:
        # Set mobility defaults
        if opts.mobility_address is None:
            info = socket.getaddrinfo(
                None, 0, 0, socket.SOCK_STREAM, 0, socket.AI_NUMERICHOST)
            family = info[0][0] if info else ''
            opts.mobility_address = '::' if family == socket.AF_INET6 else ''
    if getattr(opts, 'show_config', False):
        for name, value in sorted(vars(opts).iteritems()):
            print name, repr(value)
        return

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log, level, handler_class=handlers.TimedRotatingFileHandler, when='midnight', backupCount=opts.log_backupcount)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    # Setup mobility server
    if have_restricted and opts.mobility:
        ssh_dir = os.path.join(opts.volttron_home, 'ssh')
        try:
            priv_key = RSAKey(filename=os.path.join(ssh_dir, 'id_rsa'))
            authorized_keys = comms.load_authorized_keys(os.path.join(ssh_dir, 'authorized_keys'))
        except (OSError, IOError, PasswordRequiredException, SSHException) as exc:
            parser.error(exc)

    # Set configuration
    if have_restricted:
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
    try:
        exchange = gevent.spawn(
            agent_exchange, opts.publish_address, opts.subscribe_address)
        if have_restricted and opts.mobility:
            address = (opts.mobility_address, opts.mobility_port)
            mobility_in = comms_server.ThreadedServer(
                address, priv_key, authorized_keys, opts.aip)
            mobility_in.start()
            mobility_out = MobilityAgent(opts.aip,
                subscribe_address=opts.subscribe_address,
                publish_address=opts.publish_address)
            gevent.spawn(mobility_out.run)
        try:
            control = gevent.spawn(control_loop, opts)
            exchange.link(lambda *a: control.kill())
            control.join()
        finally:
            exchange.kill()
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
