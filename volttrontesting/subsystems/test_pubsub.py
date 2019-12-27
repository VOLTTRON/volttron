# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

from mock import MagicMock

message_count2 = 0


@pytest.fixture(scope="module")
def publisher_agent(request, volttron_instance):
    publisher_agent = volttron_instance.build_agent()

    def stop_agent():
        print("In teardown method of publisher_agent")
        publisher_agent.core.stop()

    request.addfinalizer(stop_agent)

    return publisher_agent


@pytest.fixture(scope="module")
def subscriber_agent(request, volttron_instance):
    subscriber_agent = volttron_instance.build_agent()

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()

    test_topic = "testtopic1/test/foo/bar"
    # Agent subscribes to both the desired topic and a topic that is not going to ever be published
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic,
                                          callback=subscriber_agent.callback)

    def stop_agent():
        print("In teardown method of publisher_agent")
        subscriber_agent.core.stop()

    request.addfinalizer(stop_agent)

    return subscriber_agent


@pytest.mark.pubsub
def test_granularity(volttron_instance, publisher_agent, request):
    g1_topic = "testtopic1"
    g2_topic = "testtopic1/test"
    g3_topic = "testtopic1/test/foo"

    # Low level granularity callback method, will get least amount of messages
    new_agent1_sub = volttron_instance.build_agent(identity='agenta')
    new_agent2_sub = volttron_instance.build_agent(identity='agentb')
    new_agent3_sub = volttron_instance.build_agent(identity='agentc')

    new_agent1_sub.callback = MagicMock(name="callback")
    new_agent1_sub.callback.reset_mock()
    new_agent2_sub.callback = MagicMock(name="callback")
    new_agent2_sub.callback.reset_mock()
    new_agent3_sub.callback = MagicMock(name="callback")
    new_agent3_sub.callback.reset_mock()

    def stop():
        new_agent1_sub.core.stop()
        new_agent2_sub.core.stop()
        new_agent3_sub.core.stop()

    request.addfinalizer(stop)

    new_agent1_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1',
                                        callback=new_agent1_sub.callback)
    new_agent2_sub.vip.pubsub.subscribe(peer='pubsub', prefix='testtopic1/test',
                                        callback=new_agent2_sub.callback)
    new_agent3_sub.vip.pubsub.subscribe(peer='pubsub',
                                        prefix='testtopic1/test/foo',
                                        callback=new_agent3_sub.callback)
    gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=g1_topic,
                                       headers=None, message="Test G1 Message")
    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=g2_topic,
                                       headers=None, message="Test G2 Message")
    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=g3_topic,
                                       headers=None, message="Test G3 Message")
    gevent.sleep(1)

    assert new_agent1_sub.callback.call_count == 3
    assert new_agent2_sub.callback.call_count == 2
    assert new_agent3_sub.callback.call_count == 1


@pytest.mark.pubsub
def test_incorrect_topic(publisher_agent, subscriber_agent):
    subscriber_agent.callback.reset_mock()
    gevent.sleep(0.2)

    test_topic = "testtopic1/test/foo/bar"

    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                                          prefix='incorrecttopic',
                                          callback=subscriber_agent.callback)
    gevent.sleep(.5)

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=test_topic,
                                       headers=None, message="Test message")
    gevent.sleep(.5)

    # Should get messages from the topic that has messages being published but not from the topic that
    # does not have messages being published
    assert subscriber_agent.callback.call_count == 1


@pytest.mark.pubsub
def test_unsubscribe(publisher_agent, subscriber_agent):
    subscriber_agent.callback.reset_mock()

    test_topic = "testtopic1/test/foo/bar"

    # Messages should be recieved by new_agent1 since it has subscribed to test_topic
    for i in range(0, 5):
        publisher_agent.vip.pubsub.publish(peer="pubsub", topic=test_topic,
                                           headers=None, message="Test message")
        gevent.sleep(0.01)
        print("count:{}".format(i))

    gevent.sleep(0.5)
    subscriber_agent.vip.pubsub.unsubscribe(peer='pubsub', prefix=test_topic,
                                            callback=subscriber_agent.callback)
    gevent.sleep(0.5)

    # Since agent has unsubscribed from test_topic, these messages should not be recieved
    for x in range(0, 5):
        publisher_agent.vip.pubsub.publish(peer="pubsub", topic=test_topic,
                                           headers=None, message="Test message")
        gevent.sleep(0.01)

    assert subscriber_agent.callback.call_count <= 5


