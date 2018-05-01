"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.messaging import headers
from volttron.platform.vip.agent import Agent
from datetime import datetime, timedelta

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def data_cleaner(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: DataCleaner
    :rtype: DataCleaner
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    period = int(config.get('period', 300))
    points = config.get('points', {})

    return DataCleaner(period,
                       points,
                       **kwargs)


class DataCleaner(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, period=300, points={},
                 **kwargs):
        super(DataCleaner, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.period = period
        self.points = points

        self.periodic = None

        self.default_config = {"period": period,
                               "points": points}


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
            period = int(config["period"])
            points = config["points"]
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        self.period = period
        self.points = points

        if self.periodic is not None:
            self.periodic.kill()

        self.periodic = self.core.periodic(self.period, self.process_points)

    def process_points(self):
        now = utils.get_aware_utc_now()
        for topic, settings in self.points.iteritems():
            self.process_point(now, topic, **settings)

    def process_point(self, now, topic, min_value=None, max_value=None, output_topic=None,
                      aggregate_method=None):
        _log.debug("Processing topic: {}".format(topic))

        if output_topic is None:
            _log.error("No output topic for {}".format(topic))
            return

        # Query the data from the historian
        results = self.vip.rpc.call("platform.historian", "query", topic, "now -1d").get(timeout=5.0)

        values = results["values"]
        if not values:
            _log.error("No values for {}".format(topic))
            return

        last_timestamp, value = values[-1]
        last_timestamp = utils.parse_timestamp_string(last_timestamp)

        if now - last_timestamp > timedelta(seconds=self.period):
            _log.warning("Data used for {} is stale".format(topic))
            if aggregate_method == "avg":
                results = self.vip.rpc.call("platform.historian", "query", topic, "now -30d").get(timeout=5.0)
                values = results["values"]
                average = sum(x[1] for x in values)
                average /= len(values)
                value = average
            # Do something here to fake a better value.

        # Make sure the value is within bounds.
        if min_value is not None:
            value = max(min_value, value)

        if max_value is not None:
            value = min(max_value, value)

        #Publish the result.
        self.vip.pubsub.publish("pubsub", output_topic,
                            headers={headers.TIMESTAMP: utils.format_timestamp(now), "source": topic},
                            message=value)


def main():
    """Main method called to start the agent."""
    utils.vip_main(data_cleaner, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
