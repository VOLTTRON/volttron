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


__docformat__ = 'reStructuredText'

import gevent
import logging
import random
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from integrations.helics_integration import HELICSSimIntegration


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
    HelicsExampleAgent demonstrates how VOLTTRON agent can interact with HELICS simulation environment
    """

    def __init__(self, config, **kwargs):
        super(HelicsExample, self).__init__(enable_store=False, **kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.config = config
        self.helics_sim = HELICSSimIntegration(config, self.vip.pubsub)
        try:
            self._federate_name = config['properties']['name']
        except KeyError:
            self._federate_name = self.core.identity
        self.volttron_subscriptions = config.get('volttron_subscriptions', None)
        _log.debug("volttron subscriptions: {}".format(self.volttron_subscriptions))
        self.volttron_messages = None
        self.endpoints = config.get('endpoints', None)
        self.publications = config.get('inputs', None)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        Subscribe to VOLTTRON topics on VOLTTRON message bus.
        Register config parameters with HELICS.
        Start HELICS simulation.
        """
        # subscribe to the VOLTTRON topics if given.
        if self.volttron_subscriptions is not None:
            for sub in self.volttron_subscriptions:
                _log.info('Subscribing to {}'.format(sub))
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=sub,
                                          callback=self.on_receive_publisher_message)

        # Subscribe to VOLTTRON topic to be republished on HELICS bus if needed
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
                    self.volttron_messages[volttron_topic] = dict(pub_key=pub['sim_topic'],
                                                                  value=None,
                                                                  global_flag=pub.get('global', False),
                                                                  received=False)

        # Exit if HELICS isn't installed in the current environment.
        if not self.helics_sim.is_sim_installed():
            _log.error("HELICS module is unavailable please add it to the python environment.")
            self.core.stop()
            return

        # Register inputs with HELICS and start simulation
        try:
            self.helics_sim.register_inputs(self.config, self.do_work)
            self.helics_sim.start_simulation()
        except ValueError as ex:
            _log.error("Unable to register inputs with HELICS: {}".format(ex))
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
        for endpoint in self.endpoints:
            val = '200000 + 0 j'
            status = self.helics_sim.send_to_endpoint(endpoint['name'], endpoint['destination'], val)
        _log.debug("******publications: {}".format(self.publications))
        for pub in self.publications:
            key = pub['sim_topic']
            # Check if VOLTTRON topic has been configured. If no, publish dummy value for the HELICS
            # publication key
            volttron_topic = pub.get('volttron_topic', None)
            if volttron_topic is None:
                value = 90.5
                global_flag = pub.get('global', False)
                # If global flag is False, prepend federate name to the key
                if not global_flag:
                    key = "{fed}/{key}".format(fed=self._federate_name, key=key)
                    value = 67.90
                self.helics_sim.publish_to_simulation(key, value)

        value = {}
        # Check if the VOLTTRON agents update the information
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
        #         if not msg['global_flag']:
        #             key = "{fed}/{key}".format(fed=self._federate_name, key=key)
        #         value = msg['value']
        #         self.helics_sim.publish_to_simulation(key, value)
        #         _log.debug("Published New value : {} to HELICS key: {}".format(value))

        # Request HELICS to advance timestep
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
        _log.debug("Received volttron topic: {}, value: {}".format(topic, message))
        # Update controller data
        val = message
        self.volttron_messages[topic]['value'] = val
        self.volttron_messages[topic]['received'] = True

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it
        disconnects from the message bus.
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
