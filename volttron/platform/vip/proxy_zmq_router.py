# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

from __future__ import print_function, absolute_import
import logging
import pika
import json
from .agent import Agent, Core, RPC
from . import green as vip
from volttron.platform.agent import json as jsonapi
from .socket import Message
from zmq import green as zmq
from zmq import ZMQError

_log = logging.getLogger(__name__)


class ZMQProxyRouter(Agent):
    """
    Proxy ZMQ based router agent is implemented for backward compatibility with ZeroMQ based message bus. In a single
    instance setup, either ZeroMQ or RabbitMQ based message bus will be running and all the agents will be using
    the same message bus. But in multi-platform setup, some instances maybe running with RabbitMQ message bus and
    others with ZeroMQ message bus. The Proxy router agent is implemented to manage the routing between local and
    external instances in such cases.

    Please note, if all instances in multi-platform setup are RabbitMQ based, then RabbitMQ federation/shovel have to
    be used.
    """
    def __init__(self, address, identity, zmq_router, *args, **kwargs):
        super(ZMQProxyRouter, self).__init__(identity, address, **kwargs)
        self.zmq_router = zmq_router
        self._routing_key = self.core.instance_name + '.' + 'proxy'
        self._outbound_proxy_queue = 'proxy_outbound'
        self._external_pubsub_rpc_queue = 'proxy_inbound'
        #
        # def subscriptions():
        #     return defaultdict(set)
        # self._peer_subscriptions = defaultdict(subscriptions)

    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        """
        On startup, it does the following:
         - Start ZMQ Router loop.
         - Establish RMQ queue bindings to handle routing of messages between internal and external agents.
        :param sender:
        :param kwargs:
        :return:
        """
        self.core.spawn(self.vip_loop)
        connection = self.core.connection
        channel = connection.channel
        # Create a queue to receive messages from local platform (for example, response for RPC request etc)
        result = channel.queue_declare(queue=self._outbound_proxy_queue,
                                       durable=False,
                                       exclusive=True,
                                       auto_delete=True,
                                       callback=None)
        channel.queue_bind(exchange=connection.exchange,
                            queue=self._outbound_proxy_queue,
                            routing_key=self.core.instance_name + '.proxy.router.subsystems',
                            callback=None)
        channel.basic_consume(self.zmq_outbound_handler,
                                queue=self._outbound_proxy_queue,
                                no_ack=True)

        # Create a queue to receive messages from local platform.
        # For example, external platform pubsub/RPC subscribe/unsubscribe requests from internal agents
        channel.queue_declare(queue=self._external_pubsub_rpc_queue,
                              durable=False,
                              exclusive=True,
                              auto_delete=True,
                              callback=None)
        # Binding for external platform pubsub message requests
        channel.queue_bind(exchange=connection.exchange,
                            queue=self._external_pubsub_rpc_queue,
                            routing_key=self.core.instance_name + '.proxy.router.pubsub',
                            callback=None)

        # Binding for external platform RPC message requests
        channel.queue_bind(exchange=self.core.connection.exchange,
                                 queue=self._external_pubsub_rpc_queue,
                                 routing_key=self.core.instance_name + '.proxy.router.external_rpc',
                                 callback=None)
        channel.basic_consume(self.external_pubsub_rpc_handler,
                                    queue=self._external_pubsub_rpc_queue,
                                    no_ack=True)


    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        """
        Stop the ZMQ router
        :param sender:
        :param kwargs:
        :return:
        """
        _log.debug("Stopping ZMQ Router")
        self.zmq_router.stop()

    def zmq_outbound_handler(self, ch, method, props, body):
        """
        Message received from internal agent to send to remote agent in ZMQ VIP message format.
        :param ch: channel
        :param method: contains routing key
        :param properties: message properties like VIP header information
        :param body: message
        :return:
        """
        # Strip sender's identity from binding key
        routing_key = str(method.routing_key)
        platform, to_identity = routing_key.split(".", 1)
        platform, from_identity = props.app_id.split(".", 1)
        try:
            args = json.loads(body)
            args = json.loads(args[0])
        except TypeError as e:
            # TODO: to be fixed
            _log.error("Invalid json format {}".format(e))
            return
        userid = props.headers.get('userid', b'')
        #_log.debug("Proxy ZMQ Router Outbound handler {0}, {1}".format(to_identity, args))
        # Reformat message into ZMQ VIP format
        frames = [bytes(to_identity), bytes(from_identity), b'VIP1', bytes(userid),
                  bytes(props.message_id), bytes(props.type), json.dumps(args)]
        try:
            self.zmq_router.socket.send_multipart(frames, copy=True)
        except ZMQError as ex:
            _log.debug("ZMQ Error {}".format(ex))
        #self.zmq_router.socket.vip_send(frames, copy=False)

    def external_pubsub_rpc_handler(self, ch, method, props, body):
        """
        Handler for receiving external platform PubSub/RPC requests from internal agents. It then calls external
        PubSub/RPC router handler to forward the request to external platform.
        :param ch: channel
        :param method: contains the routing key
        :param props: message properties
        :param body: message body
        :return:
        """
        _log.debug("Proxy ZMQ Router {}".format(body))
        frames = jsonapi.loads(body)
        if len(frames) > 6:
            if frames[5] == 'pubsub':
                # Forward the message to pubsub component of the router to take action
                self.zmq_router.pubsub.handle_subsystem(frames)
            else:
                # Forward the message to external RPC handler component of the router to take action
                self.zmq_router.ext_rpc.handle_subsystem(frames)

    def publish_callback(self, peer, sender, bus,  topic, headers, message):
        """
        Callback method registered with local message bus to receive PubSub messages
        subscribed by external platform agents. PubSub component of router will route the message to
        appropriate external platform subscribers.
        :return:
        """
        json_msg = jsonapi.dumps(dict(bus=bus, headers=headers, message=message))
        # Reformat the message into ZMQ VIP message frames
        frames = [sender, b'', b'VIP', '', '', 'pubsub',
                  zmq.Frame(b'publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]

        self.zmq_router.pubsub.handle_subsystem(frames, '')

    def vip_loop(self):
        """
        Infinite ZMQ based VIP loop to receive and send messages over ZMQ message bus.
        :return:
        """
        connection = self.core.connection
        # Set up ZMQ router socket connection
        self.zmq_router.start()
        # Register proxy agent handle
        self.zmq_router.pubsub.add_rabbitmq_agent(self)

        while True:
            try:
                frames = self.zmq_router.socket.recv_multipart(copy=False)
                sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
                recipient = bytes(recipient)
                # Check if router is the intended recipient or it has to route the message to an agent.
                # for f in frames:
                #     _log.debug("Proxy router message frames: {}".format(f))
                if not recipient:
                    self.zmq_router.route(frames)
                else:
                    self._handle_other_subsystems(frames)
            except ZMQError as e:
                _log.error("Error while receiving message: {}".format(e))

    def _handle_other_subsystems(self, frames):
        """
        Send the message to local agent using internal RabbitMQ message bus
        :param frames: ZMQ message frames
        :return:
        """
        sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
        args = frames[6:]
        args = [bytes(arg) for arg in args]
        # for f in frames:
        #     _log.debug("Frames:; {}".format(bytes(f)))
        connection = self.core.connection

        app_id = "{0}.{1}".format(self.core.instance_name, bytes(sender))
        # Change queue binding
        connection.channel.queue_bind(exchange=connection.exchange,
                           queue=self._outbound_proxy_queue,
                           routing_key=app_id,
                           callback=None)

        # Set the destination routing key to destination agent
        destination_routing_key = "{0}.{1}".format(self.core.instance_name, bytes(recipient))

        # Fit VIP frames into the PIKA properties dictionary
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'app_id': app_id,  # Routing key of SOURCE AGENT
            'headers': dict(sender=bytes(sender),  # SENDER
                            recipient=destination_routing_key,  # RECEIVER
                            proto=b'VIP',  # PROTO
                            userid=bytes(auth_token),  # USER_ID
                            ),
            'message_id': bytes(msg_id),  # MSG_ID
            'type': bytes(subsystem),  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        #_log.debug("PROXY PUBLISHING TO CHANNEL {0}, {1}, {2}".format(destination_routing_key, app_id, properties))
        connection.channel.basic_publish(connection.exchange,
                                   destination_routing_key,
                                   jsonapi.dumps(args, ensure_ascii=False),
                                   properties)
