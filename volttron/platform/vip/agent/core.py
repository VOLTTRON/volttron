# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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


import heapq
import inspect
import logging
import os
import platform as python_platform
import signal
import threading
import time
import urllib.parse
import uuid
import warnings
import weakref
from contextlib import contextmanager
from errno import ENOENT
from urllib.parse import urlsplit, parse_qs, urlunsplit

import gevent.event
from gevent.queue import Queue
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN, ENOTSOCK
from zmq.utils.monitor import recv_monitor_message

from volttron.platform import get_address
from volttron.platform import is_rabbitmq_available
from volttron.platform.agent import utils
from volttron.platform.agent.utils import load_platform_config, get_platform_instance_name
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from .decorators import annotate, annotations, dualmethod
from .dispatch import Signal
from .errors import VIPError
from .. import router
from ..rmq_connection import RMQConnection
from ..socket import Message
from ..zmq_connection import ZMQConnection
from .... import platform

if is_rabbitmq_available():
    import pika

__all__ = ['BasicCore', 'Core', 'RMQCore', 'ZMQCore', 'killing']

_log = logging.getLogger(__name__)


class Periodic(object):  # pylint: disable=invalid-name
    ''' Decorator to set a method up as a periodic callback.

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
        # Use monotonic clock provided on hu's loop instance.
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
        self.tie_breaker = 0

        # SIGINT does not work in Windows.
        # If using the standalone agent on a windows machine,
        # this section will be skipped
        if python_platform.system() != 'Windows':
            prev_int_signal = gevent.signal.getsignal(signal.SIGINT)
            # To avoid a child agent handler overwriting the parent agent handler
            if prev_int_signal in [None, signal.SIG_IGN, signal.SIG_DFL]:
                self.oninterrupt = gevent.signal.signal(signal.SIGINT,
                                                        self._on_sigint_handler)
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
            for deadline, args, kwargs in annotations(member, list, 'core.schedule'):
                self.schedule(deadline, member, *args, **kwargs)
            for name in annotations(member, set, 'core.signals'):
                findsignal(self, owner, name).connect(member, owner)

        inspect.getmembers(owner, setup)

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

        self._schedule_event = gevent.event.Event()
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
                    _, _, callback = heapq.heappop(heap)
                    greenlet = gevent.spawn(callback)
                    cur.link(lambda glt: greenlet.kill())

        self._stop_event = stop = gevent.event.Event()
        self._async = gevent.get_hub().loop.async()
        self._async.start(handle_async)
        current.link(lambda glt: self._async.stop())

        looper = self.loop(running_event)
        next(looper)
        self.onsetup.send(self)

        loop = next(looper)
        if loop:
            self.spawned_greenlets.add(loop)
        scheduler = gevent.Greenlet(schedule_loop)
        if loop:
            loop.link(lambda glt: scheduler.kill())
        self.onstart.connect(lambda *_, **__: scheduler.start())
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
        next(looper)
        receivers = self.onstop.sendby(self.link_receiver, self)
        gevent.wait(receivers)
        next(looper)
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
        _log.debug("SIG interrupt received. Calling stop")
        if signo == signal.SIGINT:
            self._stop_event.set()
            # self.stop()

    def send(self, func, *args, **kwargs):
        self._async_calls.append((func, args, kwargs))
        self._async.send()

    def send_async(self, func, *args, **kwargs):
        result = gevent.event.AsyncResult()
        async_ = gevent.hub.get_hub().loop.async_()
        results = [None, None]

        def receiver():
            async_.stop()
            exc, value = results
            if exc is None:
                result.set(value)
            else:
                result.set_exception(exc)

        async_.start(receiver)

        def worker():
            try:
                results[:] = [None, func(*args, **kwargs)]
            except Exception as exc:  # pylint: disable=broad-except
                results[:] = [exc, None]
            async_.send()

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
        warnings.warn(
            'Use of the periodic() method is deprecated in favor of the '
            'schedule() method with the periodic() generator. This '
            'method will be removed in a future version.',
            DeprecationWarning)
        greenlet = Periodic(period, args, kwargs, wait).get(func)
        self.spawned_greenlets.add(greenlet)
        greenlet.start()
        return greenlet

    @periodic.classmethod
    def periodic(cls, period, args=None, kwargs=None, wait=0):  # pylint: disable=no-self-argument
        warnings.warn(
            'Use of the periodic() decorator is deprecated in favor of '
            'the schedule() decorator with the periodic() generator. '
            'This decorator will be removed in a future version.',
            DeprecationWarning)
        return Periodic(period, args, kwargs, wait)

    @classmethod
    def receiver(cls, signal):
        def decorate(method):
            annotate(method, set, 'core.signals', signal)
            return method

        return decorate

    @dualmethod
    def schedule(self, deadline, func, *args, **kwargs):
        event = ScheduledEvent(func, args, kwargs)
        try:
            it = iter(deadline)
        except TypeError:
            self._schedule_callback(deadline, event)
        else:
            self._schedule_iter(it, event)
        return event

    def get_tie_breaker(self):
        self.tie_breaker += 1
        return self.tie_breaker

    def _schedule_callback(self, deadline, callback):
        deadline = utils.get_utc_seconds_from_epoch(deadline)
        heapq.heappush(self._schedule, (deadline, self.get_tie_breaker(), callback))
        if self._schedule_event:
            self._schedule_event.set()

    def _schedule_iter(self, it, event):
        def wrapper():
            if event.canceled:
                event.finished = True
                return
            try:
                deadline = next(it)
            except StopIteration:
                event.function(*event.args, **event.kwargs)
                event.finished = True
            else:
                self._schedule_callback(deadline, wrapper)
                event.function(*event.args, **event.kwargs)

        try:
            deadline = next(it)
        except StopIteration:
            event.finished = True
        else:
            self._schedule_callback(deadline, wrapper)

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
                 version='0.1', instance_name=None, messagebus=None):
        self.volttron_home = volttron_home

        # These signals need to exist before calling super().__init__()
        self.onviperror = Signal()
        self.onsockevent = Signal()
        self.onconnected = Signal()
        self.ondisconnected = Signal()
        self.configuration = Signal()
        super(Core, self).__init__(owner)
        self.address = address if address is not None else get_address()
        self.identity = str(identity) if identity is not None else str(uuid.uuid4())
        self.agent_uuid = agent_uuid
        self.publickey = publickey
        self.secretkey = secretkey
        self.serverkey = serverkey
        self.reconnect_interval = reconnect_interval
        self._reconnect_attempt = 0
        self.instance_name = instance_name
        self.messagebus = messagebus
        self.subsystems = {'error': self.handle_error}
        self.__connected = False
        self._version = version
        self.socket = None
        self.connection = None

        _log.debug('address: %s', address)
        _log.debug('identity: %s', self.identity)
        _log.debug('agent_uuid: %s', agent_uuid)
        _log.debug('serverkey: %s', serverkey)

    def version(self):
        return self._version

    def get_connected(self):
        return self.__connected

    def set_connected(self, value):
        self.__connected = value

    connected = property(fget=lambda self: self.get_connected(),
                         fset=lambda self, v: self.set_connected(v)
                         )

    def stop(self, timeout=None, platform_shutdown=False):
        # Send message to router that this agent is stopping
        if self.__connected and not platform_shutdown:
            frames = [self.identity]
            self.connection.send_vip('', 'agentstop', args=frames, copy=False)
        super(Core, self).stop(timeout=timeout)

    # This function moved directly from the zmqcore agent.  it is included here because
    # when we are attempting to connect to a zmq bus from a rmq bus this will be used
    # to create the public and secret key for that connection or use it if it was already
    # created.
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

    def register(self, name, handler, error_handler=None):
        self.subsystems[name] = handler
        if error_handler:
            name_bytes = name

            def onerror(sender, error, **kwargs):
                if error.subsystem == name_bytes:
                    error_handler(sender, error=error, **kwargs)

            self.onviperror.connect(onerror)

    def handle_error(self, message):
        if len(message.args) < 4:
            _log.debug('unhandled VIP error %s', message)
        elif self.onviperror:
            args = message.args
            error = VIPError.from_errno(*args)
            self.onviperror.send(self, error=error, message=message)

    def create_event_handlers(self, state, hello_response_event, running_event):
        def connection_failed_check():
            # If we don't have a verified connection after 10.0 seconds
            # shut down.
            if hello_response_event.wait(10.0):
                return
            _log.error("No response to hello message after 10 seconds.")
            _log.error("Type of message bus used {}".format(self.messagebus))
            _log.error("A common reason for this is a conflicting VIP IDENTITY.")
            _log.error("Another common reason is not having an auth entry on"
                       "the target instance.")
            _log.error("Shutting down agent.")
            _log.error("Possible conflicting identity is: {}".format(
                self.identity
            ))

            self.stop(timeout=10.0)

        def hello():
            # Send hello message to VIP router to confirm connection with
            # platform
            state.ident = ident = 'connect.hello.%d' % state.count
            state.count += 1
            self.spawn(connection_failed_check)
            message = Message(peer='', subsystem='hello',
                              id=ident, args=['hello'])
            self.connection.send_vip_object(message)

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

        return connection_failed_check, hello, hello_response


class ZMQCore(Core):
    """
    Concrete Core class for ZeroMQ message bus
    """

    def __init__(self, owner, address=None, identity=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, reconnect_interval=None,
                 version='0.1', enable_fncs=False,
                 instance_name=None, messagebus='zmq'):
        super(ZMQCore, self).__init__(owner, address=address, identity=identity,
                                      context=context, publickey=publickey, secretkey=secretkey,
                                      serverkey=serverkey, volttron_home=volttron_home,
                                      agent_uuid=agent_uuid, reconnect_interval=reconnect_interval,
                                      version=version,
                                      instance_name=instance_name, messagebus=messagebus)
        self.context = context or zmq.Context.instance()
        self._fncs_enabled = enable_fncs
        self.messagebus = messagebus
        self._set_keys()

        _log.debug("AGENT RUNNING on ZMQ Core {}".format(self.identity))

        self.socket = None

    def get_connected(self):
        return super(ZMQCore, self).get_connected()

    def set_connected(self, value):
        super(ZMQCore, self).set_connected(value)

    connected = property(get_connected, set_connected)

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
            query_dict = parse_qs(query_str)
            if not value or key in query_dict:
                return ''
            # urlparse automatically adds '?', but we need to add the '&'s
            return '{}{}={}'.format('&' if query_str else '', key, value)

        url = list(urlsplit(self.address))
        if url[0] in ['tcp', 'ipc']:
            url[3] += add_param(url[3], 'publickey', self.publickey)
            url[3] += add_param(url[3], 'secretkey', self.secretkey)
            url[3] += add_param(url[3], 'serverkey', self.serverkey)
            self.address = str(urlunsplit(url))

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
                            "not match known serverkey ({}).".format(
                self.serverkey, self.address, known_serverkey))

        # Until we have containers for agents we should not require all
        # platforms that connect to be in the known host file.
        # See issue https://github.com/VOLTTRON/volttron/issues/1117
        if known_serverkey is not None:
            self.serverkey = known_serverkey

    def _get_serverkey_from_known_hosts(self):
        known_hosts_file = os.path.join(self.volttron_home, 'known_hosts')
        known_hosts = KnownHostsStore(known_hosts_file)
        return known_hosts.serverkey(self.address)

    def _get_keys_from_addr(self):
        url = list(urlsplit(self.address))
        query = parse_qs(url[3])
        publickey = query.get('publickey', [None])[0]
        secretkey = query.get('secretkey', [None])[0]
        serverkey = query.get('serverkey', [None])[0]
        return publickey, secretkey, serverkey

    def loop(self, running_event):
        # pre-setup
        # self.context.set(zmq.MAX_SOCKETS, 30690)
        self.connection = ZMQConnection(self.address,
                                        self.identity,
                                        self.instance_name,
                                        context=self.context)
        self.connection.open_connection(zmq.DEALER)
        flags = dict(hwm=6000, reconnect_interval=self.reconnect_interval)
        self.connection.set_properties(flags)
        self.socket = self.connection.socket
        yield

        # pre-start
        state = type('HelloState', (), {'count': 0, 'ident': None})

        hello_response_event = gevent.event.Event()
        connection_failed_check, hello, hello_response = \
            self.create_event_handlers(state, hello_response_event, running_event)

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
                                self.connected = False
                            elif event & zmq.EVENT_CONNECT_RETRIED:
                                self._reconnect_attempt += 1
                                if self._reconnect_attempt == 50:
                                    self.connected = False
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
                        url = list(urllib.parse.urlsplit(self.address))
                        if url[0] in ['tcp'] and sock is not None:
                            sock.close()
                        if self.socket is not None:
                            self.socket.monitor(None, 0)
                    except Exception as exc:
                        _log.debug("Error in closing the socket: {}".format(exc))

        self.onconnected.connect(hello_response)
        self.ondisconnected.connect(close_socket)

        if self.address[:4] in ['tcp:', 'ipc:']:
            self.spawn(monitor).join(0)
        self.connection.connect()
        if self.address.startswith('inproc:'):
            hello()

        def vip_loop():
            sock = self.socket
            while True:
                try:
                    # Message at this point in time will be a
                    # volttron.platform.vip.socket.Message object that has attributes
                    # for all of the vip elements.  Note these are no longer bytes.
                    # see https://github.com/volttron/volttron/issues/2123
                    message = sock.recv_vip_object(copy=False)
                except ZMQError as exc:

                    if exc.errno == EAGAIN:
                        continue
                    elif exc.errno == ENOTSOCK:
                        self.socket = None
                        break
                    else:
                        raise
                subsystem = message.subsystem
                # _log.debug("Received new message {0}, {1}, {2}, {3}".format(
                #     subsystem, message.id, len(message.args), message.args[0]))

                # Handle hellos sent by CONNECTED event
                if (str(subsystem) == 'hello' and
                        message.id == state.ident and
                        len(message.args) > 3 and
                        message.args[0] == 'welcome'):
                    version, server, identity = message.args[1:4]
                    self.connected = True
                    self.onconnected.send(self, version=version,
                                          router=server, identity=identity)
                    continue

                try:
                    handle = self.subsystems[subsystem]
                except KeyError:
                    _log.error('peer %r requested unknown subsystem %r',
                               message.peer, subsystem)
                    message.user = ''
                    message.args = list(router._INVALID_SUBSYSTEM)
                    message.args.append(message.subsystem)
                    message.subsystem = 'error'
                    sock.send_vip_object(message, copy=False)
                else:
                    handle(message)

        yield gevent.spawn(vip_loop)
        # pre-stop
        yield
        # pre-finish
        try:
            self.connection.disconnect()
            self.socket.monitor(None, 0)
            self.connection.close_connection(1)
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


class RMQCore(Core):
    """
    Concrete Core class for RabbitMQ message bus
    """

    def __init__(self, owner, address=None, identity=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, reconnect_interval=None,
                 version='0.1', instance_name=None, messagebus='rmq',
                 volttron_central_address=None,
                 volttron_central_instance_name=None):
        super(RMQCore, self).__init__(owner, address=address, identity=identity,
                                      context=context, publickey=publickey, secretkey=secretkey,
                                      serverkey=serverkey, volttron_home=volttron_home,
                                      agent_uuid=agent_uuid, reconnect_interval=reconnect_interval,
                                      version=version, instance_name=instance_name, messagebus=messagebus)
        self.volttron_central_address = volttron_central_address

        # TODO Look at this and see if we really need this here.
        # if instance_name is specified as a parameter in this calls it will be because it is
        # a remote connection. So we load it from the platform configuration file
        if not instance_name:
            config_opts = load_platform_config()
            self.instance_name = config_opts.get('instance-name')
        else:
            self.instance_name = instance_name

        assert self.instance_name, "Instance name must have been set in the platform config file."
        assert not volttron_central_instance_name, "Please report this as volttron_central_instance_name shouldn't be passed."

        # self._event_queue = gevent.queue.Queue
        self._event_queue = Queue()

        self.rmq_user = '.'.join([self.instance_name, self.identity])

        _log.debug("AGENT RUNNING on RMQ Core {}".format(self.rmq_user))

        self.messagebus = messagebus
        self.rmq_mgmt = RabbitMQMgmt()
        self.rmq_address = address

    def _get_keys_from_addr(self):
        return None, None, None

    def get_connected(self):
        return super(RMQCore, self).get_connected()

    def set_connected(self, value):
        super(RMQCore, self).set_connected(value)

    connected = property(get_connected, set_connected)

    def _build_connection_parameters(self):
        param = None

        if self.identity is None:
            raise ValueError("Agent's VIP identity is not set")
        else:
            try:
                if self.instance_name == get_platform_instance_name():
                    param = self.rmq_mgmt.build_agent_connection(self.identity,
                                                                 self.instance_name)
                else:
                    param = self.rmq_mgmt.build_remote_connection_param(self.rmq_user,
                                                                        self.rmq_address,
                                                                        True)
            except AttributeError:
                _log.error("RabbitMQ broker may not be running. Restart the broker first")
                param = None

        return param

    def loop(self, running_event):
        if not isinstance(self.rmq_address, pika.ConnectionParameters):
            self.rmq_address = self._build_connection_parameters()
        # pre-setup
        self.connection = RMQConnection(self.rmq_address,
                                        self.identity,
                                        self.instance_name,
                                        reconnect_delay=self.rmq_mgmt.rmq_config.reconnect_delay(),
                                        vc_url=self.volttron_central_address)
        yield

        # pre-start
        flags = dict(durable=False, exclusive=True, auto_delete=True)
        if self.connection:
            self.connection.set_properties(flags)
            # Register callback handler for VIP messages
            self.connection.register(self.vip_message_handler)

        state = type('HelloState', (), {'count': 0, 'ident': None})
        hello_response_event = gevent.event.Event()
        connection_failed_check, hello, hello_response = \
            self.create_event_handlers(state, hello_response_event, running_event)

        def connection_error():
            self.connected = False
            self.stop()
            self.ondisconnected.send(self)

        def connect_callback():
            router_connected = False
            try:
                bindings = self.rmq_mgmt.get_bindings('volttron')
            except AttributeError:
                bindings = None
            router_user = router_key = "{inst}.{ident}".format(inst=self.instance_name,
                                                               ident='router')
            if bindings:
                for binding in bindings:
                    if binding['destination'] == router_user and \
                            binding['routing_key'] == router_key:
                        router_connected = True
                        break
            # Connection retry attempt issue #1702.
            # If the agent detects that RabbitMQ broker is reconnected before the router, wait
            # for the router to connect before sending hello()
            if router_connected:
                hello()
            else:
                _log.debug("Router not bound to RabbitMQ yet, waiting for 2 seconds before sending hello {}".
                           format(self.identity))
                self.spawn_later(2, hello)

        # Connect to RMQ broker. Register a callback to get notified when
        # connection is confirmed
        if self.rmq_address:
            self.connection.connect(connect_callback, connection_error)

        self.onconnected.connect(hello_response)
        self.ondisconnected.connect(self.connection.close_connection)

        def vip_loop():
            if self.rmq_address:
                wait_period = 1  # 1 second
                while True:
                    message = None
                    try:
                        message = self._event_queue.get(wait_period)
                    except gevent.Timeout:
                        pass
                    except Exception as exc:
                        _log.error(exc.args)
                        raise
                    if message:
                        subsystem = message.subsystem

                        if subsystem == 'hello':
                            if (subsystem == 'hello' and
                                    message.id == state.ident and
                                    len(message.args) > 3 and
                                    message.args[0] == 'welcome'):
                                version, server, identity = message.args[1:4]
                                self.connected = True
                                self.onconnected.send(self, version=version,
                                                      router=server,
                                                      identity=identity)
                                continue
                        try:
                            handle = self.subsystems[subsystem]
                        except KeyError:
                            _log.error('peer %r requested unknown subsystem %r',
                                       message.peer, subsystem)
                            message.user = ''
                            message.args = list(router._INVALID_SUBSYSTEM)
                            message.args.append(message.subsystem)
                            message.subsystem = 'error'
                            self.connection.send_vip_object(message)
                        else:
                            handle(message)

        yield gevent.spawn(vip_loop)
        # pre-stop
        yield
        # pre-finish
        if self.rmq_address:
            self.connection.close_connection()
        yield

    def vip_message_handler(self, message):
        # _log.debug("RMQ VIP Core {}".format(message))
        self._event_queue.put(message)
