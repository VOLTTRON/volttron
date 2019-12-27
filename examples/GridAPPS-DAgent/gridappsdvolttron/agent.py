"""
Agent documentation goes here.
"""
from volttron.platform.agent.utils import get_aware_utc_now

__docformat__ = 'reStructuredText'

import datetime
import logging
import sys

import gevent
from gridappsd import GridAPPSD

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def gridappsdvolttron(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Gridappsdvolttron
    :rtype: GridAPPSDVolttron
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    return GridAPPSDVolttron(**kwargs)


class GridAPPSDVolttron(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, setting1=1, setting2="some/random/topic",
                 **kwargs):
        super(GridAPPSDVolttron, self).__init__(**kwargs)
        self._gapps = GridAPPSD(override_threading=gevent.spawn)
        self._publish_event = None

    def publish_next(self):
        if self._publish_event is not None:
            self._publish_event.cancel()
        if self._gapps.connected:
            self._gapps.send("/queue/test", "foo bar")
        else:
            print("Not connected")
        now = get_aware_utc_now()
        print(utils.get_utc_seconds_from_epoch(now))
        next_update_time = now + datetime.timedelta(seconds=5)
        self._publish_event = self.core.schedule(next_update_time, self.publish_next)
        gevent.sleep(0.1)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):

        def message_published(headers, body):
            self.vip.pubsub.publish('pubsub', "data/foo", headers=headers, message=body)
        self._gapps.subscribe('/queue/test', message_published)
        gevent.sleep(0.1)
        self.publish_next()

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        print("Stopping data!")

        # self._gapps.disconnect()
        print("After disconnect")


def main():
    """Main method called to start the agent."""
    utils.vip_main(gridappsdvolttron, identity="gridappsd",
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
