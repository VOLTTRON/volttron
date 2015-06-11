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

from contextlib import contextmanager
import heapq
import inspect
import logging
import os
import sys
import threading
import time

import gevent.event
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN

from .decorators import annotate, annotations, dualmethod
from .dispatch import Signal
from ...vip import green as vip
from .... import platform


__all__ = ['Core', 'killing']


_log = logging.getLogger(__name__)


class Periodic(object):   # pylint: disable=invalid-name
    '''Decorator to set a method up as a periodic callback.

    The decorated method will be called with the given arguments every
    period seconds while the agent is executing its run loop.
    '''

    def __init__(self, period, args=None, kwargs=None, wait=0):
        '''Store period (seconds) and arguments to call method with.'''
        assert period > 0
        self.period = period
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.timeout = wait

    def __call__(self, method):
        '''Attach this object instance to the given method.'''
        annotate(method, list, 'core.periodics', self)
        return method

    def _loop(self, method):
        # pylint: disable=missing-docstring
        if self.timeout != 0:
            gevent.sleep(self.timeout or self.period)
        while True:
            method(*self.args, **self.kwargs)
            gevent.sleep(self.period)

    def get(self, method):
        '''Return a Greenlet for the given method.'''
        return gevent.Greenlet(self._loop, method)


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
        self._schedule_event = None
        self._schedule = []
        self.onsetup = Signal()
        self.onstart = Signal()
        self.onstop = Signal()
        self.onfinish = Signal()

        periodics = []
        def setup(member):   # pylint: disable=redefined-outer-name
            periodics.extend(
                periodic.get(member) for periodic in annotations(
                    member, list, 'core.periodics'))
            self._schedule.extend(
                (deadline, member, args, kwargs) for deadline, args, kwargs in
                annotations(member, list, 'core.schedule'))
            for name in annotations(member, set, 'core.signals'):
                signal = getattr(self, name)
                assert isinstance(signal, Signal)
                signal.connect(member, owner)
        inspect.getmembers(owner, setup)
        heapq.heapify(self._schedule)

        def start_periodics(sender, **kwargs):   # pylint: disable=unused-argument
            for periodic in periodics:
                sender.greenlet.link(lambda glt: periodic.kill())
                periodic.start()
            del periodics[:]
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
                current.link(lambda glt: greenlet.kill())

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

        def schedule_loop():
            heap = self._schedule
            event = self._schedule_event
            cur = gevent.getcurrent()
            now = time.time()
            while True:
                if heap:
                    deadline = heap[0][0]
                    timeout = min(60.0, max(0.0, deadline - now))
                else:
                    timeout = None
                if event.wait(timeout):
                    event.clear()
                now = time.time()
                while heap and now >= heap[0][0]:
                    _, func, args, kwargs = heapq.heappop(heap)
                    greenlet = gevent.spawn(func, *args, **kwargs)
                    cur.link(lambda glt: greenlet.kill())

        def link_receiver(receiver, sender, **kwargs):
            greenlet = gevent.spawn(receiver, sender, **kwargs)
            current.link(lambda glt: greenlet.kill())
            return greenlet

        self._stop_event = stop = gevent.event.Event()
        self._schedule_event = gevent.event.Event()
        self._async = gevent.get_hub().loop.async()
        self._async.start(handle_async)
        current.link(lambda glt: self._async.stop())

        self.socket = vip.Socket(self.context)
        if self.identity:
            self.socket.identity = self.identity
        self.onsetup.send(self)
        self.socket.connect(self.address)

        loop = gevent.spawn(vip_loop)
        current.link(lambda glt: loop.kill())
        scheduler = gevent.spawn(schedule_loop)
        loop.link(lambda glt: scheduler.kill())
        self.onstart.sendby(link_receiver, self)
        if loop in gevent.wait([loop, stop], count=1):
            raise RuntimeError('VIP loop ended prematurely')
        stop.wait()
        scheduler.kill()
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
            except Exception as exc:   # pylint: disable=broad-except
                results[:] = [exc, None]
            async.send()
        self.send(worker)
        return result

    def spawn(self, func, *args, **kwargs):
        assert self.greenlet is not None
        greenlet = gevent.spawn(func, *args, **kwargs)
        self.greenlet.link(lambda glt: greenlet.kill())

    def spawn_in_thread(self, func, *args, **kwargs):
        result = gevent.event.AsyncResult()
        def wrapper():
            try:
                self.send(result.set, func(*args, **kwargs))
            except Exception as exc:   # pylint: disable=broad-except
                self.send(result.set_exception, exc)
        result.thread = thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        return result

    @dualmethod
    def periodic(self, period, func, args=None, kwargs=None, wait=0):
        greenlet = Periodic(period, args, kwargs, wait).get(func)
        self.greenlet.link(lambda glt: greenlet.kill())
        greenlet.start()
        return greenlet

    @periodic.classmethod
    def periodic(cls, period, args=None, kwargs=None, wait=0):   # pylint: disable=no-self-argument
        return Periodic(period, args, kwargs, wait)

    @classmethod
    def receiver(cls, signal):
        def decorate(method):
            annotate(method, set, 'core.signals', signal)
            return method
        return decorate

    @dualmethod
    def schedule(self, deadline, func, *args, **kwargs):
        if hasattr(deadline, 'timetuple'):
            deadline = time.mktime(deadline.timetuple())
        heapq.heappush(self._schedule, (deadline, func, args, kwargs))
        self._schedule_event.set()

    @schedule.classmethod
    def schedule(cls, deadline, *args, **kwargs):   # pylint: disable=no-self-argument
        def decorate(method):
            annotate(method, list, 'core.schedule', (deadline, args, kwargs))
            return method
        return decorate


@contextmanager
def killing(greenlet, *args, **kwargs):
    '''Context manager to automatically kill spawned greenlets.

    Allows one to kill greenlets that would continue after a timeout:

        with killing(agent.vip.pubsub.subscribe(
                'peer', 'topic', callback)) as subscribe:
            subscribe.get(timeout=10)
    '''
    try:
        yield greenlet
    finally:
        greenlet.kill(*args, **kwargs)
