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

import argparse
from contextlib import nested, closing
import logging
from logging import handlers
import os
import re
import sys

import gevent
from pkg_resources import load_entry_point
from zmq import green as zmq

from environment import get_environment
from control import control_loop
from agent import utils


__version__ = '0.1'


_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)


class CountdownAction(argparse._CountAction):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, getattr(namespace, self.dest, 0) - 1)


class ConfigSetAction(argparse._StoreAction):
    _confsetre = re.compile(
            r'^\s*([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+)\s*=\s*(\S.*?)\s*$')
    def __call__(self, parser, namespace, values, option_string=None):
        value = getattr(namespace, self.dest, None)
        if value is None:
            value = []
            setattr(namespace, self.dest, value)
        if isinstance(values, basestring):
            values = [values]
        for string in values:
            match = ConfigSetAction._confsetre.match(string)
            if match is None:
                raise argparse.ArgumentTypeError(
                        'not a valid config string: {!r} '
                        "(use 'section.name=value')".format(string))
            names, setting = match.groups()
            value.append((names.split('.'), setting))


class DeprecatedAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        sys.stderr.write('{}: warning: {!r} option is deprecated and has no '
                         'effect.  Please remove this option from any scripts '
                         'to prevent future errors.\n'.format(
                                 parser.prog, option_string))


class OptionParser(argparse.ArgumentParser):
    def __init__(self, progname):
        argparse.ArgumentParser.__init__(self, usage='%(prog)s [OPTION]...',
            prog=progname, add_help=False,
            description='Volttron Lite agent platform daemon',
            ) #formatter=self.GnuishHelpFormatter())
        self.add_argument('-c', '--config', metavar='FILE',
                help='read configuration from FILE')
        self.add_argument('-l', '--log', metavar='FILE',
                help='send log output to FILE instead of stderr')
        self.add_argument('-L', '--log-config', metavar='FILE',
                help='read logging configuration from FILE')
        self.add_argument('-q', '--quiet', action='count',
                dest='verboseness', default=0,
                help='decrease logger verboseness; may be used multiple times')
        self.add_argument('-s', '--set', action=ConfigSetAction, default=[],
                dest='extra_config', metavar="SECTION.NAME=VALUE",
                help='specify additional configuration')
        self.add_argument('--skip-autostart', action='store_true',
                help='skip automatic starting of enabled agents and services')
        self.add_argument('-v', '--verbose', action=CountdownAction, dest='verboseness',
                help='increase logger verboseness; may be used multiple times')
        self.add_argument('--help', action='help',
                help='show this help message and exit')
        self.add_argument('--version', action='version',
                version='%(prog)s ' + __version__,
                help='show version information and exit')


def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
            '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
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
    with nested(closing(ctx.socket(zmq.PULL)),
                closing(ctx.socket(zmq.XPUB))) as (in_sock, out_sock):
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


def main(argv=sys.argv):
    # Parse options
    parser = OptionParser(os.path.basename(argv[0]))
    opts = parser.parse_args(argv[1:])

    # Load configuration
    env = get_environment()
    env.config.parser_load(parser, opts.config, opts.extra_config)
    sub_addr = env.config['agent-exchange']['subscribe-address']
    append_pid = env.config['agent-exchange']['append-pid']
    if append_pid and sub_addr.startswith('ipc://'):
        sub_addr += '.{}'.format(os.getpid())
        env.config['agent-exchange']['subscribe-address'] = sub_addr
    pub_addr = env.config['agent-exchange']['publish-address']
    if append_pid and pub_addr.startswith('ipc://'):
        pub_addr += '.{}'.format(os.getpid())
        env.config['agent-exchange']['publish-address'] = pub_addr

    env.resmon = load_entry_point(
            'volttronlite', 'volttron.switchboard.resmon', 'lite')(env)
    env.aip = load_entry_point(
            'volttronlite', 'volttron.switchboard.aip', 'lite')(env)

    # Configure logging
    level = max(0, logging.WARNING + opts.verboseness * 10)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(opts.log, level, handler_class=handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    env.aip.setup()
    if not opts.skip_autostart:
        for name, error in env.aip.autostart():
            _log.error('error starting {!r}: {}\n'.format(name, error))

    # Main loops
    try:
        exchange = gevent.spawn(agent_exchange, pub_addr, sub_addr)
        try:
            control = gevent.spawn(control_loop, env.config)
            exchange.link(lambda *a: control.kill())
            control.join()
        finally:
            exchange.kill()
    finally:
        env.aip.finish()


def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        pass

