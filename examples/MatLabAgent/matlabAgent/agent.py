"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC, PubSub
from pprint import pformat

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class Matlabagent(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, config_path, **kwargs):
        super(Matlabagent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        _log.debug("vip_identity: " + self.core.identity)
        
        log_level = self.config.get('log-level', 'INFO')
        if log_level == 'ERROR':
            self._logfn = _log.error
        elif log_level == 'WARN':
            self._logfn = _log.warn
        elif log_level == 'DEBUG':
            self._logfn = _log.debug
        else:
            self._logfn = _log.info

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        _log.debug("VERSION IS: {}".format(self.core.version()))
        self.vip.pubsub.publish('pubsub', 'matlab-in', message="testScript.py,20")

    

    @PubSub.subscribe('pubsub', 'matlab-out')
    def get_output(self, peer, sender, bus, topic, headers, message):
        self._logfn("Message: \n" + pformat(message[:-1]))

def main():
    """Main method called to start the agent."""
    utils.vip_main(Matlabagent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
