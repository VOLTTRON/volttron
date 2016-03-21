import pytest
import gevent
import time

from volttron.platform.vip.agent import Agent, PubSub, Core

agent_dir = "services/core/MasterDriverAgent"
MAX_WAIT_TIME = 20

class Failover(object):
    def __init__(self, instance, config):
        self.instance = instance
        self.uuid_listener = self.build_listener()
        self.uuid_master = self.build_master(config)
        self.messages = {}

    def _save_message(self, peer, sender, bus, topic, headers, message):
        self.messages[topic] = message

    def build_listener(self):
        uuid = self.instance.build_agent()
        uuid.vip.pubsub.subscribe(peer='pubsub', prefix='', callback=self._save_message)
        return uuid

    def build_master(self, config):
        uuid = self.instance.install_agent(agent_dir=agent_dir, config_file=agent_dir + config)
        assert uuid is not None
        return uuid

    def stop_master(self):
        self.instance.stop_agent(self.uuid_master)

    def time_delay(self):
        m = self.messages
        m.clear()
        assert not m.keys()

        publish_delay = 0
        time_start = time.time()
        while not m.keys() and time.time() < time_start + MAX_WAIT_TIME:
            gevent.sleep(1)
            publish_delay += 1

        return publish_delay

    def is_publishing(self):
        return self.time_delay() < MAX_WAIT_TIME


@pytest.fixture
def failover_primary(request, volttron_instance1):
    p = Failover(volttron_instance1,"/tests/config0")
    def cleanup():
        p.instance.stop_agent(p.uuid_master)
        p.instance.remove_agent(p.uuid_master)
    request.addfinalizer(cleanup)
    return p


@pytest.fixture
def failover_secondary(request, volttron_instance2):
    s = Failover(volttron_instance2,"/tests/config1")
    def cleanup():
        s.instance.stop_agent(s.uuid_master)
        s.instance.remove_agent(s.uuid_master)
    request.addfinalizer(cleanup)
    return s


def test_failover_publish_delay(failover_primary, failover_secondary):
    primary = failover_primary
    secondary = failover_secondary

    primary_msg_delay = primary.time_delay()
    assert primary.messages.keys()

    secondary_msg_delay = secondary.time_delay()
    assert secondary.messages.keys()

    # there should be a five second delay beween publishes
    assert abs(secondary_msg_delay - primary_msg_delay) == 5
    assert True


def test_failure_does_not_cascade(failover_primary, failover_secondary):
    primary = failover_primary
    secondary = failover_secondary

    assert primary.is_publishing()
    assert secondary.is_publishing()

    primary.stop_master()
    assert not primary.is_publishing()

    assert secondary.is_publishing()
    assert True
