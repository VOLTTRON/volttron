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

'''VOLTTRON platform™ base RPC agent and helper classes/functions.'''

from __future__ import absolute_import, print_function

import functools
import inspect
import logging
import os
import sys
import traceback
import weakref

import gevent
import gevent.local
from gevent.event import AsyncResult
from zmq import green as zmq
from zmq import EAGAIN, ZMQError, SNDMORE
from zmq.utils import jsonapi

# Import gevent-friendly version of vip
from ..vip import green as vip
from .. import jsonrpc
from ... import platform

import volttron

_VOLTTRON_PATH = os.path.dirname(volttron.__path__[-1]) + os.sep
del volttron


_log = logging.getLogger(__name__)   # pylint: disable=invalid-name


def default_vip_address():
    '''Return the default VIP ZMQ address.'''
    home = os.path.abspath(platform.get_home())
    abstract = '@' if sys.platform.startswith('linux') else ''
    return 'ipc://%s%s/run/vip.socket' % (abstract, home)


class periodic(object):   # pylint: disable=invalid-name
    '''Decorator to set a method up as a periodic callback.

    The decorated method will be called with the given arguments every
    period seconds while the agent is executing its run loop.
    '''

    def __init__(self, period, args=None, kwargs=None, wait=False):
        '''Store period (seconds) and arguments to call method with.'''
        self.period = period
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.wait = wait

    def __call__(self, method):
        '''Attach this object instance to the given method.'''
        # pylint: disable=protected-access
        try:
            periodics = method._periodics
        except AttributeError:
            method._periodics = periodics = []
        periodics.append(self)
        return method

    def _loop(self, method):
        # pylint: disable=missing-docstring
        if self.wait:
            gevent.sleep(self.period)
        while True:
            method(*self.args, **self.kwargs)
            gevent.sleep(self.period)

    def get(self, method):
        '''Return a Greenlet for the given method.'''
        return gevent.Greenlet(self._loop, method)


def subsystem(name):
    '''Decorator to set a method as a subsystem callback.'''
    def decorate(method):
        # pylint: disable=protected-access,missing-docstring
        try:
            subsystems = method._vip_subsystems
        except AttributeError:
            method._vip_subsystems = subsystems = []
        subsystems.append(name)
        return method
    return decorate


def onevent(event, args=None, kwargs=None):
    '''Decorator to call method on given event trigger during agent run.

    Decorated method will be called with args and kwargs (if given) in
    the same greenlet as the communications loop, meaning that no
    communications can occur while while the method is running.
    '''
    assert event in ['setup', 'connect', 'start',
                     'finish', 'disconnect', 'stop']
    def decorate(method):
        # pylint: disable=protected-access,missing-docstring
        try:
            events = method._event_callbacks
        except AttributeError:
            method._event_callbacks = events = []
        events.append((event, args or (), kwargs or {}))
        return method
    return decorate


def spawn(method):
    '''Run a decorated method in its own greenlet, which is returned.'''
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        return gevent.spawn(method, *args, **kwargs)
    return wrapper


