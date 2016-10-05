import os
import sys

import gevent

from volttron.platform import get_address
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.keystore import KeyStore
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent


keystore = KeyStore()
agent = Agent(address=get_address(), identity="blahagent",
              publickey=keystore.public(), secretkey=keystore.secret(),
              enable_store=False)

event = gevent.event.Event()
config_store_task = gevent.spawn(agent.core.run, event)
event.wait()
del event

if VOLTTRON_CENTRAL_PLATFORM not in agent.vip.peerlist().get():
    agent.core.stop()
    print('no vcp availablel')
    sys.exit()


def receive_platform_data(peer, sender, bus, topic, headers, message):
    #assert 'message' in kwargs

    print('############33 platform data is: {}'.format(message))


def receive_iam_data(peer, sender, bus, topic, headers, message):


    address = message['address']
    device_id = message['device_id']

    print('###################I am response is: {}'.format(message))
    agent.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'publish_bacnet_props',
                       proxy_identity="platform.bacnet_proxy", address=address,
                       device_id=device_id)

agent.vip.pubsub.subscribe('pubsub', topics.BACNET_I_AM, receive_iam_data)
agent.vip.pubsub.subscribe('pubsub', "platforms", receive_platform_data)

agent.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM, 'start_bacnet_scan',
                   proxy_identity="platform.bacnet_proxy")

while True:
    try:
        gevent.sleep(0.5)
    except KeyboardInterrupt:
        sys.exit()


# if __name__ == '__main__':
#     address =