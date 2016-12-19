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
from collections import defaultdict

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

        def subscriptions():
            return defaultdict(set)

        self._my_subscriptions = defaultdict(subscriptions)
        self.protected_topics = ProtectedPubSubTopics()
        core.register('pubsub', self._handle_subsystem, self._handle_error)
        self.vip_socket = None
        self._results = ResultsDictionary()
        self._event_queue = Queue()
        self._retry_period = 300.0
        self._processgreenlet = None

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self._processgreenlet = gevent.spawn(self._process_loop)
            core.onconnected.connect(self._connected)
            self.vip_socket = self.core().socket
            def subscribe(member):   # pylint: disable=redefined-outer-name
                for peer, bus, prefix in annotations(
                        member, set, 'pubsub.subscriptions'):
                    # XXX: needs updated in light of onconnected signal
                    self._add_subscription(prefix, member, bus)
            inspect.getmembers(owner, subscribe)
        core.onsetup.connect(setup, self)

    def _connected(self, sender, **kwargs):
        """
        Synchronize local subscriptions with PubSubService upon receiving connected signal.
        param sender: identity of sender
        type sender: str
        param kwargs: optional arguments
        type kwargs: pointer to arguments
        """
        #_log.debug("PUBSUB SUBSYS: connected so sync up {}".format(sender))
        self.synchronize()

    def _process_callback(self, sender, bus, topic, headers, message):
        """Handle incoming subscription pushes from PubSubService. It iterates over all subscriptions to find the
        subscription matching the topic and bus. It then calls the corresponding callback on finding a match.
        param sender: identity of the publisher
        type sender: str
        param bus: bus
        type bus: str
        param topic: publishing topic
        type topic: str
        param headers: header information for the incoming message
        type headers: dict
        param message: actual message
        type message: dict
        """
        peer = 'pubsub'
        handled = 0
        if bus in self._my_subscriptions:
            subscriptions = self._my_subscriptions[bus]
            for prefix, callbacks in subscriptions.iteritems():
                if topic.startswith(prefix):
                    handled += 1
                    for callback in callbacks:
                        callback(peer, sender, bus, topic, headers, message)
        if not handled:
            # No callbacks for topic; synchronize with sender
            self.synchronize()

    def synchronize(self):
        """Synchronize local subscriptions with the PubSubService.
        """
        items = [{bus: subscriptions.keys()
                         for bus, subscriptions in self._my_subscriptions.items()}]
        for subscriptions in items:
            sync_msg = jsonapi.dumps(
                        dict(subscriptions=subscriptions)
                    )
            frames = [b'synchronize', b'connected', sync_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, copy=False)

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False):
        """Gets list of subscriptions matching the prefix and bus for the specified peer.
        param peer: peer
        type peer: str
        param prefix: prefix of a topic
        type prefix: str
        param bus: bus
        type bus: bus
        param subscribed: subscribed or not
        type subscribed: boolean
        param reverse: reverse
        type reverse:
        :returns: List of subscriptions, i.e, list of tuples of bus, topic and flag to indicate if peer is a
        subscriber or not
        :rtype: list of tuples

        :Return Values:
        List of tuples [(topic, bus, flag to indicate if peer is a subscriber or not)]
        """
        result = next(self._results)

        list_msg = jsonapi.dumps(dict(prefix=prefix, subscribed=subscribed, reverse=reverse, bus=bus))
        frames = [b'list', list_msg]
        self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
        return result

    def _add_subscription(self, prefix, callback, bus=''):
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            self._my_subscriptions[bus][prefix].add(callback)
        except KeyError:
            _log.error("PUBSUB something went wrong in add subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus=''):
        """Subscribe to topic and register callback.

        Subscribes to topics beginning with prefix. If callback is
        supplied, it should be a function taking four arguments,
        callback(peer, sender, bus, topic, headers, message), where peer
        is the ZMQ identity of the bus owner sender is identity of the
        publishing peer, topic is the full message topic, headers is a
        case-insensitive dictionary (mapping) of message headers, and
        message is a possibly empty list of message parts.
        :param peer
        :type peer
        :param prefix prefix to the topic
        :type prefix str
        :param callback callback method
        :type callback method
        :param bus bus
        :type bus str
        :returns: Subscribe is successful or not
        :rtype: boolean

        :Return Values:
        Success or Failure
        """
        result = next(self._results)
        self._add_subscription(prefix, callback, bus)

        sub_msg = jsonapi.dumps(
            dict(prefix=prefix, bus=bus)
        )
        frames = [b'subscribe', sub_msg]
        self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
        return result

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus=''):
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix))
            return method
        return decorate

    def _drop_subscription(self, prefix, callback, bus=''):
        """
        Drop the subscription for the specified prefix, callback and bus.
        param prefix: prefix to be removed
        type prefix: str
        param callback: callback method
        type callback: method
        param bus: bus
        type bus: bus
        return: list of topics/prefixes
        :rtype: list

        :Return Values:
        List of prefixes
        """
        topics = []
        if prefix is None:
            if callback is None:
                if bus in self._my_subscriptions:
                    subscriptions = self._my_subscriptions.pop(bus)
                    topics = subscriptions.keys()
            else:
                if bus in self._my_subscriptions:
                    subscriptions = self._my_subscriptions[bus]
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
                        del self._my_subscriptions[bus]
            if not topics:
                raise KeyError('no such subscription')
        else:
            if bus in self._my_subscriptions:
                subscriptions = self._my_subscriptions[bus]
                if callback is None:
                    del subscriptions[prefix]
                else:
                    callbacks = subscriptions[prefix]
                    try:
                        callbacks.remove(callback)
                    except KeyError:
                        pass
                    if not callbacks:
                        del subscriptions[prefix]
                topics = [prefix]
                if not subscriptions:
                    del self._my_subscriptions[bus]
        return topics

    def unsubscribe(self, peer, prefix, callback, bus=''):
        """Unsubscribe and remove callback(s).

        Remove all handlers matching the given info - peer, callback and bus, which was used earlier to subscribe as
        well. If all handlers for a topic prefix are removed, the topic is also unsubscribed.
        param peer: peer
        type peer: str
        param prefix: prefix that needs to be unsubscribed
        type prefix: str
        param callback: callback method
        type callback: method
        param bus: bus
        type bus: bus
        return: success or not
        :rtype: boolean

        :Return Values:
        success or not
        """
        result = next(self._results)
        topics = self._drop_subscription(prefix, callback, bus)
        unsub_msg = jsonapi.dumps(
            dict(prefix=topics, bus=bus)
        )
        frames = [b'unsubscribe', unsub_msg]
        self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
        return result

    def publish(self, peer, topic, headers=None, message=None, bus=''):
        """Publish a message to a given topic via a peer.

        Publish headers and message to all subscribers of topic on bus.
        If peer is None, use self. Adds volttron platform version
        compatibility information to header as variables
        min_compatible_version and max_compatible version
        param peer: peer
        type peer: str
        param topic: topic for the publish message
        type topic: str
        param headers: header info for the message
        type headers: None or dict
        param message: actual message
        type message: None or any
        param bus: bus
        type bus: str
        return: Number of subscribers the message was sent to.
        :rtype: int

        :Return Values:
        Number of subscribers
        """
        result = next(self._results)
        if headers is None:
            headers = {}
        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version

        if peer is None:
            peer = 'pubsub'

        json_msg = jsonapi.dumps(
            dict(bus=bus, headers=headers, message=message)
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
        """Handler for incoming messages
        param message: VIP message from PubSubService
        type message: dict
        """
        self._event_queue.put(message)

    def _process_incoming_message(self, message):
        """Process incoming messages
        param message: VIP message from PubSubService
        type message: dict
        """
        op = message.args[0].bytes
        # if op == 'request_response':
        #     _log.debug("Reponse to request")
        #     try:
        #         result = self._results.pop(bytes(message.id))
        #     except KeyError:
        #         return
        #     _log.debug("Message result: {}".format(message.args))
        #     result.set([bytes(arg) for arg in message.args[1:]])
        if op == 'request_response':
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            response = message.args[1].bytes
            _log.debug("Message result: {}".format(response))
            result.set(response)
        elif op == 'publish':
            try:
                topic = topic = message.args[1].bytes
                data = message.args[2].bytes
                #_log.debug("DATA: {}".format(data))
            except IndexError:
                return
            msg = jsonapi.loads(data)
            headers = msg['headers']
            message = msg['message']
            sender = msg['sender']
            bus = msg['bus']
            self._process_callback(sender, bus, topic, headers, message)
        else:
            _log.error("Unknown operation")

    # Incoming message processing loop
    def _process_loop(self):
        for msg in self._event_queue:
            self._process_incoming_message(msg)

    def _handle_error(self, sender, message, error, **kwargs):
        _log.debug("Error is generated {0}, {1}, {2}".format(sender, message, error))
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(error)

class ProtectedPubSubTopics(object):
    """Simple class to contain protected pubsub topics"""
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

