import os
import pika
import logging
import json
from volttron.platform.vip.socket import Message
import errno
#from gevent import monkey
from volttron.utils.rmq_mgmt import build_rmq_address, create_user
#monkey.patch_socket()
import uuid
import time

_log = logging.getLogger(__name__)
# reduce pika log level
logging.getLogger("pika").setLevel(logging.WARNING)

class BaseConnection(object):
    """
    Base connection class for message bus connection.
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
    Maintains connection with RabbitMQ broker
    """
    def __init__(self, url, identity, instance_name, type='agent', vc_url=None, *args, **kwargs):
        super(RMQConnection, self).__init__(url, identity, instance_name, args, kwargs)
        self._connection = None
        self.channel = None
        self._closing = False
        self._consumer_tag = None
        self._error_tag = None
        #self._userid = agent_uuid if agent_uuid is not None else identity
        # Create new agent user
        #create_user(self._userid, str(uuid.uuid4()))
        self._logger = logging.getLogger(__name__)
        self._logger.debug("AGENT address: {}".format(url))
        if vc_url:
            self._url = url
        else:
            self._url = build_rmq_address()
        _log.debug("AMQP address: {}".format(self._url))#'amqp://guest:guest@localhost:5672/%2F'
        self.routing_key = "{0}.{1}".format(instance_name, identity)
        #self.routing_key = identity
        self._vip_queue = "__{0}__.{1}".format(instance_name, identity)#identity

        self.exchange = 'volttron'
        self._vip_queue = identity
        self._alternate_exchange = 'undeliverable'
        self._alternate_queue = 'alternate_queue'
        self._connect_callback = None
        self._connect_error_callback = None
        self._type = type
        self._queue_properties = dict()
        #_log.debug("ROUTING KEY: {}".format(self.routing_key))

    def open_connection(self, type=None):
        """
        If the connection is for an agent, open a gevent adapter connection. If the connection
        is for platform, open asynchronous connection.
        :param type: agent/platform
        :return:
        """
        if self._type == 'agent':
            self._connection = pika.GeventConnection(pika.URLParameters(self._url),
                                                     on_open_callback=self.on_connection_open,
                                                     on_open_error_callback=self.on_open_error
                                                     #on_close_callback=self.on_connection_closed,
                                                     )
        else:
            self._connection = pika.SelectConnection(
                                    pika.URLParameters(self._url),
                                    on_open_callback=self.on_connection_open,
                                    on_close_callback=self.on_connection_closed,
                                    on_open_error_callback=self.on_open_error,
                                    stop_ioloop_on_close=False
                                    )
        self._type = type

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
        _log.error("Connection open error. Check if RabbitMQ broker is running.")
        if self._type == 'platform':
            self._connection.ioloop.stop()
        if self._connect_error_callback:
            self._connect_error_callback()

    def on_connection_closed(self, connection, reply_code, reply_text):
        """
        Try to reconnect to the broker after few seconds
        :param connection:
        :param reply_code:
        :param reply_text:
        :return:
        """
        _log.debug("Connection closed unexpectedly, reopening in 5 seconds. {}".format(self._identity))
        self._connection.add_timeout(5, self._reconnect)

    def _reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is closed
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
                                       exclusive=True,
                                       auto_delete= True,
                                       callback=self.on_alternate_queue_declare_ok)

    def set_properties(self, flags):
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
        self._logger.debug('Binding {0} to {1} with {2}'.format(self.exchange,
                                                                self._vip_queue,
                                                                self.routing_key))
        self.channel.queue_bind(self.on_bind_ok,
                                exchange=self.exchange,
                                queue=self._vip_queue,
                                routing_key=self.routing_key)

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

    def on_bind_ok(self, unused_frame):
        """
        Callback method invoked by Pika when VIP queue bind has completed. At this point
        we will start consuming messages by calling start_consuming.
        :param unused_frame: The Queue.BindOk response frame
        :return:
        """
        self._consumer_tag = self.channel.basic_consume(self.rmq_message_handler,
                                                        queue=self._vip_queue)
        if self._connect_callback:
            self._connect_callback()

    def on_alternate_queue_bind_ok(self, unused_frame):
        """
        Callback method invoked by Pika when alternate queue bind has completed. At this point
        we will start consuming messages by calling start_consuming.
        :param unused_frame: The Queue.BindOk response frame
        :return:
        """
        self._error_tag = self.channel.basic_consume(self._handle_error,
                                                     queue=self._alternate_queue)

    def connect(self, connection_callback=None, connection_error_callback=None):
        """
        Connect to RabbitMQ broker. Save the callback method to be invoked after connection
        steps are completed.
        :param callback:
        :return:
        """
        self._connect_callback = connection_callback
        self._connect_error_callback = connection_error_callback
        self.open_connection(type=self._type)

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
        :param props: message properties containing VIP info such as
                      [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS,]
        :param body: message body
        :return:
        """
        #content_type = None, content_encoding = None, headers = None, delivery_mode = None, \
        #priority = None, correlation_id = None, reply_to = None, expiration = None, message_id = None, \
        #timestamp = None, type = None, user_id = None, app_id = None, cluster_id = None
        #_log.debug("*************{}*****************************".format(self._identity))
        #_log.debug("Channel {0}, Props {1}, body {2}".format(channel, props, body))
        app_id = str(props.app_id)
        platform, peer = app_id.split(".", 1)

        msg = Message()
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
         Handle unroutable messages. Send error message back to sender.
         Ignore if subsystem is pubsub.
        :param channel: channel object
        :param method: method frame - contains routing key
        :param props: message properties containing VIP info such as
                      [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS,]
        :param body: message body
        :return:
        """
        #Ignore if message type is 'pubsub'
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
        Send the VIP message over rabbitmq message bus. Reformats the VIP message object into Pika
        message object.
        :param message: VIP message object
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
            self._connection.ioloop.start()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as exc:
            _log.error("RabbitMQ Connection Error. {}".format(exc))

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
