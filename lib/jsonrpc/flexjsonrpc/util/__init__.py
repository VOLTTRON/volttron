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

import socket
import threading

try:
    import simplejson as jsonapi
except ImportError:
    import json as jsonapi

from ..core import Requester, Dispatcher, PyConnector, parse_error
from ..framing import raw


__all__ = ['dispatch_loop', 'Connection']


def dispatch_loop(stream, dispatcher, jsonlib=jsonapi, log=None):
    if log is None:
        log = lambda data, **kwargs: None
    for chunk in stream:
        try:
            request = jsonlib.loads(chunk)
        except Exception as e:
            stream.write_chunk(jsonlib.dumps(parse_error(str(e))))
            return
        log(request, direction='in')
        response = dispatcher.dispatch(request)
        if response:
            log(response, direction='out')
            stream.write_chunk(jsonlib.dumps(response))


class Connection(PyConnector):
    '''Simple connection handler.

    Simplifies setting up a connection and making RPC calls.

    Defaults to using simplejson for JSON serialization if it is
    available.  Otherwise, the built-in json module is used. Another
    implementation may be used by setting the module-level jsonapi
    attribute to a module/object supporting the dumps() and loads()
    methods.

    sock is a socket or socket-like object that should support the
    close(), makefile(), and shutdown() methods. handler, if given,
    should be a subclass of flexjsonrpc.BaseHandler and is used to
    export methods and attributes to the remote connection. Raw
    framing is used by default but may be changed using the framing
    argument. A daemonic thread is started for the dispatch loop and
    may be made non-daemonic by setting the daemon argument to False.
    '''

    def __init__(self, sock, handler=None, framing=raw, daemon=True):
        self.sock = sock
        self.stream = framing.Stream(sock.makefile('rb+'))
        send = lambda chunk: self.stream.write_chunk(jsonapi.dumps(chunk))
        requester = Requester(send)
        self.dispatcher = Dispatcher(handler, requester.handle_response)
        super(Connection, self).__init__(requester)
        args = (self.stream, self.dispatcher, jsonapi)
        self.thread = threading.Thread(target=dispatch_loop, args=args)
        self.thread.daemon = daemon
        self.thread.start()

    def shutdown(self):
        '''Attempt to shutdown the connection, if supported.'''
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except AttributeError:
            pass

    def close(self):
        '''Attempt to close the connection and file stream.'''
        try:
            self.sock.close()
        except AttributeError:
            pass
        self.stream.rfile.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()
        self.close()
