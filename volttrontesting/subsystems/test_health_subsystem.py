import gevent
import pytest

from volttron.platform.messaging.health import *
from volttron.platform.agent.utils import parse_timestamp_string
from volttrontesting.utils.utils import (poll_gevent_sleep,
                                         messages_contains_prefix)

messages = {}


def onmessage(peer, sender, bus, topic, headers, message):
    global messages
    messages[topic] = {'headers': headers, 'message': message}


@pytest.mark.subsystems
def test_can_set_status(volttron_instance1):
    """ Tests the ability to change a status by sending a different status
    code.

    This test also tests that the heartbeat is received.

    :param volttron_instance1:
    :return:
    """
    new_agent = volttron_instance1.build_agent(identity='test_status')
    new_agent.vip.heartbeat.start()
    orig_status = new_agent.vip.health.get_status()
    assert orig_status[CURRENT_STATUS] == STATUS_GOOD
    assert orig_status[CONTEXT] is None
    assert orig_status[LAST_UPDATED] is not None
    print('original status: {}'.format(orig_status))
    new_context = {'foo': 'A test something when wrong',
                   'woah': ['blah', 'blah']}
    agent_prefix = 'heartbeat/Agent'
    new_agent.vip.pubsub.subscribe(peer='pubsub',
                                   prefix=agent_prefix, callback=onmessage)
    gevent.sleep(1)
    new_agent.vip.health.set_status(STATUS_BAD, new_context)
    poll_gevent_sleep(2, lambda: messages_contains_prefix(agent_prefix,
                                                          messages))
    new_status = new_agent.vip.health.get_status()
    print('new status: {}'.format(new_status))
    assert STATUS_BAD == new_status[CURRENT_STATUS]
    assert new_context == new_status[CONTEXT]
    assert new_status[LAST_UPDATED] is not None
    old_date = parse_timestamp_string(orig_status[LAST_UPDATED])
    new_date = parse_timestamp_string(new_status[LAST_UPDATED])
    assert old_date < new_date


@pytest.mark.subsystems
def test_invalid_status(volttron_instance1):
    """ Tests if a non-known status is sent then the sstatus is set to
    bad.

    :param volttron_instance1:
    :return:
    """
    new_agent = volttron_instance1.build_agent()
    new_agent.vip.heartbeat.start()
    orig_status = new_agent.vip.health.get_status()
    assert orig_status[CURRENT_STATUS] == STATUS_GOOD
    new_agent.vip.health.set_status('Bogus')
    assert STATUS_BAD == new_agent.vip.health.get_status()[CURRENT_STATUS]
