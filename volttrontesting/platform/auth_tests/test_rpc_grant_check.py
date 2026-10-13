"""Tests for the argument restrictions on a capability grant.

The RPC gate (RPC._add_auth_check) and the actuator's pub/sub gate both apply them through
grant_allows_call, so these tests pin the gate's verdicts and the shared function together.
"""
import re
import types
from unittest.mock import MagicMock

import pytest

from volttron.platform import jsonrpc
from volttron.platform.vip.agent.subsystems.rpc import RPC, grant_allows_call, grant_refusal

CAP = 'some_capability'


def target(requester_id, topic, value, point=None, **kwargs):
    return 'ran'


def _gate_verdict(grant, args=(), kwargs=None):
    """Run target through the real RPC gate with the caller holding CAP with ``grant``."""
    owner = MagicMock()
    owner.vip.auth.get_capabilities.return_value = {CAP: grant}
    rpc = object.__new__(RPC)
    rpc._enable_auth = True
    rpc._message_bus = 'zmq'
    rpc._owner = owner
    rpc.context = types.SimpleNamespace(vip_message=types.SimpleNamespace(user='s'))
    checked = rpc._add_auth_check(target, {CAP})
    try:
        return checked(*args, **(kwargs or {}))
    except Exception as ex:
        return ex


# grant, call args, whether the call is allowed
CASES = [
    pytest.param(None, ('s', 'dev/point', 1), True, id='no_restriction'),
    pytest.param({'topic': 'dev/point'}, ('s', 'dev/point', 1), True, id='exact_match'),
    pytest.param({'topic': 'dev/point'}, ('s', 'dev/other', 1), False, id='exact_mismatch'),
    pytest.param({'topic': '/dev/.*/'}, ('s', 'dev/point', 1), True, id='regex_match'),
    pytest.param({'topic': '/dev/.*/'}, ('s', 'other/dev/point', 1), False, id='regex_prefix_refused'),
    pytest.param({'topic': '/dev/.*/'}, ('s', 'dev/point\n', 1), False, id='regex_trailing_newline_refused'),
    pytest.param({'topic': '/dev|other/'}, ('s', 'other', 1), True, id='regex_alternative_whole_string'),
    pytest.param({'topic': '/dev|other/'}, ('s', 'xother', 1), False, id='regex_alternative_anchored'),
    pytest.param({'path': 'devA'}, ('s', 'dev/point', 1), False, id='missing_parameter_refused'),
    pytest.param({'requester_id': 's', 'topic': 'dev/point'}, ('s', 'dev/point', 1), True, id='two_restrictions'),
    pytest.param({'requester_id': 't', 'topic': 'dev/point'}, ('s', 'dev/point', 1), False, id='one_of_two_fails'),
    pytest.param({'topic': 'dev/point'}, ('s', 'dev/point', 1, 'p'), True, id='positional_extra_arg'),
    pytest.param({'value': 1}, ('s', 'dev/point', 1), True, id='non_string_value_match'),
    pytest.param({'value': 2}, ('s', 'dev/point', 1), False, id='non_string_value_mismatch'),
]


@pytest.mark.parametrize("grant, args, allowed", CASES)
def test_rpc_gate_verdict(grant, args, allowed):
    result = _gate_verdict(grant, args)
    assert (result == 'ran') is allowed
    if not allowed:
        assert isinstance(result, Exception)


def test_rpc_gate_applies_keyword_arguments():
    assert _gate_verdict({'topic': 'dev/point'}, ('s',), {'topic': 'dev/point', 'value': 1}) == 'ran'
    refused = _gate_verdict({'topic': 'dev/point'}, ('s',), {'topic': 'dev/x', 'value': 1})
    assert isinstance(refused, Exception)


@pytest.mark.parametrize("grant, args, allowed", [c.values[:3] for c in CASES if c.values[0]])
def test_grant_allows_call_agrees_with_the_gate(grant, args, allowed):
    assert grant_allows_call(grant, target, args, {}) is allowed


def test_grant_refusal_names_the_parameter_and_value():
    reason = grant_refusal({'topic': 'dev/point'}, target, ('s', 'dev/x', 1), {})
    assert reason == ("can call method target only with topic=dev/point but called with topic=dev/x")
    reason = grant_refusal({'topic': '/dev.*/'}, target, ('s', 'x', 1), {})
    assert reason == ("can call method target only with topic matching pattern /dev.*/ but called with topic=x")
    reason = grant_refusal({'nope': 'x'}, target, ('s', 'x', 1), {})
    assert reason == "capability is not defined properly. method target does not have a parameter nope"


def test_gate_error_message_is_unchanged():
    result = _gate_verdict({'topic': 'dev/point'}, ('s', 'dev/x', 1))
    assert "User s can call method target only with topic=dev/point but called with topic=dev/x" in str(result)


# A grant that cannot be evaluated refuses, with a reason, instead of raising out of the check.
MALFORMED = [
    pytest.param({'topic': '/[/'}, id='invalid_regex'),
    pytest.param(['topic'], id='list_restriction'),
    pytest.param('topic', id='string_restriction'),
]


@pytest.mark.parametrize("grant", MALFORMED)
def test_malformed_grant_is_refused_with_a_reason(grant):
    assert grant_allows_call(grant, target, ('s', 'dev/point', 1), {}) is False
    assert grant_refusal(grant, target, ('s', 'dev/point', 1), {})


@pytest.mark.parametrize("grant", MALFORMED)
def test_rpc_gate_refuses_a_malformed_grant_as_unauthorized(grant):
    result = _gate_verdict(grant, ('s', 'dev/point', 1))
    assert isinstance(result, jsonrpc.Error) and result.code == jsonrpc.UNAUTHORIZED
    assert not isinstance(result, (AttributeError, re.error))
    assert 'malformed' in str(result) or 'not defined properly' in str(result)


def test_non_string_argument_against_a_regex_is_refused():
    assert grant_allows_call({'topic': '/dev.*/'}, target, ('s', 5, 1), {}) is False
