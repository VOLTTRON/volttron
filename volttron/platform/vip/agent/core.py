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

from __future__ import absolute_import, print_function

from contextlib import contextmanager
from datetime import datetime
from errno import ENOENT
import heapq
import inspect
import logging
import os
import sys
import threading
import time
import urlparse

import gevent.event
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN
from zmq.utils import jsonapi as json
from zmq.utils.monitor import recv_monitor_message

from .decorators import annotate, annotations, dualmethod
from .dispatch import Signal
from .errors import VIPError
from .. import green as vip
from .. import router
from .... import platform
from volttron.platform.keystore import KeyStore

__all__ = ['BasicCore', 'Core', 'killing']


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
        # Use monotonic clock provided on hub's loop instance.
        now = gevent.get_hub().loop.now
        period = self.period
        deadline = now()
        if self.timeout != 0:
            timeout = self.timeout or period
            deadline += timeout
            gevent.sleep(timeout)
        while True:
            try:
                method(*self.args, **self.kwargs)
            except Exception:
                _log.exception('unhandled exception in periodic callback')
            deadline += period
            timeout = deadline - now()
            if timeout > 0:
                gevent.sleep(timeout)
            else:
                # Prevent catching up.
                deadline -= timeout

    def get(self, method):
        '''Return a Greenlet for the given method.'''
        return gevent.Greenlet(self._loop, method)


class ScheduledEvent(object):
    '''Class returned from Core.schedule.'''

    def __init__(self, function, args=None, kwargs=None):
        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.canceled = False
        self.finished = False

    def cancel(self):
        '''Mark the timer as canceled to avoid a callback.'''
        self.canceled = True

    def __call__(self):
        if not self.canceled:
            self.function(*self.args, **self.kwargs)
        self.finished = True


def findsignal(obj, owner, name):
    parts = name.split('.')
    if len(parts) == 1:
        signal = getattr(obj, name)
    else:
        signal = owner
        for part in parts:
            signal = getattr(signal, part)
    assert isinstance(signal, Signal), 'bad signal name %r' % (name,)
    return signal


class BasicCore(object):
    def __init__(self, owner):
        self.greenlet = None
        self._async = None
        self._async_calls = []
        self._stop_event = None
        self._schedule_event = None
        self._schedule = []
        self.onsetup = Signal()
        self.onstart = Signal()
        self.onstop = Signal()
        self.onfinish = Signal()
        self._owner = owner

    def setup(self):
        # Split out setup from __init__ to give oportunity to add
        # subsystems with signals
        try:
            owner = self._owner
        except AttributeError:
            return
        del self._owner
        periodics = []

        def setup(member):   # pylint: disable=redefined-outer-name
            periodics.extend(
                periodic.get(member) for periodic in annotations(
                    member, list, 'core.periodics'))
            self._schedule.extend(
                (deadline, ScheduledEvent(member, args, kwargs))
                for deadline, args, kwargs in
                annotations(member, list, 'core.schedule'))
            for name in annotations(member, set, 'core.signals'):
                findsignal(self, owner, name).connect(member, owner)
        inspect.getmembers(owner, setup)
        heapq.heapify(self._schedule)

        def start_periodics(sender, **kwargs):   # pylint: disable=unused-argument
            for periodic in periodics:
                sender.greenlet.link(lambda glt: periodic.kill())
                periodic.start()
            del periodics[:]
        self.onstart.connect(start_periodics)

    def loop(self):
        # pre-setup
        yield
        # pre-start
        yield
        # pre-stop
        yield
        # pre-finish
        yield

    def run(self, running_event=None):   # pylint: disable=method-hidden
        '''Entry point for running agent.'''

        self.setup()
        self.greenlet = current = gevent.getcurrent()

        def handle_async():
            '''Execute pending calls.'''
            calls = self._async_calls
            while calls:
                func, args, kwargs = calls.pop()
                greenlet = gevent.spawn(func, *args, **kwargs)
                current.link(lambda glt: greenlet.kill())

        def schedule_loop():
            heap = self._schedule
            event = self._schedule_event
            cur = gevent.getcurrent()
            now = time.time()
            while True:
                if heap:
                    deadline = heap[0][0]
                    timeout = min(5.0, max(0.0, deadline - now))
                else:
                    timeout = None
                if event.wait(timeout):
                    event.clear()
                now = time.time()
                while heap and now >= heap[0][0]:
                    _, callback = heapq.heappop(heap)
                    greenlet = gevent.spawn(callback)
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

        looper = self.loop()
        looper.next()
        self.onsetup.send(self)

        loop = looper.next()
        if loop:
            current.link(lambda glt: loop.kill())
        scheduler = gevent.spawn(schedule_loop)
        if loop:
            loop.link(lambda glt: scheduler.kill())
        self.onstart.sendby(link_receiver, self)
        if running_event:
            running_event.set()
            del running_event
        try:
            if loop and loop in gevent.wait([loop, stop], count=1):
                raise RuntimeError('VIP loop ended prematurely')
            stop.wait()
        except (gevent.GreenletExit, KeyboardInterrupt):
            pass
        scheduler.kill()
        looper.next()
        receivers = self.onstop.sendby(link_receiver, self)
        gevent.wait(receivers)
        looper.next()
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
        return greenlet

    def spawn_later(self, seconds, func, *args, **kwargs):
        assert self.greenlet is not None
        greenlet = gevent.spawn_later(seconds, func, *args, **kwargs)
        self.greenlet.link(lambda glt: greenlet.kill())
        return greenlet

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
        event = ScheduledEvent(func, args, kwargs)
        heapq.heappush(self._schedule, (deadline, event))
        self._schedule_event.set()
        return event

    @schedule.classmethod
    def schedule(cls, deadline, *args, **kwargs):   # pylint: disable=no-self-argument
        if hasattr(deadline, 'timetuple'):
            deadline = time.mktime(deadline.timetuple())

        def decorate(method):
            annotate(method, list, 'core.schedule', (deadline, args, kwargs))
            return method
        return decorate