class VIPAgent(object):
    '''Base class for creating VOLTTRON platform agents.

    This class can be used as is, but it won't do much. It will sit and
    do nothing but listen for messages and exit when told to. That is it.
    '''

    def __init__(self, vip_address=None, vip_identity=None,
                 context=None, **kwargs):
        super(VIPAgent, self).__init__(**kwargs)
        if not vip_address:
            vip_address = os.environ.get(
                'VOLTTRON_VIP_ADDR', default_vip_address())
        self.context = context or zmq.Context.instance()
        self.my_context = zmq.Context()
        self.vip_address = vip_address
        self.vip_identity = vip_identity
        self.local = gevent.local.local()
        self._periodics = []
        self._event_callbacks = {}
        self._vip_subsystems = {}
        def setup(member):
            for periodic in getattr(member, '_periodics', ()):
                self._periodics.append(periodic.get(member))
            for event, args, kwargs in getattr(member, '_event_callbacks', ()):
                try:
                    evlist = self._event_callbacks[event]
                except KeyError:
                    self._event_callbacks[event] = evlist = []
                evlist.append((member, args, kwargs))
            for name in getattr(member, '_vip_subsystems', ()):
                self._vip_subsystems[name] = member
        inspect.getmembers(self, setup)

    def run(self):
        '''Entry point for running agent.

        Subclasses should not override this method. Instead, the setup
        and finish methods should be overridden to customize behavior.
        '''
        def _trigger_event(event):
            for callback, args, kwargs in self._event_callbacks.get(event, ()):
                callback(*args, **kwargs)
        self.vip_socket = vip.Socket(self.context)   # pylint: disable=attribute-defined-outside-init
        if self.vip_identity:
            self.vip_socket.identity = self.vip_identity
        _trigger_event('setup')
        self.vip_socket.connect(self.vip_address)
        _trigger_event('connect')
        # Start periodic callbacks
        for periodic in self._periodics:
            periodic.start()
        _trigger_event('start')
        try:
            self._vip_loop()
        finally:
            _trigger_event('stop')
            gevent.killall(self._periodics)
            _trigger_event('disconnect')
            try:
                self.vip_socket.disconnect(self.vip_address)
            except ZMQError:
                pass
            _trigger_event('finish')

    def _vip_loop(self):
        socket = self.vip_socket
        while True:
            try:
                message = socket.recv_vip_object(copy=False)
            except ZMQError as exc:
                if exc.errno == EAGAIN:
                    continue
                raise

            try:
                method = self._vip_subsystems[bytes(message.subsystem)]
            except KeyError:
                _log.error('peer %r requested unknown subsystem %r',
                           bytes(message.peer), bytes(message.subsystem))
                message.user = b''
                message.args = [b'51', b'unknown subsystem', message.subsystem]
                message.subsystem = b'error'
                socket.send_vip_object(message, copy=False)
            else:
                method(message)

    @subsystem('pong')
    def handle_pong_subsystem(self, message):
        print('Pong:', message)

    @subsystem('ping')
    def handle_ping_subsystem(self, message):
        message.subsystem = b'pong'
        message.user = b''
        self.vip_socket.send_vip_object(message, copy=False)

    @subsystem('error')
    def handle_error_subsystem(self, message):
        print('VIP error', message)


class RPCDispatcher(jsonrpc.Dispatcher):
    def __init__(self, methods, local):
        super(RPCDispatcher, self).__init__()
        self.methods = methods
        self.local = local
        self._results = weakref.WeakValueDictionary()

    def _add_result(self):
        result = AsyncResult()
        ident = id(result)
        self._results[ident] = result
        return ident, result

    def serialize(self, json_obj):
        return jsonapi.dumps(json_obj)

    def deserialize(self, json_string):
        return jsonapi.loads(json_string)

    def batch_call(self, requests):
        methods = []
        results = []
        for notify, method, args, kwargs in requests:
            if notify:
                ident = None
            else:
                ident, result = self._add_result()
                results.append(result)
            methods.append((ident, method, args, kwargs))
        return super(RPCDispatcher, self).batch_call(methods), results

    def call(self, method, args=None, kwargs=None):
        # pylint: disable=arguments-differ
        ident, result = self._add_result()
        return super(RPCDispatcher, self).call(
            ident, method, args, kwargs), result

    def result(self, response, ident, value, context=None):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set(value)

    def error(self, response, ident, code, message, data=None, context=None):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(jsonrpc.exception_from_json(code, message, data))

    def exception(self, response, ident, message, context=None):
        # XXX: Should probably wrap exception in RPC specific error
        #      rather than re-raising.
        exc_type, exc, exc_tb = sys.exc_info()   # pylint: disable=unused-variable
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(exc)

    def method(self, request, ident, name, args, kwargs,
               batch=None, context=None):
        if kwargs:
            try:
                args, kwargs = kwargs['*args'], kwargs['**kwargs']
            except KeyError:
                pass
        try:
            method = self.methods[name]
        except KeyError:
            if name == 'inspect':
                return {'methods': self.methods.keys()}
            elif name.endswith('.inspect'):
                try:
                    method = self.methods[name[:-8]]
                except KeyError:
                    pass
                else:
                    return self._inspect(method)
            raise NotImplementedError(name)
        local = self.local
        local.vip_message = context
        local.rpc_request = request
        local.rpc_batch = batch
        try:
            return method(*args, **kwargs)
        except Exception as exc:   # pylint: disable=broad-except
            exc_tb = traceback.format_exc()
            _log.error('unhandled exception in JSON-RPC method %r: \n%s',
                       name, exc_tb)
            if getattr(method, 'traceback', True):
                exc.exc_info = {'exc_tb': exc_tb}
            raise
        finally:
            del local.vip_message
            del local.rpc_request
            del local.rpc_batch

    def _inspect(self, method):
        params = inspect.getargspec(method)
        if hasattr(method, 'im_self'):
            params.args.pop(0)
        response = {'params': params}
        doc = inspect.getdoc(method)
        if doc:
            response['doc'] = doc
        try:
            source = inspect.getsourcefile(method)
            cut = len(os.path.commonprefix([_VOLTTRON_PATH, source]))
            source = source[cut:]
            lineno = inspect.getsourcelines(method)[1]
        except IOError:
            pass
        else:
            response['source'] = source, lineno
        try:
            # pylint: disable=protected-access
            response['return'] = method._returns
        except AttributeError:
            pass
        return response


