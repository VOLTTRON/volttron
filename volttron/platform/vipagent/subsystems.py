
from __future__ import absolute_import, print_function

import errno
import functools
import inspect
import logging
import os
import random
import string
import sys
import traceback
from types import MethodType
import weakref

import gevent.local
from gevent.event import AsyncResult
from zmq import green as zmq
from zmq import SNDMORE, ZMQError
from zmq.utils import jsonapi

from .. import jsonrpc, vip

import volttron

_VOLTTRON_PATH = os.path.dirname(volttron.__path__[-1]) + os.sep
del volttron


_log = logging.getLogger(__name__)


def annotate(obj, kind, name, value):
    # pylint: disable=protected-access
    try:
        annotations = obj._annotations
    except AttributeError:
        obj._annotations = annotations = {}
    try:
        items = annotations[name]
    except KeyError:
        annotations[name] = items = kind()
    assert isinstance(items, kind)
    try:
        add = items.add
    except AttributeError:
        try:
            add = items.append
        except AttributeError:
            try:
                add = items.update
            except AttributeError:
                items += value
                return
    add(value)


def get_annotations(obj, kind, name):
    # pylint: disable=protected-access
    try:
        annotations = obj._annotations
    except AttributeError:
        annotations = {}
    try:
        items = annotations[name]
    except KeyError:
        items = kind()
    assert isinstance(items, kind)
    return items


def spawn(method):
    '''Run a decorated method in its own greenlet, which is returned.'''
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        return gevent.spawn(method, *args, **kwargs)
    return wrapper


class dualmethod(object):
    '''Descriptor to allow class and instance methods of the same name.

    This class implements a descriptor that works similar to the
    classmethod() built-ins and can be used as a decorator, like the
    property() built-in. Instead of a method being only a class or
    instance method, two methods can share the same name and be accessed
    as an instance method or a class method based on the context.

    Example:

    >>> class Foo(object):
    ...     @dualmethod
    ...     def bar(self):
    ...         print 'instance method for', self
    ...     @bar.classmethod
    ...     def bar(cls):
    ...         print 'class method for', cls
    ...
    >>> Foo.bar()
    class method for <class '__main__.Foo'>
    >>> Foo().bar()
    instance method for <__main__.Foo object at 0x7fcd744f6610>
    >>>
    '''

    def __init__(self, finstance=None, fclass=None, doc=None):
        '''Instantiate the descriptor with the given parameters.

        If finstance is set, it must be a method implementing instance
        access. If fclass is set, it must be a method implementing class
        access similar to a classmethod. If doc is set, it will be used
        for the __doc__ attribute.  Otherwise, the __doc__ attribute
        from the instance or class method will be used, in that order.
        '''
        self.finstance = finstance
        self.fclass = fclass
        if doc is not None:
            self.__doc__ = doc
        elif finstance is not None:
            self.__doc__ = finstance.__doc__
        elif fclass is not None:
            self.__doc__ = fclass.__doc__

    def __get__(self, instance, owner):
        '''Descriptor getter method.

        See Python descriptor documentation.'''
        if instance is None:
            if self.fclass is None:
                if self.finstance is None:
                    raise AttributeError('no instance or class method is set')
                return MethodType(self.finstance, instance, owner)
            return MethodType(self.fclass, owner, owner)
        if self.finstance is None:
            if self.fclass is None:
                raise AttributeError('no instance or class method is set')
            return MethodType(self.fclass, owner, owner)
        return MethodType(self.finstance, instance, owner)

    def instancemethod(self, finstance):
        '''Descriptor to set the instance method.'''
        self.finstance = finstance
        return self

    def classmethod(self, fclass):
        '''Descriptor to set the class method.'''
        self.fclass = fclass
        return self


