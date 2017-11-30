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


class _publish_from_handler_test_agent(Agent):
    def __init__(self, **kwargs):
        super(_publish_from_handler_test_agent, self).__init__(**kwargs)
        self.subscription_results = {}

    @PubSub.subscribe('pubsub', '')
    def onmessage(self, peer, sender, bus, topic, headers, message):
        self.subscription_results[topic] = {'headers': headers, 'message': message}
        if not topic.startswith("testtopic2/test"):
            self.vip.pubsub.publish("pubsub", "testtopic2/test", headers={"foo": "bar"}, message="Test message").get(timeout=2.0)

    def setup_callback(self, topic):
        self.vip.pubsub.subscribe(peer="pubsub", prefix=topic, callback=self.onmessage).get(timeout=2.0)

    def reset_results(self):
        self.subscription_results = {}


@pytest.mark.subsystems
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

    #new_agent1.setup_callback("")

    new_agent2.vip.pubsub.publish("pubsub", test_topic, headers={}, message="Test message")

    poll_gevent_sleep(2, lambda: messages_contains_prefix(test_topic,
                                                          new_agent1.subscription_results))

    assert new_agent1.subscription_results[test_topic]["message"] == "Test message"



