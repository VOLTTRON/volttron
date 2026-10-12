"""Unit tests for the actuator's driver_write gate on the pub/sub interface.

The RPC methods are gated by @RPC.allow(DRIVER_WRITES); these tests exercise the helper that applies the same
rule to pub/sub senders, without a running platform.
"""
import inspect
import types
from unittest.mock import MagicMock

import gevent
import pytest

from actuator.agent import ActuatorAgent
from volttron.platform.agent.known_identities import DRIVER_WRITES
from volttron.platform.messaging import topics
from volttron.platform.vip.agent.subsystems.rpc import RPC

SET_ARGS = ('some.agent', 'dev/point', 1)


def _agent(enable_auth=True, auth=True, capabilities=None, error=None):
    agent = MagicMock(spec=[])
    agent.core = MagicMock()
    agent.core.enable_auth = enable_auth
    agent.vip = MagicMock(spec=['auth'] if auth else [])
    if auth:
        if error:
            agent.vip.auth.get_capabilities.side_effect = error
        else:
            agent.vip.auth.get_capabilities.return_value = capabilities
    return agent


def _gated_agent(grants):
    """A mock agent whose gate is the real _sender_may_write, with capabilities looked up by sender."""
    agent = MagicMock()
    agent.core.enable_auth = True
    agent.vip.auth.get_capabilities.side_effect = lambda who: grants.get(who, {})
    agent._sender_may_write = lambda *args: ActuatorAgent._sender_may_write(agent, *args)
    return agent


@pytest.mark.parametrize("method", ['set_point', 'set_multiple_points', 'revert_point', 'revert_device',
                                    'request_new_schedule', 'request_cancel_schedule'])
def test_write_and_schedule_rpcs_require_driver_write(method):
    annotations = getattr(getattr(ActuatorAgent, method), '_annotations', {})
    assert annotations.get('rpc.allow_capabilities') == {DRIVER_WRITES}


@pytest.mark.parametrize("method", ['get_point', 'get_multiple_points', 'scrape_all'])
def test_read_rpcs_stay_open(method):
    annotations = getattr(getattr(ActuatorAgent, method), '_annotations', {})
    assert not annotations.get('rpc.allow_capabilities')


def test_sender_with_capability_may_write():
    agent = _agent(capabilities={DRIVER_WRITES: None, 'edit_config_store': {'identity': 'x'}})
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is True
    agent.vip.auth.get_capabilities.assert_called_once_with('some.agent')


@pytest.mark.parametrize("capabilities", [None, {}, [], {'edit_config_store': {'identity': 'x'}}])
def test_sender_without_capability_is_refused(capabilities):
    agent = _agent(capabilities=capabilities)
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is False


def test_auth_disabled_skips_enforcement_like_the_rpc_gate():
    agent = _agent(enable_auth=False, auth=False)
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is True


@pytest.mark.parametrize("enable_auth", [0, None, '', 'false', []])
def test_only_a_real_false_skips_enforcement_like_the_rpc_gate(enable_auth):
    agent = _agent(enable_auth=enable_auth, auth=False)
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is False


def test_missing_auth_subsystem_fails_closed():
    agent = _agent(auth=False)
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is False


def test_capability_lookup_error_fails_closed():
    agent = _agent(error=RuntimeError('boom'))
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is False


def test_capability_lookup_timeout_fails_closed():
    # gevent.Timeout is a BaseException, so `except Exception` does not catch it.
    agent = _agent(error=gevent.Timeout())
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', 'set_point', *SET_ARGS) is False


# method name, arguments after the requester, a parameter the grant may restrict, its matching value
RESTRICTABLE = [
    ('set_point', ('dev/point', 1), 'topic', 'dev/point'),
    ('revert_point', ('dev/point',), 'topic', 'dev/point'),
    ('revert_device', ('dev',), 'topic', 'dev'),
    ('request_new_schedule', ('task', 'LOW', [['dev', 'a', 'b']]), 'task_id', 'task'),
    ('request_cancel_schedule', ('task',), 'task_id', 'task'),
]


@pytest.mark.parametrize("method, args, param, value", RESTRICTABLE)
def test_restricted_grant_that_matches_is_honored(method, args, param, value):
    agent = _agent(capabilities={DRIVER_WRITES: {param: value}})
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', method, 'some.agent', *args) is True


@pytest.mark.parametrize("method, args, param, value", RESTRICTABLE)
def test_restricted_grant_that_does_not_match_is_refused(method, args, param, value):
    agent = _agent(capabilities={DRIVER_WRITES: {param: value + '-other'}})
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', method, 'some.agent', *args) is False


