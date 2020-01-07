"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import gevent
import logging
import random
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent.base_simulation_integration import helics_integration

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def helics_example(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: HelicsExample
    :rtype: HelicsExample
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    _log.debug("CONFIG: {}".format(config))
    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    return HelicsExample(config, **kwargs)


class HelicsExample(Agent):
    """
    HelicsExampleAgent demonstrates how a VOLTTRON agent can interact with HELICS simulation environment
    """

    def __init__(self, config, **kwargs):
        super(HelicsExample, self).__init__(enable_store=False, **kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.config = config
        self.helics_sim = helics_integration.HELICSSimIntegration(config)
        self._federate_name = config.get('name', self.core.identity)
        self.volttron_subscriptions = config.get('volttron_subscriptions', None)
        self.volttron_messages = None
        self.endpoints = config.get('endpoints', None)
        self.publications = config.get('publications', None)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """

        """
        # subscribe to the volttron topics if given.
        if self.volttron_subscriptions is not None:
            for sub in self.volttron_subscriptions:
                _log.info('Subscribing to {}'.format(sub))
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=sub,
                                          callback=self.on_receive_publisher_message)

        if self.publications is not None:
            for pub in self.publications:
                volttron_topic = pub.get('volttron_topic', None)
                if volttron_topic is not None:
                    if self.volttron_messages is None:
                        self.volttron_messages = dict()
                    _log.info('Subscribing to {}'.format(volttron_topic))
                    self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=volttron_topic,
                                          callback=self.on_receive_volttron_message)
                    self.volttron_messages[volttron_topic] = dict(pub_key=pub['key'],
                                                                  value=None,
                                                                  received=False)
                                          
        # Exit if HELICS isn't installed in the current environment.
        if not self.helics_sim.is_sim_installed():
            _log.error("HELICS module is unavailable please add it to the python environment.")
            self.core.stop()
            return

        try:
            self.helics_sim.register_inputs(self.config, self.do_work)
            self.helics_sim.start_simulation()
        except ValueError as ex:
            _log.error(ex)
            self.core.stop()
            return

    def do_work(self):
        """
        Perform application specific work here using HELICS messages
        :return:
        """
        current_values = self.helics_sim.current_values
        _log.debug("Doing work: {}".format(self.core.identity))
        _log.debug("Current set of values from HELICS: {}".format(current_values))
        # Do something with HELICS messages

        # Send messages to endpoints as well
        # for endpoint in self.endpoints:
        #     val = '200000 + 0 j'
        #     status = self.helics_sim.send_to_endpoint(endpoint['name'], endpoint['destination'], val)

        # value = {}
        # # Check if the VOLTTRON agents update the information
        # if self.volttron_messages is not None:
        #     topics_ready = all([v['received'] for k, v in self.volttron_messages.items()])
        #     while not topics_ready:
        #         gevent.sleep(0.2)
        #         topics_ready = all([v['received'] for k, v in self.volttron_messages.items()])
        #     for k, v in self.received_volttron.items():
        #         self.received_volttron[k] = False
        #
        #     for topic, msg in self.volttron_messages:
        #         key = msg['pub_key']
        #         value = msg['value']
        #         self.helics_sim.publish_to_simulation(key, value)
        #         _log.debug("Published New value : {} to HELICS key: {}".format(value))
        _log.debug("MAKING NEXT TIMEREQUEST")
        self.helics_sim.make_time_request()
        
    def on_receive_publisher_message(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe to publisher publications and change the data accordingly 
        """                 
        # Update controller data 
        val = message[0]
        # Do something with message

    def on_receive_volttron_message(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe to publisher publications and change the data accordingly
        """
        # Update controller data
        val = message[0]
        self.volttron_messages[topic]['value'] = val
        self.volttron_messages[topic]['received'] = True

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(helics_example, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
