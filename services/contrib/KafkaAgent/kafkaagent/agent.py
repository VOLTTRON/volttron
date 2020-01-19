import datetime
import logging
import os
import sys
import datetime
from dateutil.parser import parse
import multiprocessing
import ast
import random

# kafka
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from volttron.platform.vip.agent import Agent, Core, PubSub
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.1"


def kafka_agent(config_path, **kwargs):
    '''
        Function: Return KafkaAgent object with configuration information

        Args: Same with Class Args

        Returns: KafkaAgent object

        Note: None

        Created: SungonLee, 2017-10-20
        Deleted: .
    '''
    # get config information
    config = utils.load_config(config_path)
    services_topic_list = config.get('services_topic_list')
    kafka_broker_ip = config.get('kafka_broker_ip')
    kafka_broker_port = config.get('kafka_broker_port')
    kafka_producer_topic = config.get('kafka_producer_topic')
    kafka_consumer_topic = config.get('kafka_consumer_topic')

    if 'all' in services_topic_list:
        services_topic_list = [topics.DRIVER_TOPIC_BASE, topics.LOGGER_BASE,
                            topics.ACTUATOR, topics.ANALYSIS_TOPIC_BASE]

    return KafkaAgent(services_topic_list,
                      kafka_broker_ip,
                      kafka_broker_port,
                      kafka_producer_topic,
                      kafka_consumer_topic,
                      **kwargs)