@pytest.mark.parametrize("method, args, param, value", RESTRICTABLE)
def test_restricted_grant_on_a_parameter_the_method_lacks_is_refused(method, args, param, value):
    agent = _agent(capabilities={DRIVER_WRITES: {'path': 'devA'}})
    assert ActuatorAgent._sender_may_write(agent, 'some.agent', method, 'some.agent', *args) is False


def test_restricted_grant_matches_regex_with_fullmatch():
    agent = _agent(capabilities={DRIVER_WRITES: {'topic': '/dev/.*/'}})
    assert ActuatorAgent._sender_may_write(agent, 's', 'set_point', 's', 'dev/point', 1) is True
    assert ActuatorAgent._sender_may_write(agent, 's', 'set_point', 's', 'other/dev/point', 1) is False
    assert ActuatorAgent._sender_may_write(agent, 's', 'set_point', 's', 'dev/point\n', 1) is False


@pytest.mark.parametrize("grant, args", [
    ({'topic': 'dev/point'}, ('s', 'dev/point', 1)),
    ({'topic': 'dev/point'}, ('s', 'dev/other', 1)),
    ({'topic': '/dev/.*/'}, ('s', 'dev/point', 1)),
    ({'topic': '/dev/.*/'}, ('s', 'other/point', 1)),
    ({'topic': '/dev/.*/'}, ('s', 'dev/point\n', 1)),
    ({'topic': '/dev/.*/'}, ('s', 5, 1)),
    ({'path': 'devA'}, ('s', 'dev/point', 1)),
    ({'requester_id': 's'}, ('s', 'dev/point', 1)),
    ({'requester_id': 't'}, ('s', 'dev/point', 1)),
    (None, ('s', 'dev/point', 1)),
])
def test_pubsub_gate_agrees_with_the_rpc_gate(grant, args):
    """Same grant, same method and arguments: the pub/sub verdict equals what @RPC.allow does."""
    def set_point(self, requester_id, topic, value, point=None, **kwargs):
        return 'ran'

    # The stub must keep the signature the RPC gate binds arguments against.
    assert inspect.signature(set_point) == inspect.signature(ActuatorAgent.set_point)

    capabilities = {DRIVER_WRITES: grant}
    owner = _agent(capabilities=capabilities)
    rpc = object.__new__(RPC)
    rpc._enable_auth = True
    rpc._message_bus = 'zmq'
    rpc._owner = owner
    rpc.context = types.SimpleNamespace(vip_message=types.SimpleNamespace(user='s'))
    checked = rpc._add_auth_check(types.MethodType(set_point, object()), {DRIVER_WRITES})
    try:
        rpc_allows = checked(*args) == 'ran'
    except Exception:
        rpc_allows = False

    assert ActuatorAgent._sender_may_write(owner, 's', 'set_point', *args) is rpc_allows


def test_refused_pubsub_write_publishes_unauthorized_error():
    agent = MagicMock()
    agent._get_headers.return_value = {'requesterID': 'some.agent'}
    ActuatorAgent._refuse_pubsub_write(agent, 'some.agent', 'dev/point')
    prefix, point, headers, error = agent._push_result_topic_pair.call_args[0]
    assert point == 'dev/point'
    assert error['type'] == 'Unauthorized' and DRIVER_WRITES in error['value']


def test_handle_set_refuses_before_touching_the_driver():
    agent = MagicMock()
    agent._sender_may_write.return_value = False
    ActuatorAgent.handle_set(agent, 'pubsub', 'no.cap', 'bus', 'devices/actuators/set/dev/point', {}, 1)
    agent._refuse_pubsub_write.assert_called_once_with('no.cap', 'dev/point')
    agent._set_point.assert_not_called()


def test_handle_schedule_request_refuses_with_failure_result():
    agent = MagicMock()
    agent._sender_may_write.return_value = False
    headers = {'type': 'NEW_SCHEDULE', 'taskID': 't', 'priority': 'LOW'}
    result = ActuatorAgent.handle_schedule_request(agent, 'pubsub', 'no.cap', 'bus',
                                                   'devices/actuators/schedule/request', headers, [['dev', 'a', 'b']])
    assert result['result'] == 'FAILURE' and DRIVER_WRITES in result['info']
    agent._request_new_schedule.assert_not_called()
    agent.vip.pubsub.publish.assert_called_once()


def _call_set(agent, sender, headers):
    ActuatorAgent.handle_set(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SET() + '/dev/point', headers, 1)


def _call_revert_point(agent, sender, headers):
    ActuatorAgent.handle_revert_point(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_REVERT_POINT() + '/dev/point',
                                      headers, None)


