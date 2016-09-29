import os
import sys

import gevent

from volttron.platform import get_address
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent

agent = Agent(address=get_address(), identity="blahagent")

event = gevent.event.Event()
config_store_task = gevent.spawn(agent.core.run, event)
event.wait()
del event

if VOLTTRON_CENTRAL_PLATFORM not in agent.vip.peerlist().get():
    agent.core.stop()
    print('no vcp availablel')
    sys.exit()


def receive_platform_data(**kwargs):
    assert 'message' in kwargs

    print('platform data is: {}'.format(kwargs['message']))


def receive_iam_data(**kwargs):
    assert 'message' in kwargs

    print('I am response is: {}'.format(kwargs['message']))

agent.vip.pubsub.subscribe('', topics.BACNET_I_AM, receive_iam_data)
agent.vip.pubsub.subscribe('', "platforms", receive_platform_data)

agent.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'start_bacnet_scan', dict(
    proxy_identity="platform.bacnet_proxy"
))

while True:
    gevent.sleep(0.5)

