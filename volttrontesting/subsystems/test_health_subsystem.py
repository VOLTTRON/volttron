import gevent
import pytest

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


@pytest.mark.subsystems
@pytest.mark.xfail(reason="Need to upgrade")
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
    orig_status = Status.from_json(new_agent.vip.health.get_status())
    assert orig_status.status == STATUS_GOOD
    assert orig_status.context is None
    assert orig_status.last_updated is not None
    print('original status: {}'.format(orig_status.as_json()))
    new_context = {'foo': 'A test something when wrong',
                   'woah': ['blah', 'blah']}
    agent_prefix = 'heartbeat/Agent'
    new_agent.vip.pubsub.subscribe(peer='pubsub',
                                   prefix=agent_prefix, callback=onmessage)
    gevent.sleep(1)
    new_agent.vip.health.set_status(STATUS_BAD, new_context)
    poll_gevent_sleep(2, lambda: messages_contains_prefix(agent_prefix,
                                                          subscription_results))
    new_status = Status.from_json(new_agent.vip.health.get_status())
    print('new status: {}'.format(new_status.as_json()))
    assert new_status.status == STATUS_BAD
    assert new_status.context == new_context
    assert new_status.last_updated is not None

    print("OLD IS: {}".format(orig_status.last_updated))
    print("NEW IS: {}".format(new_status.last_updated))
    old_date = parse_timestamp_string(orig_status.last_updated)
    new_date = parse_timestamp_string(new_status.last_updated)
    assert old_date < new_date


@pytest.mark.subsystems
@pytest.mark.xfail(reason="Need to upgrade")
def test_invalid_status(volttron_instance):
    """ Tests if a non-known status is sent then the sstatus is set to
    bad.

    :param volttron_instance:
    :return:
    """
    global subscription_results
    subscription_results.clear()
    new_agent = volttron_instance.build_agent()
    new_agent.vip.heartbeat.start()
    orig_status = Status.from_json(new_agent.vip.health.get_status())
    assert orig_status.status == STATUS_GOOD
    with pytest.raises(ValueError):
        new_agent.vip.health.set_status('Bogus')
    # new_status =Status.from_json(new_agent.vip.health.get_status())
    # assert STATUS_BAD == new_status.status


@pytest.mark.subsystems
@pytest.mark.xfail(reason="Need to upgrade")
def test_heartbeat_sending_status(volttron_instance):
    """ Tests the heartbeat message that it has the status.

    :param volttron_instance:
    :return:
    """
    global subscription_results
    subscription_results.clear()
    agent_prefix = 'heartbeat/Agent'
    new_agent = volttron_instance.build_agent(identity='test3')
    orig_status = Status.from_json(new_agent.vip.health.get_status())
    new_agent.vip.pubsub.subscribe(peer='pubsub',
                                   prefix=agent_prefix, callback=onmessage)
    new_agent.vip.heartbeat.start()
    poll_gevent_sleep(2, lambda: messages_contains_prefix(agent_prefix,
                                                          subscription_results))
    message = subscription_results[agent_prefix]['message']
    headers = subscription_results[agent_prefix]['headers']
    d = Status.from_json(message)
    assert headers[DATE] is not None
    assert d.last_updated is not None
    assert orig_status.status == d.status
    assert orig_status.context == d.context


@pytest.mark.subsystems
@pytest.mark.xfail(reason="Need to upgrade")
def test_alert_publish(volttron_instance):
    """ Tests the heartbeat message that it has the status.

    :param volttron_instance:
    :return:
    """
    global subscription_results
    subscription_results.clear()
    alert_prefix = 'alerts'
    new_agent = volttron_instance.build_agent(identity='alert1')
    status = Status.build(BAD_STATUS, "Too many connections!")
    new_agent.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='', callback=onmessage)
    gevent.sleep(0.3)
    orig_status = new_agent.vip.health.send_alert("too_many", status)
    poll_gevent_sleep(2, lambda: messages_contains_prefix(alert_prefix,
                                                          subscription_results))
    print("THE SUBSCRIPTIONS ARE: {}".format(subscription_results))
    if not messages_contains_prefix(alert_prefix, subscription_results):
        pytest.fail('prefix not found')

    headers = subscription_results['alerts/Agent']['headers']
    message = subscription_results['alerts/Agent']['message']

    assert "too_many", headers['alert_key']
    passed_status = Status.from_json(message)
    assert status.status == passed_status.status
    assert status.context == passed_status.context
    assert status.last_updated == passed_status.last_updated


