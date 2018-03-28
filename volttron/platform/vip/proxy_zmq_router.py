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

_log = logging.getLogger(__name__)


class ZMQProxyRouter(Agent):
    """

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
        # Create a queue to receive messages from internal messages (for example, response for RPC request etc)
        result = channel.queue_declare(queue=self._outbound_proxy_queue,
                                         durable=False,
                                         exclusive=False,
                                         callback=None)
        channel.queue_bind(exchange=connection.exchange,
                                 queue=self._outbound_proxy_queue,
                                 routing_key=self.core.instance_name + '.proxy.router.subsystems',
                                 callback=None)
        channel.basic_consume(self.zmq_outbound_handler,
                                    queue=self._outbound_proxy_queue,
                                    no_ack=True)

        # Create a queue to receive external platform pubsub/rpc subscribe/unsubscribe requests from internal agents
        channel.queue_declare(queue=self._external_pubsub_rpc_queue,
                                         durable=False,
                                         exclusive=False,
                                         callback=None)
        # Binding for external platform pubsub messages
        channel.queue_bind(exchange=connection.exchange,
                                 queue=self._external_pubsub_rpc_queue,
                                 routing_key=self.core.instance_name + '.proxy.router.pubsub',
                                 callback=None)

        # Binding for external platform RPC messages
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
        Stop the zmq router
        :param sender:
        :param kwargs:
        :return:
        """
        _log.debug("Stopping ZMQ Router")
        self.zmq_router.stop()

    def zmq_outbound_handler(self, ch, method, props, body):
        """
        Message received from internal agent is sent to an external agent in ZMQ VIP message format.
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
        args = json.loads(body)
        args = json.loads(args[0])
        userid = props.headers.get('userid', b'')
        _log.debug("Proxy ZMQ Router Outbound handler {0}, {1}".format(to_identity, args))
        # Fit message into ZMQ VIP format
        frames = [bytes(to_identity), bytes(from_identity), b'VIP1', bytes(userid),
                  bytes(props.message_id), bytes(props.type), json.dumps(args)]
        self.zmq_router.socket.send_multipart(frames, copy=True)
        #self.zmq_router.socket.vip_send(frames, copy=False)

    def external_pubsub_rpc_handler(self, ch, method, props, body):
        """

        :param ch:
        :param method:
        :param props:
        :param body:
        :return:
        """
        _log.debug("Proxy ZMQ Router {}".format(body))
        frames = jsonapi.loads(body)
        if len(frames) > 6:
            if frames[5] == 'pubsub':
                self.zmq_router.pubsub.handle_subsystem(frames)
            else:
                # Forward the message to zmq router to take action
                self.zmq_router.ext_rpc.handle_subsystem(frames)

    def publish_callback(self, peer, sender, bus,  topic, headers, message):
        """

        :return:
        """
        json_msg = jsonapi.dumps(dict(bus=bus, headers=headers, message=message))
        frames = [sender, b'', b'VIP', '', '', 'pubsub',
                  zmq.Frame(b'publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]

        self.zmq_router.pubsub.handle_subsystem(frames, '')
        # subscriptions = self._peer_subscriptions.get('bus', None)
        # if subscriptions:
        #     subscribers = set()
        #     for prefix, subscription in subscriptions.iteritems():
        #         if subscription and topic.startswith(prefix):
        #             subscribers |= subscription
        #     if subscribers:
        #         for peer in subscribers:
        #             json_msg = jsonapi.dumps(dict(bus=bus, headers=headers, message=message))
        #             args = [zmq.Frame(b'publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]
        #
        #             self.zmq_router.connection.send_vip_object(Message(peer=peer,
        #                                                                subsystem='pubsub',
        #                                                                id=None,
        #                                                                args=args))

    def vip_loop(self):
        """

        :return:
        """
        connection = self.core.connection
        self.zmq_router.start()
        self.zmq_router.pubsub.add_proxy_agent(self)

        while True:
            #_log.debug("I'vvvvvve started looping")
            frames = self.zmq_router.socket.recv_multipart(copy=False)
            sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
            recipient = bytes(recipient)
            subsystem = bytes(subsystem)
            # If message needs to be handled by router
            if not recipient:
                self.zmq_router.route(frames)
            else:
                self._handle_other_subsystems(frames)
            #     if subsystem == 'pubsub':
            #         for f in frames:
            #             _log.debug("ROUTER Receiving frames: {}".format(bytes(f)))
            #         self._handle_pubsub_subsystem(frames, auth_token)
            #     else:
            #         message = Message(peer=recipient, subsystem=subsystem, id=msg_id, args=frames[6:])
            #         self._handle_other_subsystems(message, sender)

    def _handle_pubsub_subsystem(self, frames, user_id):
        """

        :param message:
        :return:
        """
        sender, recipient, proto, auth_token, msg_id, subsystem, op = frames[:7]
        op = bytes(op)
        if subsystem == 'pubsub':
            if op == b'subscribe':
                self.zmq_router.pubsub.handle_subsystem(frames, user_id)
                data = frames[7]
                msg = jsonapi.loads(data)
                try:
                    prefix = msg['prefix']
                    bus = msg['bus']
                    peer = frames[0]
                except KeyError as exc:
                    _log.error("Missing key in _peer_subscribe message {}".format(exc))
                    return False
                self._peer_subscriptions[bus][prefix].add(peer)
                self.vip.pubsub.subscribe(self, prefix, self.publish_callback)
            elif op == b'publish':
                _log.debug("publish: {0}, {1}".format(subsystem, len(frames)))
                if len(frames) > 8:
                    topic = frames[7].bytes
                    data = frames[8].bytes
                    try:
                        msg = jsonapi.loads(data)
                        headers = msg['headers']
                        message = msg['message']
                        bus = msg['bus']
                        _log.debug("Publish locally {}".format(topic))
                        self.vip.pubsub.publish(self, 'pubsub', topic, headers=headers, message=message)
                    except KeyError as exc:
                        _log.error("Missing key in _peer_publish message {}".format(exc))
                        return 0
                    except ValueError:
                        _log.debug("Value error")
            else:
                self.zmq_router.pubsub.handle_subsystem(frames, user_id)

    def _handle_other_subsystems(self, frames):
        """

        :param message:
        :return:
        """
        sender, recipient, proto, auth_token, msg_id, subsystem = frames[:6]
        args = frames[6:]
        args = [bytes(arg) for arg in args]
        # for f in frames:
        #     _log.debug("Frames:; {}".format(bytes(f)))
        connection = self.core.connection

        app_id = "{0}.{1}".format(self.core.instance_name, bytes(sender))
        # Change binding
        connection.channel.queue_bind(exchange=connection.exchange,
                           queue=self._outbound_proxy_queue,
                           routing_key=app_id,
                           callback=None)

        # Special check for ZMQ agent message routing via proxy router
        # If via is proxy, then sender = actual sending peer
        # If peer is proxy_router => destination routing key remains same
        # Else, destination peer becomes proxy_router
        destination_routing_key = "{0}.{1}".format(self.core.instance_name, bytes(recipient))

        # Fit VIP frames in the PIKA properties dict
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
        _log.debug("PROXY PUBLISHING TO CHANNEL {0}, {1}, {2}".format(destination_routing_key, app_id, properties))
        connection.channel.basic_publish(connection.exchange,
                                   destination_routing_key,
                                   jsonapi.dumps(args, ensure_ascii=False),
                                   properties)
