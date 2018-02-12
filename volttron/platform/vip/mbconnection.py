import pika
import gevent
import logging
import json
from volttron.platform.vip.socket import Message

class BaseConnection(object):
    """"""
    def __init__(self, url, instance_name, identity, *args, **kwargs):
        self._url = url
        self._identity = identity
        self._instance_name = instance_name
        self._vip_handler = None

    def bind(self):
        raise NotImplementedError()


class RMQConnection(BaseConnection):
    def __init__(self, url, instance_name, identity, *args, **kwargs):
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._routing_key = instance_name + "." + identity
        self._vip_queue = identity
        self._logger = logging.getLogger(__name__)
        self._exchange = 'volttron'
        self._connect_callback = None
        self._consumer_tag = None

    def open_connection(self):
        self._connection = pika.GeventConnection(pika.URLParameters(self._url),
                                     self._on_connection_open)

    def _on_connection_open(self, unused_connection):
        if self._connection is  None:
            self._connection = unused_connection
        # Open a channel
        self._connection.channel(self._on_channel_open)

    def _on_channel_open(self, new_channel):
        """Called when our channel has opened"""
        self._channel = new_channel

    def set_properties(self, flags):
        self._channel.exchange_declare(exchange=self._exchange, exchange_type="topic")
        self._channel.queue_declare(queue=self._vip_queue,
                                    durable=True,
                                    exclusive=False,
                                    auto_delete=True,
                                    callback=self._on_queue_declare_ok)

    def _on_queue_declareok(self, method_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """

    def _on_bind_ok(self, unused_frame):
        self._consumer_tag = self._channel.basic_consume(self._rmq_message_handler, queue=self._vip_queue)
        self._connect_callback(True)

    def connect(self, callback):
        self._logger.debug('Binding %s to %s with %s',
                self._exchange, self._queue, self._routing_key)
        self._channel.queue_bind(self._on_bindok,
                                 exchange=self._exchange,
                                 queue=self._vip_queue,
                                 routing_key=self._routing_key)
        self._connect_callback = callback

    def register(self, handler):
        self._vip_handler = handler

    def _rmq_message_handler(self, channel, method, props, body):
        # [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        #content_type = None, content_encoding = None, headers = None, delivery_mode = None, \
        #priority = None, correlation_id = None, reply_to = None, expiration = None, message_id = None, \
        #timestamp = None, type = None, user_id = None, app_id = None, cluster_id = None
        msg = Message()
        msg.peer = props.app_id
        msg.user = ''
        msg.id = props.message_id
        msg.subsytem = props.type
        msg.args = body
        if self._vip_handler:
            self._vip_handler(msg)

    def send_vip_object(self, vip_message):
        #[SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'app_id': self._routing_key,
            'type': getattr(vip_message.subsytem),
            'message_id': getattr(vip_message, 'id', b''),
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        msg = getattr(vip_message, 'args', None)
        routing_key = vip_message.peer
        if routing_key == b'':
            routing_key = self._instance_name + '.' + 'router'
        self._channel.basic_publish(self._exchange,
                                    routing_key,
                                    json.dumps(msg, ensure_ascii=False),
                                    properties)

    def disconnect(self):
        if self._channel:
            self._channel.basic_cancel(self._on_cancelok, self._consumer_tag)

    def _on_cancel_ok(self):
        """Close the channel after we stop consuming from the channel"""
        self._channel.close()

    def close_connection(self):
        """This method closes the connection to RabbitMQ"""
        self._connection.close()
