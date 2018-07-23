# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt

from volttron.platform.vip.agent import Agent
import gevent
from gevent.core import callback


def onmessage(peer, sender, bus, topic, headers, message):
    print('received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, message=%r' % (
        peer, sender, bus, topic, headers, message))

if __name__ == '__main__':
    a = Agent()
    gevent.spawn(a.core.run).join(0)
    a.vip.pubsub.subscribe(peer='pubsub',
                           prefix='weather/response',
                           callback=onmessage).get(timeout=5)

    a.vip.pubsub.publish(peer='pubsub',
                         topic='weather/request',
                         headers={'requesterID': 'agent1'},
                         message={'zipcode': '99336'}).get(timeout=5)

    gevent.sleep(5)
    a.core.stop()
