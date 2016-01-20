import pytest
import gevent
import time

from volttron.platform.vip.agent import Agent, PubSub, Core

from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper

MAX_WAIT_TIME = 20

messages = {}
def onmessage(peer, sender, bus, topic, headers, message):
    messages[topic] = message

@pytest.fixture
def primary_volttron(request, instance1_config):
    wrapper = build_wrapper(instance1_config['vip-address'])

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper

@pytest.fixture
def secondary_volttron(request, instance2_config):
    wrapper = build_wrapper(instance2_config['vip-address'])

    def cleanup():
        print('Shutting down instance: {}'.format(wrapper.volttron_home))
        wrapper.shutdown_platform(True)
    request.addfinalizer(cleanup)
    return wrapper


def test_failover(primary_volttron, secondary_volttron):
    global messages
    agent_dir = "services/core/MasterDriverAgent"

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
        print "PRIMARY {}".format(primary_msg_delay)

    assert messages.keys()

    messages.clear()

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
        print "SECONDARY {}".format(secondary_msg_delay)

    assert messages.keys()

    # they shouldn't take the same ammount of time
    assert (secondary_msg_delay - primary_msg_delay) > 0

    assert True
