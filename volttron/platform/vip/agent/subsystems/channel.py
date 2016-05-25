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
#}}}

from __future__ import absolute_import

import functools
import logging
import random
import string
import weakref

import gevent
from zmq import green as zmq
from zmq import ZMQError

from .base import SubsystemBase


__all__ = ['Channel']


_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class Channel(SubsystemBase):
    ADDRESS = 'inproc://subsystem/channel'

    def __init__(self, core):
        self.context = zmq.Context()
        self.socket = None
        self.greenlet = None
        self._channels = {}
        core.register('channel', self._handle_subsystem)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self.socket = self.context.socket(zmq.ROUTER)
        core.onsetup.connect(setup, self)

        def start(sender, **kwargs):
            # pylint: disable=unused-argument
            self.greenlet = gevent.getcurrent()
            vip_sock = core.socket
            chan_sock = self.socket
            chan_sock.bind(self.ADDRESS)
            release = []
            while True:
                logit = (0 < _log.level <= logging.DEBUG)
                message = chan_sock.recv_multipart(copy=False)
                if logit:
                    _log.debug('recv {} bytes of data'.format(len(message)))
                if not message:
                    continue
                ident = bytes(message[0])
                if ident == b'release':
                    release.append([bytes(x) for x in message])
                    continue
                try:
                    peer, name = self._channels[ident]
                except KeyError:
                    # XXX: Handle channel not found
                    continue
                message[0] = name
                if logit:
                    _log.debug('send on out {} bytes of data'
                               .format(len(message)))
                vip_sock.send_vip(peer, 'channel', message, copy=False)
        core.onstart.connect(start, self)

        def stop(sender, **kwargs):
            # pylint: disable=unused-argument
            if self.greenlet is not None:
                self.greenlet.kill(block=False)
            try:
                self.socket.unbind(self.ADDRESS)
            except ZMQError:
                pass
        core.onstop.connect(stop, self)

    def _handle_subsystem(self, message):
        frames = message.args
        logit = (0 < _log.level <= logging.DEBUG)
        if logit:
            _log.debug('recv on in %r', [bytes(x) for x in frames])
        try:
            name = frames[0]
        except IndexError:
            return
        channel = (bytes(message.peer), bytes(name))
        try:
            ident = self._channels[channel]
        except KeyError:
            # XXX: Handle channel not found
            return
        frames[0] = ident
        if logit:
            _log.debug('send on in %r', [bytes(x) for x in frames])
        self.socket.send_multipart(frames, copy=False)

    def create(self, peer, name=None):
        if name is None:
            while True:
                name = ''.join(random.choice(string.printable[:-5])
                               for i in range(30))
                channel = (peer, name)
                if channel not in self._channels:
                    break
        else:
            channel = (peer, name)
            if channel in self._channels:
                raise ValueError('channel %r is unavailable' % (name,))
        sock = self.context.socket(zmq.DEALER)
        sock.identity = ident = '%s.%s' % (hash(channel), hash(sock))
        sockref = weakref.ref(sock, self._destroy)
        object.__setattr__(sock, 'peer', peer)
        object.__setattr__(sock, 'name', name)
        self._channels[channel] = ident
        self._channels[ident] = channel
        self._channels[sockref] = (ident, peer, name)
        close_socket = sock.close
        @functools.wraps(close_socket)
        def close(linger=None):
            self._destroy(sockref)
            sock.close = close_socket
            return close_socket(linger=linger)
        sock.close = close
        sock.connect(self.ADDRESS)
        return sock
    __call__ = create

    def _destroy(self, sockref):
        try:
            ident, peer, name = self._channels.pop(sockref)
        except KeyError:
            return
        self._channels.pop(ident, None)
        self._channels.pop((peer, name), None)
