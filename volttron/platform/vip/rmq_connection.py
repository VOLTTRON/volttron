import os
import pika
import logging
import json
from volttron.platform.vip.socket import Message
import errno
from volttron.platform.agent import json as jsonapi
from gevent import monkey
from volttron.utils.rmq_mgmt import build_rmq_address

monkey.patch_socket()

_log = logging.getLogger(__name__)
# reduce pika log level
logging.getLogger("pika").setLevel(logging.WARNING)

class BaseConnection(object):
    """

    """
    def __init__(self, url, identity, instance_name, *args, **kwargs):
        self._url = url
        self._identity = identity
        self._instance_name = instance_name
        self._vip_handler = None

    def bind(self):
        raise NotImplementedError()


class RMQConnection(BaseConnection):
    """
    Maintains RabbitMQ connection
    """
    def __init__(self, url, identity, instance_name, type='agent', *args, **kwargs):
        super(RMQConnection, self).__init__(url, identity, instance_name, args, kwargs)
        self._connection = None
        self.channel = None
        self._closing = False
        self._consumer_tag = None
        self._error_tag = None
        self._url = 'amqp://volttron:volttron@localhost:5672/volttron'
        _log.debug("AMQP address: {}".format(self._url))#'amqp://guest:guest@localhost:5672/%2F'
        self.routing_key = "{0}.{1}".format(instance_name, identity)
        #self.routing_key = identity
        self._vip_queue = "__{0}__.{1}".format(instance_name, identity)#identity
        self._logger = logging.getLogger(__name__)
        self.exchange = 'volttron'
        self._vip_queue = identity
        self._alternate_exchange = 'undeliverable'
        self._alternate_queue = 'alternate_queue'
        self._connect_callback = None
        self._type = type
        self._queue_properties = dict()
        #_log.debug("ROUTING KEY: {}".format(self.routing_key))

    def open_connection(self, type='agent'):
        if type == 'agent':
            self._connection = pika.GeventConnection(pika.URLParameters(self._url),
                                     self.on_connection_open)
        else:
            self._connection = pika.SelectConnection(pika.URLParameters(self._url),
                                     self.on_connection_open)

    def on_connection_open(self, unused_connection):
        if self._connection is None:
            self._connection = unused_connection
        # Open a channel
        self._connection.channel(self.on_channel_open)

    def on_channel_open(self, new_channel):
        """Called when our channel has opened"""
        self.channel = new_channel
        # self.channel.exchange_delete(exchange=self.exchange)
        # self.channel.exchange_delete(exchange=self._alternate_exchange)
        args = dict()
        args['alternate-exchange'] = self._alternate_exchange
        # self.channel.exchange_declare(exchange=self.exchange,
        #                                 exchange_type="topic"
        #                                 ,arguments=args)
        # self.channel.exchange_declare(exchange=self._alternate_exchange,
        #                                 exchange_type="fanout")
        self.channel.queue_declare(queue=self._vip_queue,
                                    durable=self._queue_properties['durable'],
                                    exclusive=self._queue_properties['exclusive'],
                                    auto_delete=self._queue_properties['auto_delete'],
                                    callback=self.on_queue_declare_ok)
        if self._type == 'platform':
            self.channel.queue_declare(queue=self._alternate_queue,
                                       durable=False,
                                       auto_delete= True,
                                       callback=self.on_alternate_queue_declare_ok)

    def set_properties(self, flags):
        self._queue_properties['durable'] = flags.get('durable', True)
        self._queue_properties['exclusive'] = flags.get('exclusive', False)
        self._queue_properties['auto_delete'] = flags.get('auto_delete', True)

    def on_queue_declare_ok(self, method_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """
        self._logger.debug('Binding %s to %s with %s',
                           self.exchange, self._vip_queue, self.routing_key)
        self.channel.queue_bind(self.on_bind_ok,
                                exchange=self.exchange,
                                queue=self._vip_queue,
                                routing_key=self.routing_key)

    def on_alternate_queue_declare_ok(self, method_frame):
        self.channel.queue_bind(self.on_alternate_queue_bind_ok,
                                exchange=self._alternate_exchange,
                                queue=self._alternate_queue,
                                routing_key=self._instance_name)

    def on_bind_ok(self, unused_frame):
        self._consumer_tag = self.channel.basic_consume(self.rmq_message_handler,
                                                        queue=self._vip_queue)
        if self._connect_callback:
            self._connect_callback()

    def on_alternate_queue_bind_ok(self, unused_frame):
        self._error_tag = self.channel.basic_consume(self._handle_error,
                                                     queue=self._alternate_queue)

    def connect(self, callback=None):
        """
        Start the connection process
        :param callback:
        :return:
        """
        self._connect_callback = callback
        self.open_connection(type=self._type)

    def register(self, handler):
        self._vip_handler = handler

    def rmq_message_handler(self, channel, method, props, body):
        # [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        #content_type = None, content_encoding = None, headers = None, delivery_mode = None, \
        #priority = None, correlation_id = None, reply_to = None, expiration = None, message_id = None, \
        #timestamp = None, type = None, user_id = None, app_id = None, cluster_id = None
        #_log.debug("*************{}*****************************".format(self._identity))
        #_log.debug("Channel {0}, Props {1}, body {2}".format(channel, props, body))
        app_id = str(props.app_id)
        platform, peer = app_id.split(".", 1)

        msg = Message()
        # If peer is "proxy router", peer becomes sender
        msg.peer = peer
        msg.user = props.headers.get('userid', b'')
        msg.platform = platform
        msg.id = props.message_id
        msg.subsystem = props.type
        msg.args = json.loads(body)
        if self._vip_handler:
            self._vip_handler(msg)

    def _handle_error(self, channel, method, props, body):
        """
         Handle Unroutable messages. Send error message back to sender
        :param channel:
        :param method:
        :param props:
        :param body:
        :return:
        """
        if props.type == 'pubsub':
            return

        sender = props.app_id
        subsystem = props.type
        props.type = b'error'
        errnum = errno.EHOSTUNREACH
        errmsg = os.strerror(errnum).encode('ascii')  # str(errnum).encode('ascii')
        recipient = props.headers.get('recipient', '')
        platform, identity = recipient.split(".", 1)
        message = [errnum, errmsg, recipient, subsystem]
        #_log.debug("Error Message is: {0}, {1}, {2}".format(method.routing_key, props.app_id, body))
        self.channel.basic_publish(self.exchange, sender, json.dumps(message, ensure_ascii=False), props)

    def send_vip_object(self, message):
        """

        :param message:
        :return:
        """
        platform = getattr(message, 'platform', self._instance_name)
        sender = getattr(message, 'sender', self._identity)

        if message.peer == b'':
            message.peer = 'router'
        if platform == b'':
            platform = self._instance_name

        destination_routing_key = "{0}.{1}".format(platform, message.peer)

        # Fit VIP frames in the PIKA properties dict
        # VIP format - [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ARGS...]
        dct = {
            'app_id': self.routing_key,  # Routing key of SENDER
            'headers': dict(
                            #sender=sender, # SENDER
                            recipient=destination_routing_key,  # RECEIVER
                            proto=b'VIP',  # PROTO
                            userid=getattr(message, 'user', b''),  # USER_ID
                            ),
            'message_id': getattr(message, 'id', b''),  # MSG_ID
            'type': message.subsystem,  # SUBSYS
            'content_type': 'application/json'
        }
        properties = pika.BasicProperties(**dct)
        msg = getattr(message, 'args', None)  # ARGS
        #_log.debug("PUBLISHING TO CHANNEL {0}, {1}, {2}".format(destination_routing_key, msg, properties))
        self.channel.basic_publish(self.exchange,
                                    destination_routing_key,
                                    json.dumps(msg, ensure_ascii=False),
                                    properties)

    def loop(self):
        """
        Connect to RabbiMQ broker and run infinite loop to listen to incoming messages
        :return:
        """
        try:
            self.connect()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError):
            _log.debug("Unable to connect to the RabbitMQ broker")
            return
        self._connection.ioloop.start()

    def disconnect(self):
        """
        Disconnection from channel
        :return:
        """
        if self.channel:
            self.channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def on_cancel_ok(self):
        """
        Close the channel after we stop consuming from the channel
        :return:
        """
        self.channel.close()

    def close_connection(self):
        """This method closes the connection to RabbitMQ"""
        if self.channel and self.channel.is_open:
            _log.debug("********************************************************************")
            _log.debug("Closing connection to RMQ: {}".format(self._identity))
            _log.debug("********************************************************************")

            self._connection.close()
