"""
Agent documentation goes here.
"""
from volttron.platform.agent.utils import get_aware_utc_now

__docformat__ = 'reStructuredText'

import datetime
import logging
import sys

import gevent.threading
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
        self._gapps = None
        self._publish_event = None
        self._test_topic = "/topic/data"
        self._receiver_thread = None

    def receiver_thread(self, arg):
        self._receiver_thread = gevent.threading.Thread(group=None, target=arg)
        self._receiver_thread.daemon = True  # Don't let thread prevent termination
        self._receiver_thread.start()
        return self._receiver_thread

    def publish_next(self):
        _log.debug("Publishing next")
        if self._publish_event is not None:
            self._publish_event.cancel()
        self._gapps.send(self._test_topic, "foo bar")
        if self._gapps.connected:
            self._gapps.send("/queue/test", "foo bar")
        else:
            print("Not connected")
        now = get_aware_utc_now()
        print(utils.get_utc_seconds_from_epoch(now))
        next_update_time = now + datetime.timedelta(seconds=5)
        _log.debug(f'Scheduling nex time {next_update_time}')
        self._publish_event = self.core.schedule(next_update_time, self.publish_next)
        _log.debug(f'After scheduling next time {next_update_time}')
        gevent.sleep(0.1)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self._gapps = GridAPPSD(override_threading=self.receiver_thread)
                                # goss_log_level=logging.DEBUG)
                                # stomp_log_level=logging.DEBUG)

        def message_published(headers, body):
            _log.debug(f"Received from gridappsd {headers}, body: {body}")
            self.vip.pubsub.publish('pubsub', "data/foo", headers=headers, message=body)
        self._gapps.subscribe(self._test_topic, message_published)
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
