# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import gevent
import pytest
from volttron.platform import get_ops, get_examples


#########################################
# Note: currently these pytests only work
# if you comment out lines 784 and 785 in
# volttron/volttron/platform/main.py.
#########################################

message_count1 = 0
message_count2 = 0
message_count3 = 0
message_count4 = 0
message_count5 = 0

@pytest.mark.rmq_pubsub
def test_granularity(volttron_instance, request):
    global message_count1, message_count2, message_count3
    message_count1 = 0
    message_count2 = 0
    message_count3 = 0

    g1_topic = "testtopic1"
    g2_topic = "testtopic1/test"
    g3_topic = "testtopic1/test/foo"

    # High level granularity callback, will get the most messages
    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith("testtopic1"):
            message_count1 += 1

    # Medium level granularity callback, will get medium amount of messages
    def onmessage2(peer, sender, bus, topic, headers, message):
        global message_count2
        if topic.startswith("testtopic1/test"):
            message_count2 += 1

    # Low level granularity callback method, will get least amount of messages
    def onmessage3(peer, sender, bus, topic, headers, message):
        global message_count3
        if topic.startswith("testtopic1/test/foo"):
            message_count3 += 1

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

    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1', callback=onmessage1)
    new_agent2_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1/test', callback=onmessage2)
    new_agent3_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1/test/foo', callback=onmessage3)
    gevent.sleep(2)

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

    # Agent subscribes to both the desired topic and a topic that is not going to ever be published
    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage)
    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix='incorrecttopic', callback=onmessage)
    gevent.sleep(.5)


    new_agent2_pub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
    gevent.sleep(.5)

    # Should get messages from the topic that has messages being published but not from the topic that
    # does not have messages being published
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

    # Messages should be recieved by new_agent1 since it has subscribed to test_topic
    for i in range(0, 5):
        new_agent2_unsub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    new_agent1_sub.vip.pubsub.unsubscribe(peer='pubsub', prefix=test_topic, callback=onmessage)
    gevent.sleep(0.01)

    # Since agent has unsubscribed from test_topic, these messages should not be recieved
    for i in range(0, 5):
        new_agent2_unsub.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    assert message_count1 == 5

@pytest.mark.rmq_pubsub
def test_irrelevant_unsubscribe(volttron_instance, request):
    global message_count1
    message_count1 = 0

    not_subscribed_topic = "testtopic1/not/subscribed"

    def onmessage(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(not_subscribed_topic):
            message_count1 += 1

    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    request.addfinalizer(stop)

    # Agent has never subscribed to this topic but is attempting to unsubscribe anyway
    # Nothing should happen as a result
    new_agent1.vip.pubsub.unsubscribe(peer='pubsub', prefix=not_subscribed_topic, callback=onmessage)
    gevent.sleep(0.01)

    for i in range(0, 5):
        new_agent2.vip.pubsub.publish(peer="pubsub", topic=not_subscribed_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    # Confirm that no messages were ever recieved from the not_subscribed_topic
    assert message_count1 == 0


@pytest.mark.rmq_pubsub
def test_regex(volttron_instance, request):
    global message_count1, message_count2, message_count3, message_count4, message_count5
    message_count1 = 0
    message_count2 = 0
    message_count3 = 0
    message_count4 = 0
    message_count5 = 0

    ### Test fails. Cause currently unknown ####

    test_topic1 = "test.topic.one.test1"

    # Tests to confirm messages get discarded due to lack of match
    test_topic2 = "testtopic1.foo.bar.three"

    # Tests whether * does exactly one word match multiple places
    test_topic3 = "test.one.topic"

    # Tests whether # can do multiple word matches
    test_topic4 = "testtopic2.one.two.test"

    # Tests whether * does exactly one word match that using both * and # delimiters works
    test_topic5 = "testtopic3.test.foo."

    prefix_astrix_ends = "*.one.*"
    prefix_astrix_middle = "testtopic1.*.test"
    prefix_hashtag_ends = "#.one.#"
    prefix_hashtag_middle = "testtopic2.#.test"
    prefix_both_delimiters_ends = "*.test.foo.#"

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(prefix_astrix_ends):
            message_count1 += 1

    def onmessage2(peer, sender, bus, topic, headers, message):
        global message_count2
        if topic.startswith(prefix_astrix_middle):
            message_count2 += 1

    def onmessage3(peer, sender, bus, topic, headers, message):
        global message_count3
        if topic.startswith(prefix_hashtag_ends):
            message_count3 += 1

    def onmessage4(peer, sender, bus, topic, headers, message):
        global message_count4
        if topic.startswith(prefix_hashtag_middle):
            message_count4 += 1

    def onmessage5(peer, sender, bus, topic, headers, message):
        global message_count5
        if topic.startswith(prefix_both_delimiters_ends):
            message_count5 += 1

    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    request.addfinalizer(stop)

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic1, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic2, callback=onmessage2)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic3, callback=onmessage3)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic4, callback=onmessage4)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic5, callback=onmessage5)
    gevent.sleep(0.01)

    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic1, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic2, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic3, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic4, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic5, headers=None, message="Test message")

    assert message_count1 == 1
    assert message_count2 == 0
    assert message_count3 == 2
    assert message_count4 == 1
    assert message_count5 == 1

