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

import inspect
import weakref

from zmq import green as zmq
from zmq import SNDMORE
from zmq.utils import jsonapi

from .base import SubsystemBase
from ..decorators import annotate, annotations, dualmethod, spawn
from ... import jsonrpc


__all__ = ['PubSub']


class PubSub(SubsystemBase):
    def __init__(self, core, rpc, owner):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc)
        self._peer_subscriptions = {}
        self._my_subscriptions = {}
        self._synchronizing = 0

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            rpc.export(self._peer_subscribe, 'pubsub.subscribe')
            rpc.export(self._peer_unsubscribe, 'pubsub.unsubscribe')
            rpc.export(self._peer_list, 'pubsub.list')
            rpc.export(self._peer_publish, 'pubsub.publish')
            rpc.export(self._peer_push, 'pubsub.push')
        core.onsetup.connect(setup, self)

        def start(sender, **kwargs):
            def subscribe(member):   # pylint: disable=redefined-outer-name
                for peer, bus, prefix in annotations(
                        member, set, 'pubsub.subscriptions'):
                    self.subscribe(peer, prefix, member, bus)
            inspect.getmembers(owner, subscribe)
        core.onstart.connect(start, self)

    def add_bus(self, name):
        self._peer_subscriptions.setdefault(name, {})

    def remove_bus(self, name):
        subscriptions = self._peer_subscriptions.pop(name, {})
        # XXX: notify subscribers of removed bus

    def _peer_subscribe(self, prefix, bus=''):
        peer = bytes(self.rpc().context.vip_message.peer)
        subscriptions = self._peer_subscriptions[bus]
        for prefix in prefix if isinstance(prefix, list) else [prefix]:
            try:
                subscribers = subscriptions[prefix]
            except KeyError:
                subscriptions[prefix] = subscribers = set()
            subscribers.add(peer)

    def _peer_unsubscribe(self, prefix, bus=''):
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

    def _peer_list(self, prefix='', bus='', subscribed=True, reverse=False):
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

    def _peer_publish(self, topic, headers, message=None, bus=''):
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
            frames = [zmq.Frame(b''), zmq.Frame(b''),
                      zmq.Frame(b'RPC'), zmq.Frame(json_msg)]
            socket = self.core().socket
            for subscriber in subscribers:
                socket.send(subscriber, flags=SNDMORE)
                socket.send_multipart(frames, copy=False)
        return len(subscribers)

    def _peer_push(self, sender, bus, topic, headers, message):
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
            self.synchronize(peer).get(timeout=15)   # pylint: disable=no-member

    @spawn
    def synchronize(self, peer, force=False):
        '''Unsubscribe from stale/forgotten/unsolicited subscriptions.'''
        # Limit to one cleanup operation at a time unless force is True.
        # There is no race condition setting _synchronizing
        # because the method is running in the context of gevent.
        if self._synchronizing and not force:
            return False
        self._synchronizing += 1
        try:
            rpc = self.rpc()
            topics = self.list(peer).get()
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
                    peer, ((True, 'pubsub.unsubscribe', (list(topics), bus), {})
                           for bus, topics in unsubscribe.iteritems()))
            if subscribe:
                rpc.batch(
                    peer, ((True, 'pubsub.subscribe', (list(topics), bus), {})
                           for bus, topics in subscribe.iteritems()))
        finally:
            self._synchronizing -= 1
        return True

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False):
        return self.rpc().call(peer, 'pubsub.list', prefix,
                               bus, subscribed, reverse)

    @dualmethod
    def subscribe(self, peer, prefix, callback, bus=''):
        '''Subscribe to topic and register callback.

        Subscribes to topics beginning with prefix. If callback is
        supplied, it should be a function taking four arguments,
        callback(peer, sender, bus, topic, headers, message), where peer
        is the ZMQ identity of the bus owner sender is identity of the
        publishing peer, topic is the full message topic, headers is a
        case-insensitive dictionary (mapping) of message headers, and
        message is a possibly empty list of message parts.
        '''
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        def finish(result):
            if not result.successful():
                return
            try:
                subscriptions = self._my_subscriptions[(peer, bus)]
            except KeyError:
                self._my_subscriptions[(peer, bus)] = subscriptions = {}
            try:
                callbacks = subscriptions[prefix]
            except KeyError:
                subscriptions[prefix] = callbacks = set()
            callbacks.add(callback)
        result = self.rpc().call(peer, 'pubsub.subscribe', prefix, bus=bus)
        result.rawlink(finish)
        return result
    
    @subscribe.classmethod
    def subscribe(self, peer, prefix, bus=''):
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix))
            return method
        return decorate

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
