# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

from volttron.platform.agent import json as jsonapi

from .base import SubsystemBase
from ..decorators import annotate, annotations, dualmethod, spawn
from ..errors import Unreachable, VIPError, UnknownSubsystem
from .... import jsonrpc
from volttron.platform.agent import utils
from ..results import ResultsDictionary
from gevent.queue import Queue, Empty
from collections import defaultdict
from datetime import timedelta
import pika
import sys

min_compatible_version = '3.0'
max_compatible_version = ''

class BasePubSub(SubsystemBase):
    def __init__(self):

    def synchronize(self):

    def subscribe(self):

    def publish(self):

    def list(self):

    def unsubscribe(self):

class RMQPubSub(BasePubSub):
    def __init__(self, core, rpc_subsys, peerlist_subsys, owner):
        self.core = weakref.ref(core)
        self._connection = None
        self.rpc = weakref.ref(rpc_subsys)
        self.peerlist = weakref.ref(peerlist_subsys)
        self._owner = owner

        def subscriptions():
            return defaultdict(set)

        self._my_subscriptions = defaultdict(subscriptions)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self._processgreenlet = gevent.spawn(self._process_loop)
            core.onconnected.connect(self._connected)

            def subscribe(member):  # pylint: disable=redefined-outer-name
                for peer, bus, prefix, all_platforms in annotations(
                        member, set, 'pubsub.subscriptions'):
                    # XXX: needs updated in light of onconnected signal
                    self._add_subscription(prefix, member, bus, all_platforms)
                    # _log.debug("SYNC: all_platforms {}".format(self._my_subscriptions['internal'][bus][prefix]))

            inspect.getmembers(owner, subscribe)

        core.onsetup.connect(setup, self)

    def _connected(self, sender, **kwargs):
        """
        Synchronize local subscriptions with RMQ broker.
        param sender: identity of sender
        type sender: str
        param kwargs: optional arguments
        type kwargs: pointer to arguments
        """
        self.synchronize()


    def synchronize(self):
        """Synchronize local subscriptions with the PubSubService.
        """
        result = next(self._results)
        items = [{platform: {bus: subscriptions.keys()} for platform, bus_subscriptions in self._my_subscriptions.items()
                  for bus, subscriptions in bus_subscriptions.items()}]
        for subscriptions in items:
            sync_msg = jsonapi.dumps(
                        dict(subscriptions=subscriptions)
                        )
            frames = [b'synchronize', b'connected', sync_msg]
            # For backward compatibility with old pubsub
            if self._send_via_rpc:
                delay = random.random()
                self.core().spawn_later(delay, self.rpc().notify, 'pubsub', 'pubsub.sync', subscriptions)
            else:
                # Parameters are stored initially, in case remote agent/platform is using old pubsub
                if self._parameters_needed:
                    kwargs = dict(op='synchronize', subscriptions=subscriptions)
                    self._save_parameters(result.ident, **kwargs)
                self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)

    def _add_subscription(self, prefix, queue_name, callback, isPersistent=False):
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            self._my_subscriptions[prefix].add((queue_name, isPersistent, callback))
            #_log.debug("SYNC: add subscriptions: {}".format(self._my_subscriptions['internal'][bus][prefix]))
        except KeyError:
            self._logger.error("PUBSUB something went wrong in add subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus='', all_platforms=False):
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

        # For backward compatibility with old pubsub
        if self._send_via_rpc == True:
            self._add_subscription(prefix, callback, bus)
            return self.rpc().call(peer, 'pubsub.subscribe', prefix, bus=bus)
        else:
            result = self._results.next()
            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='subscribe', prefix=prefix, bus=bus)
                self._save_parameters(result.ident, **kwargs)
            self._add_subscription(prefix, callback, bus, all_platforms)
            sub_msg = jsonapi.dumps(
                dict(prefix=prefix, bus=bus, all_platforms=all_platforms)
            )

            frames = [b'subscribe', sub_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

    def rabbitmq_subscribe(self, prefix, callback, all_platforms=False, persistent_queue=None):
        result = None
        routing_key = '__pubsub__.'
        queue_name = None
        if all_platforms:
            #'__pubsub__.*.<prefix>.#'
            routing_key += '*.' + prefix.replace("/",".")+".#"
        else:
            routing_key += self.core.instance_name + '.' + prefix.replace("/",".")+".#"

        if persistent_queue:
            self._channel.queue_declare(queue=persistent_queue, exclusive=True)
            queue_name = persistent_queue
        else:
            result = self._channel.queue_declare(exclusive=False)
            queue_name = result.method.queue
        #Store subscriptions for later use
        self._add_subscription(prefix, queue_name, callback)
        self._channel.queue_bind(exchange=self._exchange,
                                 queue=queue_name,
                                 routing_key=routing_key)
        self._channel.basic_consume(callback,
                                    queue=queue_name,
                                    no_ack=True)
        return result

    def _on_queue_declareok(self, method_frame):

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus='', all_platforms=False):
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix, all_platforms))
            return method
        return decorate

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
        :returns: List of subscriptions, i.e, list of tuples of bus, topic and flag to indicate if peer is a
        subscriber or not
        :rtype: list of tuples

        :Return Values:
        List of tuples [(topic, bus, flag to indicate if peer is a subscriber or not)]
        """

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
        routing_key = '__pubsub__.' + self._instance_name + '.' + topic.replace('\/', '.')
        if headers is None:
            headers = {}
        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version
        self._channel.basic_publish(exchange=self._exchange,
                              routing_key=routing_key,
                              body=str(message))


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

        # For backward compatibility with old pubsub
        if self._send_via_rpc == True:
            topics = self._drop_subscription(prefix, callback, bus)
            return self.rpc().call(peer, 'pubsub.unsubscribe', topics, bus=bus)
        else:
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

            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='unsubscribe', prefix=topics, bus=bus)
                self._save_parameters(result.ident, **kwargs)

            unsub_msg = jsonapi.dumps(subscriptions)
            topics = self._drop_subscription(prefix, callback, bus)
            frames = [b'unsubscribe', unsub_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

