import gevent
import pytest
from mock import MagicMock
from volttron.platform.messaging import topics
from volttron.platform.messaging.headers import DATE
from volttron.platform.messaging.health import *
from volttron.platform.agent.utils import parse_timestamp_string
from volttrontesting.utils.utils import (poll_gevent_sleep,
                                         messages_contains_prefix)

from volttron.platform.vip.agent import PubSub

from volttron.platform.vip.agent import Agent


class _publish_from_handler_test_agent(Agent):
    def __init__(self, **kwargs):
        super(_publish_from_handler_test_agent, self).__init__(**kwargs)
        self.subscription_results = {}

    @PubSub.subscribe('pubsub', '')
    def onmessage(self, peer, sender, bus, topic, headers, message):
        self.subscription_results[topic] = {'headers': headers,
                                            'message': message}
        if not topic.startswith("testtopic2/test"):
            self.vip.pubsub.publish("pubsub", "testtopic2/test",
                                    headers={"foo": "bar"},
                                    message="Test message").get(timeout=2.0)

    def setup_callback(self, topic):
        self.vip.pubsub.subscribe(peer="pubsub", prefix=topic,
                                  callback=self.onmessage).get(timeout=2.0)

    def reset_results(self):
        self.subscription_results = {}


@pytest.mark.pubsub
def test_publish_from_message_handler(volttron_instance):
    """ Tests the ability to change a status by sending a different status
    code.

    This test also tests that the heartbeat is received.

    :param volttron_instance:
    :return:
    """
    test_topic = "testtopic1/test"
    new_agent1 = volttron_instance.build_agent(identity='test_publish1',
                                               agent_class=_publish_from_handler_test_agent)

    new_agent2 = volttron_instance.build_agent(identity='test_publish2')

    # new_agent1.setup_callback("")

    new_agent2.vip.pubsub.publish("pubsub", test_topic, headers={},
                                  message="Test message").get()

    poll_gevent_sleep(2, lambda: messages_contains_prefix(test_topic,
                                                          new_agent1.subscription_results))

    assert new_agent1.subscription_results[test_topic][
               "message"] == "Test message"


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

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=topic_to_check,
                                       message="test message 1")
    gevent.sleep(1)

    assert subscriber_agent.subscription_callback.call_count == 3
    subscriber_agent.subscription_callback.reset_mock()

    subscriber_agent.vip.pubsub.unsubscribe(peer='pubsub',
                                            prefix="testtopic1/test/foo/bar",
                                            callback=None)
    gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=topic_to_check,
                                       message="test message 2")
    gevent.sleep(1)

    assert subscriber_agent.subscription_callback.call_count == 2
    subscriber_agent.subscription_callback.reset_mock()

    subscriber_agent.vip.pubsub.unsubscribe("pubsub", prefix=None,
                                            callback=None)
    gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer="pubsub", topic=topic_to_check,
                                       message="test message 3")
    gevent.sleep(1)

    assert subscriber_agent.subscription_callback.call_count == 0