def export(name=None):
    def decorate(method):
        # pylint: disable=protected-access,attribute-defined-outside-init
        try:
            exports = method._rpc_exports
        except AttributeError:
            method._rpc_exports = exports = []
        exports.append(name or method.__name__)
        return method
    return decorate


class RPCMixin(object):
    @onevent('setup')
    def setup_rpc_subsystem(self):
        # pylint: disable=attribute-defined-outside-init
        self._rpc_exports = {}
        def setup(member):
            for name in getattr(member, '_rpc_exports', ()):
                self._rpc_exports[name] = member
        inspect.getmembers(self, setup)
        self._rpc_dispatcher = RPCDispatcher(self._rpc_exports, self.local)

    @subsystem('RPC')
    @spawn
    def handle_rpc_message(self, message):
        dispatch = self._rpc_dispatcher.dispatch
        responses = [response for response in (
            dispatch(bytes(msg), message) for msg in message.args) if response]
        if responses:
            message.user = ''
            message.args = responses
            self.vip_socket.send_vip_object(message, copy=False)

    def rpc_batch(self, peer, requests):
        request, results = self._rpc_dispatcher.batch_call(requests)
        self.vip_socket.send_vip(peer, 'RPC', [request])
        return results or None

    def rpc_call(self, peer, method, args=None, kwargs=None):
        request, result = self._rpc_dispatcher.call(method, args, kwargs)
        self.vip_socket.send_vip(peer, 'RPC', [request], msg_id=str(id(result)))
        return result

    def rpc_notify(self, peer, method, args=None, kwargs=None):
        request = self._rpc_dispatcher.notify(method, args, kwargs)
        self.vip_socket.send_vip(peer, 'RPC', [request])


class ChannelMixin(object):
    @onevent('setup')
    def setup_channel_subsystem(self):
        # pylint: disable=attribute-defined-outside-init
        self._channel_socket = self.my_context.socket(zmq.ROUTER)

    @onevent('connect')
    def connect_channel_subsystem(self):
        self._channel_socket.bind('inproc://subsystem/channel')

    @onevent('disconnect')
    def disconnect_channel_subsystem(self):
        try:
            self._channel_socket.unbind('inproc://subsystem/channel')
        except ZMQError:
            pass

    @onevent('start')
    def start_channel_subsystem(self):
        vip_socket = self.vip_socket
        socket = self._channel_socket
        def loop():
            while True:
                message = socket.recv_multipart(copy=False)
                if not message:
                    continue
                ident = bytes(message[0])
                length, ident = ident.split(':', 1)
                peer = ident[:int(length)]
                name = ident[len(peer)+1:]
                message[0] = name
                vip_socket.send_vip(peer, 'channel', message, copy=False)
        self._channel_subsystem = gevent.spawn(loop)   # pylint: disable=attribute-defined-outside-init

    @onevent('stop')
    def stop_channel_subsystem(self):
        greenlet = getattr(self, '_channel_subsystem', None)
        if greenlet is not None:
            greenlet.kill()

    @subsystem('channel')
    def handle_channel_message(self, message):
        frames = message.args
        try:
            name = frames[0]
        except IndexError:
            return
        peer, name = bytes(message.peer), bytes(name)
        frames[0] = ':'.join([str(len(peer)), peer, name])
        self._channel_socket.send_multipart(frames, copy=False)

    def channel_create(self, peer, name):
        socket = self.my_context.socket(zmq.DEALER)
        # XXX: Creating the identity this way is potentially problematic
        # because the peer name and identity can both be no longer than
        # 255 characters. Explore alternate solutions or limit names.
        ident = ':'.join([str(len(peer)), peer, name])
        socket.identity = ident
        socket.connect('inproc://subsystem/channel')
        return socket


