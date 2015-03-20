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


from __future__ import absolute_import, print_function

import logging
import re
import weakref

import gevent
import zmq.green as zmq

from .agent.vipagent import RPCAgent, export, onevent, subsystem


def dump_user(*args):
    return ','.join([re.sub(r'([,\\])', r'\\\1', arg) for arg in args])


def load_user(string):
    def sub(match):
        return match.group(1) or '\x00'
    return re.sub(r'\\(.)|,', sub, string).split('\x00')


class AuthService(RPCAgent):
    def __init__(self, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.zap_socket = None
        self._zap_greenlet = None

    @export()
    def get_authorization(self):
        pass

    @onevent('setup')
    def setup_zap(self):
        self.zap_socket = zmq.Context.instance().socket(zmq.ROUTER)

    @onevent('connect')
    def bind_zap(self):
        self.zap_socket.bind('inproc://zeromq.zap.01')

    @onevent('start')
    def start_zap(self):
        self._zap_greenlet = gevent.spawn(self.zap_loop)

    @onevent('stop')
    def stop_zap(self):
        if self._zap_greenlet is not None:
            self._zap_greenlet.kill()

    @onevent('disconnect')
    def stop_zap(self):
        if self._zap_socket is not None:
            self.zap_socket.unbind('inproc://zeromq.zap.01')

    def zap_loop(self):
        sock = self.zap_socket
        blocked = weakref.WeakValueDictionary()
        while True:
            if sock.poll():
                zap = sock.recv_multipart()
                version = zap[2]
                if version != b'1.0':
                    continue
                domain, address, _, kind = zap[4:8]
                if kind not in ['NULL', 'PLAIN', 'CURVE']:
                    continue
                credentials = zap[8:]
                response = zap[:4]
                try:
                    greenlet = blocked[address]
                except KeyError:
                    greenlet = None
                if ((greenlet is None or greelet.dead) and
                        self.authenticate(domain, address, kind, credentials)):
                    user = dump_user(domain, address, kind, *credentials[:1])
                    response.extend([b'200', b'SUCCESS', user, b''])
                    sock.send_multipart(response)
                else:
                    if greenlet is None:
                        delay = random.random() * 2
                    else:
                        delay = greenlet.delay * 2
                        if delay > 100:
                            delay = 100
                    response.extend([b'400', b'FAIL', b'', b''])
                    greenlet = gevent.spawn_later(
                        delay, sock.send_multipart, response)
                    greenlet.delay = delay
                    blocked[address] = greenlet

    def authenticate(self, domain, address, mechanism, credentials):
        pass
