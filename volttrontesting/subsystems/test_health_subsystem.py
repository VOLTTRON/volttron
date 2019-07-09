import gevent
import pytest

from mock import MagicMock

from volttron.platform.messaging import topics
from volttron.platform.messaging.headers import DATE
from volttron.platform.messaging.health import *
from volttron.platform.agent.utils import parse_timestamp_string
from volttrontesting.utils.utils import (poll_gevent_sleep,
                                         messages_contains_prefix)

subscription_results = {}


def onmessage(peer, sender, bus, topic, headers, message):
    global subscription_results
    subscription_results[topic] = {'headers': headers, 'message': message}
    print("subscription_results[{}] = {}".format(topic, subscription_results[topic]))


@pytest.fixture(scope="module")
def alert_watcher_agent(volttron_instance):
    alert_watcher = volttron_instance.build_agent()

    alert_watcher.alert_callback = MagicMock(name="callback")
    alert_watcher.alert_callback.reset_mock()

    alerts_topic = "alerts"
    # Agent subscribes to both the desired topic and a topic that is not going to ever be published
    alert_watcher.vip.pubsub.subscribe(peer='pubsub', prefix=alerts_topic, callback=alert_watcher.alert_callback)

    yield alert_watcher

    alert_watcher.core.stop()


@pytest.fixture(scope="module")
def alerting_agent(volttron_instance):
    alerting_agent = volttron_instance.build_agent(identity='alerting.agent')
    yield alerting_agent
    alerting_agent.core.stop()


@pytest.mark.subsystems
@pytest.mark.health
def test_can_set_status(volttron_instance):
    """ Tests the ability to change a status by sending a different status
    code.

    This test also tests that the heartbeat is received.

    :param volttron_instance:
    :return:
    """
    global subscription_results
    subscription_results.clear()
    new_agent = volttron_instance.build_agent(identity='test_status')
    new_agent.vip.heartbeat.start()
    orig_status = new_agent.vip.health.get_status()
    assert orig_status["status"] == STATUS_GOOD
    assert orig_status["context"] is None
    assert orig_status["last_updated"] is not None
    print('original status: {}'.format(orig_status))
    new_context = {'foo': 'A test something when wrong',
                   'woah': ['blah', 'blah']}
    agent_prefix = 'heartbeat/Agent'
    new_agent.vip.pubsub.subscribe(peer='pubsub',
                                   prefix=agent_prefix, callback=onmessage)
    gevent.sleep(1)
    new_agent.vip.health.set_status(STATUS_BAD, new_context)
    poll_gevent_sleep(2, lambda: messages_contains_prefix(agent_prefix,
                                                          subscription_results))
    new_status = new_agent.vip.health.get_status()
    print('new status: {}'.format(new_status))
    assert new_status["status"] == STATUS_BAD
    assert new_status["context"] == new_context
    assert new_status["last_updated"] is not None

    print("OLD IS: {}".format(orig_status["last_updated"]))
    print("NEW IS: {}".format(new_status["last_updated"]))
    old_date = parse_timestamp_string(orig_status["last_updated"])
    new_date = parse_timestamp_string(new_status["last_updated"])
    assert old_date < new_date


@pytest.mark.subsystems
@pytest.mark.health
def test_invalid_status(volttron_instance):
    """ Tests if a non-known status is sent then the sstatus is set to
    bad.

    :param volttron_instance:
    :return:
    """
    global subscription_results
    subscription_results.clear()
    new_agent = volttron_instance.build_agent(identity='test_status2')
    new_agent.vip.heartbeat.start()
    orig_status = new_agent.vip.health.get_status()
    assert orig_status["status"] == STATUS_GOOD
    with pytest.raises(ValueError):
        new_agent.vip.health.set_status('Bogus')


@pytest.mark.subsystems
@pytest.mark.heartbeat
def test_heartbeat_sending_status(volttron_instance):
    """ Tests the heartbeat message that it has the status.

    :param volttron_instance:
    :return:
    """
    heartbeat_agent = volttron_instance.build_agent(identity='heartbeat_agent')
    heartbeat_watcher = volttron_instance.build_agent(identity='heartbeat_watcher')
    try:
        heartbeat_watcher.callback_heartbeat = MagicMock(name='callback')
        heartbeat_watcher.callback_heartbeat.reset_mock()
        heartbeat_watcher.vip.pubsub.subscribe(peer='pubsub', prefix='heartbeat',
                                               callback=heartbeat_watcher.callback_heartbeat).get()
        gevent.sleep(0.1)
        heartbeat_agent.vip.heartbeat.enabled = True
        heartbeat_agent.vip.heartbeat.start_with_period(2)
        gevent.sleep(0.1)
        heartbeat_watcher.callback_heartbeat.assert_called_once()
        heartbeat_watcher.callback_heartbeat.reset_mock()
        gevent.sleep(2)
        heartbeat_watcher.callback_heartbeat.assert_called_once()

        args = heartbeat_watcher.callback_heartbeat.call_args[0]
        # args[5] is the message sent during the heartbeat, if it is OK then the word GOOD (STATUS_GOOD)
        assert STATUS_GOOD == args[5]

    finally:
        heartbeat_watcher.core.stop()
        heartbeat_agent.core.stop()


@pytest.mark.subsystems
@pytest.mark.alert
def test_alert_publish(volttron_instance, alert_watcher_agent, alerting_agent):
    """ Tests the heartbeat message that it has the status.

    :param volttron_instance:
    :return:
    """

    try:
        # pubsub topics always have the following signature
        # peer, sender, bus,  topic, headers, message
        # so the arugments taht should be passed to the alert callback should be the following
        alerting_agent.vip.health.send_alert("Foo/Bar", Status.build(STATUS_BAD))
        gevent.sleep(0.1)
        assert alert_watcher_agent.alert_callback.call_count == 1
        alert_watcher_agent.alert_callback.assert_called_once()
        args = alert_watcher_agent.alert_callback.call_args[0]
        # Peer
        assert 'pubsub' == args[0]
        # sender (i.e. the agent that is alerting)
        assert alerting_agent.core.identity == args[1]
        # topic (note topic now has _ instead of dots
        expected_topic = 'alerts/Agent/{}.{}'.format(volttron_instance.instance_name, alerting_agent.core.identity)
        expected_topic = expected_topic.replace('.', '_')
        assert expected_topic == args[3]
        # header
        assert 'alert_key' in args[4]
        assert 'Foo/Bar' == args[4]['alert_key']
        # message
        status = Status.from_json(args[5])
        assert status.context is None
        assert status.status == 'BAD'
        assert status.last_updated is not None

    finally:
        alert_watcher_agent.alert_callback.reset_mock()



