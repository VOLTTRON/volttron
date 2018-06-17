"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

from datetime import datetime
import gevent
import logging
import random
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def fncs_example(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: FncsExample
    :rtype: FncsExample
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    if not config.get("topic_mapping"):
        raise ValueError("Configuration must have a topic_mapping entry.")

    topic_mapping = config.get("topic_mapping")
    federate = config.get("federate_name")
    broker_location = config.get("broker_location", "tcp://localhost:5570")
    time_delta = config.get("time_delta", "1s")
    sim_length = config.get("sim_length", "60s")
    stop_agent_when_sim_complete = config.get("stop_agent_when_sim_complete", False)
    return FncsExample(topic_mapping=topic_mapping, federate_name=federate, broker_location=broker_location,
                       time_delta=time_delta, sim_length=sim_length,
                       stop_agent_when_sim_complete=stop_agent_when_sim_complete, **kwargs)


class FncsExample(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, topic_mapping, federate_name=None, broker_location="tcp://localhost:5570",
                 time_delta="1s", simulation_start_time=None, sim_length="10s", stop_agent_when_sim_complete=False,
                 **kwargs):
        super(FncsExample, self).__init__(enable_fncs=True, enable_store=False, **kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self._federate_name = federate_name
        if self._federate_name is None:
            self._federate_name = self.core.identity

        if not broker_location:
            raise ValueError("Invalid broker location specified.")
        self._broker_location = broker_location
        self._time_delta = time_delta
        self._topic_mapping = topic_mapping
        self._sim_start_time = simulation_start_time
        if self._sim_start_time is None:
            self._sim_start_time = datetime.now()

        self._sim_length = sim_length
        self._stop_agent_when_complete = stop_agent_when_sim_complete

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """

        """
        # Exit if fncs isn't installed in the current environment.
        if not self.vip.fncs.fncs_installed:
            _log.error("fncs module is unavailable please add it to the python environment.")
            self.core.stop()
            return

        try:

            self.vip.fncs.initialize(topic_maping=self._topic_mapping, federate_name=self._federate_name,
                                     time_delta=self._time_delta, sim_start_time=self._sim_start_time,
                                     sim_length=self._sim_length, work_callback=self.do_work,
                                     stop_agent_when_sim_complete=self._stop_agent_when_complete)
            self.vip.fncs.start_simulation()

        except ValueError as ex:
            _log.error(ex.message)
            self.core.stop()
            return

    def do_work(self):
        current_values = self.vip.fncs.current_values
        _log.debug("Doing work: {}".format(self.core.identity))
        _log.debug("Current values: {}".format(self.vip.fncs.getvalues()))
        value = str(random.randint(0, 10))
        _log.debug("Value is: {}".format(value))
        # Must publish to the fncs_topic here.
        self.vip.fncs.publish("devices/abcd", str(value))
        self.vip.fncs.next_timestep()

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        self.vip.fncs.reset()


def main():
    """Main method called to start the agent."""
    utils.vip_main(fncs_example, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
