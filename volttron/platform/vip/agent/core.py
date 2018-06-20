# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

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
import uuid
import weakref
import signal

import gevent.event
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN, ENOTSOCK, EADDRINUSE
from volttron.platform.agent import json
from zmq.utils.monitor import recv_monitor_message

from volttron.platform import get_address
from .decorators import annotate, annotations, dualmethod
from .dispatch import Signal
from .errors import VIPError
from .. import green as vip
from .. import router
from .... import platform
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.agent import utils

__all__ = ['BasicCore', 'Core', 'killing']

_log = logging.getLogger(__name__)


class Periodic(object):  # pylint: disable=invalid-name
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
            except (Exception, gevent.Timeout):
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
    delay_onstart_signal = False
    delay_running_event_set = False

    def __init__(self, owner):
        self.greenlet = None
        self.spawned_greenlets = weakref.WeakSet()
        self._async = None
        self._async_calls = []
        self._stop_event = None
        self._schedule_event = None
        self._schedule = []
        self.onsetup = Signal()
        self.onstart = Signal()
        self.onstop = Signal()
        self.onfinish = Signal()
        self.oninterrupt = None
        prev_int_signal = gevent.signal.getsignal(signal.SIGINT)
        # To avoid a child agent handler overwriting the parent agent handler
        if prev_int_signal in [None, signal.SIG_IGN, signal.SIG_DFL, signal.default_int_handler]:
            self.oninterrupt = gevent.signal.signal(signal.SIGINT, self._on_sigint_handler)
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

        def setup(member):  # pylint: disable=redefined-outer-name
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

        def start_periodics(sender, **kwargs):  # pylint: disable=unused-argument
            for periodic in periodics:
                sender.spawned_greenlets.add(periodic)
                periodic.start()
            del periodics[:]

        self.onstart.connect(start_periodics)

    def loop(self, running_event):
        # pre-setup
        yield
        # pre-start
        yield
        # pre-stop
        yield
        # pre-finish
        yield

    def link_receiver(self, receiver, sender, **kwargs):
        greenlet = gevent.spawn(receiver, sender, **kwargs)
        self.spawned_greenlets.add(greenlet)
        return greenlet

    def run(self, running_event=None):  # pylint: disable=method-hidden
        '''Entry point for running agent.'''

        self.setup()
        self.greenlet = current = gevent.getcurrent()

        def kill_leftover_greenlets():
            for glt in self.spawned_greenlets:
                glt.kill()

        self.greenlet.link(lambda _: kill_leftover_greenlets())

        def handle_async():
            '''Execute pending calls.'''
            calls = self._async_calls
            while calls:
                func, args, kwargs = calls.pop()
                greenlet = gevent.spawn(func, *args, **kwargs)
                self.spawned_greenlets.add(greenlet)

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

        self._stop_event = stop = gevent.event.Event()
        self._schedule_event = gevent.event.Event()
        self._async = gevent.get_hub().loop.async()
        self._async.start(handle_async)
        current.link(lambda glt: self._async.stop())

        looper = self.loop(running_event)
        looper.next()
        self.onsetup.send(self)

        loop = looper.next()
        if loop:
            self.spawned_greenlets.add(loop)
        scheduler = gevent.spawn(schedule_loop)
        if loop:
            loop.link(lambda glt: scheduler.kill())
        if not self.delay_onstart_signal:
            self.onstart.sendby(self.link_receiver, self)
        if not self.delay_running_event_set:
            if running_event is not None:
                running_event.set()
        try:
            if loop and loop in gevent.wait([loop, stop], count=1):
                raise RuntimeError('VIP loop ended prematurely')
            stop.wait()
        except (gevent.GreenletExit, KeyboardInterrupt):
            pass
        scheduler.kill()
        looper.next()
        receivers = self.onstop.sendby(self.link_receiver, self)
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

    def _on_sigint_handler(self, signo, *_):
        '''
        Event handler to set onstop event when the agent needs to stop
        :param signo:
        :param _:
        :return:
        '''
        _log.debug("SIG interrupt received. Setting stop event")
        if signo == signal.SIGINT:
            self._stop_event.set()

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
            except Exception as exc:  # pylint: disable=broad-except
                results[:] = [exc, None]
            async.send()

        self.send(worker)
        return result

    def spawn(self, func, *args, **kwargs):
        assert self.greenlet is not None
        greenlet = gevent.spawn(func, *args, **kwargs)
        self.spawned_greenlets.add(greenlet)
        return greenlet

    def spawn_later(self, seconds, func, *args, **kwargs):
        assert self.greenlet is not None
        greenlet = gevent.spawn_later(seconds, func, *args, **kwargs)
        self.spawned_greenlets.add(greenlet)
        return greenlet

    def spawn_in_thread(self, func, *args, **kwargs):
        result = gevent.event.AsyncResult()

        def wrapper():
            try:
                self.send(result.set, func(*args, **kwargs))
            except Exception as exc:  # pylint: disable=broad-except
                self.send(result.set_exception, exc)

        result.thread = thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        return result

    @dualmethod
    def periodic(self, period, func, args=None, kwargs=None, wait=0):
        greenlet = Periodic(period, args, kwargs, wait).get(func)
        self.spawned_greenlets.add(greenlet)
        greenlet.start()
        return greenlet

    @periodic.classmethod
    def periodic(cls, period, args=None, kwargs=None, wait=0):  # pylint: disable=no-self-argument
        return Periodic(period, args, kwargs, wait)

    @classmethod
    def receiver(cls, signal):
        def decorate(method):
            annotate(method, set, 'core.signals', signal)
            return method

        return decorate

    @dualmethod
    def schedule(self, deadline, func, *args, **kwargs):
        deadline = utils.get_utc_seconds_from_epoch(deadline)
        event = ScheduledEvent(func, args, kwargs)
        heapq.heappush(self._schedule, (deadline, event))
        self._schedule_event.set()
        return event

    @schedule.classmethod
    def schedule(cls, deadline, *args, **kwargs):  # pylint: disable=no-self-argument
        if hasattr(deadline, 'timetuple'):
            # deadline = time.mktime(deadline.timetuple())
            deadline = utils.get_utc_seconds_from_epoch(deadline)

        def decorate(method):
            annotate(method, list, 'core.schedule', (deadline, args, kwargs))
            return method

        return decorate


