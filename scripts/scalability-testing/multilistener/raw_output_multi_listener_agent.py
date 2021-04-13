from __future__ import print_function

import argparse
import gevent
import json
import logging
import os
import sys

from multiprocessing import Process, Lock, JoinableQueue

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform import get_address
from volttron.platform.agent.utils import setup_logging


def eprint(*args, **kwargs):
    print("###>", *args, file=sys.stderr, **kwargs)


setup_logging()
_log = logging.getLogger('multiagent')
_log.setLevel(logging.INFO)


class MultiAgent(Process):
    def __init__(self, agentid, lock, dev, msgque, raw_queue, message_bus):
        Process.__init__(self)
        self.lock = lock
        self.msgque = msgque
        self.raw_queue = raw_queue
        ident = 'Agent' + str(agentid)
        self.agent = Agent(address=get_address(), identity=ident, message_bus=message_bus)
        event = gevent.event.Event()
        self.agent._agentid = 'Agent' + str(agentid)

        self.task = gevent.spawn(self.agent.core.run, event)

        event.wait(timeout=2)

        self.agent.vip.pubsub.subscribe('pubsub', 'devices', self.on_message)

        _log.debug("Process id: {}".format(os.getpid()))
        eprint("eprint - Process id: {}".format(os.getpid()))
        self.count = 0
        self.publishes = 0
        self.data_list = [[], [], [], [], []]
        self.delta_list = []
        self.msg = []
        self.devices = dev
        self.max_publishes = 5*dev
        self.utcnow_string = ''

    def on_message(self, peer, sender, bus, topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        #if self.count == 0:
        #    eprint(f"the max publishes is {self.max_publishes}")
        client_time = utils.get_aware_utc_now()
        utcnow_string = utils.format_timestamp(client_time)
        self.count += 1
        #eprint(
        #    "Process name: [%r], Count: [%r], Time: [%r], Peer: [%r], Sender: [%r]:, Bus: [%r], Topic: [%r], Headers: [%r], "
        #    "Message: [%r]" % (self.name, self.count, utcnow_string, peer, sender, bus, topic, headers, message))
        header_time = utils.parse_timestamp_string(headers['TimeStamp'])
        # eprint("Agent: {0}, current timestamp {1}, header timestamp {2}!".format(self.agent._agentid,
        #                                                                          utcnow_string,
        #                                                                          headers['TimeStamp']))
        self.data_list[self.publishes].append({
            'header_t': header_time.timestamp(),
            'client_t': client_time.timestamp(),
            })
        #if self.count%21 == 0 or self.count%42 == 1:
        diff = client_time - header_time
        d_float = diff.seconds + (diff.microseconds* 0.000001)
        #eprint(f"--- count [{self.count}] | Agent {self.agent._agentid} | pub time is {d_float} seconds")
        ##TODO: why do we take the last device? Should it be a mean?
        if self.count % self.devices == 0:
            #eprint("Agent: {0}, current timestamp {1}, header timestamp {2}!".format(self.agent._agentid,
            #                                                                         utcnow_string,
            #                                                                         headers['TimeStamp']))
            #eprint("I'M HERE!")
            diff = client_time - header_time
            d_float = diff.seconds + (diff.microseconds* 0.000001)
            self.msg.append(d_float)
            # increment publish count
            eprint(f'[{self.agent._agentid}] done with publish [{self.publishes}]')
            self.publishes += 1

        #self.delta_list.append(diff)
        #avg = sum(self.delta_list, timedelta(0))/len(self.delta_list)

        if (self.count == self.max_publishes):
            eprint(f"finishing because count [{self.count}] == max_publishes [{self.max_publishes}] (publish counter is [{self.publishes}])")
            self.queue_put(self.msg)
            self.task.kill()

    def queue_put(self, msg):
        self.lock.acquire()
        self.msgque.put(msg)
        self.raw_queue.put({self.agent._agentid: self.data_list})
        #self.agent._agentid = 'Agent' + str(agentid)

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
        '-m', '--messagebus', action='store', type=str, dest="mb",
        help='message bus')
    parser.add_argument(
        '-f', '--file', metavar='FILE', dest="test_opt",
        help='send test result to FILE')

    parser.set_defaults(
        ps=2,
        dev=50,
        mb='zmq',
        test_opt='test.log'
    )
    opts = parser.parse_args(args)
    ps = opts.ps
    test_opt = opts.test_opt
    dev = opts.dev
    message_bus = opts.mb
    #_log.debug("Num of listener agents {0}, Devices {1}, test output file: {2}".format(ps, dev, test_opt))
    eprint("Num of listener agents {0}, Devices {1}, test output file: {2}".format(ps, dev, test_opt))

    try:
        proc = []
        time_delta_msg = []
        raw_time_data = {}
        l = Lock()
        msgQ = JoinableQueue()
        raw_queue = JoinableQueue()
        proc = [MultiAgent(i, l, dev, msgQ, raw_queue, message_bus=message_bus) for i in range(ps)]
       
        raw_output_file = f'{os.path.splitext(test_opt)[0]}.raw{os.path.splitext(test_opt)[-1]}'
        if os.path.exists(raw_output_file):
            raise ValueError(f'file [{raw_output_file}] already exists')

        for p in proc:
            #_log.debug("Process name {0}, Process Id: {1}".format(p.name, p.pid))
            p.start()
            eprint("Process name [{}], Process Id: [{}]".format(p.name, p.pid))
        eprint('listeners processes started')
        
        #Wait for queue to be done
        while True:
            if not msgQ.empty():
                time_delta_msg.append(msgQ.get(True))
                msgQ.task_done()
                #_log.debug("msg len {0}, proc len {1}".format(len(time_delta_msg), len(proc)))
                #eprint("msg len {0}, proc len {1}".format(len(time_delta_msg), len(proc)))
                if len(time_delta_msg) == len(proc):
                    break
            gevent.sleep(0.5)
        eprint('data collected, processing')
        ## and the raw queue
        while True:
            if not raw_queue.empty():
                raw_time_data.update(raw_queue.get(True))
                raw_queue.task_done()
                if len(raw_time_data) == len(proc):
                    break
            gevent.sleep(0.5)
        eprint('raw data collected')
        eprint(f'size is {len(raw_time_data)}')
        
        # Calculate the mean for each time samples/deltas
        td = []
        mean = []
        for i in range(5):
            td = []
            for j in range(len(time_delta_msg)):
                td.append(time_delta_msg[j][i])
            mn = sum(td) / len(td)
            mean.append(mn)

        # Write the collected time samples into a file
        fd = 0
        try:
            fd = open(test_opt, 'w')
            fd.write('Mean=' + str(mean))
            total_mean = sum(mean) / len(mean)
            fd.write('Total Mean= ' + str(total_mean))
            eprint("TOTAL MEAN = {}".format(total_mean))
        except IOError:
            eprint("Error writing into file")
        finally:
            if fd:
                fd.close()
        with open(raw_output_file, 'x') as a_file:
            a_file.write(json.dumps(raw_time_data))
        #_log.debug("I'M DONE WITH THE TEST.")
        eprint("I'M DONE WITH THE TEST")
        for p in proc:
            p.task.join()
    except KeyboardInterrupt:
        for p in proc:
            p.task.kill()
        eprint("KEYBOARD INTERRUPT")


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
