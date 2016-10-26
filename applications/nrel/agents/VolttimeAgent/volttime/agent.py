#
from __future__ import absolute_import
from datetime import datetime
import logging
import sys
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
import time
from . import settings

utils.setup_logging()
_log = logging.getLogger(__name__)

class VolttimeAgent(Agent):
    """
        This agent will publish a current timestamp on the bus every second
        Template to enable faster tha realtime simulation in volttorn.
        Agents subscribe to this timestamp and synchronize accordingly

    """

    def __init__(self, config_path, **kwargs):
        """Initialize the calss and get config information"""
        super(VolttimeAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        """Setup the class and log agent information """
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']

    @Core.periodic(settings.HEARTBEAT_PERIOD)
    def publish_heartbeat(self):
        """Publish the current timestamp every second on the bus """
        headers = {
            'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: datetime.utcnow().isoformat(' ') + 'Z',
        }
        value = {}
        value['timestamp'] = {
            'Readings': str(time.strftime("%Y-%m-%d %H:%M:%S",
                                          time.localtime())), 'Units':'ts'
        }
        self.vip.pubsub.publish('pubsub', 'datalogger/log/volttime',
                                headers, value)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(VolttimeAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
