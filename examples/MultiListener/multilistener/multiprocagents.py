from __future__ import print_function
from multiprocessing import Process, Lock, JoinableQueue
from gevent.queue import Queue, Empty
import sys
import gevent
import logging
import random
from datetime import timedelta
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform import get_address
from volttron.platform.agent.utils import setup_logging
import os
from math import sqrt, pow
import argparse
from volttron.platform.keystore import KeyStore
from volttron.platform.agent import math_utils

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

setup_logging()
_log = logging.getLogger('multiagent')
#_log.setLevel(logging.WARNING)
keystore = KeyStore()

class MasterAgent(Process):
    def __init__(self, agentid, lock, listeners, msgque):
        Process.__init__(self)
        self.lock = lock
        self.msgque = msgque
        ident = 'Master' + str(agentid)

        self.agent = Agent(address=get_address(), identity=ident,  publickey=keystore.public, secretkey=keystore.secret, enable_store=False)
        event = gevent.event.Event()
        self.agent._agentid = 'Master' + str(agentid)
        self.task = gevent.spawn(self.agent.core.run, event)
        event.wait(timeout=1)
        _log.debug("Process id: {}".format(os.getpid()))

        self.count = 0
        self.prices = []
        self.listeners = listeners
        self._subtopic = "demand"
        self._pubtopic = "supply"
        self.subscribe()

    def subscribe(self):
        self.agent.vip.pubsub.subscribe('pubsub',
                                    self._subtopic,
                                    self.master_callback)

    def master_callback(self, peer, sender, bus, topic, headers, message):
        self.count += 1
        self.prices.append(message[0]['price'])
        # _log.debug(
        #     "Process name: %r, Count: %r, Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
        #     "Message: %r ", self.agent._agentid, self.count, peer, sender, bus, topic, headers, message)
        if self.count == self.listeners:
            mn = sum(self.prices) / len(self.prices)
            eprint("Master: Sending Supply price: {}".format(mn))
            self.agent.vip.pubsub.publish(peer='pubsub',
                                     topic=self._pubtopic,
                                     message=[{'price': mn}])
            self.count = 0

#class MultiListenerAgent(Process):
class MultiListenerAgent(Process):
    def __init__(self, agentid, lock, dev, msgque):
        Process.__init__(self)
        self.lock = lock
        self.msgque = msgque
        ident = 'House' + str(agentid)

        self.agent = Agent(address=get_address(), identity=ident,  publickey=keystore.public, secretkey=keystore.secret, enable_store=False)
        event = gevent.event.Event()
        self.agent._agentid = 'House' + str(agentid)
        self.task = gevent.spawn(self.agent.core.run, event)
        event.wait(timeout=1)

        self._pubtopic = "demand/" + ident
        self._subtopic = "supply"
        _log.debug("Process id: {}".format(os.getpid()
                                           ))
        self.subscribe()
        self.count = 0
        delay = utils.get_aware_utc_now() + timedelta(minutes=3)
        grnlt = self.agent.core.schedule(delay, self.next_publish, agentid)

    def subscribe(self):
        self.agent.vip.pubsub.subscribe('pubsub',
                                    self._subtopic,
                                    self.listener_callback)
    def unsubscribe(self):
        _log.debug("topic: {}".format(self._subtopic))
        self.agent.vip.pubsub.unsubscribe('pubsub',
                                        self._subtopic,
                                        self.listener_callback)


    def listener_callback(self, peer, sender, bus, topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        # _log.debug(
        #     "Process name: %r, Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
        #     "Message: %r ", self.agent._agentid, peer, sender, bus, topic, headers, message)
        price = message[0]['price']
        self.count += 1
        eprint("{0}: Count: {1} Supply Price: {2}".format(self.agent._agentid, self.count, message[0]['price']))
        delay = utils.get_aware_utc_now() + timedelta(seconds=60)
        grnlt = self.agent.core.schedule(delay, self.next_publish, price)

    def next_publish(self, price):
        new_price = price + random.random()
        self.agent.vip.pubsub.publish(peer='pubsub',
                                     topic=self._pubtopic,
                                     message=[{'price': new_price}])

def main(argv=sys.argv):
    args = argv[1:]

    parser = argparse.ArgumentParser()

    # Add options for number of listeners and test results file
    parser.add_argument("-l", "--listener", action='store', type=int, dest="listeners",
                        help="Number of listener agents")
    parser.add_argument(
        '-d', '--devices', action='store', type=int, dest="dev",
        help='Number of devices')
    parser.add_argument(
        '-f', '--file', metavar='FILE', dest = "test_opt",
        help='send test result to FILE')

    parser.set_defaults(
        listeners = 2,
        dev = 50,
        test_opt='opt/timesamples.txt'
    )
    opts = parser.parse_args(args)
    listeners = opts.listeners
    test_opt = opts.test_opt
    dev = opts.dev
    _log.debug("Num of listener agents {0}, Devices {1}, test output file: {2}".format(listeners, dev, test_opt))

    try:
        proc = []
        time_delta_msg = []
        l = Lock()
        msgQ = JoinableQueue()
        pub = MasterAgent(1, l, listeners, msgQ)
        pub.start()

        proc = [MultiListenerAgent(i, l, dev, msgQ) for i in range(listeners)]
        for p in proc:
            _log.debug("Process name {0}, Process Id: {1}".format(p.name, p.pid))
            p.start()

        gevent.sleep(1)

        #Wait for queue to be done
        while True:
            gevent.sleep(0.5)

        for p in proc:
            p.task.join()
    except KeyboardInterrupt:
        for p in proc:
            p.task.kill()
        _log.debug("KEYBOARD INTERRUPT")

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
