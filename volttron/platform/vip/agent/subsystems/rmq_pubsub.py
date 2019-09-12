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
# }}}


from __future__ import absolute_import

import errno
import inspect
import logging
import uuid
import weakref

from volttron.platform import jsonapi
import errno
from .base import SubsystemBase

from collections import defaultdict

import requests
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)

from volttron.platform import is_rabbitmq_available
from volttron.platform import jsonapi
from ..decorators import annotate, annotations, dualmethod, spawn
from ..errors import Unreachable
from ..results import ResultsDictionary

if is_rabbitmq_available():
    import pika


__all__ = ['RMQPubSub']
min_compatible_version = '5.0'
max_compatible_version = ''


class RMQPubSub(SubsystemBase):
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
            core.onconnected.connect(self._connected)

            def subscribe(member):  # pylint: disable=redefined-outer-name
                for peer, bus, prefix, all_platforms, queue_name in annotations(
                        member, set, 'pubsub.subscriptions'):
                    self._logger.debug("peer: {0}, prefix:{1}".format(peer, prefix))
                    routing_key = self._form_routing_key(prefix, all_platforms=all_platforms)
                    # If named queue, add "persistent" in the queue name
                    if queue_name:
                        queue_name = "{user}.pubsub.persistent.{queue_name}".format(user=self.core().rmq_user,
                                                                                    queue_name=queue_name)
                    else:
                        queue_name = "{user}.pubsub.{uid}".format(user=self.core().rmq_user,
                                                                  uid=uuid.uuid4())

                    self._add_subscription(routing_key, member, queue_name)
                    # self._logger.debug("SYNC RMQ: all_platforms {}")

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
        # self.core().connection.channel.confirm_delivery(self.on_delivery_confirmation,nowait=True)
        self._isconnected = True
        self.synchronize()

    def synchronize(self):
        """
        Synchronize local subscriptions with RMQ broker.
        :return:
        """
        connection = self.core().connection
        # self._logger.debug("Synchronize {}".format(self._my_subscriptions))
        for prefix, subscriptions in self._my_subscriptions.items():
            for queue_name, callback in subscriptions.items():
                durable = False
                auto_delete = True
                # Check if queue needs to be persistent
                if 'persistent' in queue_name:
                    durable = True
                    auto_delete = False
                connection.channel.queue_declare(queue=queue_name,
                                                 durable=durable,
                                                 exclusive=True,
                                                 auto_delete=auto_delete,
                                                 callback=None)
                connection.channel.queue_bind(exchange=connection.exchange,
                                              queue=queue_name,
                                              routing_key=prefix,
                                              callback=None)

                if prefix.startswith('__pubsub__.*.'):
                    original_prefix = self._get_original_topic(prefix)
                    self._send_proxy(original_prefix)
                for cb in callback:
                    self._add_callback(connection, queue_name, cb)
        return True

    def _add_subscription(self, prefix, callback, queue_name):
        """
        Store subscriptions so that it can used later
        :param prefix: subscription prefix
        :param callback: callback method
        :param queue: queue name
        :return:
        """
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            self._my_subscriptions[prefix][queue_name].add(callback)
            # _log.debug("SYNC: add subscriptions: {}".format(self._my_subscriptions['internal'][bus][prefix]))
        except KeyError:
            self._logger.error("PUBSUB something went wrong when adding subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus='', all_platforms=False, persistent_queue=None):
        """Subscribe to a prefix and register callback. If 'all_platforms' flag is set to True, then
        agent subscribes to receive topic from all platforms. A named queue will set persistent
        behavior to the topic subscriptions. That means even if the agent shutdowns and restarts, it
        will receive all the messages during the shutdown/turn off period.

        :param peer "pubsub" string
        :type peer str
        :param prefix prefix of the topic
        :type prefix str
        :param callback callback method
        :type callback method
        :param bus bus
        :type bus str
        :param all_platforms Flag indicating if type is 'local' or 'all'
        :type all_platforms boolean
        :param persistent_queue Name of the queue for persistent behavior
        :type persistent_queue str
        :returns: Subscribe is successful or not
        :rtype: boolean

        :Return Values:
        Success or Failure
        """
        result = None
        connection = self.core().connection  # bytes(uuid.uuid4())
        routing_key = self._form_routing_key(prefix, all_platforms=all_platforms)
        if all_platforms:
            # Send message to proxy agent in order to subscribe with zmq message bus
            self._send_proxy(prefix)

        queue_name = ''
        durable = False
        auto_delete = True

        if persistent_queue:
            durable = True
            auto_delete = False
            queue_name = "{user}.pubsub.persistent.{queue_name}".format(user=self.core().rmq_user,
                                                                        queue_name=persistent_queue)
        else:
            queue_name = "{user}.pubsub.{uid}".format(user=self.core().rmq_user, uid=str(uuid.uuid4()))
        # Store subscriptions for later use
        self._add_subscription(routing_key, callback, queue_name)

        self._logger.debug("RMQ PUBSUB subscribing to {}".format(routing_key))

        try:
            connection.channel.queue_declare(callback=None,
                                             queue=queue_name,
                                             durable=durable,
                                             exclusive=False,
                                             auto_delete=auto_delete)
            connection.channel.queue_bind(callback=None,
                                          exchange=connection.exchange,
                                          queue=queue_name,
                                          routing_key=routing_key)
            self._add_callback(connection, queue_name, callback)
        except AttributeError as ex:
            self._logger.error("Subscription will be added when agent gets connected to messagebus."
                               .format(self.core().identity))
        return result

    def _send_proxy(self, prefix, bus=''):
        """
        Send the message to proxy router
        :param prefix:
        :param bus:
        :return:
        """
        connection = self.core().connection
        rkey = self.core().instance_name + '.proxy.router.pubsub'
        sub_msg = jsonapi.dumps(
            dict(prefix=prefix, bus=bus, all_platforms=True)
        )
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        frames = [self.core().identity, '', 'VIP1', '', '', 'pubsub', 'subscribe', sub_msg]
        connection.channel.basic_publish(exchange=connection.exchange,
                                         routing_key=rkey,
                                         body=jsonapi.dumps(frames, ensure_ascii=False))

    def _add_callback(self, connection, queue, callback):
        """
        Register agent's callback method with RabbitMQ broker
        :param connection: RabbitMQ connection object
        :param queue: queue name
        :param callback: callback method
        :return:
        """

        def rmq_callback(ch, method, properties, body):
            # Strip prefix from routing key
            topic = self._get_original_topic(str(method.routing_key))
            try:
                msg = jsonapi.loads(body)
                headers = msg['headers']
                message = msg['message']
                bus = msg['bus']
                sender = msg['sender']
                self.core().spawn(callback, 'pubsub', sender, bus, topic, headers, message)
            except KeyError as esc:
                self._logger.error("Missing keys in pubsub message {}".format(esc))

        connection.channel.basic_consume(rmq_callback,
                                         queue=queue,
                                         no_ack=True)

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus='', all_platforms=False, persistent_queue=None):
        """
        Class method for subscribe
        :param peer: "pubsub" string
        :param prefix: prefix of the topic
        :param bus: bus
        :param all_platforms: Flag indicating if type is 'local' or 'all'
        :param persistent_queue: Name of the queue for persistent behavior
        :return:
        """

        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix, all_platforms, persistent_queue))
            return method

        return decorate

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False, all_platforms=False):
        """Gets list of subscriptions matching the prefix
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
        List of tuples [(bus, topic, flag to indicate if peer is a subscriber or not)]
        """
        async_result = next(self._results)
        results = []
        if reverse:
            test = prefix.startswith
        else:
            test = lambda t: t.startswith(prefix)

        try:
            bindings = self.core().rmq_mgmt.get_bindings('volttron')
        except (requests.exceptions.HTTPError, ConnectionError, NewConnectionError) as e:
            self._logger.error("Error making request to RabbitMQ Management interface.\n"
                          "Check Connection Parameters: {} \n".format(e))
        else:
            try:
                items = [(b['destination'], self._get_original_topic(b['routing_key']))
                     for b in bindings if b['routing_key'].startswith('__pubsub__')]
            except KeyError as e:
                return async_result

            for item in items:
                peer = item[0]
                topic = item[1]
                if test(topic):
                    member = self.core().identity in peer
                    if not subscribed or member:
                        results.append(('', topic, member))
        self.core().spawn_later(0.01, self.set_result, async_result.ident, results)
        return async_result

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
        routing_key = self._form_routing_key(topic)
        connection = self.core().connection
        self.core().spawn_later(0.01, self.set_result, result.ident, 1)
        if headers is None:
            headers = {}

        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version
        # self._logger.debug("RMQ PUBSUB publish message To. {0}, {1}, {2}, {3} ".format(routing_key,
        #                                                                            self.core().identity,
        #                                                                            message,
        #                                                                            topic))

        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            # 'user_id': self.core().identity,
            'app_id': connection.routing_key,  # SENDER
            'headers': dict(recipient='',  # RECEIVER
                            proto='VIP',  # PROTO
                            user=self.core().identity,  # USER_ID
                            ),
            'message_id': result.ident,  # MSG_ID
            'type': 'pubsub',  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        json_msg = dict(sender=self.core().identity, bus=bus, headers=headers, message=message)
        try:
            connection.channel.basic_publish(exchange=connection.exchange,
                                         routing_key=routing_key,
                                         properties=properties,
                                         body=jsonapi.dumps(json_msg, ensure_ascii=False))
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            self._isconnected = False
            raise Unreachable(errno.EHOSTUNREACH, "Connection to RabbitMQ is lost",
                              'rabbitmq broker', 'pubsub')
        return result

    def set_result(self, ident, value=None):
        try:
            result = self._results.pop(ident)
            if result:
                result.set(value)
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
                    result = self._results.pop(ident)
                    if result:
                        result.set(delivery_number)
                except KeyError:
                    pass
        except TypeError:
            pass

    def unsubscribe(self, peer, prefix, callback, bus='', all_platforms=False):
        """Unsubscribe and remove callback(s).

        Remove all handlers matching the given info - peer, callback and bus,
        which was used earlier to subscribe as well. If all handlers for a
        topic prefix are removed, the topic is also unsubscribed.
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

        result = next(self._results)
        if prefix is not None:
            routing_key = self._form_routing_key(prefix, all_platforms=all_platforms)
        topics = self._drop_subscription(routing_key, callback)
        self.core().spawn_later(0.01, self.set_result, result.ident, topics)
        # Send the message to proxy router to send it to external 'zmq' platforms
        if all_platforms:
            subscriptions = dict()
            subscriptions['all'] = dict(prefix=topics, bus=bus)
            rkey = self.core().instance_name + '.proxy.router.pubsub'
            frames = [self.core().identity, '', 'VIP1', '', '', 'pubsub',
                      'unsubscribe', jsonapi.dumps(subscriptions)]
            self.core().connection.channel.basic_publish(exchange=self.core().connection.exchange,
                                                         routing_key=rkey,
                                                         body=frames)
        return result

    def _drop_subscription(self, routing_key, callback):
        """
        Utility method to remove subscription
        :param routing_key: routing key
        :param callback: callback method
        :return:
        """
        self._logger.debug("DROP subscriptions: {}".format(routing_key))
        topics = []
        remove = []
        remove_topics = []
        if routing_key is None:
            if callback is None:
                for prefix in self._my_subscriptions:
                    subscriptions = self._my_subscriptions[prefix]
                    for queue_name in subscriptions.keys():
                        self.core().connection.channel.queue_delete(
                            callback=None, queue=queue_name)
                        subscriptions.pop(queue_name)
                    topics.append(prefix)
            else:
                # Traverse through all subscriptions to find the callback
                for prefix in self._my_subscriptions:
                    subscriptions = self._my_subscriptions[prefix]
                    self._logger.debug("prefix: {0}, {1}".format(prefix, subscriptions))
                    for queue_name, callbacks in subscriptions.items()():
                        try:
                            callbacks.remove(callback)
                        except KeyError:
                            pass
                        else:
                            topics.append(prefix)
                        if not callbacks:
                            # Delete queue
                            self.core().connection.channel.queue_delete(callback=None, queue=queue_name)
                            remove.append(queue_name)
                    for que in remove:
                        del subscriptions[que]
                    del remove[:]
                    if not subscriptions:
                        remove_topics.append(prefix)
                for prefix in remove_topics:
                    del self._my_subscriptions[prefix]
                if not topics:
                    raise KeyError('no such subscription')
                self._logger.debug("my subscriptions: {0}".format(self._my_subscriptions))
        else:
            # Search based on routing key
            if routing_key in self._my_subscriptions:
                self._logger.debug("RMQ subscriptions {}".format(self._my_subscriptions))
                topics.append(routing_key)
                subscriptions = self._my_subscriptions[routing_key]
                if callback is None:
                    for queue_name, callbacks in subscriptions.items()():
                        self._logger.debug("RMQ queues {}".format(queue_name))
                        self.core().connection.channel.queue_delete(callback=None, queue=queue_name)
                    del self._my_subscriptions[routing_key]
                else:
                    self._logger.debug("topics: {0}".format(topics))
                    for queue_name, callbacks in subscriptions.items()():
                        try:
                            callbacks.remove(callback)
                        except KeyError:
                            pass
                        if not callbacks:
                            # Delete queue
                            self.core().connection.channel.queue_delete(callback=None, queue=queue_name)
                            remove.append(queue_name)
                    for que in remove:
                        del subscriptions[que]
                    if not subscriptions:
                        del self._my_subscriptions[routing_key]
            self._logger.debug("my subscriptions: {0}".format(self._my_subscriptions))
        orig_topics = []
        # Strip '__pubsub__.<instance_name>' from the topic string
        for topic in topics:
            orig_topics.append(self._get_original_topic(topic))
        # self._logger.debug("AFTER DROP topics: {}".format(orig_topics))
        return orig_topics

    def _get_original_topic(self, routing_key):
        """
        Replace '.' delimiter with '/'
        :param routing_key: routing_key string
        :return: return original topic string
        """
        try:
            original_topic = routing_key.split('.')[2:]
            original_topic = original_topic[:-1]
            original_topic = '/'.join(original_topic)
            return original_topic
        except IndexError as exc:
            return routing_key

    def _form_routing_key(self, topic, all_platforms=False):
        """
        Form routing key from the original topic
        :param topic: Original topic
        :param all_platforms: Flag indicating if it is intended for all platforms
        :return: Routing key string
        """
        routing_key = ''
        topic = '#' if topic == '' else topic + '.#'

        if all_platforms:
            # Format is '__pubsub__.*.<prefix>.#'
            routing_key = "__pubsub__.*.{}".format(topic.replace("/", "."))
        else:
            routing_key = "__pubsub__.{0}.{1}".format(self.core().instance_name, topic.replace("/", "."))
        return routing_key
