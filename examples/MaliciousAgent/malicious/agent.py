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

__docformat__ = "reStructuredText"

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
DEFAULT_TOPIC = "default/foobar"
DEFAULT_POINT_NAME = "SampleWritableLong1"
DEFAULT_POINT_VALUE = 66
DEFAULT_DRIVER_VIP_IDENTITY = "MALICIOUS_platform.driver"
DEFAULT_HEARTBEAT_PERIOD = 5

DEFAULT_HEARTBEAT_MESSAGE = "MALICIOUS HEARTBEAT"


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

    if not config:
        _log.info(
            "No configuration given for MaliciousAgent. Using MaliciousAgent configuration defaults."
        )

    # Get all configuration for MaliciousAgent; use defaults if necessary
    topic = config.get("topic", DEFAULT_TOPIC)
    point_name = config.get("point_name", DEFAULT_POINT_NAME)
    point_value = config.get("point_value", DEFAULT_POINT_VALUE)
    driver_vip_identity = config.get("driver_vip_identity", DEFAULT_DRIVER_VIP_IDENTITY)

    return MaliciousAgent(topic, point_name, point_value, driver_vip_identity, **kwargs)


class MaliciousAgent(Agent):
    """
    A Malicious agent that tries but fails to do two illegal actions on a "secure" volttron platform:
     1) publish to a protected topic on the volttron message bus
     2) set a point to a device via the volttron platform driver
    """

    def __init__(self, topic, point_name, point_value, driver_vip_identity, **kwargs):
        super(MaliciousAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.topic = topic
        self.point_name = point_name
        self.point_value = point_value
        self.driver_vip_identity = driver_vip_identity
        self._heartbeat_period = DEFAULT_HEARTBEAT_PERIOD
        self._heartbeat_message = DEFAULT_HEARTBEAT_MESSAGE
        self.default_config = {
            "topic": self.topic,
            "point_name": self.point_name,
            "point_value": self.point_value,
            "driver_vip_identity": self.driver_vip_identity,
            "heartbeat_period": self._heartbeat_period,
            "heartbeat_message": self._heartbeat_message,
        }

        _log.debug(f"Default config for Malicious Agent: {self.default_config}")

        # Set a default configuration to ensure that self.configure is called immediately to setup
        # the agent.
        self.vip.config.set_default("config", self.default_config)
        # Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(
            self.configure, actions=["NEW", "UPDATE"], pattern="config"
        )

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
            point_name = config["point_name"]
            point_value = config["point_value"]
            driver_vip_identity = config["driver_vip_identity"]
            heartbeat_period = config["heartbeat_period"]
            heartbeat_message = config["heartbeat_message"]
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        self.topic = topic
        self.point_name = point_name
        self.point_value = point_value
        self.driver_vip_identity = driver_vip_identity
        self._heartbeat_period = heartbeat_period
        self._heartbeat_message = heartbeat_message
        self._create_subscriptions(self.topic)

    def _create_subscriptions(self, topic):
        # Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(
            peer="pubsub", prefix=topic, callback=self._handle_publish
        )

        _log.info(f"Successfully subscribed to topic: {topic}")

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
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
        _log.info(
            "******************Malicious agent has been started******************"
        )
        # _log.debug("VERSION IS: {}".format(self.core.version()))
        # if self._heartbeat_period != 0:
        #     _log.debug(f"Heartbeat starting for {self.core.identity}, published every {self._heartbeat_period}s")
        # self.vip.heartbeat.start_with_period(self._heartbeat_period)
        # self.vip.health.set_status(STATUS_GOOD, self._heartbeat_message)
        # query = Query(self.core)
        # _log.info('query: %r', query.query('serverkey').get())

    @Core.schedule(periodic(10))
    def execute_illegal_actions(self):
        self.publish_msg()
        self.set_point_on_device()

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
            headers_mod.TIMESTAMP: now,
        }
        try:
            _log.info(f"MaliciousAgent attempting to publish to topic: {self.topic}")
            res = self.vip.pubsub.publish(
                "pubsub", self.topic + "/all", headers=headers, message=message
            ).get(timeout=2)
            _log.debug(
                f"ERROR: MaliciousAgent illegally published to a protected topic. {res}"
            )
        except VIPError as ex:
            _log.info("MaliciousAgent failed to publish " + self.topic + ": " + str(ex))

    @RPC.export
    def set_point_on_device(self):
        """
        RPC method
        Attempts to set point on a device via PlatformDriver
        """
        topic = self.topic.strip("/")
        if topic.startswith("devices"):
            topic_parts = topic.split("/")
            topic = "".join(topic_parts[1:])

        _log.debug(
            f"INPUTS: topic: {topic},  point_name: {self.point_name}, value: {self.point_value}"
        )
        try:
            res = self.vip.rpc.call(
                self.driver_vip_identity,
                "set_point",
                topic,
                self.point_name,
                self.point_value,
            ).get()
            _log.debug(
                f"ERROR: MaliciousAgent illegally set a point on a device. {res}"
            )
        except Exception as e:
            _log.info(f"*****MaliciousAgent tried to set_point on a device: {e}")

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        _log.info("******************Malicious Agent shutting down******************")


def main():
    """Main method called to start the agent."""
    utils.vip_main(malicious_agent, version=__version__)


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
