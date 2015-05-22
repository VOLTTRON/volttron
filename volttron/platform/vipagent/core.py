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

import inspect
import logging
import os
import sys
import threading
import weakref

import gevent.event
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN

from . import decorators
from .dispatch import Signal
from ..vip import green as vip
from ... import platform


__all__ = ['Core']


_log = logging.getLogger(__name__)


class Core(object):
    def __init__(self, owner, address=None, identity=None, context=None):
        if not address:
            address = os.environ.get('VOLTTRON_VIP_ADDR')
            if not address:
                home = os.path.abspath(platform.get_home())
                abstract = '@' if sys.platform.startswith('linux') else ''
                address = 'ipc://%s%s/run/vip.socket' % (abstract, home)
        self.context = context or zmq.Context.instance()
        self.address = address
        self.identity = identity
        self.socket = None
        self.greenlet = None
        self.subsystems = {'error': (self.handle_error, None)}
        self._async = None
        self._async_calls = []
        self._stop_event = None
        self.onsetup = Signal()
        self.onstart = Signal()
        self.onstop = Signal()
        self.onfinish = Signal()

        def start_periodics(sender, **kwargs):
            def export(member):   # pylint: disable=redefined-outer-name
                for periodic in decorators.annotations(
                        member, list, 'core.periodics'):
                    print('starting', member.__name__)
                    greenlet = periodic.get(member)
                    sender.greenlet.link(lambda glt: greenlet.kill())
                    greenlet.start()
            inspect.getmembers(owner, export)
        self.onstart.connect(start_periodics)

    def register(self, name, handler, error_handler):
        self.subsystems[name] = (handler, error_handler)

    def handle_error(self, message):
        subsystem = bytes(message.args[2 if message.peer else 3])
        try:
            _, handle = self.subsystems[subsystem]
        except KeyError:
            handle = None
        if handle:
            handle(message)
        else:
            _log.debug('unhandled VIP error %s', message)


    def run(self):   # pylint: disable=method-hidden
        '''Entry point for running agent.'''

        self.greenlet = current = gevent.getcurrent()

        def handle_async():
            '''Execute pending calls.'''
            calls = self._async_calls
            while calls:
                func, args, kwargs = calls.pop()
                greenlet = gevent.spawn(func, *args, **kwargs)
                current.link(lambda glt: greenlet.kill)

        def vip_loop():
            socket = self.socket
            while True:
                try:
                    message = socket.recv_vip_object(copy=False)
                except ZMQError as exc:
                    if exc.errno == EAGAIN:
                        continue
                    raise

                subsystem = bytes(message.subsystem)
                try:
                    handle, _ = self.subsystems[subsystem]
                except KeyError:
                    _log.error('peer %r requested unknown subsystem %r',
                               bytes(message.peer), subsystem)
                    message.user = b''
                    message.args = list(vip._INVALID_SUBSYSTEM)
                    message.args.append(message.subsystem)
                    message.subsystem = b'error'
                    socket.send_vip_object(message, copy=False)
                else:
                    handle(message)

        def link_receiver(receiver, sender, **kwargs):
            greenlet = gevent.spawn(receiver, sender, **kwargs)
            current.link(lambda glt: greenlet.kill)
            return greenlet

        self._stop_event = stop = gevent.event.Event()
        self._async = gevent.get_hub().loop.async()
        self._async.start(handle_async)
        current.link(lambda glt: self._async.stop)

        self.socket = vip.Socket(self.context)
        if self.identity:
            self.socket.identity = self.identity
        self.onsetup.send(self)
        self.socket.connect(self.address)

        loop = gevent.spawn(vip_loop)
        current.link(lambda glt: loop.kill)
        self.onstart.sendby(link_receiver, self)
        if loop in gevent.wait([loop, stop], count=1):
            raise RuntimeError('VIP loop ended prematurely')
        stop.wait()
        receivers = self.onstop.sendby(link_receiver, self)
        gevent.wait(receivers)
        self.socket.disconnect(self.address)
        self.onfinish.send(self)

    def stop(self, timeout=None):
        def halt():
            self._stop_event.set()
            self.greenlet.join(timeout)
            return self.greenlet.ready()
        if gevent.get_hub() is self._stop_event.hub:
            return halt()
        return self.send_async(halt).get()

    def send(self, func, *args, **kwargs):
        self._async_calls.append((func, args, kwargs))
        self._async.send()

    def send_async(self, func, *args, **kwargs):
        result = gevent.event.AsyncResult()
        async = result.hub.loop.async()
        results = [None, None]
        def receiver():
            async.stop()
            exc, value = results
            if exc is None:
                result.set(value)
            else:
                result.set_exception(exc)
        async.start(receiver)
        def worker():
            try:
                results[:] = [None, func(*args, **kwargs)]
            except Exception as exc:
                results[:] = [exc, None]
            async.send()
        self.send(worker)
        return result

    def spawn_in_thread(self, func, *args, **kwargs):
        result = gevent.event.AsyncResult()
        def wrapper():
            try:
                self.send(result.set, func(*args, **kwargs))
            except Exception as exc:
                self.send(result.set_exception, exc)
        result.thread = thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        return result

    @decorators.dualmethod
    def periodic(self, period, func, args=None, kwargs=None, wait=0):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        greenlet = decorators.periodic(
            period, *args, **kwargs).wait(wait).get(func)
        self.greenlet.link(lambda glt: greenlet.kill)
        greenlet.start()
        return greenlet

    @periodic.classmethod
    def periodic(cls, period, *args, **kwargs):   # pylint: disable=no-self-argument
        return decorators.periodic(period, *args, **kwargs)
