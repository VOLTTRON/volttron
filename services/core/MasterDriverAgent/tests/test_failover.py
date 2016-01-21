import pytest
import gevent
import time

from volttron.platform.vip.agent import Agent, PubSub, Core


MAX_WAIT_TIME = 20

messages = {}
def onmessage(peer, sender, bus, topic, headers, message):
    messages[topic] = message


def test_failover(volttron_instance1, volttron_instance2):
    global messages
    agent_dir = "services/core/MasterDriverAgent"
    primary_volttron = volttron_instance1
    secondary_volttron = volttron_instance2

    # find out how long it takes to get data from primary instance
    assert primary_volttron is not None
    assert primary_volttron.is_running()

    primary_listener = primary_volttron.build_agent()
    primary_listener.vip.pubsub.subscribe(peer='pubsub', prefix='', callback=onmessage)

    primary_master = primary_volttron.install_agent(agent_dir=agent_dir, config_file=agent_dir + "/tests/config0")
    assert primary_master is not None

    time_start = time.time()
    primary_msg_delay = 0
    while not messages.keys() and time.time() < time_start + MAX_WAIT_TIME:
        gevent.sleep(1)
        primary_msg_delay += 1

    assert messages.keys()

    primary_volttron.stop_agent(primary_master)
    messages.clear()
    assert(not primary_volttron.is_agent_running(primary_master))

    
    # find out how long it takes to get data from secondary instance
    assert secondary_volttron is not None
    assert secondary_volttron.is_running()

    secondary_listener = secondary_volttron.build_agent()
    secondary_listener.vip.pubsub.subscribe(peer='pubsub', prefix='', callback=onmessage)

    secondary_master = secondary_volttron.install_agent(agent_dir=agent_dir, config_file=agent_dir + "/tests/config1")
    assert secondary_master is not None

    time_start = time.time()
    secondary_msg_delay = 0
    while not messages.keys() and time.time() < time_start + MAX_WAIT_TIME:
        gevent.sleep(1)
        secondary_msg_delay += 1

    assert messages.keys()

    # there should be a delay beween publishes
    assert (secondary_msg_delay - primary_msg_delay) > 0

    assert True
