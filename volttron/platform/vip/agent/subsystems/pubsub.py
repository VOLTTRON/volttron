# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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



from base64 import b64encode, b64decode
import inspect
import logging
import random
import re
import weakref
import sys
import gevent

from zmq import green as zmq
from zmq import SNDMORE
from volttron.platform import jsonapi
from volttron.utils.frame_serialization import serialize_frames
from .base import SubsystemBase
from ..decorators import annotate, annotations, dualmethod, spawn
from ..errors import Unreachable, VIPError, UnknownSubsystem
from .... import jsonrpc
from volttron.platform.agent import utils
from ..results import ResultsDictionary
from gevent.queue import Queue, Empty
from collections import defaultdict
from datetime import timedelta

__all__ = ['PubSub']

min_compatible_version = '3.0'
max_compatible_version = ''

# utils.setup_logging()
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
    """
    Pubsub subsystem concrete class implementation for ZMQ message bus.
    """

    def __init__(self, core, rpc_subsys, peerlist_subsys, owner):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc_subsys)
        self.peerlist = weakref.ref(peerlist_subsys)
        self._owner = owner

        def platform_subscriptions():
            return defaultdict(subscriptions)

        def subscriptions():
            return defaultdict(set)

        self._my_subscriptions = defaultdict(platform_subscriptions)
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
                for peer, bus, prefix, all_platforms, queue in annotations(
                        member, set, 'pubsub.subscriptions'):
                    # XXX: needs updated in light of onconnected signal
                    self._add_subscription(prefix, member, bus, all_platforms)
                    #_log.debug("SYNC ZMQ: all_platforms {}".format(self._my_subscriptions['internal'][bus][prefix]))

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
        for platform in self._my_subscriptions:
            # _log.debug("SYNC: process callback subscriptions: {}".format(self._my_subscriptions[platform][bus]))
            buses = self._my_subscriptions[platform]
            if bus in buses:
                subscriptions = buses[bus]
                for prefix, callbacks in subscriptions.items():
                    if topic.startswith(prefix):
                        handled += 1
                        for callback in callbacks:
                            callback(peer, sender, bus, topic, headers, message)
        if not handled:
            # No callbacks for topic; synchronize with sender
            self.synchronize()

    def _viperror(self, sender, error, **kwargs):
        if isinstance(error, Unreachable):
            self._peer_drop(self, error.peer)

    def _peer_add(self, sender, peer, **kwargs):
        # Delay sync by some random amount to prevent reply storm.
        delay = random.random()
        self.core().spawn_later(delay, self.synchronize, peer)

    def _peer_drop(self, sender, peer, **kwargs):
        self._sync(peer, {})

    def _sync(self, peer, items):
        items = {(bus, prefix) for bus, topics in items.items()
                 for prefix in topics}
        remove = []
        for bus, subscriptions in self._my_subscriptions.items():
            for prefix, subscribers in subscriptions.items():
                item = bus, prefix
                try:
                    items.remove(item)
                except KeyError:
                    subscribers.discard(peer)
                    if not subscribers:
                        remove.append(item)
                else:
                    subscribers.add(peer)
        for bus, prefix in remove:
            subscriptions = self._my_subscriptions[bus]
            assert not subscriptions.pop(prefix)
        for bus, prefix in items:
            self._add_peer_subscription(peer, bus, prefix)

    def _add_peer_subscription(self, peer, bus, prefix):
        try:
            subscriptions = self._my_subscriptions[bus]
        except KeyError:
            self._my_subscriptions[bus] = subscriptions = dict()
        try:
            subscribers = subscriptions[prefix]
        except KeyError:
            subscriptions[prefix] = subscribers = set()
        subscribers.add(peer)

    def _distribute(self, peer, topic, headers, message=None, bus=''):
        self._check_if_protected_topic(topic)
        try:
            subscriptions = self._my_subscriptions[bus]
        except KeyError:
            subscriptions = dict()
        subscribers = set()
        for prefix, subscription in subscriptions.items():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            sender = encode_peer(peer)
            json_msg = jsonapi.dumpb(jsonrpc.json_method(
                None, 'pubsub.push',
                [sender, bus, topic, headers, message], None))
            frames = [zmq.Frame(''), zmq.Frame(''),
                      zmq.Frame('RPC'), zmq.Frame(json_msg)]
            socket = self.core().socket
            for subscriber in subscribers:
                socket.send(subscriber, flags=SNDMORE)
                socket.send_multipart(frames, copy=False)
        return len(subscribers)

    def synchronize(self):
        """Synchronize local subscriptions with the PubSubService.
        """
        result = next(self._results)

        subscriptions = {platform: {bus: list(subscriptions.keys())}
                         for platform, bus_subscriptions in self._my_subscriptions.items()
                         for bus, subscriptions in bus_subscriptions.items()}
        sync_msg = jsonapi.dumpb(dict(subscriptions=subscriptions))
        frames = ['synchronize', 'connected', sync_msg]
        self.vip_socket.send_vip('', 'pubsub', frames, result.ident, copy=False)

        # 2073 - python3 dictionary keys method returns a dict_keys structure that isn't serializable.
        #        added list(subscriptions.keys()) to make it like python2 list of strings.
        items = [
            {platform: {bus: list(subscriptions.keys())}
             for platform, bus_subscriptions in self._my_subscriptions.items()
             for bus, subscriptions in bus_subscriptions.items()}]
        for subscriptions in items:
            sync_msg = jsonapi.dumpb(
                dict(subscriptions=subscriptions)
            )
            frames = ['synchronize', 'connected', sync_msg]
            self.vip_socket.send_vip('', 'pubsub', frames, result.ident, copy=False)

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False, all_platforms=False):
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
        :returns: List of subscriptions, i.e, list of tuples of bus, topic and
        flag to indicate if peer is a subscriber or not
        :rtype: list of tuples

        :Return Values:
        List of tuples [(topic, bus, flag to indicate if peer is a subscriber or not)]
        """
        result = next(self._results)
        list_msg = jsonapi.dumpb(dict(prefix=prefix, all_platforms=all_platforms,
                                      subscribed=subscribed, reverse=reverse, bus=bus))

        frames = ['list', list_msg]
        self.vip_socket.send_vip('', 'pubsub', frames, result.ident, copy=False)
        return result

    def _add_subscription(self, prefix, callback, bus='', all_platforms=False):
        # _log.debug(f"Adding subscription prefix: {prefix} allplatforms: {all_platforms}")
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            if not all_platforms:
                self._my_subscriptions['internal'][bus][prefix].add(callback)
            else:
                self._my_subscriptions['all'][bus][prefix].add(callback)
                # _log.debug("SYNC: add subscriptions: {}".format(self._my_subscriptions['internal'][bus][prefix]))
        except KeyError:
            _log.error("PUBSUB something went wrong in add subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus='', all_platforms=False, persistent_queue=None):
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
        :param platforms
        :type platforms
        :returns: Subscribe is successful or not
        :rtype: boolean

        :Return Values:
        Success or Failure
        """
        result = next(self._results)
        self._add_subscription(prefix, callback, bus, all_platforms)
        sub_msg = jsonapi.dumpb(
            dict(prefix=prefix, bus=bus, all_platforms=all_platforms)
        )

        frames = ['subscribe', sub_msg]
        self.vip_socket.send_vip('', 'pubsub', frames, result.ident, copy=False)
        return result

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus='', all_platforms=False, persistent_queue=None):
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix, all_platforms, persistent_queue))
            return method

        return decorate

    def _drop_subscription(self, prefix, callback, bus='', platform='internal'):

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
        bus_subscriptions = dict()
        if prefix is None:
            if callback is None:
                if len(self._my_subscriptions) and platform in \
                        self._my_subscriptions:
                    bus_subscriptions = self._my_subscriptions[platform]
                    if bus in bus_subscriptions:
                        topics.extend(bus_subscriptions[bus].keys())
                if not len(topics):
                    return []
            else:
                if platform in self._my_subscriptions:
                    bus_subscriptions = self._my_subscriptions[platform]
                if bus in bus_subscriptions:
                    subscriptions = bus_subscriptions[bus]
                    remove = []
                    for topic, callbacks in subscriptions.items():
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
                        del bus_subscriptions[bus]
                    if not bus_subscriptions:
                        del self._my_subscriptions[platform]
            if not topics:
                raise KeyError('no such subscription')
        else:
            _log.debug(f"BEFORE: {self._my_subscriptions}")
            if platform in self._my_subscriptions:
                bus_subscriptions = self._my_subscriptions[platform]
                if bus in bus_subscriptions:
                    _log.debug(f"BUS: {bus}")
                    subscriptions = bus_subscriptions[bus]
                    _log.debug(f"subscriptions: {subscriptions}")
                    if callback is None:
                        try:
                            del subscriptions[prefix]
                        except KeyError:
                            return []
                    else:
                        try:
                            callbacks = subscriptions[prefix]
                            _log.debug(f"callbacks: {callbacks}")
                        except KeyError:
                            return []
                        try:
                            callbacks.remove(callback)
                        except KeyError as e:
                            _log.debug(f"KeyError: {e}")
                            pass
                        if not callbacks:
                            try:
                                del subscriptions[prefix]
                                _log.debug(f"subscriptions: {subscriptions}")
                            except KeyError:
                                return []
                    topics = [prefix]
                    if not subscriptions:
                        del bus_subscriptions[bus]
                    if not bus_subscriptions:
                        del self._my_subscriptions[platform]
        _log.debug(f"AFTER: {self._my_subscriptions}")
        return topics

    def unsubscribe(self, peer, prefix, callback, bus='', all_platforms=False):
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
        subscriptions = dict()
        result = next(self._results)
        if not all_platforms:
            platform = 'internal'
            topics = self._drop_subscription(prefix, callback, bus, platform)
            subscriptions[platform] = dict(prefix=topics, bus=bus)
        else:
            platform = 'all'
            topics = self._drop_subscription(prefix, callback, bus, platform)
            subscriptions[platform] = dict(prefix=topics, bus=bus)

        unsub_msg = jsonapi.dumpb(subscriptions)
        topics = self._drop_subscription(prefix, callback, bus)
        frames = ['unsubscribe', unsub_msg]
        self.vip_socket.send_vip('', 'pubsub', frames, result.ident, copy=False)
        return result

    def publish(self, peer: str, topic: str, headers=None, message=None, bus=''):
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
        if headers is None:
            headers = {}
        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version

        if peer is None:
            peer = 'pubsub'

        result = next(self._results)
        args = ['publish', topic, dict(bus=bus, headers=headers, message=message)]
        self.vip_socket.send_vip('', 'pubsub', args, result.ident, copy=False)
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

    @spawn
    def _process_incoming_message(self, message):
        """Process incoming messages
        param message: VIP message from PubSubService
        type message: dict
        """
        op = message.args[0]

        if op == 'request_response':
            result = None
            try:
                result = self._results.pop(message.id)
            except KeyError:
                pass

            response = message.args[1]
            import struct
            if not isinstance(response, int):
                if len(response) == 4: #integer
                    response = struct.unpack('I', response.encode('utf-8'))
                    response = response[0]
                elif len(response) == 1: #bool
                    response = struct.unpack('?', response.encode('utf-8'))
                    response = response[0]
            if result:
                result.set(response)

        elif op == 'publish':
            try:
                topic = message.args[1]
                msg = message.args[2]
            except IndexError:
                return
            try:
                headers = msg['headers']
                message = msg['message']
                sender = msg['sender']
                bus = msg['bus']
            except KeyError as exc:
                _log.error("Missing keys in pubsub message: {}".format(exc))
            else:
                self._process_callback(sender, bus, topic, headers, message)

        elif op == 'list_response':
            result = None
            try:
                result = self._results.pop(message.id)
                response = message.args[1]
                if result:
                    result.set(response)
            except KeyError:
                pass
        else:
            _log.error("Unknown operation ({})".format(op))

    def _process_loop(self):
        """Incoming message processing loop"""
        for msg in self._event_queue:
            self._process_incoming_message(msg)

    def _handle_error(self, sender, message, error, **kwargs):
        """Error handler. If UnknownSubsystem error is received, it implies that agent is connected to platform that has
        OLD pubsub implementation. So messages are resent using RPC method.
        param message: Error message
        type message: dict
        param error: indicates error type
        type error: error class
        param **kwargs: variable arguments
        type **kwargs: dict
        """
        try:
            result = self._results.pop(message.id)
        except KeyError:
            return
        result.set_exception(error)


class ProtectedPubSubTopics(object):
    """Simple class to contain protected pubsub topics"""

    def __init__(self):
        self._dict = {}
        self._re_list = []

    def add(self, topic, capabilities):
        if isinstance(capabilities, str):
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