@pytest.mark.rmq_pubsub
def test_regex_incorrect_word_count(volttron_instance, request):
    global message_count1
    message_count1 = 0

    ### Test currently fails ###

    prefix1 = "testtopic.test.test1.*"
    test_topic1 = "testtopic.test.test1.foo.bar"
    test_topic3 = "testtopic"

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(prefix1):
            message_count1 += 1

    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    request.addfinalizer(stop)

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=prefix1, callback=onmessage1)

    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic1, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic2, headers=None, message="Test message")
    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic3, headers=None, message="Test message")

    # Since test_topic1 is the only one with the exact amount of words (test_topic 2 having too many and
    # test_topic3 having too few), new_agent1 should have only recieved one message
    assert message_count1 == 1


@pytest.mark.rmq_pubsub
def test_callback(volttron_instance, request):
    global message_count1, message_count2
    message_count1 = 0
    message_count2 = 0

    ### Test failed. Cause currently unknown ###

    test_topic = "testtopic1/test/foo/bar"

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(test_topic):
            message_count1 += 1

    def onmessage2(peer, sender, bus, topic, headers, message):
        global message_count2
        if topic.startswith(test_topic):
            message_count2 += 1

    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')


    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    request.addfinalizer(stop)

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage2)
    gevent.sleep(0.01)


    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
    gevent.sleep(0.01)


    new_agent1.vip.pubsub.unsubscribe(peer='pubsub', prefix=test_topic, callback=onmessage1)
    gevent.sleep(0.01)

    new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
    gevent.sleep(0.01)



    assert message_count1 == 1
    assert message_count2 == 2


@pytest.mark.rmq_pubsub
def test_list(volttron_instance, request):
    global message_count1
    message_count1 = 0

    prefix0 = "testtopic1/test/foo/bar"
    test_topic1 = "testtopic1/test/foo/bar/one"
    test_topic2 = "testtopic1/test/foo/bar/two"
    test_topic3 = "testtopic1/test/foo/bar/three"

    tup_topic = ""
    topic_result_index = 2
    member_result_index = 3

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(prefix0):
            message_count1 += 1


    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic1, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic2, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic3, callback=onmessage1)

    list_results = new_agent1.vip.pubsub.list(peer='pubsub', prefix=prefix0, bus='', subscribed=True, reverse=False,
                               all_platforms=False)

    for result in list_results:
        tup_topic = result[topic_result_index]
        assert tup_topic in [test_topic1, test_topic2, test_topic3]
        assert result[member_result_index] == True

@pytest.mark.rmq_pubsub
def test_list_reverse(volttron_instance, request):
    global message_count1
    message_count1 = 0

    ### Test currently fails ###

    prefix0 = "testtopic1/test/foo/bar"
    test_topic1 = "testtopic1/test/foo/bar/one"
    test_topic2 = "testtopic1/test/foo/bar/two"
    test_topic3 = "testtopic1/test/foo/bar/three"

    tup_topic = ""
    topic_result_index = 2
    member_result_index = 3

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(prefix0):
            message_count1 += 1

    new_agent1 = volttron_instance.build_agent(identity='agent1')
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent1.core.stop()
        new_agent2.core.stop()

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic1, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic2, callback=onmessage1)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic3, callback=onmessage1)

    list_results = new_agent1.vip.pubsub.list(peer='pubsub', prefix=prefix0, bus='', subscribed=True, reverse=False,
                                              all_platforms=False)


    for result in list_results:
        tup_topic = result[topic_result_index]
        assert tup_topic in [prefix0]
        # assert tup_topic in [test_topic1, test_topic2, test_topic3]
        assert result[member_result_index] == True


@pytest.mark.rmq_pubsub
def test_persistence(volttron_instance, request):
    global message_count1
    message_count1 = 0

    ### Test Fails due to lack of uuid for anonymous agent ###

    test_topic = "testtopic1/test/foo/bar"

    def onmessage1(peer, sender, bus, topic, headers, message):
        global message_count1
        if topic.startswith(test_topic):
            message_count1 += 1

    listener_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        vip_identity="listener",
        start=True)
    gevent.sleep(2)

    new_agent2 = volttron_instance.build_agent(identity='agent2')

    # Subscribe
    listener_uuid.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic, callback=onmessage1,
                                    persistent_queue="persistence_test")
    gevent.sleep(0.01)

    for i in range(0, 5):
        new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    def stop():
        listener_uuid.core.stop()
        new_agent2.core.stop()

    request.addfinalizer(stop)

    listener_uuid.core.stop()

    for i in range(0, 5):
        new_agent2.vip.pubsub.publish(peer="pubsub", topic=test_topic, headers=None, message="Test message")
        gevent.sleep(0.01)

    volttron_instance.start_agent()

    assert message_count1 == 10
