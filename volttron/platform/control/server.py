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

'''VOLTTRON platform™ control classes/functions.'''


import grp
import logging
import os
import pwd
import struct

import gevent
from gevent import socket

try:
    import simplejson as json
except ImportError:
    import json

import flexjsonrpc.green as jsonrpc
from flexjsonrpc.framing import raw as framing


__all__ = ['control_loop', 'ControlConnector']


_log = logging.getLogger(__name__)


SO_PEERCRED = 17


def dispatch_loop(stream, dispatcher):
    for chunk in stream:
        try:
            request = json.loads(chunk)
        except Exception as e:
            stream.write_chunk(json.dumps(jsonrpc.parse_error(str(e))))
            return
        response = dispatcher.dispatch(request)
        if response:
            stream.write_chunk(json.dumps(response))

class ControlConnector(jsonrpc.PyConnector):
    def __init__(self, address):
        if address[:1] == '@':
            address = '\x00' + address[1:]
        self._sock = sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(address)
        _log.debug("control socket created")
        stream = framing.Stream(sock.makefile('rb', -1), sock.makefile('rw', 0))
        self._requester = requester = jsonrpc.Requester(
                lambda chunk: stream.write_chunk(json.dumps(chunk)))
        super(ControlConnector, self).__init__(requester)
        self._dispatcher = dispatcher = jsonrpc.Dispatcher(
                None, requester.handle_response)
        self._task = gevent.spawn(dispatch_loop, stream, dispatcher)


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


class ControlHandler(jsonrpc.BaseHandler):
    def __init__(self, env):
        self._env = env
    def clear_status(self, clear_all=False):
        self._env.aip.clear_status(clear_all)
    def agent_status(self, agent_name):
        return self._env.aip.agent_status(agent_name)
    def status_agents(self):
        return self._env.aip.status_agents()
    def start_agent(self, agent_name):
        self._env.aip.start_agent(agent_name)
    def run_agent(self, agent_path):
        self._env.aip.launch_agent(agent_path)
    def stop_agent(self, agent_name):
        self._env.aip.stop_agent(agent_name)
    def shutdown(self):
        self._env.aip.shutdown()


def _verify_request(opts, request, client_address):
    pid, uid, gid = get_peercred(request)
    authorized = authorize_user(
            uid, gid, opts.allow_users, opts.allow_groups, opts.allow_root)
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


def control_loop(opts):
    handler = ControlHandler(opts)
    address = opts.control_socket
    _log.debug("address from options: {}".format(address))
    if address[:1] == '@':
        address = '\00' + address[1:]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
    status = sock.bind(address)
    _log.debug("Binding to address: {}".format(address))
    _log.debug("Status of bind: {}".format(str(status)))
    sock.listen(5)
    while True:
        client, client_address = sock.accept()
        if _verify_request(opts, client, client_address):
            gevent.spawn(_handle_request, client, handler)
        else:
            client.close()
