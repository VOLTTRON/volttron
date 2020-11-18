# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

from datetime import datetime
import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.scheduling import periodic
from volttron.platform.vip.agent.errors import VIPError

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"
DEFAULT_HEARTBEAT_PERIOD = 5
DEFAULT_TOPIC = 'default/foobar'
DEFAULT_MESSAGE = 'MALICIOUS HEARTBEAT'


def malicious_agent(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: MaliciousAgent
    :rtype: MaliciousAgent
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
        _log.debug(f"Agent configuration for Malicious Agent was empty: {config}")

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    # Agent defaults defined below via 'get' function
    topic = config.get('topic', DEFAULT_TOPIC)
    heartbeat = config.get('heartbeat_period', DEFAULT_HEARTBEAT_PERIOD)
    heartbeat_message = config.get('message', DEFAULT_MESSAGE)
    return MaliciousAgent(topic, heartbeat, heartbeat_message, **kwargs)


class MaliciousAgent(Agent):
    """
    A simple agent that tries to publish to a protected topic on a volttron platform that is "secure"
    """

    def __init__(self, topic, heartbeat_period, heartbeat_message, **kwargs):
        super(MaliciousAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.topic = topic
        self._heartbeat_period = heartbeat_period
        self._heartbeat_message = heartbeat_message
        self.default_config = {"topic": self.topic,
                               "heartbeat_period": self._heartbeat_period,
                               "heartbeat_message": self._heartbeat_message}

        _log.debug(f"Default config for Malicious Agent: {self.default_config}")

        #Set a default configuration to ensure that self.configure is called immediately to setup
        #the agent.
        self.vip.config.set_default("config", self.default_config)
        #Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a configuration exists at startup
        this will be called before onstart.

        Is called every time the configuration in the store changes.
        """
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")

        try:
            topic = config["topic"]
            heartbeat_period = config['heartbeat_period']
            heartbeat_message = config['heartbeat_message']
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        self.topic = topic
        self._heartbeat_period = heartbeat_period
        self._heartbeat_message = heartbeat_message
        self._create_subscriptions(self.topic)

    def _create_subscriptions(self, topic):
        #Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)

        _log.info(f"Successfully subscribed to topic: {topic}")

    def _handle_publish(self, peer, sender, bus, topic, headers,
                                message):
        pass

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """
        _log.info("******************Malicious agent has been started******************")
        # _log.debug("VERSION IS: {}".format(self.core.version()))
        # if self._heartbeat_period != 0:
        #     _log.debug(f"Heartbeat starting for {self.core.identity}, published every {self._heartbeat_period}s")
            # self.vip.heartbeat.start_with_period(self._heartbeat_period)
            # self.vip.health.set_status(STATUS_GOOD, self._heartbeat_message)
        # query = Query(self.core)
        # _log.info('query: %r', query.query('serverkey').get())

        #Example RPC call
        #self.vip.rpc.call("some_agent", "some_method", arg1, arg2)

    @Core.schedule(periodic(10))
    def publish_msg(self):
        # message can be either a "simple" message or a "data" message
        # A "simple" message is a simple plain text message
        # A "data" message contains an array of 2 elements.  The first element
        #     contains a dictionary of (point name: value) pairs.  The second element
        #     contains context around the point data and the "Date" header.
        # Example of "data" message: [ {'EKG': 0.42424242, ....},
        #           {'EKG': {'type': 'integer', 'tz': 'US/Pacific', 'units': 'waveform'} } ]

        message = f"**********MALICIOUS AGENT HAS PUBLISHED THIS MESSAGE TO {self.topic}**********"
        now = utils.format_timestamp(datetime.utcnow())
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        try:
            _log.info(f"MaliciousAgent attempting to publish to topic: {self.topic}")
            self.vip.pubsub.publish('pubsub', self.topic, headers=headers, message=message)
        except VIPError as ex:
            _log.debug("MaliciousAgent failed to publish " + self.topic + ": " + str(ex))

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        _log.info("******************Malicious Agent shutting down******************")

    @RPC.export
    def rpc_method(self, arg1, arg2, kwarg1=None, kwarg2=None):
        """
        RPC method

        May be called from another agent via self.core.rpc.call """
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(malicious_agent,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