class PubSubMixin(object):
    @onevent('setup')
    def setup_pubsub_subsystem(self):
        assert isinstance(self, RPCMixin)
        # pylint: disable=attribute-defined-outside-init
        self._pubsub_peer_subscriptions = {}
        self._pubsub_subscriptions = {}
        self._pubsub_synchronizing = 0

    def pubsub_add_bus(self, name):
        self._pubsub_peer_subscriptions.setdefault(name, {})

    def pubsub_remove_bus(self, name):
        subscriptions = self._pubsub_peer_subscriptions.pop(name, {})
        # XXX: notify subscribers of removed bus

    @export('pubsub.subscribe')
    def pubsub_peer_subscribe(self, prefix, bus=''):
        peer = bytes(self.local.vip_message.peer)
        subscriptions = self._pubsub_peer_subscriptions[bus]
        for prefix in prefix if isinstance(prefix, list) else [prefix]:
            try:
                subscribers = subscriptions[prefix]
            except KeyError:
                subscriptions[prefix] = subscribers = set()
            subscribers.add(peer)

    @export('pubsub.unsubscribe')
    def pubsub_peer_unsubscribe(self, prefix, bus=''):
        peer = bytes(self.local.vip_message.peer)
        subscriptions = self._pubsub_peer_subscriptions[bus]
        if prefix is None:
            empty = []
            for topic, subscribers in subscriptions.iteritems():
                subscribers.discard(peer)
                if not subscribers:
                    empty.append(topic)
            for topic in empty:
                subscriptions.pop(topic, None)
        else:
            for prefix in prefix if isinstance(prefix, list) else [prefix]:
                try:
                    subscribers = subscriptions[prefix]
                except KeyError:
                    pass
                else:
                    subscribers.discard(peer)
                    if not subscribers:
                        subscriptions.pop(prefix, None)

    @export('pubsub.list')
    def pubsub_peer_list(self, prefix='', bus='',
                         subscribed=True, reverse=False):
        peer = bytes(self.local.vip_message.peer)
        if bus is None:
            buses = [(bus, self._pubsub_peer_subscriptions[bus])]
        else:
            buses = self._pubsub_peer_subscriptions.iteritems()
        if reverse:
            test = lambda t: prefix.startswith(t)
        else:
            test = lambda t: t.startswith(prefix)
        results = []
        for _, subscriptions in buses:
            for topic, subscribers in subscriptions.iteritems():
                if test(topic):
                    member = peer in subscribers
                    if not subscribed or member:
                        results.append((bus, topic, member))
        return results

    @export('pubsub.publish')
    def pubsub_peer_publish(self, topic, headers, message=None, bus=''):
        peer = bytes(self.local.vip_message.peer)
        try:
            subscriptions = self._pubsub_peer_subscriptions[bus]
        except KeyError:
            return 0
        subscribers = set()
        for prefix, subscription in subscriptions.iteritems():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            json_msg = jsonapi.dumps(jsonrpc.json_method(
                None, 'pubsub.push', [peer, bus, topic, headers, message], None))
            frames = [zmq.Frame(b'RPC'), zmq.Frame(json_msg)]
            socket = self.vip_socket
            for subscriber in subscribers:
                socket.send_vip(subscriber, 'RPC', flags=SNDMORE)
                socket.send_multipart(frames, copy=False)
        return len(subscribers)

    @export('pubsub.push')
    def pubsub_peer_push(self, sender, bus, topic, headers, message):
        '''Handle incoming subscriptions from peers.'''
        peer = bytes(self.local.vip_message.peer)
        handled = 0
        try:
            subscriptions = self._pubsub_subscriptions[(peer, bus)]
        except KeyError:
            pass
        else:
            for prefix, callbacks in subscriptions.iteritems():
                if topic.startswith(prefix):
                    handled += 1
                    for callback in callbacks:
                        callback(peer, sender, bus, topic, headers, message)
        if not handled:
            self.pubsub_synchronize(peer)

    def pubsub_synchronize(self, peer, timeout=15, force=False):
        '''Unsubscribe from stale/forgotten/unsolicited subscriptions.'''
        # Limit to one cleanup operation at a time unless force is True.
        # There is no race condition setting _pubsub_synchronizing
        # because the method is running in the context of gevent.
        if self._pubsub_synchronizing and not force:
            return False
        self._pubsub_synchronizing += 1
        try:
            topics = self.rpc_call(peer, 'pubsub.list').get(timeout=timeout)
            unsubscribe = {}
            for bus, prefix, _ in topics:
                try:
                    unsubscribe[bus].add(prefix)
                except KeyError:
                    unsubscribe[bus] = set([prefix])
            subscribe = {}
            for (ident, bus), subscriptions \
                    in self._pubsub_subscriptions.iteritems():
                if peer != ident:
                    continue
                for prefix in subscriptions:
                    try:
                        topics = unsubscribe[bus]
                        topics.remove(prefix)
                    except KeyError:
                        try:
                            subscribe[bus].add(prefix)
                        except KeyError:
                            subscribe[bus] = set([prefix])
                    else:
                        if not topics:
                            del unsubscribe[bus]
            if unsubscribe:
                self.rpc_batch(
                    peer, ((True, 'pubsub.unsubscribe', (list(topics), bus), None)
                           for bus, topics in unsubscribe.iteritems()))
            if subscribe:
                self.rpc_batch(
                    peer, ((True, 'pubsub.subscribe', (list(topics), bus), None)
                           for bus, topics in subscribe.iteritems()))
        finally:
            self._pubsub_synchronizing -= 1
        return True

    def pubsub_subscribe(self, peer, prefix, callback, bus='', timeout=15):
        '''Subscribe to topic and register callback.

        Subscribes to topics beginning with prefix. If callback is
        supplied, it should be a function taking four arguments,
        callback(peer, bus, topic, headers, message), where peer is the
        ZMQ identity of the sender, topic is the full message topic,
        headers is a case-insensitive dictionary (mapping) of message
        headers, and message is a possibly empty list of message parts.

        Returns an ID number which can be used later to unsubscribe.
        '''
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        self.rpc_call(peer, 'pubsub.subscribe',
                      [prefix], {'bus': bus}).get(timeout=timeout)
        try:
            subscriptions = self._pubsub_subscriptions[(peer, bus)]
        except KeyError:
            self._pubsub_subscriptions[(peer, bus)] = subscriptions = {}
        try:
            callbacks = subscriptions[prefix]
        except KeyError:
            subscriptions[prefix] = callbacks = set()
        callbacks.add(callback)

    def pubsub_unsubscribe(self, peer, prefix, callback, bus='', timeout=15):
        '''Unsubscribe and remove callback(s).

        Remove all handlers matching the given handler ID, which is the
        ID returned by the subscribe method. If all handlers for a
        topic prefix are removed, the topic is also unsubscribed.
        '''
        if prefix is None:
            if callback is None:
                topics = self._pubsub_subscriptions.pop((peer, bus)).keys()
            else:
                subscriptions = self._pubsub_subscriptions[(peer, bus)]
                topics = []
                remove = []
                for topic, callbacks in subscriptions.iteritems():
                    try:
                        callbacks.remove(callback)
                    except KeyError:
                        pass
                    else:
                        topics.append(topic)
                    if not callbacks:
                        remove.append(topic)
                for topic in remove:
                    del subscriptions[topic]
        else:
            subscriptions = self._pubsub_subscriptions[(peer, bus)]
            if callback is None:
                subscriptions.pop(prefix)
            else:
                callbacks = subscriptions[prefix]
                callbacks.discard(callback)
                if callbacks:
                    return
                del subscriptions[prefix]
            topics = [prefix]
        self.rpc_call(peer, 'pubsub.unsubscribe',
                      topics, bus).get(timeout=timeout)


    def pubsub_publish(self, topic, headers={},
                       message=None, peer='pubsub', bus='', timeout=15):
        '''Publish a message to a given topic via a peer.

        Publish headers and message to all subscribers of topic on bus
        at peer.
        '''
        return self.rpc_call(
            peer, 'pubsub.publish',
            {'topic': topic, 'headers': headers,
             'message': message, 'bus': bus}).get(timeout=timeout)


class RPCAgent(VIPAgent, RPCMixin):
    pass


class BaseAgent(VIPAgent, RPCMixin, ChannelMixin, PubSubMixin):
    pass
