"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from datetime import timedelta as td, datetime as dt
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

# Set up logging for the agent - this allows us to write to the volttron logging file
_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def CsvDriverAgent(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: String path to the agent's configuration in the Volttron config store
    :returns: Csvdriveragent instance
    :rtype: Csvdriveragent
    """
    # Load the configuration into keyword arguments to be used by the agent, creating an empty configuration if
    # parsing goes wrong
    _log.debug("Config path: {}".format(config_path))
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    if not config:
        _log.info("Using Agent defaults for starting configuration.")
    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)
    # Create an instance of the agent
    return Csvdriveragent(**kwargs)


class Csvdriveragent(Agent):
    """
    Agent used to test the functionality of the CSV driver
    """

    def __init__(self, csv_topic="", **kwargs):
        # Configure the base agent
        super(Csvdriveragent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        # This agent is for testing purposes, so we'll default our ID
        self.agent_id = "csv_actuation_agent"
        # Get the topic that the Driver will publish to from the configuration file
        self.csv_topic = csv_topic

        # This value will be used to send requests to the Driver to set a point on the device with an alternating value
        self.value = 0
        # Our default configuration will be from the values we initially are configured with
        self.default_config = {
            "csv_topic": self.csv_topic
        }

        # Set a default configuration to ensure that self.configure is called immediately to setup
        # the agent.
        self.vip.config.set_default("config", self.default_config)

        # Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a configuration exists at startup
        this will be called before onstart.

        Is called every time the configuration in the store changes.
        """
        # Copy the default configuration, and change any values which are specified in the new agent configuration
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")
        _log.debug(config)

        # set the new configuration topic value
        self.csv_topic = config.get("csv_topic", "")

        # Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        # then subscribe to "all" publishes for the CSV device on the message bus
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="devices/" + self.csv_topic + "/all",
                                  callback=self._handle_publish)

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
        """
        When we recieve an update from our all publish subscription, log something so we can see that we are
        successfully scraping CSV points with the Master Driver
        :param peer: unused
        :param sender: unused
        :param bus: unused
        :param topic: unused
        :param headers: unused
        :param message: "All" messaged published by the Master Driver for the CSV Driver containing values for all
        registers on the device
        """
        # Just write something to the logs so that we can see our success
        _log.info("Device {} Publish: {}".format(self.csv_topic, message))

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """
        # Every 30 seconds, ask the core agent loop to run the actuate point method with no parameters
        self.core.periodic(30, self.actuate_point)

    def actuate_point(self):
        """
        Request that the Actuator set a point on the CSV device
        """
        # Create a start and end timestep to serve as the times we reserve to communicate with the CSV Device
        _now = get_aware_utc_now()
        str_now = format_timestamp(_now)
        _end = _now + td(seconds=10)
        str_end = format_timestamp(_end)
        # Wrap the timestamps and device topic (used by the Actuator to identify the device) into an actuator request
        schedule_request = [[self.csv_topic, str_now, str_end]]
        # Use a remote procedure call to ask the actuator to schedule us some time on the device
        result = self.vip.rpc.call(
            'platform.actuator', 'request_new_schedule', self.agent_id, 'my_test', 'HIGH', schedule_request).get(
            timeout=4)
        # This topic allows us to set a specific point on the device using the actuator
        point_topic = self.csv_topic + "/" + "test1"
        # Now use another RPC call to ask the actuator to set the point during the scheduled time
        result = self.vip.rpc.call(
            'platform.actuator', 'set_point', self.agent_id, point_topic, self.value).get(
            timeout=4)
        # Alternate the value we want to set for future calls to this method
        self.value = 0 if self.value is 1 else 1

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(CsvDriverAgent,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
