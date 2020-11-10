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


import errno
import logging

import gevent
from zmq import green as zmq

from base64 import b64encode, b64decode
from zmq import SNDMORE
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.vip.agent.errors import VIPError
from volttron.platform import jsonrpc, jsonapi
from collections import defaultdict


_log = logging.getLogger(__name__)

def encode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64encode(peer[1:])
    return peer

def decode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64decode(peer[1:])
    return peer

class PubSubWrapper(Agent):
    """PubSubWrapper Agent acts as a wrapper agent for PubSub subsystem when connected to remote platform that which is using
       old pubsub (RPC based implementation).
       When it receives PubSub requests from remote platform,
       - calls the appropriate method of new platform.
       - returns the result back"""
    def __init__(self, identity, **kwargs):
        super(PubSubWrapper, self).__init__(identity, **kwargs)

        def subscriptions():
            return defaultdict(set)

        self._peer_subscriptions = defaultdict(subscriptions)

    @Core.receiver('onsetup')
    def onsetup(self, sender, **kwargs):
        # pylint: disable=unused-argument
        self.vip.rpc.export(self._peer_sync, 'pubsub.sync')
        self.vip.rpc.export(self._peer_publish, 'pubsub.publish')
        self.vip.rpc.export(self._peer_subscribe, 'pubsub.subscribe')
        self.vip.rpc.export(self._peer_unsubscribe, 'pubsub.unsubscribe')
        self.vip.rpc.export(self._peer_list, 'pubsub.list')

    def _sync(self, peer, items):
        items = {(bus, prefix) for bus, topics in items.items()
                 for prefix in topics}
        remove = []
        for bus, subscriptions in self._peer_subscriptions.items():
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
            subscriptions = self._peer_subscriptions[bus]
            assert not subscriptions.pop(prefix)
        for bus, prefix in items:
            self._add_peer_subscription(peer, bus, prefix)
            self.vip.pubsub.subscribe(peer, prefix, self._collector, bus=bus)

    def _peer_sync(self, items):
        peer = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        assert isinstance(items, dict)
        self._sync(peer, items)

    def _peer_publish(self, topic, headers, message=None, bus=''):
        peer = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        self.vip.pubsub.publish(peer, topic, headers, message=message, bus=bus)

    def add_bus(self, name):
        self._peer_subscriptions.setdefault(name, {})

    def _add_peer_subscription(self, peer, bus, prefix):
        self._peer_subscriptions[bus][prefix].add(peer)

    def _peer_subscribe(self, prefix, bus=''):
        peer = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        for prefix in prefix if isinstance(prefix, list) else [prefix]:
            self._add_peer_subscription(peer, bus, prefix)
        self.vip.pubsub.subscribe(peer, prefix, self._collector, bus=bus)

    def _distribute(self, peer, topic, headers, message=None, bus=''):
        #self._check_if_protected_topic(topic)
        subscriptions = self._peer_subscriptions[bus]
        subscribers = set()
        for prefix, subscription in subscriptions.items():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            sender = encode_peer(peer)
            json_msg = jsonapi.dumps(jsonrpc.json_method(
                None, 'pubsub.push',
                [sender, bus, topic, headers, message], None))
            frames = [zmq.Frame(b''), zmq.Frame(b''),
                      zmq.Frame(b'RPC'), zmq.Frame(json_msg)]
            socket = self.core.socket
            for subscriber in subscribers:
                socket.send(subscriber, flags=SNDMORE)
                socket.send_multipart(frames, copy=False)
        return len(subscribers)

    def _collector(self, peer, sender, bus,  topic, headers, message):
        self._distribute(peer, topic, headers, message, bus)

    def _peer_list(self, prefix='', bus='', subscribed=True, reverse=False):
        peer = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        if bus is None:
            buses = iter(self._peer_subscriptions.items())
        else:
            buses = [(bus, self._peer_subscriptions[bus])]
        if reverse:
            test = prefix.startswith
        else:
            test = lambda t: t.startswith(prefix)
        results = []
        for bus, subscriptions in buses:
            for topic, subscribers in subscriptions.items():
                if test(topic):
                    member = peer in subscribers
                    if not subscribed or member:
                        results.append((bus, topic, member))
        return results

    def _peer_unsubscribe(self, prefix, bus=''):
        peer = bytes(self.vip.rpc.context.vip_message.peer).decode("utf-8")
        subscriptions = self._peer_subscriptions[bus]
        if prefix is None:
            remove = []
            for topic, subscribers in subscriptions.items():
                subscribers.discard(peer)
                if not subscribers:
                    remove.append(topic)
            for topic in remove:
                del subscriptions[topic]
                self.vip.pubsub.unsubscribe(peer, prefix, self._collector, bus=bus)
        else:
            for prefix in prefix if isinstance(prefix, list) else [prefix]:
                subscribers = subscriptions[prefix]
                subscribers.discard(peer)
                if not subscribers:
                    del subscriptions[prefix]
                    self.vip.pubsub.unsubscribe(peer, prefix, self._collector, bus=bus)
