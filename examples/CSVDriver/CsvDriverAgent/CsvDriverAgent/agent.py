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

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def CsvDriverAgent(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Csvdriveragent
    :rtype: Csvdriveragent
    """
    _log.debug("Config path: {}".format(config_path))
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")
    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)
    return Csvdriveragent(**kwargs)


class Csvdriveragent(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, csv_topic="", **kwargs):
        super(Csvdriveragent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.agent_id = "csv_actuation_agent"
        self.csv_topic = csv_topic

        self.value = 0
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
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")
        _log.debug(config)

        self.csv_topic = config.get("csv_topic", "")

        # Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="devices/" + self.csv_topic + "/all",
                                  callback=self._handle_publish)

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
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
        self.core.periodic(30, self.actuate_point)

    def actuate_point(self):
        _now = get_aware_utc_now()
        str_now = format_timestamp(_now)
        _end = _now + td(seconds=10)
        str_end = format_timestamp(_end)
        schedule_request = [[self.csv_topic, str_now, str_end]]
        result = self.vip.rpc.call(
            'platform.actuator', 'request_new_schedule', self.agent_id, 'my_test', 'HIGH', schedule_request).get(
            timeout=4)
        point_topic = self.csv_topic + "/" + "test1"
        result = self.vip.rpc.call(
            'platform.actuator', 'set_point', self.agent_id, point_topic, self.value).get(
            timeout=4)
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
