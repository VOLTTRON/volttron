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

'''VOLTTRON Lite™ control classes/functions.'''


import grp
import logging
import os
import pwd
import struct
import sys
import warnings

import gevent
from gevent import socket
from pkg_resources import iter_entry_points

import flexjsonrpc.green as jsonrpc
from flexjsonrpc.framing import raw as framing

from .command import dispatch_loop
from .commands import commands as builtin_commands
from ..core import control
from .environment import get_environment


__version__ = '0.1'

__all__ = ['control_loop']


_log = logging.getLogger(__name__)


SO_PEERCRED = 17


def get_peercred(sock):
    '''Return (pid, gid, uid) of peer socket.'''
    data = sock.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, 12)
    return struct.unpack('3I', data)


def authorize_user(uid, gid, users=None, groups=None, allow_root=True):
    '''Return True if given user or group ID is in an authorized list.

    Given the uid (user ID) and gid (group ID) of a user and lists of
    authorized user and group names, this function will return True if
    the user appears in the users list, if the group or one of the users
    supplemental groups appears in the groups list, or if the user is
    root (uid is 0) and allow_root is True.  Otherwise, the user is not
    authorized and False is returned.  The users and groups lists must
    contain strings only.  Id numbers may be specified as strings
    containing all digits.
    '''
    # Allow root or the process owner
    if (allow_root and uid == 0) or uid == os.getuid():
        return True
    if not (users or groups):
        return False
    try:
        username = pwd.getpwuid(uid).pw_name
    except KeyError:
        username = None
    if users:
        # Check user name and uid against allowed users
        if str(uid) in users or (username and username in users):
            return True
    if groups:
        # Check group name and gid against allowed groups
        try:
            groupname = grp.getgrgid(gid).gr_name
        except KeyError:
            groupname = None
        if str(gid) in groups or (groupname and groupname in groups):
            return True
        # Check supplemental groups against allowed groups
        return username and any(username in gr.gr_mem for gr in grp.getgrall()
                           if gr.gr_name in groups or str(gr.gr_gid) in groups)
    return False


def make_control_handler():
    '''Factory to build ControlHandler class from control handler entry points.
    '''
    def make_class_method(func):
        def method(self, *args, **kwargs):
            return func(*args, **kwargs)
        method.__name__ = func.__name__
        return method
    handlers = dict((cls.__name__, make_class_method(cls.handler))
                    for name, cls in builtin_commands)
    for ep in iter_entry_points(group='volttron.lite.control.handlers'):
        if ep.name in handlers:
            warnings.warn('duplicate control handler entry point: {}'.format(
                    ep.name))
            continue
        handlers[ep.name] = make_class_method(ep.load())
    return type('ControlHandler', (jsonrpc.BaseHandler,), handlers)


def _verify_request(config, request, client_address):
    pid, uid, gid = get_peercred(request)
    authorized = authorize_user(
            uid, gid, config['users'], config['groups'], config['allow-root'])
    _log.info('Connection from addr={!r}, pid={}, uid={}, gid={} '
              '{}authorized'.format(client_address, pid, uid, gid,
                                    '' if authorized else 'not '))
    return authorized


def _handle_request(sock, handler):
    rfile = sock.makefile('rb', -1)
    wfile = sock.makefile('wb', 0)
    stream = framing.Stream(rfile, wfile)
    dispatcher = jsonrpc.Dispatcher(handler)
    dispatch_loop(stream, dispatcher)


def control_loop(config):
    handler = make_control_handler()()
    config = config['control']
    address = config['socket']
    if address[:1] == '@':
        address = '\00' + address[1:]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    sock.bind(address)
    sock.listen(5)
    while True:
        client, client_address = sock.accept()
        if _verify_request(config, client, client_address):
            gevent.spawn(_handle_request, client, handler)
        else:
            client.close()


def load_commands():
    commands = {'help': None}
    for name, cmd in builtin_commands:
        commands[name] = cmd.parser()
    for ep in iter_entry_points(group='volttron.lite.control.commands'):
        if ep.name in commands:
            warnings.warn('duplicate control command entry point: {}'.format(
                    ep.name))
            continue
        commands[ep.name] = parser = ep.load()()
        aliases = []
        for alias in (getattr(parser, 'aliases', None) or ()):
            if alias in commands:
                warnings.warn('duplicate control command alias: {}'.format(
                        alias))
                continue
            commands[alias] = None
            aliases.append(alias)
        aliases.sort()
        parser.aliases = aliases
    return [(name, parser) for name, parser in commands.iteritems() if parser]


def main(argv=sys.argv):
    env = get_environment()
    commands = load_commands()
    parser, args = control.parse_command(commands, argv, version=__version__,
            description='Control volttron and perform other related tasks')
    env.config.parser_load(parser, args.config, args.extra_config)
    try:
        return args.handler(env, parser, args)
    except jsonrpc.RemoteError as e:
        e.print_tb()
        return os.EX_SOFTWARE

def _main():
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

