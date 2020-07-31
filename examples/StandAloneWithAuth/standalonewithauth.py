"""
    This python script is copied from the StandAloneListener agent.
    It demonstrates how to limit which agents can call an exported method
    (via RPC) based on capabilities.

    With a volttron activated shell this script can be run like:

        python standalonewithauth.py

    You will need to modify settings.py to have the correct agent_public and
    agent_secret values or you can modify VOLTTRON_HOME/auth.json to match
    the following:

{
    "allow": [
        {"credentials": "CURVE:XR-l7nMBB1zDRsUS2Mjb9lePkcNsgoosHKpCDm6D9TI", "domain": "vip", "address": "127.0.0.1", "capabilities": ["can_call_bar"]}
    ]
}

    (You will still need to change the 'server_key' value in settings.py)

"""
from datetime import datetime
import os
import sys

import gevent
import logging
from gevent.core import callback

from volttron.platform.vip.agent import Agent, Core, RPC
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

IDENTITY = 'Standalone With Authorization'

class StandAloneWithAuth(Agent):
    ''' A standalone agent that demonstrates how to use agent authorization'''

    # Demonstrate calling methods via RPC
    @Core.schedule(periodic(heartbeat_period))
    def call_foo_and_bar(self):
        foo_result = self.vip.rpc.call(IDENTITY, 'foo').get(timeout=5)
        sys.stdout.write('foo returned: {}\n'.format(foo_result))
        bar_result = self.vip.rpc.call(IDENTITY, 'bar').get(timeout=5)
        sys.stdout.write('bar returned: {}\n'.format(bar_result))

    @RPC.export
    def foo(self):
        return 'Anybody can call this function via RPC'

    @RPC.export
    @RPC.allow('can_call_bar')
    def bar(self):
        return 'If you can see this, then you have the required capabilities'

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
