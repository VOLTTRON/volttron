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

from __future__ import absolute_import

import functools
import random
import string
import weakref

import gevent
from zmq import green as zmq
from zmq import ZMQError

from .base import SubsystemBase


__all__ = ['Channel']


class Channel(SubsystemBase):
    class Tracker(object):
        def __init__(self):
            self._channels = {}
            self._handles = {}
            self._sockets = {}

        def add(self, channel, handle, socket):
            sockref = weakref.ref(socket, self.remove)
            self._channels[channel] = (handle, sockref)
            self._handles[handle] = (channel, sockref)
            self._sockets[sockref] = (channel, handle)
            return sockref

        def remove(self, key):
            if isinstance(key, weakref.ref):
                channel, handle = self._sockets.pop(key)
                sockref = None
            elif isinstance(key, basestring):
                channel, sockref = self._handles.pop(key)
                handle = None
            else:
                handle, sockref = self._channels.pop(key)
                channel = None
            if handle:
                self._handles.pop(handle)
            if sockref:
                self._sockets.pop(sockref)
            if channel:
                self._channels.pop(channel)

        def handle_from_channel(self, channel):
            handle, sockref = self._channels[channel]
            socket = sockref()
            if socket is None:
                self.remove(sockref)
                raise KeyError(channel)
            return handle

        def channel_from_handle(self, handle):
            channel, sockref = self._handles[handle]
            socket = sockref()
            if socket is None:
                self.remove(sockref)
                raise KeyError(handle)
            return channel

    def __init__(self, core):
        self.core = weakref.ref(core)
        self.context = zmq.Context()
        self.socket = None
        self.greenlet = None
        self._tracker = Channel.Tracker()
        core.register('channel', self._handle_subsystem, None)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self.socket = self.context.socket(zmq.ROUTER)
        core.onsetup.connect(setup, self)

        def start(sender, **kwargs):
            # pylint: disable=unused-argument
            self.greenlet = gevent.getcurrent()
            socket = self.core().socket
            server = self.socket
            server.bind('inproc://subsystem/channel')
            while True:
                message = server.recv_multipart(copy=False)
                if not message:
                    continue
                ident = bytes(message[0])
                try:
                    peer, name = self._tracker.channel_from_handle(ident)
                except KeyError:
                    # XXX: Handle channel not found
                    continue
                message[0] = name
                socket.send_vip(peer, 'channel', message, copy=False)
        core.onstart.connect(start, self)

        def stop(sender, **kwargs):
            # pylint: disable=unused-argument
            if self.greenlet is not None:
                self.greenlet.kill(block=False)
            try:
                self.socket.unbind('inproc://subsystem/channel')
            except ZMQError:
                pass
        core.onstop.connect(stop, self)

    def _handle_subsystem(self, message):
        frames = message.args
        try:
            name = frames[0]
        except IndexError:
            return
        channel = (bytes(message.peer), bytes(name))
        try:
            ident = self._tracker.handle_from_channel(channel)
        except KeyError:
            # XXX: Handle channel not found
            return
        frames[0] = ident
        self.socket.send_multipart(frames, copy=False)

    def create(self, peer, name=None):
        if name is None:
            while True:
                name = ''.join(random.choice(string.printable[:-5])
                               for i in range(30))
                channel = (peer, name)
                try:
                    self._tracker.handle_from_channel(channel)
                except KeyError:
                    break
        else:
            channel = (peer, name)
            try:
                self._tracker.handle_from_channel(channel)
            except KeyError:
                pass
            else:
                raise ValueError('channel %r is unavailable' % (name,))
        socket = self.context.socket(zmq.DEALER)
        socket.identity = '%s.%s' % (hash(channel), hash(socket))
        object.__setattr__(socket, 'channel', channel)
        sockref = self._tracker.add(channel, socket.identity, socket)
        close_socket = socket.close
        @functools.wraps(close_socket)
        def close(linger=None):
            self._tracker.remove(sockref)
            return close_socket(linger=linger)
        socket.close = close
        socket.connect('inproc://subsystem/channel')
        return socket
    __call__ = create
