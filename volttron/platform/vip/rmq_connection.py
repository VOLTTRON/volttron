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

import json
import logging
import os

import pika
import errno
from volttron.platform.vip.socket import Message
from volttron.platform.vip import BaseConnection


_log = logging.getLogger(__name__)
# reduce pika log level
logging.getLogger("pika").setLevel(logging.WARNING)


class RMQConnection(BaseConnection):
    """
    Connection class for RabbitMQ message bus.
    1. It maintains connection with RabbitMQ broker using Pika library APIs
    2. Translates from VIP message format to RabbitMQ message format and visa-versa
    3. Sends and receives messages using Pika library APIs
    """
    def __init__(self, url, identity, instance_name, vc_url=None):
        super(RMQConnection, self).__init__(url, identity, instance_name)
        self._connection = None
        self.channel = None
        self._closing = False
        self._consumer_tag = None
        self._error_tag = None

        if vc_url:
            self._url = url

        self._connection_param = url
        self.routing_key = self._vip_queue_name = self._rmq_userid = \
            "{instance}.{identity}".format(instance=instance_name, identity=identity)
        self.exchange = 'volttron'
        self._connect_callback = None
        self._connect_error_callback = None
        self._queue_properties = dict()
        #_log.debug("ROUTING KEY: {}".format(self.routing_key))

    def open_connection(self):
        """
        Open a gevent adapter connection.
        :return:
        """
        self._connection = pika.GeventConnection(self._connection_param,
                                                 on_open_callback=self.on_connection_open,
                                                 on_open_error_callback=self.on_open_error,
                                                 #on_close_callback=self.on_connection_closed,
                                                 )

    def on_connection_open(self, unused_connection):
        """
        This method is invoked by pika when connection has been opened.
        :param unused_connection: new connection object
        :return:
        """
        if self._connection is None:
            self._connection = unused_connection
        # Open a channel
        self._connection.channel(self.on_channel_open)

    def on_open_error(self, _connection_unused, error_message=None):
        """
        Call the registered error handler
        :param _connection_unused:
        :param error_message: connection error message
        :return:
        """
        _log.error("Connection open error. Check if RabbitMQ broker is running.")
        if self._connect_error_callback:
            self._connect_error_callback()

    def on_connection_closed(self, connection, reply_code, reply_text):
        """
        Try to reconnect to the broker after few seconds
        :param connection: connection object
        :param reply_code: Connection Code
        :param reply_text: Connection reply message
        :return:
        """
        _log.debug("Connection closed unexpectedly, reopening in 5 seconds. {}"
                   .format(self._identity))
        self._connection.add_timeout(5, self._reconnect)

    def _reconnect(self):
        """
        Will be invoked by the IOLoop timer if the connection is closed
        """
        # First, close the old connection IOLoop instance
        self._connection.ioloop.stop()
        # Next, create a new connection
        self.open_connection()

        # There is now a new connection, needs a new ioloop to run
        self._connection.ioloop.start()

    def on_channel_open(self, channel):
        """
        This method is invoked by pika when channel has been opened. Declare VIP queue to
        handle messages
        :param new_channel: new channel object
        :return:
        """
        self.channel = channel
        self.channel.queue_declare(queue=self._vip_queue_name,
                                    durable=self._queue_properties['durable'],
                                    exclusive=self._queue_properties['exclusive'],
                                    auto_delete=self._queue_properties['auto_delete'],
                                    callback=self.on_queue_declare_ok)

    def set_properties(self, flags):
        """
        Set queue properties
        :param flags:
        :return:
        """
        self._queue_properties['durable'] = flags.get('durable', True)
        self._queue_properties['exclusive'] = flags.get('exclusive', False)
        self._queue_properties['auto_delete'] = flags.get('auto_delete', True)

    def on_queue_declare_ok(self, method_frame):
        """
        Callback method invoked after VIP queue has been declared. Next, we bind the
        queue to the exchange with VIP routing key.
        :param method_frame: The Queue.DeclareOk frame
        :return:
        """
        _log.debug('Binding {0} to {1} with {2}'.format(self.exchange,
                                                                self._vip_queue_name,
                                                                self.routing_key))
        self.channel.queue_bind(self.on_bind_ok,
                                exchange=self.exchange,
                                queue=self._vip_queue_name,
                                routing_key=self.routing_key)

    def on_bind_ok(self, unused_frame):
        """
        Callback method invoked by Pika when VIP queue bind has completed. At this point
        we will start consuming messages by calling start_consuming.
        :param unused_frame: The Queue.BindOk response frame
        :return:
        """
        self._consumer_tag = self.channel.basic_consume(self.rmq_message_handler,
                                                        queue=self._vip_queue_name)
        if self._connect_callback:
            self._connect_callback()

    def connect(self, connection_callback=None, connection_error_callback=None):
        """
        Connect to RabbitMQ broker. Save the callback method to be invoked
        after connection steps are completed.
        :param connection_callback:
        :param connection_error_callback:
        :return:
        """
        self._connect_callback = connection_callback
        self._connect_error_callback = connection_error_callback
        self.open_connection()

    def register(self, handler):
        """
        Register VIP handler to be invoked to handle incoming messages
        :param handler: VIP handler callback method
        :return:
        """
        self._vip_handler = handler

    def rmq_message_handler(self, channel, method, props, body):
        """
        Message handler for incoming messages. Reformats the incoming messages to VIP message
        object and hands it over to VIP message handler.
        :param channel: channel object
        :param method: method frame - contains routing key
        :param props: message properties containing VIP details such as
                      [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS,]
        :param body: message body
        :return:
        """
        # _log.debug("*************rmq_message_handler {}*****************************".
        # format(self._identity))
        # _log.debug("Channel {0}, Props {1}, body {2}".format(channel, props, body))
        app_id = str(props.app_id)
        platform, peer = app_id.split(".", 1)

        msg = Message()
        msg.peer = peer
        msg.user = props.headers.get('user', b'')
        msg.platform = platform
        msg.id = props.message_id
        msg.subsystem = props.type
        msg.args = json.loads(body)
        if self._vip_handler:
            self._vip_handler(msg)

    def send_vip_object(self, message):
        """
        Send the VIP message over RabbitMQ message bus.
        Reformat the VIP message object into Pika message object and
        publish it using Pika library
        :param message: VIP message object
        :return:
        """
        platform = getattr(message, 'platform', self._instance_name)
        if message.peer == b'':
            message.peer = 'router'
        if platform == b'':
            platform = self._instance_name

        destination_routing_key = "{0}.{1}".format(platform, message.peer)

        # Fit VIP frames in the PIKA properties dict
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'user_id': self._rmq_userid,
            'app_id': self.routing_key,  # Routing key of SENDER
            'headers': dict(
                            recipient=destination_routing_key,  # RECEIVER
                            proto=b'VIP',  # PROTO
                            user=getattr(message, 'user', self._rmq_userid),  # USER_ID
                            ),
            'message_id': getattr(message, 'id', b''),  # MSG_ID
            'type': message.subsystem,  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        msg = getattr(message, 'args', None)  # ARGS
        # _log.debug("PUBLISHING TO CHANNEL {0}, {1}, {2}, {3}".format(destination_routing_key,
        #                                                              msg,
        #                                                              properties,
        #                                                              self.routing_key))
        self.channel.basic_publish(self.exchange,
                                   destination_routing_key,
                                   json.dumps(msg, ensure_ascii=False),
                                   properties)

    def disconnect(self):
        """
        Disconnect from channel i.e, stop consuming from the channel
        :return:
        """
        try:
            if self.channel and self.channel.is_open:
                self.channel.basic_cancel(self.on_cancel_ok, self._consumer_tag)
        except (pika.exceptions.ConnectionClosed, pika.exceptions.ChannelClosed) as exc:
            _log.error("Connection to RabbitMQ broker or Channel is already closed.")
            self._connection.ioloop.stop()

    def on_cancel_ok(self):
        """
        Callback method invoked by Pika when RabbitMQ acknowledges the cancellation of a consumer.
        Next step is to close the channel.
        :return:
        """
        self.channel.close()
        self._connection.close()

    def close_connection(self, linger=None):
        """
        This method closes the connection to RabbitMQ.
        :return:
        """
        if self.channel and self.channel.is_open:
            _log.debug("********************************************************************")
            _log.debug("Closing connection to RMQ: {}".format(self._identity))
            _log.debug("********************************************************************")
            self._connection.close()


