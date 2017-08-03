from multiprocessing import Process, Lock, JoinableQueue
from gevent.queue import Queue, Empty
import sys
import gevent
import logging
from datetime import timedelta
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.utils import setup_logging
import os


setup_logging()
_log = logging.getLogger('multiagent')

class MultiAgent(object):
    def __init__(self, msgque, id):
        agent = Agent()
        event = gevent.event.Event()
        self.task = gevent.spawn(agent.core.run, event)
        event.wait(timeout=2)
        agent.vip.pubsub.subscribe('pubsub',
                                   'devices',
                                   self.on_message)
        _log.debug("Process id: {}".format(os.getpid()
                                      ))
        self.msgque = msgque
        self.count = 0
        self.delta_list = []
        self.msg = []
        self.id = id

    def on_message(self, peer, sender, bus, topic, headers, message):
        '''Use match_all to receive all messages and print them out.'''
        client_time = utils.get_aware_utc_now()
        utcnow_string = utils.format_timestamp(client_time)
        self.count += 1
        _log.debug(
            "Process name: %r, Count: %r, Time: %r, Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
            "Message: %r ", self.id, self.count, utcnow_string, peer, sender, bus, topic, headers, message)
        header_time = utils.parse_timestamp_string(headers['TimeStamp'])

        if self.count%42 == 0:
            diff = client_time - header_time
            self.msg.append(diff)
        if(self.count == 420):
            self.queue_put(self.msg)

    def queue_put(self, msg):
        self.msgque.put(msg)

def main(argv=sys.argv):
    try:
        ag = []
        msg = []
        l = Lock()
        msgQ = JoinableQueue()
        ag = [MultiAgent(msgQ, i) for i in range(100)]

        #Wait for queue to be done
        while True:
            if not msgQ.empty():
                msg.append(msgQ.get(True))
                msgQ.task_done()
                _log.debug("msg len {0}, proc len {1}".format(len(msg), len(ag)))
                if len(msg) == len(ag):
                    break
            gevent.sleep(1)
        #Display the stats
        avg = []
        t = []

        #Plot it into a graph later
        avg = []
        t = []
        for i in range(10):
            t = []
            for j in range(len(msg)):
                t.append(msg[j][i])
            avg.append(sum(t, timedelta(0))/len(t))
        print("Mean time {}".format(avg))

        for a in ag:
            a.task.join()
    except KeyboardInterrupt:
        for a in ag:
            a.task.kill()
        _log.debug("KEYBOARD INTERRUPT")

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())