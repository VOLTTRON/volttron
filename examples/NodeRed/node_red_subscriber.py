from datetime import datetime
import os
import sys


import gevent

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils
from volttron.platform.scheduling import periodic
from volttron.platform import jsonapi

from settings import topic_prefixes_to_watch, heartbeat_period, agent_kwargs


class NodeRedSubscriber(Agent):

    def onmessage(self, peer, sender, bus, topic, headers, message):
        d = {'topic': topic,
             'headers': headers,
             'message': message}
        sys.stdout.write(jsonapi.dumps(d)+'\n')
        sys.stdout.flush()

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for prefix in topic_prefixes_to_watch:
            self.vip.pubsub.subscribe(peer='pubsub', prefix=prefix, callback=self.onmessage).get(timeout=10)

    # Demonstrate periodic decorator and settings access
    @Core.schedule(periodic(heartbeat_period))
    def publish_heartbeat(self):
        now = utils.format_timestamp(datetime.utcnow())
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        result = self.vip.pubsub.publish('pubsub', 'heartbeat/NodeRedSubscriber', headers, now)
        result.get(timeout=10)


if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        agent = NodeRedSubscriber(identity='NodeRedSubscriber', **agent_kwargs)
        task = gevent.spawn(agent.core.run)

        try:
            task.join()
        finally:
            task.kill()

    except KeyboardInterrupt:
        pass

