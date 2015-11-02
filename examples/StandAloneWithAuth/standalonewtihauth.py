'''
    This python script is copied from the StandAloneListener agent.
    It demonstrates how to how to use two forms of agent authorization:
      1. publishing messages via PubSub that can only be read by agents
         that have specified capabilities
      2. limiting which agents can call an exported method (via RPC) based
         on capabilities

    With a volttron activated shell this script can be run like:

        python standalonewithauth.py

'''
from datetime import datetime
import os
import sys

import json
import gevent
import logging
from gevent.core import callback

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core, RPC
from volttron.platform.agent import utils

# These are the options that can be set from the settings module.
from settings import remote_url, topics_prefixes_to_watch, heartbeat_period

# Setup logging so that we could use it if we needed to.
utils.setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(
                level=logging.debug,
                format='%(asctime)s   %(levelname)-8s %(message)s',
                datefmt='%m-%d-%y %H:%M:%S')

IDENTITY = 'Standalone With Authorization'

class StandAloneWithAuth(Agent):
    ''' A standalone agent that demonstrates how to use agent authorization'''

    def onmessage(self, peer, sender, bus, topic, headers, message):
        '''Handle incoming messages on the bus.'''
        d = {'topic': topic, 'headers': headers, 'message': message}
        sys.stdout.write(json.dumps(d)+'\n')

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
    @Core.periodic(heartbeat_period)
    def publish_heartbeat(self):
        '''Send heartbeat message every heartbeat_period seconds.

        heartbeat_period is set and can be adjusted in the settings module.
        '''
        sys.stdout.write('publishing heartbeat.\n')
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            #'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        self.vip.pubsub.publish(
            'pubsub', 'heartbeat/anybody', headers,
            now).get(timeout=5)

        # Demonstrate how to publish only to agents with a certain capability
        self.vip.pubsub.publish(
            'pubsub', 'heartbeat/admin_only', headers,
            'must have admin capability to see this',
            required_capabilities=['admin']).get(timeout=5)

    # Demonstrate calling methods via RPC
    @Core.periodic(heartbeat_period)
    def call_foo_and_bar(self):
        foo_result = self.vip.rpc.call(IDENTITY, 'foo').get(timeout=5)
        sys.stdout.write('foo returned: {}\n'.format(foo_result))
        bar_result = self.vip.rpc.call(IDENTITY, 'bar').get(timeout=5)
        sys.stdout.write('bar returned: {}\n'.format(bar_result))

    @RPC.export
    def foo(self):
        return 'Anybody can call this function via RPC'

    @RPC.allow('admin') # TODO: this decorator is a work in progress
    @RPC.export
    def bar(self):
        return 'If you can see this, then you have the admin capability'

if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        print(remote_url())
        agent = StandAloneWithAuth(address=remote_url(),
                                   identity=IDENTITY)

        task = gevent.spawn(agent.core.run)

        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
