# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

from base64 import b64encode, b64decode
import inspect
import logging
import random
import re
import weakref

import gevent
from zmq import green as zmq
from zmq import SNDMORE
from zmq.utils import jsonapi

from .base import SubsystemBase
from ..decorators import annotate, annotations, dualmethod, spawn
from ..errors import Unreachable
from .... import jsonrpc
from volttron.platform.agent import utils
from ..results import ResultsDictionary
from gevent.queue import Queue, Empty

__all__ = ['PubSub']
min_compatible_version = '3.0'
max_compatible_version = ''

#utils.setup_logging()
_log = logging.getLogger(__name__)

def encode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64encode(peer[1:])
    return peer

def decode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64decode(peer[1:])
    return peer


class PubSub(SubsystemBase):
    def __init__(self, core, rpc_subsys, peerlist_subsys, owner):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc_subsys)
        self.peerlist = weakref.ref(peerlist_subsys)
        self._owner = owner
        self._peer_subscriptions = {}
        self._my_subscriptions = {}
        self.protected_topics = ProtectedPubSubTopics()
        core.register('pubsub', self._handle_subsystem, self._handle_error)
        self.vip_socket = None
        self._results = ResultsDictionary()
        self._event_queue = Queue()
        self._retry_period = 300.0
        self._processgreenlet = None

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            # rpc_subsys.export(self._peer_sync, 'pubsub.sync')
            # rpc_subsys.export(self._peer_subscribe, 'pubsub.subscribe')
            # rpc_subsys.export(self._peer_unsubscribe, 'pubsub.unsubscribe')
            # rpc_subsys.export(self._peer_list, 'pubsub.list')
            # rpc_subsys.export(self._peer_publish, 'pubsub.publish')
            # rpc_subsys.export(self._peer_push, 'pubsub.push')
            self._processgreenlet = gevent.spawn(self._process_loop)
            core.onconnected.connect(self._connected)
            peerlist_subsys.onadd.connect(self._peer_add)
            self.vip_socket = self.core().socket
            def subscribe(member):   # pylint: disable=redefined-outer-name
                for peer, bus, prefix in annotations(
                        member, set, 'pubsub.subscriptions'):
                    # XXX: needs updated in light of onconnected signal
                    self.add_subscription(peer, prefix, member, bus)
                    #_log.debug("PUBSUB SUBSYS subscribe with annotate. prefix {0}, identity: {1}".format(prefix, self.core().identity))
            inspect.getmembers(owner, subscribe)
        core.onsetup.connect(setup, self)

    def _connected(self, sender, **kwargs):
        #_log.debug("PUBSUB SUBSYS: connected so sync up {}".format(sender))
        self.synchronize(None, True)

    def _peer_add(self, sender, peer, **kwargs):
        # Delay sync by some random amount to prevent reply storm.
        #_log.debug("PUBSUB SUBSYS: peer add {}".format(peer))
        delay = random.random()
        self.core().spawn_later(delay, self.synchronize, peer, False)

    def _peer_push(self, sender, bus, topic, headers, message):
        '''Handle incoming subscription pushes from peers.'''
        #peer = bytes(self.rpc().context.vip_message.peer)
        peer = 'pubsub'
        handled = 0
        try:
            subscriptions = self._my_subscriptions[peer][bus]
        except KeyError:
            pass
        else:
            sender = decode_peer(sender)
            for prefix, callbacks in subscriptions.iteritems():
                if topic.startswith(prefix):
                    handled += 1
                    for callback in callbacks:
                        callback(peer, sender, bus, topic, headers, message)
        if not handled:
            # No callbacks for topic; synchronize with sender
            self.synchronize(peer, False)

    def synchronize(self, peer, connected_event):
        #_log.debug("AGENT PUBSUB {0} before synchronize: {1}".format(self.core().identity, self._my_subscriptions))
        '''Unsubscribe from stale/forgotten/unsolicited subscriptions.'''
        if peer is None:
            items = [(peer, {bus: subscriptions.keys()
                             for bus, subscriptions in buses.iteritems()})
                     for peer, buses in self._my_subscriptions.iteritems()]
        else:
            buses = self._my_subscriptions.get(peer) or {}
            items = [(peer, {bus: subscriptions.keys()
                             for bus, subscriptions in buses.iteritems()})]
        for (peer, subscriptions) in items:
            #self.rpc().notify(peer, 'pubsub.sync', subscriptions)
            sync_msg = jsonapi.dumps(
                dict(identity=self.core().identity, subscriptions=subscriptions)
            )
            if connected_event:
                #_log.debug("AGENT PUBSUB Syncing: {}".format(sync_msg))
                frames = [b'synchronize', b'connected', sync_msg]
                self.vip_socket.send_vip(b'', 'pubsub', frames, copy=False)
                # else:
                #     frames = [b'synchronize', b'', sync_msg]
                #_log.debug("Syncing: {}".format(sync_msg))
                #self.vip_socket.send_vip(b'', 'pubsub', frames, copy=False)

            #self.rpc().notify(peer, 'pubsub.sync', subscriptions)

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False):
        result = next(self._results)

        list_msg = jsonapi.dumps(
            dict(identity=self.core().identity, prefix=prefix,
                 subscribed=subscribed, reverse=reverse, bus=bus)
        )
        frames = [b'list', list_msg]
        self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
        return result
        #return self.rpc().call(peer, 'pubsub.list', prefix,
        #                       bus, subscribed, reverse)

    def add_subscription(self, peer, prefix, callback, bus=''):
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            buses = self._my_subscriptions[peer]
        except KeyError:
            self._my_subscriptions[peer] = buses = {}
        try:
            subscriptions = buses[bus]
        except KeyError:
            buses[bus] = subscriptions = {}
        try:
            callbacks = subscriptions[prefix]
        except KeyError:
            subscriptions[prefix] = callbacks = set()
        callbacks.add(callback)

    @dualmethod
    @spawn
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
        #result = next(self._results)
        self.add_subscription(peer, prefix, callback, bus)

        sub_msg = jsonapi.dumps(
            dict(identity=self.core().identity, prefix=prefix, bus=bus)
        )
        frames = [b'subscribe', sub_msg]
        #_log.debug("PUBSUB SUBSYS Subscribing: {}".format(sub_msg))
        self.vip_socket.send_vip(b'', 'pubsub', frames, copy=False)
        #return result
        return FakeAsyncResult()

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus=''):
        #_log.debug("PUBSUB SUBSYS subscribe with classmethod. prefix {}".format(prefix))
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix))
            return method
        return decorate

    def drop_subscription(self, peer, prefix, callback, bus=''):
        buses = self._my_subscriptions[peer]
        if prefix is None:
            if callback is None:
                subscriptions = buses.pop(bus)
                topics = subscriptions.keys()
            else:
                subscriptions = buses[bus]
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
                if not subscriptions:
                    del buses[bus]
            if not topics:
                raise KeyError('no such subscription')
        else:
            subscriptions = buses[bus]
            if callback is None:
                del subscriptions[prefix]
            else:
                callbacks = subscriptions[prefix]
                callbacks.remove(callback)
                if not callbacks:
                    del subscriptions[prefix]
            topics = [prefix]
            if not subscriptions:
                del buses[bus]
        if not buses:
            del self._my_subscriptions[peer]
        return topics

    def unsubscribe(self, peer, prefix, callback, bus=''):
        '''Unsubscribe and remove callback(s).

        Remove all handlers matching the given handler ID, which is the
        ID returned by the subscribe method. If all handlers for a
        topic prefix are removed, the topic is also unsubscribed.
        '''
        #result = next(self._results)
        topics = self.drop_subscription(peer, prefix, callback, bus)
        unsub_msg = jsonapi.dumps(
            dict(identity=self.core().identity, prefix=topics, bus=bus)
        )
        frames = [b'unsubscribe', unsub_msg]
        # frames.append(zmq.Frame(b'subscribe'))
        # frames.append(zmq.Frame(str(sub_msg)))
        #_log.debug("UnSubscribing: {}".format(unsub_msg))
        self.vip_socket.send_vip(b'', 'pubsub', frames, copy=False)
        return FakeAsyncResult()
        #return result
        #return self.rpc().call(peer, 'pubsub.unsubscribe', topics, bus=bus)

    def publish(self, peer, topic, headers=None, message=None, bus=''):
        '''Publish a message to a given topic via a peer.

        Publish headers and message to all subscribers of topic on bus
        at peer. If peer is None, use self. Adds volttron platform version
        compatibility information to header as variables
        min_compatible_version and max_compatible version
        '''
        result = next(self._results)
        if headers is None:
            headers = {}
        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version

        if peer is None:
            peer = 'pubsub'

        json_msg = jsonapi.dumps(
            dict(identity=self.core().identity, bus=bus, headers=headers, message=message)
        )
        frames = [zmq.Frame(b'publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]
        #<recipient, subsystem, args, msg_id, flags>
        self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
        return result

    def _check_if_protected_topic(self, topic):
        required_caps = self.protected_topics.get(topic)
        if required_caps:
            user = str(self.rpc().context.vip_message.user)
            caps = self._owner.vip.auth.get_capabilities(user)
            if not set(required_caps) <= set(caps):
                msg = ('to publish to topic "{}" requires capabilities {},'
                      ' but capability list {} was'
                      ' provided').format(topic, required_caps, caps)
                raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED, msg)

    def _handle_subsystem(self, message):
        self._event_queue.put(message)

    def _process_incoming_message(self, message):
        #_log.debug("Pubsub Agent handle subsystem: ")
        op = message.args[0].bytes
        #_log.debug("OP: {}".format(op))
        if op == 'subscribe_response':
            _log.debug("subscribe response message")
        elif op == 'publish':
            try:
                #data = message.args[1].bytes
                topic = topic = message.args[1].bytes
                data = message.args[2].bytes
                #_log.debug("DATA: {}".format(data))
            except IndexError:
                return
            #topic = message.args[1].bytes
            #json0 = data.find('{')
            #topic = data[0:json0 - 1]
            #msg = jsonapi.loads(data[json0:])
            msg = jsonapi.loads(data)
            headers = msg['headers']
            message = msg['message']
            # peer = bytes(self.vip.rpc.context.vip_message.peer)
            peer = msg['identity']
            bus = msg['bus']
            #_log.debug("PUBSUB Got pub message {0}, {1}, {2}, {3}, {4}".format(peer, topic, headers, message, bus))
            self._peer_push(peer, bus, topic, headers, message)
            # if self.core().identity == "platform.actuator":
            #     _log.debug("PUBSUB SUBSYS: Done with callback{}")
        elif op == 'publish_response':
            #_log.debug("publish response message value: {}".format(message.args[1].bytes))
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            result.set([bytes(arg) for arg in message.args[1:]])
        elif op == 'list_response':
            #_log.debug("list response message value: {}".format(message.args[1].bytes))
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                _log.debug("list response key error")
                return
            result.set([bytes(arg) for arg in message.args[1:]])

    # Incoming message processing loop
    def _process_loop(self):
        new_msg_list = []
        #Testing
        # _log.debug("Reading from/waiting for queue.")
        while True:
            try:
                new_msg_list = []
                # _log.debug("PUBSUB Reading from/waiting for queue.")
                new_msg_list = [
                    self._event_queue.get(True, self._retry_period)]

            except Empty:
                # _log.debug("Queue wait timed out. Falling out.")
                new_to_publish = []

            if len(new_msg_list) != 0:
                # _log.debug("Checking for queue build up.")
                while True:
                    try:
                        new_msg_list.append(self._event_queue.get_nowait())
                    except Empty:
                        break

            # _log.debug('SUB: Length of data got from event queue {}'.format(len(new_msg_list)))
            for msg in new_msg_list:
                self._process_incoming_message(msg)

    def _handle_error(self, sender, message, error, **kwargs):
        _log.debug("Error is generated {0}, {1}, {2}".format(sender, message, error))
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(error)

class ProtectedPubSubTopics(object):
    '''Simple class to contain protected pubsub topics'''
    def __init__(self):
        self._dict = {}
        self._re_list = []

    def add(self, topic, capabilities):
        if isinstance(capabilities, basestring):
            capabilities = [capabilities]
        if len(topic) > 1 and topic[0] == topic[-1] == '/':
            regex = re.compile('^' + topic[1:-1] + '$')
            self._re_list.append((regex, capabilities))
        else:
            self._dict[topic] = capabilities

    def get(self, topic):
        if topic in self._dict:
            return self._dict[topic]
        for regex, capabilities in self._re_list:
            if regex.match(topic):
                return capabilities
        return None


class FakeAsyncResult(object):
    '''Dummy class that fakes get()'''
    def get(self, *args, **kwargs):
        pass
