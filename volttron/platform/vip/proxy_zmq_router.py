# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

from zmq import green as zmq
from zmq.green import ZMQError, ENOTSOCK

from volttron.platform import jsonapi
from volttron.utils.frame_serialization import deserialize_frames
from .agent import Agent, Core
from volttron.platform import is_rabbitmq_available

if is_rabbitmq_available():
    import pika

_log = logging.getLogger(__name__)


class ZMQProxyRouter(Agent):
    """
    Proxy ZMQ based router agent is implemented for backward compatibility with ZeroMQ based message bus. In a single
    instance setup, either ZeroMQ or RabbitMQ based message bus will be running and all the agents will be using
    the same message bus. But in multi-platform setup, some instances maybe running with RabbitMQ message bus and
    others with ZeroMQ message bus. The Proxy router agent is implemented to manage the routing between local and
    external instances in such cases.

    Please note, if all instances in multi-platform setup are RabbitMQ based, then RabbitMQ federation/shovel need to
    be used.
    """

    def __init__(self, address, identity, zmq_router, *args, **kwargs):
        super(ZMQProxyRouter, self).__init__(identity, address, **kwargs)
        self.zmq_router = zmq_router
        self._routing_key = self.core.instance_name + '.' + 'proxy'
        rmq_user = self.core.instance_name + '.' + identity
        self._outbound_response_queue = "{user}.zmq.outbound.response".format(user=rmq_user)
        self._outbound_request_queue = "{user}.zmq.outbound.request".format(user=rmq_user)
        self._rpc_handler_queue = "{user}.zmq.outbound.subsystem".format(user=rmq_user)
        self._vip_loop_running = False
        self._zmq_peers = set()

    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        """
        On startup, it does the following:
         - Start ZMQ Router loop.
         - Establish RMQ queue bindings to handle routing of messages
         between internal and external agents.
        :param sender:
        :param kwargs:
        :return:
        """
        if not self._vip_loop_running:
            self.core.spawn(self.vip_loop)

        connection = self.core.connection
        channel = connection.channel

        # ----------------------------------------------------------------------------------
        # Create a queue to receive messages from local platform
        # (for example, response for RPC request etc)
        result = channel.queue_declare(queue=self._rpc_handler_queue,
                                       durable=False,
                                       exclusive=True,
                                       auto_delete=True,
                                       callback=None)
        channel.queue_bind(exchange=connection.exchange,
                           queue=self._rpc_handler_queue,
                           routing_key=self.core.instance_name + '.proxy.router.zmq.outbound.subsystem',
                           callback=None)
        channel.basic_consume(self.rpc_message_handler,
                              queue=self._rpc_handler_queue,
                              no_ack=True)
        # --------------------------------------------------------------------------------------

        # Create a queue to receive messages from local platform
        # (for example, response for RPC request etc)
        result = channel.queue_declare(queue=self._outbound_response_queue,
                                       durable=False,
                                       exclusive=True,
                                       auto_delete=True,
                                       callback=None)
        channel.queue_bind(exchange=connection.exchange,
                           queue=self._outbound_response_queue,
                           routing_key=self.core.instance_name + '.proxy.router.subsystems',
                           callback=None)
        channel.basic_consume(self.outbound_response_handler,
                              queue=self._outbound_response_queue,
                              no_ack=True)

        # Create a queue to receive messages from local platform.
        # For example, external platform pubsub/RPC subscribe/unsubscribe
        # requests from internal agents
        channel.queue_declare(queue=self._outbound_request_queue,
                              durable=False,
                              exclusive=True,
                              auto_delete=True,
                              callback=None)
        # Binding for external platform pubsub message requests
        channel.queue_bind(exchange=connection.exchange,
                           queue=self._outbound_request_queue,
                           routing_key=self.core.instance_name + '.proxy.router.pubsub',
                           callback=None)

        # Binding for external platform RPC message requests
        channel.queue_bind(exchange=connection.exchange,
                           queue=self._outbound_request_queue,
                           routing_key=self.core.instance_name + '.proxy.router.external_rpc',
                           callback=None)
        channel.basic_consume(self.outbound_request_handler,
                              queue=self._outbound_request_queue,
                              no_ack=True)

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        """
        Stop the ZMQ router
        :param sender:
        :param kwargs:
        :return:
        """
        _log.debug("********************************************************************")
        _log.debug("Stopping ZMQ Router")
        _log.debug("********************************************************************")
        self.zmq_router.stop()

    def outbound_response_handler(self, ch, method, props, body):
        """
        Message received from internal agent to send to remote agent in ZMQ VIP message format.
        :param ch: channel
        :param method: contains routing key
        :param props: message properties like VIP header information
        :param body: message
        :return:
        """
        # Strip sender's identity from binding key
        routing_key = str(method.routing_key)
        platform, to_identity = routing_key.split(".", 1)
        platform, from_identity = props.app_id.split(".", 1)
        userid = props.headers.get('user', '')
        # Reformat message into ZMQ VIP format
        frames = [to_identity, from_identity, 'VIP1', userid,
                  props.message_id, props.type]
        try:
            args = jsonapi.loads(body)
            try:
                # This is necessary because jsonrpc request/response is inside a list which the
                # ZMQ agent subsystem does not like
                args = jsonapi.loads(args[0])
                frames.append(jsonapi.dumps(args))
            except ValueError as e:
                if isinstance(args, list):
                    for m in args:
                        frames.append(m)
                else:
                    frames.append(jsonapi.dumps(args))
        except TypeError as e:
            _log.error("Invalid json format {}".format(e))
            return

        _log.debug("Proxy ZMQ Router Outbound handler {0}, {1}".format(to_identity, args))

        try:
            self.zmq_router.socket.send_multipart(frames, copy=True)
        except ZMQError as ex:
            _log.error("ZMQ Error {}".format(ex))

    def rpc_message_handler(self, ch, method, props, body):
        """

        :param ch:
        :param method:
        :param props:
        :param body:
        :return:
        """
        zmq_frames = []
        frames = jsonapi.loads(body)

        try:
            self.zmq_router.socket.send_multipart(frames, copy=False)
        except ZMQError as ex:
            _log.error("ZMQ Error {}".format(ex))

    def outbound_request_handler(self, ch, method, props, body):
        """
        Handler for receiving external platform PubSub/RPC requests from internal agents.
        It then calls external PubSub/RPC router handler to forward the request to external platform.
        :param ch: channel
        :param method: contains the routing key
        :param props: message properties
        :param body: message body
        :return:
        """
        _log.debug("Proxy ZMQ Router {}".format(body))
        frames = jsonapi.loads(body.decode('utf-8'))
        if len(frames) > 6:
            if frames[5] == 'pubsub':
                # Forward the message to pubsub component of the router to take action
                self.zmq_router.pubsub.handle_subsystem(frames)
            else:
                # Forward the message to external RPC handler component of the router to take action
                self.zmq_router.ext_rpc.handle_subsystem(frames)

    def publish_callback(self, peer, sender, bus, topic, headers, message):
        """
        Callback method registered with local message bus to receive PubSub messages
        subscribed by external platform agents. PubSub component of router will route the message to
        appropriate external platform subscribers.
        :return:
        """
        json_msg = jsonapi.dumps(dict(bus=bus, headers=headers, message=message))
        # Reformat the message into ZMQ VIP message frames
        frames = [sender, '', 'VIP', '', '', 'pubsub',
                  zmq.Frame('publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]

        self.zmq_router.pubsub.handle_subsystem(frames, '')

    def vip_loop(self):
        """
        Infinite VIP loop to receive and send messages over ZMQ message bus.
        :return:
        """
        connection = self.core.connection
        # Set up ZMQ router socket connection
        self.zmq_router.start()
        # Register proxy agent handle
        self.zmq_router.pubsub.add_rabbitmq_agent(self)
        self._vip_loop_running = True

        while True:
            try:
                frames = self.zmq_router.socket.recv_multipart(copy=False)
                frames = deserialize_frames(frames)
                sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
                sender = sender
                recipient = recipient
                subsystem = subsystem

                if subsystem == 'hello':
                    self.vip.peerlist.add_peer(sender, 'zmq')
                    self._zmq_peers.add(sender)
                elif subsystem == 'agentstop':
                    self.vip.peerlist.drop_peer(sender, 'zmq')
                    self._zmq_peers.remove(sender)
                if not recipient or recipient in self._zmq_peers:
                    # Handle router specific messages or route to ZMQ peer
                    self.zmq_router.route(frames)
                else:
                    # Route to RabbitMQ agent
                    self._route_to_agent(frames)
            except ZMQError as exc:
                # _log.error("Error while receiving message: {}".format(exc))
                if exc.errno == ENOTSOCK:
                    break
        self._vip_loop_running = False

    def _route_to_agent(self, frames):
        """
        Send the message to local agent using internal RabbitMQ message bus
        :param frames: ZMQ message frames
        :return:
        """
        sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
        args = [arg for arg in frames[6:]]
        # for f in frames:
        #     _log.debug("Frames:; {}".format(f))
        connection = self.core.connection

        app_id = "{instance}.{identity}".format(instance=self.core.instance_name,
                                                identity=sender)
        # Change queue binding for the Response message
        # After sending the message (request) on behalf of ZMQ client, the response has to
        # routed back to the caller. Queue binding is modified for that purpose.
        # outbound_response_handler() gets called (based on the binding) to reformat response
        # message and send over zmq bus
        connection.channel.queue_bind(exchange=connection.exchange,
                                      queue=self._outbound_response_queue,
                                      routing_key=app_id,
                                      callback=None)

        # Set the destination routing key to destination agent
        destination_routing_key = "{0}.{1}".format(self.core.instance_name, recipient)

        # Fit VIP frames into the PIKA properties dictionary
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'user_id': self.core.instance_name + '.' + self.core.identity,
            'app_id': app_id,  # Routing key of SOURCE AGENT
            'headers': dict(sender=sender,  # SENDER
                            recipient=destination_routing_key,  # RECEIVER
                            proto='VIP',  # PROTO
                            user=auth_token,  # USER_ID
                            ),
            'message_id': msg_id,  # MSG_ID
            'type': subsystem,  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        # _log.debug("PROXY PUBLISHING TO CHANNEL {0}, {1}, {2}".format(destination_routing_key, app_id, properties))
        connection.channel.basic_publish(connection.exchange,
                                         destination_routing_key,
                                         jsonapi.dumps(args, ensure_ascii=False),
                                         properties)
