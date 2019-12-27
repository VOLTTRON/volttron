from datetime import datetime
import os
import sys


import gevent
import logging
from gevent.core import callback
from gevent import Timeout

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils

# Log warnings and errors to make the node red log less chatty
utils.setup_logging(level=logging.WARNING)
_log = logging.getLogger(__name__)

# These are the options that can be set from the settings module.
from settings import agent_kwargs

''' takes two arguments.  Firist is topic to publish under.  Second is message. '''
if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        agent = Agent(identity='NodeRedPublisher', **agent_kwargs)
        now = utils.format_timestamp(datetime.utcnow())
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        event = gevent.event.Event()
        task = gevent.spawn(agent.core.run, event)
        with gevent.Timeout(10):
            event.wait()

        try:
            result = agent.vip.pubsub.publish('pubsub', sys.argv[1], headers, sys.argv[2])
            result.get(timeout=10)
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