class VIPError(Exception):
    def __init__(self, errnum, msg, *args):
        super(VIPError, self).__init__(errnum, msg, *args)
        self.errno = errnum
        self.msg = msg

    def __string__(self):
        return 'VIP Error (%d): %s' % (self.errno, self.msg)

    def __repr__(self):
        return '%s%r' % (type(self).__name__, self.args)

    @classmethod
    def from_errno(cls, errnum, msg, *args):
        errnum = int(errnum)
        return {
            errno.EHOSTUNREACH: Unreachable,
            errno.EAGAIN: Again,
            errno.EPROTONOSUPPORT: UnknownSubsystem,
        }.get(errnum, cls)(errnum, msg, *args)


class Unreachable(VIPError):
    pass

class Again(VIPError):
    pass

class UnknownSubsystem(VIPError):
    pass


def counter(start=None, minimum=0, maximum=2**64-1):
    count = random.randint(minimum, maximum) if start is None else start
    while True:
        yield count
        count += 1
        if count >= maximum:
            count = minimum


class ResultsDictionary(weakref.WeakValueDictionary):
    def __init__(self):
        weakref.WeakValueDictionary.__init__(self)
        self._counter = counter()

    def next(self):
        result = gevent.event.AsyncResult()
        result.ident = ident = '%s.%s' % (next(self._counter), hash(result))
        self[ident] = result
        return result


class SubsystemBase(object):
    pass


class Ping(SubsystemBase):
    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('ping', self._handle_ping, self._handle_error)
        core.register('pong', self._handle_pong, self._handle_error)

    def ping(self, peer, *args):
        socket = self.core().socket
        result = next(self._results)
        socket.send_vip(peer, b'ping', args, result.ident)
        return result

    __call__ = ping

    def _handle_ping(self, message):
        socket = self.core().socket
        message.subsystem = vip._PONG
        message.user = b''
        socket.send_vip_object(message, copy=False)

    def _handle_pong(self, message):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set([bytes(arg) for arg in message.args])

    def _handle_error(self, message):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(
            VIPError.from_errno(*[bytes(arg) for arg in message.args]))


class Dispatcher(jsonrpc.Dispatcher):
    def __init__(self, methods, local):
        super(Dispatcher, self).__init__()
        self.methods = methods
        self.local = local
        self._results = ResultsDictionary()

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
                result = next(self._results)
                ident = result.ident
                results.append(result)
            methods.append((ident, method, args, kwargs))
        return super(Dispatcher, self).batch_call(methods), results

    def call(self, method, args=None, kwargs=None):
        # pylint: disable=arguments-differ
        result = next(self._results)
        return super(Dispatcher, self).call(
            result.ident, method, args, kwargs), result

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
        local.request = request
        local.batch = batch
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
            del local.request
            del local.batch

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


class RPC(SubsystemBase):
    def __init__(self, core, owner):
        self.core = weakref.ref(core)
        self.context = None
        self._exports = {}
        self._dispatcher = None
        self._counter = counter()
        self._outstanding = weakref.WeakValueDictionary()
        core.register('RPC', self._handle_subsystem, self._handle_error)

        def export(member):   # pylint: disable=redefined-outer-name
            for name in get_annotations(member, set, 'rpc.exports'):
                self._exports[name] = member
        inspect.getmembers(owner, export)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self.context = gevent.local.local()
            self._dispatcher = Dispatcher(self._exports, self.context)
        core.onsetup.connect(setup, self)

    @spawn
    def _handle_subsystem(self, message):
        dispatch = self._dispatcher.dispatch
        responses = [response for response in (
            dispatch(bytes(msg), message) for msg in message.args) if response]
        if responses:
            message.user = ''
            message.args = responses
            self.core().socket.send_vip_object(message, copy=False)

    def _handle_error(self, message):
        result = self._outstanding.pop(bytes(message.id), None)
        if isinstance(result, AsyncResult):
            result.set_exception(
                VIPError.from_errno(*[bytes(arg) for arg in message.args]))
        elif result:
            args = [bytes(arg) for arg in message.args]
            for result in result:
                result.set_exception(VIPError.from_errno(*args))

    @dualmethod
    def export(self, method, name=None):
        self._exports[name or method.__name__] = method
        return method

    @export.classmethod
    def export(cls, method, name=None):   # pylint: disable=no-self-argument
        annotate(method, set, 'rpc.exports', name or method.__name__)
        return method

    def batch(self, peer, requests):
        request, results = self._dispatcher.batch_call(requests)
        if results:
            items = weakref.WeakSet(results)
            ident = '%s.%s' % (next(self._counter), id(items))
            for result in results:
                result._weak_set = items   # pylint: disable=protected-access
            self._outstanding[ident] = items
        else:
            ident = None
        self.core().socket.send_vip(peer, 'RPC', [request], msg_id=ident)
        return results or None

    def call(self, peer, method, *args, **kwargs):
        request, result = self._dispatcher.call(method, args, kwargs)
        ident = '%s.%s' % (next(self._counter), hash(result))
        self._outstanding[ident] = result
        self.core().socket.send_vip(peer, 'RPC', [request], msg_id=ident)
        return result

    __call__ = call

    def notify(self, peer, method, *args, **kwargs):
        request = self._dispatcher.notify(method, args, kwargs)
        self.core().socket.send_vip(peer, 'RPC', [request])


