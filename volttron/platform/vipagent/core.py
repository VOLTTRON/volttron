
from __future__ import absolute_import, print_function

import logging
import os
import sys
import threading

import gevent.event
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN

from .dispatch import Signal
from ..vip import green as vip
from ... import platform


_log = logging.getLogger(__name__)


class Core(object):
    def __init__(self, address=None, identity=None, context=None):
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
        self.onstart.send_via(link_receiver, self)
        if loop in gevent.wait([loop, stop], count=1):
            raise RuntimeError('VIP loop ended prematurely')
        stop.wait()
        receivers = self.onstop.send_via(link_receiver, self)
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
