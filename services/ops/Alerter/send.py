import os
import random

import gevent

from volttron.platform.vip.agent import Agent
from volttron.platform import get_home
import argparse

VIP_ADDR = 'ipc://@' + os.path.join(get_home(), 'run/vip.socket')
parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=['setstatusgood',
                                          'setstatusbad',
                                          'alert'],
                    help="Set the status of the alert agent")
parser.add_argument("message",
                    help="Set the status of the alert agent")

args = parser.parse_args()

agent = Agent(address=VIP_ADDR)
event = gevent.event.Event()
gevent.spawn(agent.core.run, event)#.join(0)
event.wait(timeout=2)

if args.operation == 'setstatusgood':
    agent.vip.rpc.call('alerter', 'status_good').get(timeout=2)
if args.operation == 'setstatusbad':
    agent.vip.rpc.call('alerter', 'status_bad', args.message).get(timeout=2)

if args.operation == 'alert':
    # alert
    alertkey = 'key{}'.format(random.randint(1,1000))
    agent.vip.rpc.call('alerter', 'send_alert1', alertkey, args.message).get(timeout=2)


print(VIP_ADDR)
print(args)

# def status_bad(self, context):
#         self.vip.health.set_status(STATUS_BAD, context)
#
#     @RPC.export
#     def status_good(self):
#         self.vip.health.set_status(STATUS_GOOD)
#
#     @RPC.export
#     def send_alert(self, key, message):