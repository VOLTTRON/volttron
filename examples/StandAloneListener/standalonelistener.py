#!env/bin/python

import os
import sys

import json
import gevent

from gevent.core import callback

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent.utils import isapipe
from settings import remote_url, topics_prefixes_to_watch, heartbeat_period

class StandAloneListener(Agent):
    
    def onmessage(self, peer, sender, bus, topic, headers, message):
        sys.stdout.write(json.dumps(message)+'\n')
#     print('received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, message=%r' % (
#         peer, sender, bus, topic, headers, message))


    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        # Demonstrate accessing a value from the config file
        #_log.info(self.config['message'])
        #self._agent_id = self.config['agentid']
        for prefix in topics_prefixes_to_watch:
            sys.stdout.write('connecting to prefix: {}\n'.format(prefix))
            self.vip.pubsub.subscribe(peer='pubsub', 
                       prefix=prefix,
                       callback=self.onmessage).get(timeout=5)

    # Demonstrate periodic decorator and settings access
    @Core.periodic(heartbeat_period)
    def publish_heartbeat(self):
        '''Send heartbeat message every HEARTBEAT_PERIOD seconds.

        HEARTBEAT_PERIOD is set and can be adjusted in the settings module.
        '''
        sys.stdout.write('publishing heartbeat.\n')
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            #'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        self.vip.pubsub.publish(
            'pubsub', 'heartbeat/standalonelistener', headers, now)

# 
# def onmessage(peer, sender, bus, topic, headers, message):
#     print('received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, message=%r' % (
#         peer, sender, bus, topic, headers, message))
#     
# a = Agent()
# gevent.spawn(a.core.run).join(0)
# a.vip.pubsub.subscribe(peer='pubsub', 
#                        prefix='weather/response',
#                        callback=onmessage).get(timeout=5)
#                        
# a.vip.pubsub.publish(peer='pubsub',
#                      topic='weather/request',
#                      headers={'requesterID': 'agent1'},
#                      message={'zipcode': '99336'}).get(timeout=5)
#                  
# gevent.sleep(5)
# a.core.stop()
# 
    
if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)
        
        agent = StandAloneListener(address=remote_url(),
                                   identity='Standalone Listener') 
        task = gevent.spawn(agent.core.run)
        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass