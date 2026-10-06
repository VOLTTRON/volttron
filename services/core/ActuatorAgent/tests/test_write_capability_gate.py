"""Unit tests for the actuator's driver_write gate on the pub/sub interface.

The RPC methods are gated by @RPC.allow(DRIVER_WRITES); these tests exercise the helper that applies the same
rule to pub/sub senders, without a running platform.
"""
from unittest.mock import MagicMock

import pytest

from actuator.agent import ActuatorAgent
from volttron.platform.agent.known_identities import DRIVER_WRITES
from volttron.platform.vip.agent.subsystems.rpc import RPC


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
    assert ActuatorAgent._sender_may_write(agent, 'some.agent') is True
    agent.vip.auth.get_capabilities.assert_called_once_with('some.agent')


@pytest.mark.parametrize("capabilities", [None, {}, [], {'edit_config_store': {'identity': 'x'}}])
def test_sender_without_capability_is_refused(capabilities):
    assert ActuatorAgent._sender_may_write(_agent(capabilities=capabilities), 'some.agent') is False


def test_auth_disabled_skips_enforcement_like_the_rpc_gate():
    assert ActuatorAgent._sender_may_write(_agent(enable_auth=False, auth=False), 'some.agent') is True


def test_missing_auth_subsystem_fails_closed():
    assert ActuatorAgent._sender_may_write(_agent(auth=False), 'some.agent') is False


def test_capability_lookup_error_fails_closed():
    assert ActuatorAgent._sender_may_write(_agent(error=RuntimeError('boom')), 'some.agent') is False


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