def _call_revert_device(agent, sender, headers):
    ActuatorAgent.handle_revert_device(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_REVERT_DEVICE() + '/dev',
                                       headers, None)


def _call_schedule_new(agent, sender, headers):
    headers = dict(headers, type='NEW_SCHEDULE', taskID='t', priority='LOW')
    ActuatorAgent.handle_schedule_request(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SCHEDULE_REQUEST,
                                          headers, [['dev', 'a', 'b']])


def _call_schedule_cancel(agent, sender, headers):
    headers = dict(headers, type='CANCEL_SCHEDULE', taskID='t')
    ActuatorAgent.handle_schedule_request(agent, 'pubsub', sender, 'bus', topics.ACTUATOR_SCHEDULE_REQUEST,
                                          headers, None)


# handler call, the private method it reaches when the sender may write, whether it refuses with a schedule result
HANDLERS = [
    pytest.param(_call_set, '_set_point', False, id='set'),
    pytest.param(_call_revert_point, '_revert_point', False, id='revert_point'),
    pytest.param(_call_revert_device, '_revert_device', False, id='revert_device'),
    pytest.param(_call_schedule_new, '_request_new_schedule', True, id='schedule_new'),
    pytest.param(_call_schedule_cancel, '_request_cancel_schedule', True, id='schedule_cancel'),
]


def _refused(agent, schedule):
    if schedule:
        return agent.vip.pubsub.publish.called
    return agent._refuse_pubsub_write.called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_handler_without_capability_is_refused_and_does_not_reach_the_driver(call, reaches, schedule):
    agent = _gated_agent({})
    call(agent, 'no.cap', {})
    assert _refused(agent, schedule)
    assert not getattr(agent, reaches).called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_handler_with_capability_reaches_the_driver(call, reaches, schedule):
    agent = _gated_agent({'granted': {DRIVER_WRITES: None}})
    call(agent, 'granted', {})
    assert getattr(agent, reaches).called
    assert not _refused(agent, schedule)


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_gate_uses_the_bus_sender_not_the_requester_header(call, reaches, schedule):
    # An ungranted sender cannot borrow a granted identity through the requesterID header.
    agent = _gated_agent({'granted': {DRIVER_WRITES: None}})
    call(agent, 'ungranted', {'requesterID': 'granted'})
    assert _refused(agent, schedule)
    assert not getattr(agent, reaches).called


@pytest.mark.parametrize("call, reaches, schedule", HANDLERS)
def test_gate_ignores_an_ungranted_requester_header_on_a_granted_sender(call, reaches, schedule):
    agent = _gated_agent({'granted': {DRIVER_WRITES: None}})
    call(agent, 'granted', {'requesterID': 'ungranted'})
    assert getattr(agent, reaches).called
    assert getattr(agent, reaches).call_args[0][0] == 'granted'
    assert not _refused(agent, schedule)


# handler call, reached method, the arguments the handler passes to the RPC gate as (parameter, value) pairs
HANDLER_ARGS = [
    (_call_set, '_set_point', False, 'requester_id', 's'),
    (_call_set, '_set_point', False, 'topic', 'dev/point'),
    (_call_set, '_set_point', False, 'value', 1),
    (_call_revert_point, '_revert_point', False, 'topic', 'dev/point'),
    (_call_revert_device, '_revert_device', False, 'topic', 'dev'),
    (_call_schedule_new, '_request_new_schedule', True, 'task_id', 't'),
    (_call_schedule_new, '_request_new_schedule', True, 'priority', 'LOW'),
    (_call_schedule_new, '_request_new_schedule', True, 'requests', ['dev', 'a', 'b']),
    (_call_schedule_cancel, '_request_cancel_schedule', True, 'task_id', 't'),
]


@pytest.mark.parametrize("call, reaches, schedule, param, value", HANDLER_ARGS)
def test_handler_passes_its_real_arguments_to_a_restricted_grant(call, reaches, schedule, param, value):
    allowed = _gated_agent({'s': {DRIVER_WRITES: {param: value}}})
    call(allowed, 's', {})
    assert getattr(allowed, reaches).called
    assert not _refused(allowed, schedule)

    refused = _gated_agent({'s': {DRIVER_WRITES: {param: 'not-' + str(value)}}})
    call(refused, 's', {})
    assert not getattr(refused, reaches).called
    assert _refused(refused, schedule)


def test_handle_set_refuses_after_a_capability_lookup_timeout():
    agent = _gated_agent({})
    agent.vip.auth.get_capabilities.side_effect = gevent.Timeout()
    _call_set(agent, 's', {})
    agent._refuse_pubsub_write.assert_called_once_with('s', 'dev/point')
    assert not agent._set_point.called
