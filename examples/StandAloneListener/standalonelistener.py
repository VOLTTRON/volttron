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
from scriptwrapper import script_runner

import os
import sys

import json
import gevent
import logging

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils
from volttron.platform.scheduling import periodic

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
        sys.stdout.write(json.dumps(d)+'\n')

    @PubSub.subscribe('pubsub','matlab/to_agent/1')
    def print_message(self, peer, sender, bus, topic, headers, message):
        print('The Message is: ' + str(message))
        messageOut = script_runner(message)
        self.vip.pubsub.publish('pubsub', 'matlab/from_agent/1', message=messageOut)



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