class RMQRouterConnection(RMQConnection):
    """
    RabbitMQ message bus connection class for Router module
    """
    def __init__(self, url, identity, instance_name, vc_url=None):
        super(RMQRouterConnection, self).__init__(url, identity, instance_name)
        _log.debug("ROUTER URL: {}".format(url))
        self._alternate_exchange = 'undeliverable'
        self._alternate_queue = "{instance}.{identity}.unroutable".format(instance=instance_name,
                                                                          identity=identity)

    def open_connection(self):
        """
        Open asynchronous connection for router/platform
        :return:
        """
        self._connection = pika.SelectConnection(self._connection_param,
                                                 on_open_callback=self.on_connection_open,
                                                 on_close_callback=self.on_connection_closed,
                                                 on_open_error_callback=self.on_open_error,
                                                 stop_ioloop_on_close=False
                                                 )

    def on_channel_open(self, channel):
        """
        This method is invoked by pika when channel has been opened.
        Declare VIP queue to handle messages
        :param new_channel: new channel object
        :return:
        """
        self.channel = channel
        args = dict()
        args['alternate-exchange'] = self._alternate_exchange

        self.channel.queue_declare(queue=self._vip_queue_name,
                                    durable=self._queue_properties['durable'],
                                    exclusive=self._queue_properties['exclusive'],
                                    auto_delete=self._queue_properties['auto_delete'],
                                    callback=self.on_queue_declare_ok)
        self.channel.queue_declare(queue=self._alternate_queue,
                                   durable=False,
                                   exclusive=True,
                                   auto_delete= True,
                                   callback=self.on_alternate_queue_declare_ok)

    def on_alternate_queue_declare_ok(self, method_frame):
        """
        Callback method invoked after alternate queue has been declared. Next, we bind the
        queue to the alternate exchange to receive unroutable messages.
        :param method_frame: The Queue.DeclareOk frame
        :return:
        """
        self.channel.queue_bind(self.on_alternate_queue_bind_ok,
                                exchange=self._alternate_exchange,
                                queue=self._alternate_queue,
                                routing_key=self._instance_name)

    def on_alternate_queue_bind_ok(self, unused_frame):
        """
        Callback method invoked by Pika when alternate queue bind has completed. At this point
        we will start consuming messages by calling start_consuming.
        :param unused_frame: The Queue.BindOk response frame
        :return:
        """
        self._error_tag = self.channel.basic_consume(self._handle_error,
                                                     queue=self._alternate_queue)

    def on_open_error(self, _connection_unused, error_message=None):
        """
        Stop the infinite loop and call the registered error handler
        :param _connection_unused:
        :param error_message: connection error message
        :return:
        """
        _log.error("Connection open error. Check if RabbitMQ broker is running.")
        self._connection.ioloop.stop()
        if self._connect_error_callback:
            self._connect_error_callback()

    def _handle_error(self, channel, method, props, body):
        """
         Handle unroutable messages. Send error message back to sender.
         Ignore if subsystem is pubsub.
        :param channel: channel object
        :param method: method frame - contains routing key
        :param props: message properties containing VIP info such as
                      [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS,]
        :param body: message body
        :return:
        """
        # Ignore if message type is 'pubsub'
        if props.type == 'pubsub':
            return

        sender = props.app_id
        subsystem = props.type
        props.app_id = self.routing_key
        props.type = b'error'
        props.user_id = self._rmq_userid
        errnum = errno.EHOSTUNREACH
        errmsg = os.strerror(errnum).encode('ascii')
        recipient = props.headers.get('recipient', '')
        message = [errnum, errmsg, recipient, subsystem]
        # _log.debug("Host Unreachable Error Message is: {0}, {1}, {2}".format(method.routing_key,
        #                                                     sender,
        #                                                     props))
        self.channel.basic_publish(self.exchange,
                                   sender,
                                   json.dumps(message, ensure_ascii=False),
                                   props)

    def loop(self):
        """
        Connect to RabbiMQ broker and run infinite loop to listen to incoming messages
        :return:
        """
        try:
            self.connect()
            self._connection.ioloop.start()
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            _log.error("RabbitMQ Connection Error. {}".format(exc))