class Core(BasicCore):
    def __init__(self, owner, address=None, identity=None, context=None,
                 publickey=None, secretkey=None, serverkey=None):
        if not address:
            address = os.environ.get('VOLTTRON_VIP_ADDR')
            if not address:
                home = os.path.abspath(platform.get_home())
                abstract = '@' if sys.platform.startswith('linux') else ''
                address = 'ipc://%s%s/run/vip.socket' % (abstract, home)
        # These signals need to exist before calling super().__init__()
        self.onviperror = Signal()
        self.onsockevent = Signal()
        self.onconnected = Signal()
        self.ondisconnected = Signal()
        super(Core, self).__init__(owner)
        self.context = context or zmq.Context.instance()
        self.address = address
        self.identity = identity
        self.agent_uuid = os.environ.get('AGENT_UUID', None)

        # The public and secret keys are obtained by:
        # 1. publickkey and secretkey parameters to __init__
        # 2. in the query string of the address parameter to __init__
        # 3. from the agent's keystore

        if publickey is None or secretkey is None:
            publickey, secretkey = self._get_keys()
        if publickey and secretkey and serverkey:
            self._add_keys_to_addr(publickey, secretkey, serverkey)

        if publickey is None:
            _log.debug('publickey is None')
        if secretkey is None:
            _log.debug('secretkey is None')

        self.publickey = publickey
        self.secretkey = secretkey

        if self.agent_uuid:
            installed_path = os.path.join(
                os.environ['VOLTTRON_HOME'], 'agents', self.agent_uuid)
            if not os.path.exists(os.path.join(installed_path, 'IDENTITY')):
                _log.debug('CREATING IDENTITY FILE')
                with open(os.path.join(installed_path, 'IDENTITY'), 'w') as fp:
                    fp.write(self.identity)
            else:
                _log.debug('IDENTITY FILE EXISTS FOR {}'
                    .format(self.agent_uuid))

        self.socket = None
        self.subsystems = {'error': self.handle_error}
        self.__connected = False

    def _add_keys_to_addr(self, publickey, secretkey, serverkey):
        '''Adds public, secret, and server keys to query in VIP address if
        they are not already present'''

        def add_param(query_str, key, value):
            query_dict = urlparse.parse_qs(query_str)
            if not value or key in query_dict:
                return ''
            # urlparse automatically adds '?', but we need to add the '&'s
            return '{}{}={}'.format('&' if query_str else '', key, value)

        url = list(urlparse.urlsplit(self.address))
        if url[0] == 'tcp':
            url[3] += add_param(url[3], 'publickey', publickey)
            url[3] += add_param(url[3], 'secretkey', secretkey)
            url[3] += add_param(url[3], 'serverkey', serverkey)
            self.address = str(urlparse.urlunsplit(url))

    def _get_keys(self):
        publickey, secretkey, _ = self._get_keys_from_addr()
        if not publickey or not secretkey:
            publickey, secretkey = self._get_keys_from_keystore()
        return publickey, secretkey

    def _get_keys_from_keystore(self):
        '''Returns agent's public and secret key from keystore'''
        if self.agent_uuid:
            # this is an installed agent
            keystore_dir = os.curdir
        elif self.identity:
            if not os.environ.get('VOLTTRON_HOME'):
                raise ValueError('VOLTTRON_HOME must be specified.')
            keystore_dir = os.path.join(
                os.environ.get('VOLTTRON_HOME'), 'keystores',
                self.identity)
            if not os.path.exists(keystore_dir):
                os.makedirs(keystore_dir)
        else:
            # the agent is not installed and its identity was not set
            return None, None
        keystore_path = os.path.join(keystore_dir, 'keystore.json')
        keystore = KeyStore(keystore_path)
        return keystore.public(), keystore.secret()

    def _get_keys_from_addr(self):
        url = list(urlparse.urlsplit(self.address))
        query = urlparse.parse_qs(url[3])
        publickey = query.get('publickey', None)
        secretkey = query.get('secretkey', None)
        serverkey = query.get('serverkey', None)
        return publickey, secretkey, serverkey

    @property
    def connected(self):
        return self.__connected

    def register(self, name, handler, error_handler=None):
        self.subsystems[name] = handler
        if error_handler:
            def onerror(sender, error, **kwargs):
                if error.subsystem == name:
                    error_handler(sender, error=error, **kwargs)
            self.onviperror.connect(onerror)

    def handle_error(self, message):
        if len(message.args) < 4:
            _log.debug('unhandled VIP error %s', message)
        elif self.onviperror:
            args = [bytes(arg) for arg in message.args]
            error = VIPError.from_errno(*args)
            self.onviperror.send(self, error=error, message=message)

    def loop(self):
        # pre-setup
        self.socket = vip.Socket(self.context)
        if self.identity:
            self.socket.identity = self.identity
        yield

        # pre-start
        state = type('HelloState', (), {'count': 0, 'ident': None})

        def hello():
            state.ident = ident = b'connect.hello.%d' % state.count
            state.count += 1
            self.spawn(self.socket.send_vip,
                       b'', b'hello', [b'hello'], msg_id=ident)

        def monitor():
            # Call socket.monitor() directly rather than use
            # get_monitor_socket() so we can use green sockets with
            # regular contexts (get_monitor_socket() uses
            # self.context.socket()).
            addr = 'inproc://monitor.v-%d' % (id(self.socket),)
            self.socket.monitor(addr)
            try:
                sock = zmq.Socket(self.context, zmq.PAIR)
                sock.connect(addr)
                while True:
                    message = recv_monitor_message(sock)
                    self.onsockevent.send(self, **message)
                    event = message['event']
                    if event & zmq.EVENT_CONNECTED:
                        hello()
                    elif event & zmq.EVENT_DISCONNECTED:
                        self.__connected = False
                        self.ondisconnected.send(self)
            finally:
                self.socket.monitor(None, 0)

        if self.address[:4] in ['tcp:', 'ipc:']:
            self.spawn(monitor).join(0)
        self.socket.connect(self.address)
        if self.address.startswith('inproc:'):
            hello()

        def vip_loop():
            sock = self.socket
            while True:
                try:
                    message = sock.recv_vip_object(copy=False)
                except ZMQError as exc:
                    if exc.errno == EAGAIN:
                        continue
                    raise

                subsystem = bytes(message.subsystem)
                # Handle hellos sent by CONNECTED event
                if (subsystem == b'hello' and
                        bytes(message.id) == state.ident and
                        len(message.args) > 3 and
                        bytes(message.args[0]) == b'welcome'):
                    version, server, identity = [
                        bytes(x) for x in message.args[1:4]]
                    self.__connected = True
                    self.onconnected.send(self, version=version,
                                          router=server, identity=identity)
                    continue

                try:
                    handle = self.subsystems[subsystem]
                except KeyError:
                    _log.error('peer %r requested unknown subsystem %r',
                               bytes(message.peer), subsystem)
                    message.user = b''
                    message.args = list(router._INVALID_SUBSYSTEM)
                    message.args.append(message.subsystem)
                    message.subsystem = b'error'
                    sock.send_vip_object(message, copy=False)
                else:
                    handle(message)

        yield gevent.spawn(vip_loop)
        # pre-stop
        yield
        # pre-finish
        try:
            self.socket.disconnect(self.address)
        except ZMQError as exc:
            if exc.errno != ENOENT:
                _log.exception('disconnect error')
        yield


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
