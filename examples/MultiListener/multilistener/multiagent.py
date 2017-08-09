import gevent
import sys
import logging
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.utils import setup_logging

setup_logging()
_log = logging.getLogger('multiagent')
count = 0

def multiagent():
    agents = []
    tasks = []
    i = 0
    for i in range(1):
        agent = Agent()
        event = gevent.event.Event()
        tasks.append(gevent.spawn(agent.core.run, event))
        event.wait(timeout=2)
        agents.append(agent)
        agent.vip.pubsub.subscribe('pubsub',
                                   'devices',
                                   on_message)

    return agents, tasks

def unsubscribe_prefix(agents):
    for a in agents:
        _log.debug("Calling unsubscribe()")
        a.vip.pubsub.unsubscribe('pubsub', 'devices', on_message)

def subscribe_prefix(agents):
    for a in agents:
        _log.debug("Calling unsubscribe()")
        a.vip.pubsub.subscribe('pubsub', 'devices', on_message)

def list_subscriptions(agents):
    for a in agents:
        lists = a.vip.pubsub.list('pubsub', 'devices').get(timeout=5)
        _log.debug("List {} ".format(lists))

def on_message(peer, sender, bus, topic, headers, message):
    '''Use match_all to receive all messages and print them out.'''
    utcnow = utils.get_aware_utc_now()
    utcnow_string = utils.format_timestamp(utcnow)
    global count
    count += 1
    _log.debug(
        "Count: %r, Time: %r, Peer: %r, Sender: %r:, Bus: %r, Topic: %r, Headers: %r, "
        "Message: %r ", count, utcnow_string, peer, sender, bus, topic, headers, message)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''

    try:
        agents, tasks = multiagent()
        _log.debug("Calling unsubscribe()")
        #gevent.sleep(5)

        #unsubscribe_prefix(agents)
        #_log.debug("Done unsubscribe()")

        #gevent.sleep(5)
        #subscribe_prefix(agents)
        #gevent.sleep(5)
        #list_subscriptions(agents)
        try:
            for a in tasks:
                a.join()
        finally:
            for a in tasks:
                a.kill()
    except KeyboardInterrupt:
        for a in agents:
            a.core.stop()
        for tk in tasks:
            tk.kill()

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())