class Hello(SubsystemBase):
    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('hello', self._handle_hello, self._handle_error)
        core.register('welcome', self._handle_welcome, self._handle_error)

    def hello(self, peer=b''):
        socket = self.core().socket
        result = next(self._results)
        socket.send_vip(peer, b'hello', msg_id=result.ident)
        return result

    __call__ = hello

    def _handle_hello(self, message):
        socket = self.core().socket
        message.subsystem = vip._WELCOME
        message.user = b''
        message.args = [vip._VERSION, socket.identity, message.peer]
        socket.send_vip_object(message, copy=False)

    def _handle_welcome(self, message):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set([bytes(arg) for arg in message.args])

    def _handle_error(self, message):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(
            VIPError.from_errno(*[bytes(arg) for arg in message.args]))


class PubSub(SubsystemBase):
    def __init__(self, core, rpc):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc)
        self._peer_subscriptions = {}
        self._my_subscriptions = {}
        self._synchronizing = 0

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            rpc.export(self.peer_subscribe, 'pubsub.subscribe')
            rpc.export(self.peer_unsubscribe, 'pubsub.unsubscribe')
            rpc.export(self.peer_list, 'pubsub.list')
            rpc.export(self.peer_publish, 'pubsub.publish')
            rpc.export(self.peer_push, 'pubsub.push')
        core.onsetup.connect(setup, self)

    def add_bus(self, name):
        self._peer_subscriptions.setdefault(name, {})

    def remove_bus(self, name):
        subscriptions = self._peer_subscriptions.pop(name, {})
        # XXX: notify subscribers of removed bus

    def peer_subscribe(self, prefix, bus=''):
        peer = bytes(self.rpc().context.vip_message.peer)
        subscriptions = self._peer_subscriptions[bus]
        for prefix in prefix if isinstance(prefix, list) else [prefix]:
            try:
                subscribers = subscriptions[prefix]
            except KeyError:
                subscriptions[prefix] = subscribers = set()
            subscribers.add(peer)

    def peer_unsubscribe(self, prefix, bus=''):
        peer = bytes(self.rpc().context.vip_message.peer)
        subscriptions = self._peer_subscriptions[bus]
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

    def peer_list(self, prefix='', bus='',
                         subscribed=True, reverse=False):
        peer = bytes(self.rpc().context.vip_message.peer)
        if bus is None:
            buses = [(bus, self._peer_subscriptions[bus])]
        else:
            buses = self._peer_subscriptions.iteritems()
        if reverse:
            test = prefix.startswith
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

    def peer_publish(self, topic, headers, message=None, bus=''):
        peer = bytes(self.rpc().context.vip_message.peer)
        self._distribute(peer, topic, headers, message, bus)

    def _distribute(self, peer, topic, headers, message=None, bus=''):
        try:
            subscriptions = self._peer_subscriptions[bus]
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
            socket = self.core().socket
            for subscriber in subscribers:
                socket.send_vip(subscriber, 'RPC', flags=SNDMORE)
                socket.send_multipart(frames, copy=False)
        return len(subscribers)

    def peer_push(self, sender, bus, topic, headers, message):
        '''Handle incoming subscriptions from peers.'''
        peer = bytes(self.rpc().context.vip_message.peer)
        handled = 0
        try:
            subscriptions = self._my_subscriptions[(peer, bus)]
        except KeyError:
            pass
        else:
            for prefix, callbacks in subscriptions.iteritems():
                if topic.startswith(prefix):
                    handled += 1
                    for callback in callbacks:
                        callback(peer, sender, bus, topic, headers, message)
        if not handled:
            self.synchronize(peer)

    def synchronize(self, peer, timeout=15, force=False):
        '''Unsubscribe from stale/forgotten/unsolicited subscriptions.'''
        # Limit to one cleanup operation at a time unless force is True.
        # There is no race condition setting _synchronizing
        # because the method is running in the context of gevent.
        if self._synchronizing and not force:
            return False
        self._synchronizing += 1
        try:
            rpc = self.rpc()
            topics = rpc.call(peer, 'pubsub.list').get(timeout=timeout)
            unsubscribe = {}
            for bus, prefix, _ in topics:
                try:
                    unsubscribe[bus].add(prefix)
                except KeyError:
                    unsubscribe[bus] = set([prefix])
            subscribe = {}
            for (ident, bus), subscriptions \
                    in self._my_subscriptions.iteritems():
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
                rpc.batch(
                    peer, ((True, 'pubsub.unsubscribe', (list(topics), bus), None)
                           for bus, topics in unsubscribe.iteritems()))
            if subscribe:
                rpc.batch(
                    peer, ((True, 'pubsub.subscribe', (list(topics), bus), None)
                           for bus, topics in subscribe.iteritems()))
        finally:
            self._synchronizing -= 1
        return True

    def subscribe(self, peer, prefix, callback, bus='', timeout=15):
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
        self.rpc().call(peer, 'pubsub.subscribe',
                        prefix, bus=bus).get(timeout=timeout)
        try:
            subscriptions = self._my_subscriptions[(peer, bus)]
        except KeyError:
            self._my_subscriptions[(peer, bus)] = subscriptions = {}
        try:
            callbacks = subscriptions[prefix]
        except KeyError:
            subscriptions[prefix] = callbacks = set()
        callbacks.add(callback)

    def unsubscribe(self, peer, prefix, callback, bus=''):
        '''Unsubscribe and remove callback(s).

        Remove all handlers matching the given handler ID, which is the
        ID returned by the subscribe method. If all handlers for a
        topic prefix are removed, the topic is also unsubscribed.
        '''
        if prefix is None:
            if callback is None:
                topics = self._my_subscriptions.pop((peer, bus)).keys()
            else:
                subscriptions = self._my_subscriptions[(peer, bus)]
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
            subscriptions = self._my_subscriptions[(peer, bus)]
            if callback is None:
                subscriptions.pop(prefix)
            else:
                callbacks = subscriptions[prefix]
                callbacks.discard(callback)
                if callbacks:
                    return
                del subscriptions[prefix]
            topics = [prefix]
        return self.rpc().call(peer, 'pubsub.unsubscribe', topics, bus=bus)


    def publish(self, peer, topic, headers=None, message=None, bus=''):
        '''Publish a message to a given topic via a peer.

        Publish headers and message to all subscribers of topic on bus
        at peer. If peer is None, use self.
        '''
        if headers is None:
            headers = {}
        if peer is None:
            self._distribute(self.core().socket.identity,
                             topic, headers, message, bus)
        else:
            return self.rpc().call(
                peer, 'pubsub.publish', topic=topic, headers=headers,
                message=message, bus=bus)


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