class KafkaAgent(Agent):
    '''
    ----------------------------------------------------------------------------
    Agent summary
    ----------------------------------------------------------------------------
        Name: KafkaAgent

        Version: 0.1

        Function:
            1. Subscribe message from message bus
            2. Send message to broker(Kafka consumer)
            3. Receive message from broker(Kafka producer)
            4. Publish data to message bus(test for message)

        Args:
            services_topic_list (list): Topic for subscribing from MessageBus
            kafka_broker_ip (str): Kafka Broker ip
            kafka_broker_port (str): Kafka Broker port
            kafka_producer_topic (str): Topic for messaging from kafka broker to VOLTTRON
            kafka_consumer_topic (str): Topic for messaging from VOLTTRON to Cloud

        Returns:
            None

        Note:
            Version 0.1: Add - Function 1, 2, 3, 4
    '''

    '''
    History
    =====
    Create '__init__' (by SungonLee, 2017-10-20)
    Create 'post_data' (by SungonLee, 2017-10-20)
    Create 'on_message_topic' (by SungonLee, 2017-10-20)
    Create 'subscriber' (by SungonLee, 2017-10-20)
    Create 'actuate_something' (by SungonLee, 2017-10-20)
    Create 'publish_command' (by SungonLee, 2017-10-20)
    '''

    def __init__(self,
                 services_topic_list,
                 kafka_broker_ip,
                 kafka_broker_port,
                 kafka_producer_topic,
                 kafka_consumer_topic,
                 **kwargs):
        '''
            Function:
                1. initiallizing the configuration information
                2. Create Connection with Kafka Consumer, Kafka Producer

            Args: Same with Class Args

            Returns: None

            Note:
                self.consumer: connection with kafka consumer
                self.producer: connection with kafka producer

            Created: SungonLee, 2017-10-20
            Deleted: .
        '''
        super(KafkaAgent, self).__init__(**kwargs)

        # set config info
        self.services_topic_list = services_topic_list
        self.kafka_broker_ip = kafka_broker_ip
        self.kafka_broker_port = kafka_broker_port
        self.kafka_producer_topic = kafka_producer_topic
        self.kafka_consumer_topic = kafka_consumer_topic

        self.default_config = {"services_topic_list": services_topic_list,
                               "kafka_broker_ip": kafka_broker_ip,
                               "kafka_broker_port": kafka_broker_port,
                               "kafka_producer_topic": kafka_producer_topic,
                               "kafka_consumer_topic": kafka_consumer_topic
                               }

        _log.info('default_config: {}'.format(self.default_config))

        self.vip.config.set_default("config", self.default_config)

        # setting up callback_method for configuration store interface
        self.vip.config.subscribe(self.configure_new, actions="NEW", pattern="kafka/*")
        self.vip.config.subscribe(self.configure_update, actions=["UPDATE",], pattern="kafka/*")
        self.vip.config.subscribe(self.configure_delete, actions=["DELETE",], pattern="kafka/*")

        self.new_value_ = 0

        # kafka
        self.kafka_producer_addr = '{0}:{1}'.format(self.kafka_broker_ip, self.kafka_broker_port)
        self.consumer = KafkaConsumer(bootstrap_servers=[self.kafka_producer_addr])
        self.consumer.subscribe([self.kafka_producer_topic])

        # kafak producer - command volttron to kafka broker
        # produce json messages
        self.kafka_consumer_addr = '{0}:{1}'.format(self.kafka_broker_ip, self.kafka_broker_port)
        self.producer = KafkaProducer(bootstrap_servers=[self.kafka_consumer_addr],
                        value_serializer=lambda v: jsonapi.dumps(v).encode('utf-8')
                         )

    # configuration callbacks
    # lnke : http://volttron.readthedocs.io/en/4.0.1/devguides/agent_development/Agent-Configuration-Store.html
    # Ensure that we use default values from anything missing in the configuration
    def configure_new(self, config_name, action, contents):
        _log.debug("configure_new")
        config = self.default_config.copy()
        config.update(contents)

    # update cloud agent config
    def configure_update(self, config_name, action, contents):
        _log.debug("configure_update")

    # delete cloud agent config
    def configure_delete(self, config_name, action, contents):
        _log.debug("configure_delete")

    def send_to_broker(self, peer, sender, bus, topic, headers, message):
        '''
            Function:
                Send Command to Cloud.
                Send Command history to Cloud(MongoDB).

            Args:
                peer: the ZMQ identity of the bus owner sender is identity of the publishing peer
                sender:
                bus:
                topic: the full message topic
                headers: case-insensitive dictionary (mapping) of message headers
                message: possibly empty list of message parts

            Returns: None

            Note:
                Callback method for subscribing.
                Subscribe message topic: 'command-to-cloud' send command to cloud,
                                         producer(KafkaAgent)-> kafka broker(Cloud) -> consumer(Cloud)

            Created: SungonLee, 2017-10-20
            Deleted: .
        '''
        try:
            msg = {
                'message_sender': sender,
                'kafka_message_sender': 'KafkaAgent',
                'description': 'message from VOLTTRON to KafkaBroker',
                'message': message
                }
            # Send command to Consumer(in Cloud)
            self.producer.send(self.kafka_consumer_topic, msg)

        except Exception as e:
            _log.error('Send_to_broker: {}'.format(e))

    @Core.receiver("onstart")
    def on_message_topic(self, sender, **kwargs):
        '''
            Function: Resister callback method for sending data to Kafka Broker.

            Args: .

            Returns: None

            Note:
                This method is executed after '__init__' method.
                Subscribes to the platform message bus on the actuator, record, datalogger, and device topics.

            Created: SungonLee, 2017-10-20
            Deleted: .
        '''
        _log.debug("sender {}, Kwargs {}".format(sender, kwargs))

        # Define method for resistering callback method
        def subscriber(subscription, callback_method):
            '''
                Args:
                    subscription: topic (e.g. "devices/fake-campus/fake-building/fake-device/PowerState")
                    callback_method: method resistered

                Note:
                    callback_mothod: 'post_data', 'send_to_broker'
            '''
            _log.debug("Subscribing to topic : {}".format(subscription))
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=subscription,
                                      callback=callback_method)

        # Resister callback method with 'subscriber'
        for topic_subscriptions in self.services_topic_list:
            subscriber(topic_subscriptions, self.send_to_broker)

    @Core.periodic(1)
    def receive_from_broker(self):
        '''
            Function: Receive message from Kafka broker and Publish message to MessageBus.
            Args: None
            Returns: None
            Note: None
            Created: SungonLee, 2017-10-20
            Deleted: .
        '''
        # partition type : nametuple
        # if timeout_ms is 0, check that is there any message in broker imm
        partition = self.consumer.poll(timeout_ms=0, max_records=None)

        try:
            if len(partition) > 0:
                for p in partition:
                    for response in partition[p]:
                        # _log.info('Receive_from_broker: {}'.format(response))
                        # convert string to dictionary
                        response_dict = ast.literal_eval(response.value)
                        # _log.info('Receive_from_broker: Receive message from kafka broker message: {}'.format(response_dict))
                        topic = response.topic
                        # sender = response_dict['sender']
                        headers = {
                            'date': str(datetime.datetime.now())
                            }
                        message = {
                            # 'kafka_message_sender': sender,
                            # 'kafka_message_receiver':'KafkaAgent',
                            'message': response_dict
                            }

                        self.vip.pubsub.publish('pubsub', topic, headers, message)
            else:
                pass
                # _log.info('Receive_from_broker: No receive message from kafka broker')

        except Exception as e:
            _log.error('Receive_from_broker: {}'.format(e))

def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(kafka_agent, identity='KafkaAgent',
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
