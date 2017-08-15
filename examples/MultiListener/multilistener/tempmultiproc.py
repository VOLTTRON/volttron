from __future__ import print_function
from multiprocessing import Process, Lock, JoinableQueue
from gevent.queue import Queue, Empty
import sys
import gevent
import logging
from datetime import timedelta
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform import get_address
from volttron.platform.agent.utils import setup_logging
import os
from math import sqrt, pow
import argparse
from volttron.platform.keystore import KeyStore

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

setup_logging()
_log = logging.getLogger('multiagent')
_log.setLevel(logging.WARNING)
class MultiAgent(Process):
    def __init__(self, agentid, lock, dev, msgque):
        Process.__init__(self)
        self.lock = lock
        self.msgque = msgque
        ident = 'Agent' + str(agentid)
        keystore = KeyStore()
        self.agent = Agent(address=get_address(), identity=ident,  publickey=keystore.public, secretkey=keystore.secret, enable_store=False)
        event = gevent.event.Event()
        self.agent._agentid = 'Agent' + str(agentid)
        self._topic = ''
        self.task = gevent.spawn(self.agent.core.run, event)

        event.wait(timeout=2)
        self._topic = 'devices/fakedriver'
        self._topic += str(agentid) + '/all'
        _log.debug("topic: {}".format(self._topic))
        # self.agent.vip.pubsub.subscribe('pubsub',
        #                                 self._topic,
        #                                 self.on_message)
        self.agent.vip.pubsub.subscribe('pubsub',
                                   'devices',
                                   self.on_message)
        _log.debug("Process id: {}".format(os.getpid()
                                           ))
        self.count = 0
        self.delta_list = []
        self.msg = []
        self.devices = dev
        self.max_publishes = 5*dev

    def ping(self):
        resp = self.agent.vip.ping('pubsub', 'hello').get(timeout=5)
        print('PUBSUB RESP: ', resp)

    def on_message(self, peer, sender, bus, topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        client_time = utils.get_aware_utc_now()
        utcnow_string = utils.format_timestamp(client_time)
        self.count += 1
        _log.debug(
            "Process name: %r, Count: %r, Time: %r, Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
            "Message: %r ", self.name, self.count, utcnow_string, peer, sender, bus, topic, headers, message)
        header_time = utils.parse_timestamp_string(headers['TimeStamp'])

        #if self.count%21 == 0 or self.count%42 == 1:
        if self.count%self.devices == 0:
            diff = client_time - header_time
            d_float = diff.seconds + (diff.microseconds* 0.000001)
            self.msg.append(d_float)
        #self.delta_list.append(diff)
        #avg = sum(self.delta_list, timedelta(0))/len(self.delta_list)

        if(self.count == self.max_publishes):
            self.queue_put(self.msg)

    def queue_put(self, msg):
        self.lock.acquire()
        self.msgque.put(msg)

        self.lock.release()

def main(argv=sys.argv):
    args = argv[1:]

    parser = argparse.ArgumentParser()

    # Add options for number of listeners and test results file
    parser.add_argument("-l", "--listener", action='store', type=int, dest="ps",
                        help="Number of listener agents")
    parser.add_argument(
        '-d', '--devices', action='store', type=int, dest="dev",
        help='Number of devices')
    parser.add_argument(
        '-f', '--file', metavar='FILE', dest = "test_opt",
        help='send test result to FILE')

    parser.set_defaults(
        ps = 2,
        dev = 50,
        test_opt='opt/timesamples.txt'
    )
    opts = parser.parse_args(args)
    ps = opts.ps
    test_opt = opts.test_opt
    dev = opts.dev
    _log.debug("Num of listener agents {0}, Devices {1}, test output file: {2}".format(ps, dev, test_opt))


    try:
        proc = []
        time_delta_msg = []
        l = Lock()
        msgQ = JoinableQueue()
        proc = [MultiAgent(i, l, dev, msgQ) for i in range(ps)]
        for p in proc:
            _log.debug("Process name {0}, Process Id: {1}".format(p.name, p.pid))
            p.start()

        for p in proc:
            # p.subscribe()
            p.ping()

        #Wait for queue to be done
        while True:
            if not msgQ.empty():
                time_delta_msg.append(msgQ.get(True))
                msgQ.task_done()
                _log.debug("msg len {0}, proc len {1}".format(len(time_delta_msg), len(proc)))
                if len(time_delta_msg) == len(proc):
                    break
            gevent.sleep(0.5)

        # Calculate the mean for each time samples/deltas
        td = []
        mean = []
        for i in range(5):
            td = []
            for j in range(len(time_delta_msg)):
                td.append(time_delta_msg[j][i])
            mn = sum(td) / len(td)
            mean.append(mn)

        #Write the collected time samples into a file
        fd = 0
        try:
            fd = open(test_opt, 'w')
            total_mean = sum(mean) / len(mean)
            fd.write('Total Mean= ' + str(total_mean))
            eprint("TOTAL MEAN = {}".format(total_mean))
        except IOError:
            _log.debug("Error writing into file")
        finally:
            if fd:
                fd.close()
        _log.debug("I'M DONE WITH THE TEST.")
        eprint("I'M DONE WITH THE TEST")
        for p in proc:
            p.task.join()
    except KeyboardInterrupt:
        for p in proc:
            p.task.kill()
        _log.debug("KEYBOARD INTERRUPT")

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
