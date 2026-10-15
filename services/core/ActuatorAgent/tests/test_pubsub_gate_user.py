"""The pub/sub write gate judges the publisher's authenticated user, not the sender named in the message.

``sender`` is a routing name; the user is what the router authenticated. The schedule lock owner stays keyed on
``sender``. Handlers run against a mock agent that carries the real gate.
"""
from unittest.mock import MagicMock

import pytest

from actuator.agent import ActuatorAgent
from volttron.platform.agent.known_identities import ACTUATOR_CONTROL
from volttron.platform.messaging import topics

SET_ARGS = ('some.agent', 'dev/point', 1)
GRANTED = {ACTUATOR_CONTROL: None}


def _agent(grants, user, enable_auth=True):
    """A mock agent with the real gate; capabilities are looked up by user, and ``user`` is the delivered one."""
    agent = MagicMock()
    agent.core.enable_auth = enable_auth
    agent.vip.auth.get_capabilities.side_effect = lambda who: grants.get(who, {})
    agent.vip.pubsub.delivered_user.return_value = user
    agent._sender_may_write = lambda *args: ActuatorAgent._sender_may_write(agent, *args)
    return agent


def _call_set(agent, sender):
    ActuatorAgent.handle_set(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SET() + '/dev/point', {}, 1)


def _call_revert_point(agent, sender):
    ActuatorAgent.handle_revert_point(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_REVERT_POINT() + '/dev/point',
                                      {}, None)


def _call_revert_device(agent, sender):
    ActuatorAgent.handle_revert_device(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_REVERT_DEVICE() + '/dev',
                                       {}, None)


def _call_schedule_new(agent, sender):
    headers = {'type': 'NEW_SCHEDULE', 'taskID': 't', 'priority': 'LOW'}
    ActuatorAgent.handle_schedule_request(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SCHEDULE_REQUEST,
                                          headers, [['dev', 'a', 'b']])


def _call_schedule_cancel(agent, sender):
    headers = {'type': 'CANCEL_SCHEDULE', 'taskID': 't'}
    ActuatorAgent.handle_schedule_request(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SCHEDULE_REQUEST,
                                          headers, None)


# handler call, the private method it reaches when the gate passes, whether a refusal is a schedule result
HANDLERS = [
    pytest.param(_call_set, '_set_point', False, id='set'),
    pytest.param(_call_revert_point, '_revert_point', False, id='revert_point'),
    pytest.param(_call_revert_device, '_revert_device', False, id='revert_device'),
    pytest.param(_call_schedule_new, '_request_new_schedule', True, id='schedule_new'),
    pytest.param(_call_schedule_cancel, '_request_cancel_schedule', True, id='schedule_cancel'),
]


def _refused(agent, schedule):
    return agent.vip.pubsub.publish.called if schedule else agent._refuse_pubsub_write.called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_a_granted_sender_named_by_an_ungranted_user_is_refused(call, reaches, schedule):
    agent = _agent({'granted.agent': GRANTED}, user='attacker')
    call(agent, 'granted.agent')
    assert _refused(agent, schedule)
    assert not getattr(agent, reaches).called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_a_granted_user_passes_whatever_sender_the_message_names(call, reaches, schedule):
    agent = _agent({'granted.user': GRANTED}, user='granted.user')
    call(agent, 'other.name')
    assert getattr(agent, reaches).called
    assert not _refused(agent, schedule)


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_the_lock_owner_stays_the_sender(call, reaches, schedule):
    agent = _agent({'granted.user': GRANTED}, user='granted.user')
    call(agent, 'other.name')
    assert getattr(agent, reaches).call_args[0][0] == 'other.name'


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
@pytest.mark.parametrize("user", ['', None])
def test_an_empty_or_missing_user_is_refused(call, reaches, schedule, user):
    agent = _agent({'': GRANTED, 'granted.agent': GRANTED}, user=user)
    call(agent, 'granted.agent')
    assert _refused(agent, schedule)
    assert not getattr(agent, reaches).called


@pytest.mark.parametrize("user", ['', None])
def test_an_empty_user_is_refused_before_any_capability_lookup(user):
    agent = _agent({'': GRANTED}, user=user)
    assert ActuatorAgent._sender_may_write(agent, user, 'set_point', *SET_ARGS) is False
    agent.vip.auth.get_capabilities.assert_not_called()


def test_the_gate_looks_capabilities_up_by_the_user():
    agent = _agent({'the.user': GRANTED}, user='the.user')
    assert ActuatorAgent._sender_may_write(agent, 'the.user', 'set_point', *SET_ARGS) is True
    agent.vip.auth.get_capabilities.assert_called_once_with('the.user')


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_a_restricted_grant_is_read_from_the_user(call, reaches, schedule):
    restricted = {ACTUATOR_CONTROL: {'topic': 'never/matches'}}
    agent = _agent({'granted.agent': GRANTED, 'restricted.user': restricted}, user='restricted.user')
    call(agent, 'granted.agent')
    assert not getattr(agent, reaches).called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
@pytest.mark.parametrize("user", ['', None, 'attacker'])
def test_with_authentication_disabled_the_gate_is_skipped_as_before(call, reaches, schedule, user):
    agent = _agent({}, user=user, enable_auth=False)
    call(agent, 'any.name')
    assert getattr(agent, reaches).called
    assert not _refused(agent, schedule)