@pytest.mark.pubsub
def test_irrelevant_unsubscribe(subscriber_agent):
    subscriber_agent.wrong_callback = MagicMock(name="wrong_callback")
    subscriber_agent.wrong_callback.reset_mock()

    not_subscribed_topic = "testtopic1/not/subscribed"

    # Agent has never subscribed to this topic but is attempting to unsubscribe anyway
    # Nothing should happen as a result
    subscriber_agent.vip.pubsub.unsubscribe(peer='pubsub',
                                            prefix=not_subscribed_topic,
                                            callback=subscriber_agent.wrong_callback)
    gevent.sleep(0.01)

    for i in range(0, 5):
        subscriber_agent.vip.pubsub.publish(peer="pubsub",
                                            topic=not_subscribed_topic,
                                            headers=None,
                                            message="Test message")
        gevent.sleep(0.01)

    # Confirm that no messages were ever recieved from the not_subscribed_topic
    assert subscriber_agent.wrong_callback.call_count == 0


@pytest.mark.pubsub
def test_list_subscribed(volttron_instance, request):
    new_agent1 = volttron_instance.build_agent(identity='agent1')

    def stop():
        new_agent1.core.stop()

    request.addfinalizer(stop)

    new_agent1.list_callback = MagicMock(name="list_callback")
    new_agent1.list_callback.reset_mock()

    prefix0 = "testtopic1/test/foo/bar"
    test_topic1 = "testtopic1/test/foo/bar/one"
    test_topic2 = "testtopic1/test/foo/bar/two"
    test_topic3 = "testtopic1/test/foo/bar/three"

    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic1,
                                    callback=new_agent1.list_callback)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic2,
                                    callback=new_agent1.list_callback)
    new_agent1.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic3,
                                    callback=new_agent1.list_callback)

    gevent.sleep(1)
    topic_result_index = 1
    member_result_index = 2

    list_results = new_agent1.vip.pubsub.list(peer='pubsub',
                                              prefix=prefix0,
                                              bus='',
                                              subscribed=True,
                                              reverse=False,
                                              all_platforms=False).get()

    for result in list_results:
        tup_topic = result[topic_result_index]
        assert tup_topic in [test_topic1, test_topic2, test_topic3]
        assert result[member_result_index]


@pytest.mark.pubsub
def test_list_subscribed_reverse(volttron_instance, request):
    new_agent2 = volttron_instance.build_agent(identity='agent2')

    def stop():
        new_agent2.core.stop()

    request.addfinalizer(stop)

    new_agent2.list_callback = MagicMock(name="list_callback")
    new_agent2.list_callback.reset_mock()

    topic_to_check = "testtopic1/test/foo/bar/one"
    test_topic1 = "testtopic1/test/foo/bar"
    test_topic2 = "testtopic1/test/foo"
    test_topic3 = "testtopic1"

    topic_result_index = 1
    member_result_index = 2

    new_agent2.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic1,
                                    callback=new_agent2.list_callback)
    new_agent2.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic2,
                                    callback=new_agent2.list_callback)
    new_agent2.vip.pubsub.subscribe(peer='pubsub', prefix=test_topic3,
                                    callback=new_agent2.list_callback)

    gevent.sleep(1)
    list_results = new_agent2.vip.pubsub.list(peer='pubsub',
                                              prefix=topic_to_check,
                                              bus='',
                                              subscribed=True,
                                              reverse=True,
                                              all_platforms=False).get()

    for result in list_results:
        topic = result[topic_result_index]
        assert topic in [test_topic1, test_topic2, test_topic3]
        assert result[member_result_index] is True


@pytest.mark.pubsub
def test_multi_unsubscribe(volttron_instance):
    subscriber_agent = volttron_instance.build_agent()
    subscriber_agent.subscription_callback = MagicMock(
        callback='subscription_callback')
    subscriber_agent.subscription_callback.reset_mock()

    # test unsubscribe all when there are no subscriptions
    subscriber_agent.vip.pubsub.unsubscribe("pubsub", prefix=None,
                                            callback=None)

    publisher_agent = volttron_instance.build_agent()

    topic_to_check = "testtopic1/test/foo/bar/one"
    test_topic1 = "testtopic1/test/foo/bar"
    test_topic2 = "testtopic1/test/foo"
    test_topic3 = "testtopic1"

    subscriber_agent.vip.pubsub.subscribe(
        peer='pubsub', prefix=test_topic1,
        callback=subscriber_agent.subscription_callback)
    subscriber_agent.vip.pubsub.subscribe(
        peer='pubsub', prefix=test_topic2,
        callback=subscriber_agent.subscription_callback)
    subscriber_agent.vip.pubsub.subscribe(
        peer='pubsub', prefix=test_topic3,
        callback=subscriber_agent.subscription_callback)
    gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer="pubsub",
                                       topic=topic_to_check,
                                       message="test message 1")
    gevent.sleep(1)

    assert subscriber_agent.subscription_callback.call_count == 3
    subscriber_agent.subscription_callback.reset_mock()

    subscriber_agent.vip.pubsub.unsubscribe("pubsub", prefix=None,
                                            callback=None)
    gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=topic_to_check,
                                       message="test message 3")
    gevent.sleep(1)

    assert subscriber_agent.subscription_callback.call_count == 0
