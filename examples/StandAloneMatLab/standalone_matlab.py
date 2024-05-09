from scriptwrapper import script_runner

import gevent
import json
import logging
import os
import sys

from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils

# These are the options that can be set from the settings module.
from settings import remote_url, _topics

# Setup logging so that we could use it if we needed to.
utils.setup_logging()
_log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.debug,
    format='%(asctime)s   %(levelname)-8s %(message)s',
    datefmt='%m-%d-%y %H:%M:%S')


class StandAloneMatLab(Agent):
    '''The standalone version of the MatLab Agent'''

    @PubSub.subscribe('pubsub', _topics['volttron_to_matlab'])
    def print_message(self, peer, sender, bus, topic, headers, message):
        print('The Message is: ' + str(message))
        message_out = script_runner(message)
        self.vip.pubsub.publish(
            'pubsub', _topics['matlab_to_volttron'], message=message_out)
    
if __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        print(remote_url())
        agent = StandAloneMatLab(address=remote_url(), identity='standalone_matlab')
        task = gevent.spawn(agent.core.run)
        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
