'''

    This python script will listen to the defined vip address for specific
    topics. This script prints all output to standard  out rather than using the
    logging facilities. This script will also publish a heart beat
    (which will be returned if listening to the heartbeat topic).

    Setup:
    ~~~~~

      1. Make sure volttron instance is running using tcp address. use vcfg
         command to configure volttron instance address,.

      2. Update settings.py

      3. Add this standalone agent to volttron auth entry using vctl auth add
         command. Provide ip of the volttron instance when prompted for
         address[]: and  provide public key of standalone agent when prompted
         for credentials[]:
         For more details see
         https://volttron.readthedocs.io/en/develop/devguides/walkthroughs/Agent-Authentication-Walkthrough.html

         Example command:

         .. code-block:: console

         (volttron)[vdev@cs_cbox myvolttron]$ vctl auth add
         domain []:
         address []: 127.0.0.1
         user_id []:
         capabilities (delimit multiple entries with comma) []:
         roles (delimit multiple entries with comma) []:
         groups (delimit multiple entries with comma) []:
         mechanism [CURVE]:
         credentials []: GsEq7mIsU6mJ31TN44lQJeGwkJlb6_zbWgRxVo2gUUU
         comments []:
         enabled [True]:

      4. With a volttron activated shell this script can be run like:

         python standalonelistener.py


    Example output to standard out:

        {"topic": "heartbeat/standalonelistener",
         "headers": {"Date": "2015-10-22 15:22:43.184351Z", "Content-Type": "text/plain"},
         "message": "2015-10-22 15:22:43.184351Z"}
        {"topic": "devices/building/campus/hotwater/heater/resistive/information/power/part_realpwr_avg",
         "headers": {"Date": "2015-10-22 00:45:15.480339"},
         "message": [{"part_realpwr_avg": 0.0}, {"part_realpwr_avg": {"units": "percent", "tz": "US/Pacific", "type": "float"}}]}

    The heartbeat message is a simple plain text message with just a date stamp
    
    A "data" message contains an array of 2 elements.  The first element 
    contains a dictionary of (point name: value) pairs.  The second element
    contains context around the point data and the "Date" header.
'''
from datetime import datetime
import os
import sys

import gevent
import logging

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils
from volttron.platform.scheduling import periodic
from volttron.platform import jsonapi


# These are the options that can be set from the settings module.
from settings import remote_url, topics_prefixes_to_watch, heartbeat_period

# Setup logging so that we could use it if we needed to.
utils.setup_logging()
_log = logging.getLogger(__name__)

logging.basicConfig(
                level=logging.debug,
                format='%(asctime)s   %(levelname)-8s %(message)s',
                datefmt='%m-%d-%y %H:%M:%S')

class StandAloneListener(Agent):
    ''' A standalone version of the ListenerAgent'''
    
    def onmessage(self, peer, sender, bus, topic, headers, message):
        '''Handle incoming messages on the bus.'''
        d = {'topic': topic, 'headers': headers, 'message': message}
        sys.stdout.write(jsonapi.dumps(d)+'\n')

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        '''Handle the starting of the agent.
        
        Subscribe to all points in the topics_prefix_to_watch tuple
        defined in settings.py.
        '''

        for prefix in topics_prefixes_to_watch:
            sys.stdout.write('connecting to prefix: {}\n'.format(prefix))
            self.vip.pubsub.subscribe(peer='pubsub', 
                       prefix=prefix,
                       callback=self.onmessage).get(timeout=5)

    # Demonstrate periodic decorator and settings access
    @Core.schedule(periodic(heartbeat_period))
    def publish_heartbeat(self):
        '''Send heartbeat message every heartbeat_period seconds.

        heartbeat_period is set and can be adjusted in the settings module.
        '''
        sys.stdout.write('publishing heartbeat.\n')
        now = utils.format_timestamp(datetime.utcnow())
        headers = {
            #'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        self.vip.pubsub.publish(
            'pubsub', 'heartbeat/standalonelistener', headers,
            now).get(timeout=5)


if __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)
        
        print(remote_url())
        agent = StandAloneListener(address=remote_url(),
                                   identity='standalone_listener')
        task = gevent.spawn(agent.core.run)
        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
