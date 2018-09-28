import gevent
import pytest

from volttron.platform.messaging import topics
from volttron.platform.messaging.headers import DATE
from volttron.platform.messaging.health import *
from volttron.platform.agent.utils import parse_timestamp_string
from volttrontesting.utils.utils import (poll_gevent_sleep,
                                         messages_contains_prefix)

from volttron.platform.vip.agent import PubSub


from volttron.platform.vip.agent import Agent

#########################################
# Note: currently these pytests only work
# if you comment out lines 784 and 785 in
# volttron/volttron/platform/main.py.
#########################################

message_count1 = 0
message_count2 = 0
message_count3 = 0

@pytest.mark.rmq_pubsub
def test_granularity(volttron_instance, request):
    global message_count1, message_count2, message_count3
    message_count1 = 0
    message_count2 = 0
    message_count3 = 0

    g1_topic = "testtopic1"
    g2_topic = "testtopic1/test"
    g3_topic = "testtopic1/test/foo"

    # Different callback methods to account for the different granularity of the topics
    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith("testtopic1"):
            message_count1 += 1

    def onmessage2(peer, sender, bus, topic, headers, message):
        global message_count2
        if topic.startswith("testtopic1/test"):
            message_count2 += 1

    def onmessage3(peer, sender, bus, topic, headers, message):
        global message_count3
        if topic.startswith("testtopic1/test/foo"):
            message_count3 += 1

    # First three agents create to subscribe to messages of different granularity, fourth agent publishes
    # messages for first three agents to receive.
    new_agent1_sub = volttron_instance.build_agent(identity='agent1')
    new_agent2_sub = volttron_instance.build_agent(identity='agent2')
    new_agent3_sub = volttron_instance.build_agent(identity='agent3')
    new_agent4_pub = volttron_instance.build_agent(identity='agent4')

    def stop():
        new_agent1_sub.core.stop()
        new_agent2_sub.core.stop()
        new_agent3_sub.core.stop()
        new_agent4_pub.core.stop()
    request.addfinalizer(stop)

    # First three agents subscribe to topics of various granularity.
    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1', callback=onmessage1)
    new_agent2_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1/test', callback=onmessage2)
    new_agent3_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1/test/foo', callback=onmessage3)
    gevent.sleep(2)

    # Fourth agent publishes three different messages. first agent will recieve all three of these messages
    # second agent will receive the last two messages, and third will only recieve the last message
    new_agent4_pub.vip.pubsub.publish(peer="pubsub", topic=g1_topic, headers=None, message="Test G1 Message")
    new_agent4_pub.vip.pubsub.publish(peer="pubsub", topic=g2_topic, headers=None, message="Test G2 Message")
    new_agent4_pub.vip.pubsub.publish(peer="pubsub", topic=g3_topic, headers=None, message="Test G3 Message")
    gevent.sleep(2)

    assert message_count1 == 3
    assert message_count2 == 2
    assert message_count3 == 1


@pytest.mark.rmq_pubsub
def test_incorrect_topic(volttron_instance, request):
    global message_count1
    message_count1 = 0
    incorrect_count = 0

    test_topic = "testtopic1/test/foo/bar"

    def onmessage(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith("testtopic1/test/foo/bar"):
            message_count1 += 1

    new_agent1_sub = volttron_instance.build_agent(identity='agent1')
    new_agent2_pub = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1_sub.core.stop()
        new_agent2_pub.core.stop()
    request.addfinalizer(stop)

    # Have subscribing agent subscribe to a topic that is being published and one that is not being published
    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage)
    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix='incorrecttopic', callback=onmessage)
    gevent.sleep(.5)

    # Have publishing agent publish one topic but not the other.
    new_agent2_pub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
    gevent.sleep(.5)

    # Make sure only correct topic has a count of 1.
    assert message_count1 == 1
    assert incorrect_count == 0


@pytest.mark.rmq_pubsub
def test_unsubscribe(volttron_instance, request):
    global message_count1
    message_count1 = 0

    def onmessage(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith("testtopic1/test/foo/bar"):
            message_count1 += 1

    test_topic = "testtopic1/test/foo/bar"

    new_agent1_sub = volttron_instance.build_agent(identity='agent1')
    new_agent2_unsub = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1_sub.core.stop()
        new_agent2_unsub.core.stop()

    request.addfinalizer(stop)

    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage)
    gevent.sleep(.5)

    # Publish messages to topic for five times, then unsubscribe from the topic
    for i in range(0, 5):
        new_agent2_unsub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)
    new_agent1_sub.vip.pubsub.unsubscribe(peer='pubsub', prefix=test_topic, callback=onmessage)
    gevent.sleep(0.01)

    # Have messages published for topic five more times, then assert than only the original five messages were recieved
    # by the agent
    for i in range(0, 5):
        new_agent2_unsub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    assert message_count1 == 5