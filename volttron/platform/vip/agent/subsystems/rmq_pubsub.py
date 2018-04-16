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

import inspect
import logging

import weakref
import pika
import uuid
from volttron.platform.agent import json as jsonapi

from ..decorators import annotate, annotations, dualmethod, spawn
from .pubsub import BasePubSub
from collections import defaultdict
from ..results import ResultsDictionary
from gevent import monkey
monkey.patch_socket()

__all__ = ['RMQPubSub']
min_compatible_version = '5.0'
max_compatible_version = ''


class RMQPubSub(BasePubSub):
    """
    Pubsub subsystem concrete class implementation for RabbitMQ message bus.
    """

    def __init__(self, core, rpc_subsys, peerlist_subsys, owner):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc_subsys)
        self.peerlist = weakref.ref(peerlist_subsys)
        self._owner = owner
        self._logger = logging.getLogger(__name__)
        self._results = ResultsDictionary()
        self._message_number = 0
        self._pubcount = dict()
        self._isconnected = False

        def subscriptions():
            return defaultdict(set)

        self._my_subscriptions = defaultdict(subscriptions)

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self._connection = self.core().connection
            self._channel = self.core().connection.channel

            core.onconnected.connect(self._connected)

            def subscribe(member):  # pylint: disable=redefined-outer-name
                #for peer, prefix, all_platforms, queue in annotations(
                for peer, bus, prefix, all_platforms, queue in annotations(
                        member, set, 'pubsub.subscriptions'):
                    self._logger.debug("peer: {0}, prefix:{1}".format(peer, prefix))
                    if prefix == '':
                        prefix = '#'
                    else:
                        prefix = prefix + '.#'
                    if all_platforms:
                        # '__pubsub__.*.<prefix>.#'
                        routing_key = "__pubsub__.*.{}".format(prefix.replace("/", "."))
                    else:
                        routing_key = "__pubsub__.{0}.{1}".format(self.core().instance_name,
                                                                    prefix.replace("/", "."))
                    # If not named queue, add queue name
                    if not queue:
                        queue = "pubsub.{}".format(bytes(uuid.uuid4()))
                    self._add_subscription(routing_key, member, queue)
                    # _log.debug("SYNC: all_platforms {}".format(self._my_subscriptions['internal'][bus][prefix]))

            inspect.getmembers(owner, subscribe)

        core.onsetup.connect(setup, self)

    def _connected(self, sender, **kwargs):
        """
        After connection to RMQ broker is established, synchronize local subscriptions with RMQ broker.
        param sender: identity of sender
        type sender: str
        param kwargs: optional arguments
        type kwargs: pointer to arguments
        """
        #self.core().connection.channel.confirm_delivery(self.on_delivery_confirmation,nowait=True)
        self._isconnected = True
        self.synchronize()

    def synchronize(self):
        """
        Synchronize local subscriptions with RMQ broker.
        :return:
        """
        connection = self.core().connection
        #self._logger.debug("Synchronize {}".format(self._my_subscriptions))
        for prefix, subscriptions in self._my_subscriptions.iteritems():
            for queue, callback in subscriptions.iteritems():
                # Check if queue needs to be persistent
                durable = False
                # if not queue.startswith('volttron'):
                #     durable = True
                connection.channel.queue_declare(queue=queue,
                                                  durable=durable,
                                                  exclusive=False,
                                                  auto_delete=True,
                                                  callback=None)
                connection.channel.queue_bind(exchange=connection.exchange,
                                              queue=queue,
                                              routing_key=prefix,
                                              callback=None)
                for cb in callback:
                    self._add_callback(connection, queue, cb)
        return True

    def _add_subscription(self, prefix, callback, queue):
        """
        Store subscriptions so that
        :param prefix:
        :param callback:
        :param queue:
        :return:
        """
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            self._my_subscriptions[prefix][queue].add(callback)
            #_log.debug("SYNC: add subscriptions: {}".format(self._my_subscriptions['internal'][bus][prefix]))
        except KeyError:
            self._logger.error("PUBSUB something went wrong in add subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus='', all_platforms=False, persistent_queue=None):
        """

        :param prefix:
        :param callback:
        :param bus:
        :param all_platforms:
        :param persistent_queue:
        :return:
        """
        result = None
        if prefix == '': prefix = '#'
        else: prefix = prefix + ".#"
        routing_key = ''
        connection = self.core().connection # bytes(uuid.uuid4())

        if not all_platforms:
            routing_key = "__pubsub__.{0}.{1}".format(self.core().instance_name, prefix.replace("/", "."))
        else:
            # '__pubsub__.*.<prefix>.#'
            routing_key = "__pubsub__.*.{}".format(prefix.replace("/", "."))
            # Send message to proxy agent to subscribe with different types of message bus
            self._send_proxy(prefix, callback, bus, all_platforms)

        queue = ''
        durable = False
        auto_delete = True
        if persistent_queue:
            queue = persistent_queue
            durable = True
            auto_delete = False
        else:
            queue = "pubsub.{0}.{1}".format(self.core().identity, bytes(uuid.uuid4()))
        # Store subscriptions for later use
        self._add_subscription(routing_key, callback, queue)

        self._logger.debug("PUBUB subscribing to {}".format(routing_key))

        try:
            connection.channel.queue_declare(callback=None,
                                             queue=queue,
                                             durable=durable,
                                             exclusive=False,
                                             auto_delete=auto_delete)
            connection.channel.queue_bind(callback=None,
                                          exchange=connection.exchange,
                                          queue=queue,
                                          routing_key=routing_key)
            self._add_callback(connection, queue, callback)
        except AttributeError as ex:
            self._logger.error("Subscription will be added when agent gets connected to messagebus."
                               .format(self.core().identity))
        return result

    def _send_proxy(self, prefix, callback, bus, all_platforms):
        connection = self.core().connection
        rkey = self.core().instance_name + '.proxy.router.pubsub'
        sub_msg = jsonapi.dumps(
            dict(prefix=prefix, bus=bus, all_platforms=all_platforms)
        )
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        frames = [self.core().identity, b'', b'VIP1', b'', b'', b'pubsub', b'subscribe', sub_msg]
        connection.channel.basic_publish(exchange=connection.exchange,
                                         routing_key=rkey,
                                         body=jsonapi.dumps(frames, ensure_ascii=False))

    def _add_callback(self, connection, queue, callback):
        def rmq_callback(ch, method, properties, body):
            # Strip prefix from routing key
            topic = str(method.routing_key)
            _, _, topic = topic.split(".", 2)
            topic = topic.replace(".", "/")
            try:
                msg = jsonapi.loads(body)
                #self._logger.debug("pub message {}".format(method.routing_key))
                headers = msg['headers']
                message = msg['message']
                bus = msg['bus']
                sender = msg['sender']
                callback('pubsub', sender, bus, topic, headers, message)
            except KeyError as esc:
                self._logger.error("Missing keys in pubsub message {}".format(esc))

        connection.channel.basic_consume(rmq_callback,
                                         queue=queue,
                                         no_ack=True)


    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus='', all_platforms=False, persistent_queue=None):
        print("subscribe classmethod {}".format(prefix))
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix, all_platforms, persistent_queue))
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
        result = next(self._results)
        self._pubcount[self._message_number] = result.ident
        self._message_number += 1
        topicx = topic.replace("/", ".")
        routing_key = '__pubsub__.' + self.core().instance_name + '.' + topic.replace("/", ".")
        connection = self.core().connection
        self.core().spawn_later(0.01, self.set_result, result.ident)
        if headers is None:
            headers = {}

        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version
        # self._logger.debug("PUBSUB publish message To. {0}, {1}, {2}, {3} ".format(routing_key,
        #                                                                        self.core().identity,
        #                                                                        message,
        #                                                                        result.ident))

        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'app_id': connection.routing_key,  # SENDER
            'headers': dict(recipient=b'',  # RECEIVER
                            proto=b'VIP',  # PROTO
                            userid=b'',    # USER_ID
                            ),
            'message_id': result.ident,  # MSG_ID
            'type': 'pubsub',  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        json_msg = dict(sender=self.core().identity, bus=bus, headers=headers, message=message)
        connection.channel.basic_publish(exchange=connection.exchange,
                                         routing_key=routing_key,
                                         properties=properties,
                                         body=jsonapi.dumps(json_msg, ensure_ascii=False))
        return result

    def set_result(self, ident):
        try:
            result = self._results.pop(bytes(ident))
            if result:
                result.set(2)
        except KeyError:
            pass

    def on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        try:
            delivery_number = method_frame.method.delivery_tag
            self._logger.info("PUBSUB Delivery confirmation {0}, pending {1}, ".
                              format(method_frame.method.delivery_tag, len(self._pubcount)))
            ident = self._pubcount.pop(delivery_number, None)
            if ident:
                result = None
                try:
                    result = self._results.pop(bytes(ident))
                    if result:
                        result.set(delivery_number)
                except KeyError:
                    pass
        except TypeError:
            pass


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
        routing_key = None
        platform = 'internal'
        if prefix:
            if all_platforms:
                platform = 'all'
                routing_key = '__pubsub__.' + '*.' + prefix.replace('\/', '.') + '.#'
            else:
                routing_key = '__pubsub__.' + self._instance_name + '.' + prefix.replace('\/', '.') + '.#'
        topics = self._drop_subscription(routing_key, callback)

        if all_platforms: # Send it proxy router to send it to external 'zmq' platforms
            subscriptions = dict()
            subscriptions['all'] = dict(prefix=topics, bus=bus)
            rkey = self.core().instance_name + '.proxy.router.pubsub'
            frames = [self.core().identity, b'', b'VIP1', b'', b'', b'pubsub',
                      b'unsubscribe', jsonapi.dumps(subscriptions)]
            self.core().connection.channel.basic_publish(exchange=self.core().connection.exchange,
                                             routing_key=rkey,
                                             body=frames)
        return topics

    def _drop_subscription(self, routing_key, callback):
        topics = []
        remove = []
        subscriptions = set()
        if routing_key is None:
            if callback is None:
                return []
            else:
                for key in self._my_subscriptions:
                    subscriptions = self._my_subscriptions[key]
                    for queue, cback in subscriptions:
                        if callback == cback:
                            #Delete queue
                            self.core().connection.channel.queue_delete(queue)
                        topics.append(key)
                        remove.append((queue, cback))
                    for subs in remove:
                        subscriptions.remove(subs)
                if not topics:
                    raise KeyError('no such subscription')
        else:
            if routing_key in self._my_subscriptions:
                topics.append(routing_key)
                subscriptions = self._my_subscriptions[routing_key]
                for queue, cback in subscriptions:
                    if cback is None or callback == cback:
                        self.core().connection.channel.queue_delete(queue)
                    remove.append((queue,cback))
                for subs in remove:
                    subscriptions.remove(subs)
                if not subscriptions:
                    del subscriptions[routing_key]
        return topics