class Core(BasicCore):
    # We want to delay the calling of "onstart" methods until we have
    # confirmation from the server that we have a connection. We will fire
    # the event when we hear the response to the hello message.
    delay_onstart_signal = True

    # Agents started before the router can set this variable
    # to false to keep from blocking. AuthService does this.
    delay_running_event_set = True

    def __init__(self, owner, address=None, identity=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, reconnect_interval=None,
                 version='0.1', enable_fncs=False):

        self.volttron_home = volttron_home

        # These signals need to exist before calling super().__init__()
        self.onviperror = Signal()
        self.onsockevent = Signal()
        self.onconnected = Signal()
        self.ondisconnected = Signal()
        self.configuration = Signal()
        super(Core, self).__init__(owner)
        self.context = context or zmq.Context.instance()
        self.address = address if address is not None else get_address()
        self.identity = str(identity) if identity is not None else str(uuid.uuid4())
        self.agent_uuid = agent_uuid
        self.publickey = publickey
        self.secretkey = secretkey
        self.serverkey = serverkey
        self.reconnect_interval = reconnect_interval
        self._reconnect_attempt = 0
        self._set_keys()

        _log.debug('address: %s', address)
        _log.debug('identity: %s', identity)
        _log.debug('agent_uuid: %s', agent_uuid)
        _log.debug('serverkey: %s', serverkey)

        self.socket = None
        self.subsystems = {'error': self.handle_error}
        self.__connected = False
        self._version = version
        self._fncs_enabled=enable_fncs

    def version(self):
        return self._version

    def _set_keys(self):
        """Implements logic for setting encryption keys and putting
        those keys in the parameters of the VIP address
        """
        self._set_server_key()
        self._set_public_and_secret_keys()

        if self.publickey and self.secretkey and self.serverkey:
            self._add_keys_to_addr()

    def _add_keys_to_addr(self):
        '''Adds public, secret, and server keys to query in VIP address if
        they are not already present'''

        def add_param(query_str, key, value):
            query_dict = urlparse.parse_qs(query_str)
            if not value or key in query_dict:
                return ''
            # urlparse automatically adds '?', but we need to add the '&'s
            return '{}{}={}'.format('&' if query_str else '', key, value)

        url = list(urlparse.urlsplit(self.address))
        if url[0] in ['tcp', 'ipc']:
            url[3] += add_param(url[3], 'publickey', self.publickey)
            url[3] += add_param(url[3], 'secretkey', self.secretkey)
            url[3] += add_param(url[3], 'serverkey', self.serverkey)
            self.address = str(urlparse.urlunsplit(url))

    def _set_public_and_secret_keys(self):
        if self.publickey is None or self.secretkey is None:
            self.publickey, self.secretkey, _ = self._get_keys_from_addr()
        if self.publickey is None or self.secretkey is None:
            self.publickey, self.secretkey = self._get_keys_from_keystore()

    def _set_server_key(self):
        if self.serverkey is None:
            self.serverkey = self._get_keys_from_addr()[2]
        known_serverkey = self._get_serverkey_from_known_hosts()

        if (self.serverkey is not None and known_serverkey is not None
            and self.serverkey != known_serverkey):
            raise Exception("Provided server key ({}) for {} does "
                            "not match known serverkey ({}).".format(self.serverkey,
                                                                     self.address, known_serverkey))

        # Until we have containers for agents we should not require all
        # platforms that connect to be in the known host file.
        # See issue https://github.com/VOLTTRON/volttron/issues/1117
        if known_serverkey is not None:
            self.serverkey = known_serverkey

    def _get_serverkey_from_known_hosts(self):
        known_hosts_file = os.path.join(self.volttron_home, 'known_hosts')
        known_hosts = KnownHostsStore(known_hosts_file)
        return known_hosts.serverkey(self.address)

    def _get_keys_from_keystore(self):
        '''Returns agent's public and secret key from keystore'''
        if self.agent_uuid:
            # this is an installed agent, put keystore in its install dir
            keystore_dir = os.curdir
        elif self.identity is None:
            raise ValueError("Agent's VIP identity is not set")
        else:
            if not self.volttron_home:
                raise ValueError('VOLTTRON_HOME must be specified.')
            keystore_dir = os.path.join(
                self.volttron_home, 'keystores',
                self.identity)
            if not os.path.exists(keystore_dir):
                os.makedirs(keystore_dir)

        keystore_path = os.path.join(keystore_dir, 'keystore.json')
        keystore = KeyStore(keystore_path)
        return keystore.public, keystore.secret

    def _get_keys_from_addr(self):
        url = list(urlparse.urlsplit(self.address))
        query = urlparse.parse_qs(url[3])
        publickey = query.get('publickey', [None])[0]
        secretkey = query.get('secretkey', [None])[0]
        serverkey = query.get('serverkey', [None])[0]
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

    def loop(self, running_event):
        # pre-setup
        #self.context.set(zmq.MAX_SOCKETS, 30690)
        self.socket = vip.Socket(self.context)
        #_log.debug("CORE::MAx allowable sockets: {}".format(self.context.get(zmq.MAX_SOCKETS)))
        #_log.debug("AGENT SENDBUF: {0}, {1}".format(self.socket.getsockopt(zmq.SNDBUF), self.socket.getsockopt(zmq.RCVBUF)))
        # self.socket.setsockopt(zmq.SNDBUF, 302400)
        # self.socket.setsockopt(zmq.RCVBUF, 302400)
        # self.socket.set_hwm(500000)
        self.socket.set_hwm(6000)
        if self.reconnect_interval:
            self.socket.setsockopt(zmq.RECONNECT_IVL, self.reconnect_interval)
        if self.identity:
            self.socket.identity = self.identity
        yield

        # pre-start
        state = type('HelloState', (), {'count': 0, 'ident': None})

        hello_response_event = gevent.event.Event()

        def connection_failed_check():
            # If we don't have a verified connection after 10.0 seconds
            # shut down.
            if hello_response_event.wait(10.0):
                return
            _log.error("No response to hello message after 10 seconds.")
            _log.error("A common reason for this is a conflicting VIP IDENTITY.")
            _log.error("Another common reason is not having an auth entry on"
                       "the target instance.")
            _log.error("Shutting down agent.")
            _log.error("Possible conflicting identity is: {}".format(
                self.socket.identity
            ))

            self.stop(timeout=5.0)

        def hello():
            state.ident = ident = b'connect.hello.%d' % state.count
            state.count += 1
            self.spawn(connection_failed_check)
            self.spawn(self.socket.send_vip,
                       b'', b'hello', [b'hello'], msg_id=ident)

        def hello_response(sender, version='',
                           router='', identity=''):
            _log.info("Connected to platform: "
                      "router: {} version: {} identity: {}".format(
                router, version, identity))
            _log.debug("Running onstart methods.")
            hello_response_event.set()
            self.onstart.sendby(self.link_receiver, self)
            self.configuration.sendby(self.link_receiver, self)
            if running_event is not None:
                running_event.set()

        def close_socket(sender):
            gevent.sleep(2)
            try:
                if self.socket is not None:
                    self.socket.monitor(None, 0)
                    self.socket.close(1)
            finally:
                self.socket = None

        def monitor():
            # Call socket.monitor() directly rather than use
            # get_monitor_socket() so we can use green sockets with
            # regular contexts (get_monitor_socket() uses
            # self.context.socket()).
            addr = 'inproc://monitor.v-%d' % (id(self.socket),)
            sock = None
            if self.socket is not None:
                try:
                    self.socket.monitor(addr)
                    sock = zmq.Socket(self.context, zmq.PAIR)

                    sock.connect(addr)
                    while True:
                        try:
                            message = recv_monitor_message(sock)
                            self.onsockevent.send(self, **message)
                            event = message['event']
                            if event & zmq.EVENT_CONNECTED:
                                hello()
                            elif event & zmq.EVENT_DISCONNECTED:
                                self.__connected = False
                            elif event & zmq.EVENT_CONNECT_RETRIED:
                                self._reconnect_attempt += 1
                                if self._reconnect_attempt == 50:
                                    self.__connected = False
                                    sock.disable_monitor()
                                    self.stop()
                                    self.ondisconnected.send(self)
                            elif event & zmq.EVENT_MONITOR_STOPPED:
                                break
                        except ZMQError as exc:
                            if exc.errno == ENOTSOCK:
                                break

                except ZMQError as exc:
                    raise
                    # if exc.errno == EADDRINUSE:
                    #     pass
                finally:
                    try:
                        url = list(urlparse.urlsplit(self.address))
                        if url[0] in ['tcp'] and sock is not None:
                            sock.close()
                        if self.socket is not None:
                            self.socket.monitor(None, 0)
                    except Exception as exc:
                        _log.debug("Error in closing the socket: {}".format(exc.message))


        self.onconnected.connect(hello_response)
        self.ondisconnected.connect(close_socket)

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
                    elif exc.errno == ENOTSOCK:
                        self.socket = None
                        break
                    else:
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
            self.socket.monitor(None, 0)
            self.socket.close(1)
        except AttributeError:
            pass
        except ZMQError as exc:
            if exc.errno != ENOENT:
                _log.exception('disconnect error')
        finally:
            self.socket = None
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
