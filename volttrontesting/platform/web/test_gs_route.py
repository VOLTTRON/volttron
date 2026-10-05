# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
"""The /gs JSON-RPC gateway accepts only POST requests from admin users, for a
fixed set of read-only control queries, and calls nothing on any refusal."""

import json
from unittest.mock import MagicMock

import gevent
import pytest

from volttron.platform import jsonapi
from volttron.platform.control.control import ControlService
from volttron.platform.jsonrpc import INVALID_REQUEST, UNAUTHORIZED, RemoteError
from volttron.platform.vip.agent import Unreachable
from volttron.platform.vip.agent.decorators import annotations
from volttron.platform.web import NotAuthorized
from volttron.platform.web.platform_web_service import PlatformWebService
from volttrontesting.utils.web_utils import get_test_web_env

ADMIN = {'groups': ['admin']}
TOKEN = 'TOKEN-MARK'


def _service(claims=ADMIN, result=None):
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    value = result if result is not None else ['an-agent']
    pending = svc.vip.rpc.call.return_value
    pending.ready.return_value = True
    pending.get.return_value = value
    svc.vip.rpc.return_value.get.return_value = value
    if isinstance(claims, BaseException):
        svc.get_user_claims = MagicMock(side_effect=claims)
    else:
        svc.get_user_claims = MagicMock(return_value=claims)
    return svc


def _calls(svc):
    """Every way the handler could reach the bus: rpc.call and rpc(...)."""
    return list(svc.vip.rpc.call.call_args_list) + list(svc.vip.rpc.call_args_list)


def _body(ident='control', method='list_agents', params=None, token=TOKEN):
    params = {} if params is None else dict(params)
    if token is not None:
        params['authentication'] = token
    return {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}


def _post(svc, body, method='POST'):
    """Run the handler and return (status code, body bytes) as the WSGI layer emits them."""
    env = get_test_web_env('/gs', method=method)
    response = svc.jsonrpc(env, body)
    status = []
    chunks = response(env, lambda s, h: status.append(s))
    return int(status[0].split()[0]), b''.join(chunks)


def _error_code(raw):
    return json.loads(raw)['error']['code']


def test_admin_allowed_query_makes_exactly_one_call():
    svc = _service()
    status, raw = _post(svc, _body())
    assert status == 200
    assert json.loads(raw) == {'jsonrpc': '2.0', 'id': 'control', 'result': ['an-agent']}
    assert len(_calls(svc)) == 1
    args, kwargs = svc.vip.rpc.call.call_args
    assert args == ('control', 'list_agents')
    assert kwargs == {}
    svc.vip.rpc.call.return_value.wait.assert_called_once_with(10)
    svc.vip.rpc.call.return_value.get.assert_called_once_with(block=False)
    svc.get_user_claims.assert_called_once_with(TOKEN)


@pytest.mark.parametrize('method', ['list_agents', 'status_agents', 'peerlist'])
def test_each_allowed_query_reaches_control(method):
    svc = _service()
    status, _ = _post(svc, _body(method=method))
    assert status == 200
    assert svc.vip.rpc.call.call_args[0] == ('control', method)


def test_body_as_json_string_is_accepted():
    svc = _service()
    status, _ = _post(svc, jsonapi.dumps(_body()))
    assert status == 200
    assert len(_calls(svc)) == 1


@pytest.mark.parametrize('claims', [
    {'groups': ['vui']},
    {},
    {'groups': None},
    {'groups': 'admin'},
    {'groups': [['admin']]},
    {'groups': ['admin', 5]},
    'admin',
    None,
], ids=['vui-only', 'no-groups', 'groups-none', 'groups-str', 'groups-nested', 'groups-mixed',
        'claims-str', 'claims-none'])
def test_non_admin_claims_are_forbidden(claims):
    svc = _service(claims=claims)
    status, raw = _post(svc, _body())
    assert status == 403
    assert _error_code(raw) == UNAUTHORIZED
    assert _calls(svc) == []


@pytest.mark.parametrize('error', [NotAuthorized(), ValueError('bad'), Exception('expired')],
                         ids=['not-authorized', 'value-error', 'other'])
def test_unresolvable_token_is_unauthorized(error):
    svc = _service(claims=error)
    status, raw = _post(svc, _body())
    assert status == 401
    assert _error_code(raw) == UNAUTHORIZED
    assert _calls(svc) == []


@pytest.mark.parametrize('token', [None, '', 5, ['x']], ids=['missing', 'empty', 'int', 'list'])
def test_missing_or_malformed_token_is_unauthorized(token):
    svc = _service()
    body = _body(token=None)
    if token is not None:
        body['params']['authentication'] = token
    status, raw = _post(svc, body)
    assert status == 401
    assert _error_code(raw) == UNAUTHORIZED
    assert _calls(svc) == []
    svc.get_user_claims.assert_not_called()


def test_token_cookie_is_not_used():
    svc = _service()
    env = get_test_web_env('/gs', method='POST', HTTP_COOKIE=f'Bearer={TOKEN}',
                           HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
    response = svc.jsonrpc(env, _body(token=None))
    status = []
    response(env, lambda s, h: status.append(s))
    assert status[0].startswith('401')
    assert _calls(svc) == []


@pytest.mark.parametrize('ident, method', [
    ('platform.auth', 'approve_authorization'),
    ('control', 'stop_agent'),
    ('control', 'install_agent'),
    ('Control', 'list_agents'),
    ('control', 'List_agents'),
    ('control', 'list_agents '),
    (' control', 'list_agents'),
    ('control.connection', 'list_agents'),
    ('some.agent', 'list_agents'),
])
def test_pairs_off_the_allow_list_are_forbidden(ident, method):
    svc = _service()
    status, raw = _post(svc, _body(ident=ident, method=method))
    assert status == 403
    assert _error_code(raw) == UNAUTHORIZED
    assert _calls(svc) == []


@pytest.mark.parametrize('params', [{'external_platform': 'other'}, {'get_agent_user': True}])
def test_extra_params_are_forbidden(params):
    svc = _service()
    status, raw = _post(svc, _body(method='status_agents', params=params))
    assert status == 403
    assert _error_code(raw) == UNAUTHORIZED
    assert _calls(svc) == []


@pytest.mark.parametrize('body', [
    _body(ident=5),
    _body(ident=['control']),
    _body(ident=None),
    _body(method={}),
    _body(method=None),
    [_body()],
    {'jsonrpc': '2.0', 'id': 'control', 'method': 'list_agents', 'params': ['x']},
    {'jsonrpc': '1.0', 'id': 'control', 'method': 'list_agents', 'params': {'authentication': TOKEN}},
    'not json',
    '"a string"',
], ids=['id-int', 'id-list', 'id-null', 'method-dict', 'method-null', 'list-body', 'params-list',
        'wrong-version', 'not-json', 'json-string'])
def test_malformed_requests_are_rejected(body):
    svc = _service()
    status, raw = _post(svc, body)
    assert status == 400
    assert _error_code(raw) == INVALID_REQUEST
    assert _calls(svc) == []


def test_bad_request_answers_with_the_request_id_when_it_is_a_string():
    svc = _service()
    status, raw = _post(svc, {'jsonrpc': '2.0', 'id': 'control', 'method': 5, 'params': {}})
    assert status == 400
    assert json.loads(raw)['id'] == 'control'
    status, raw = _post(svc, {'jsonrpc': '2.0', 'id': 7, 'method': 'list_agents', 'params': {}})
    assert status == 400
    assert json.loads(raw)['id'] is None


def test_null_params_are_read_as_empty():
    svc = _service()
    status, raw = _post(svc, {'jsonrpc': '2.0', 'id': 'control', 'method': 'list_agents',
                              'params': None})
    assert status == 401
    assert _calls(svc) == []


def test_non_string_param_keys_are_rejected():
    svc = _service()
    body = _body()
    body['params'][1] = 'x'
    status, raw = _post(svc, body)
    assert status == 400
    assert _calls(svc) == []


@pytest.mark.parametrize('http_method', ['GET', 'PUT', 'DELETE'])
def test_only_post_is_accepted(http_method):
    svc = _service()
    status, raw = _post(svc, _body(), method=http_method)
    assert status == 405
    assert _error_code(raw) == INVALID_REQUEST
    assert _calls(svc) == []


@pytest.mark.parametrize('error, expected', [
    (RuntimeError('SECRET-MARK'), 500),
    (RemoteError('SECRET-MARK', exc_type='x'), 500),
    (Unreachable(113, 'SECRET-MARK', 'control', 'RPC'), 502),
])
def test_error_bodies_carry_no_request_or_exception_text(error, expected):
    svc = _service()
    svc.vip.rpc.call.return_value.get.side_effect = error
    status, raw = _post(svc, _body())
    assert status == expected
    assert b'SECRET-MARK' not in raw
    assert TOKEN.encode() not in raw
    assert json.loads(raw)['id'] == 'control'


def test_unreachable_when_sending_is_bad_gateway():
    svc = _service()
    svc.vip.rpc.call.side_effect = Unreachable(113, 'SECRET-MARK', 'control', 'RPC')
    status, raw = _post(svc, _body())
    assert status == 502
    assert b'SECRET-MARK' not in raw


def test_call_that_does_not_finish_in_time_is_gateway_timeout(caplog):
    svc = _service()
    svc.vip.rpc.call.return_value.ready.return_value = False
    with caplog.at_level('INFO'):
        status, raw = _post(svc, _body())
    assert status == 504
    assert json.loads(raw)['error']['message'] == 'timed out'
    svc.vip.rpc.call.return_value.wait.assert_called_once_with(10)
    assert 'timeout' in caplog.text


def test_outer_timeout_during_the_call_is_not_swallowed():
    svc = _service()
    svc.vip.rpc.call.return_value.wait.side_effect = gevent.Timeout()
    with pytest.raises(gevent.Timeout):
        _post(svc, _body())


def test_outer_timeout_while_resolving_claims_is_not_swallowed():
    svc = _service(claims=gevent.Timeout())
    with pytest.raises(gevent.Timeout):
        _post(svc, _body())


def test_failed_call_logs_the_remote_error_type_not_params(caplog):
    svc = _service()
    svc.vip.rpc.call.return_value.get.side_effect = RemoteError('SECRET-MARK', exc_type='KeyError',
                                                                exc_args=['SECRET-MARK'])
    with caplog.at_level('DEBUG'):
        _post(svc, _body())
    assert 'KeyError' in caplog.text
    assert 'SECRET-MARK' not in caplog.text
    assert TOKEN not in caplog.text


def test_refusal_bodies_do_not_echo_the_token():
    for body in (_body(ident=5), _body(ident='platform.auth'), _body(params={'x': TOKEN})):
        svc = _service()
        status, raw = _post(svc, body)
        assert status in (400, 403)
        assert TOKEN.encode() not in raw


def test_logs_carry_no_token_or_params(caplog):
    svc = _service()
    svc.vip.rpc.call.return_value.get.side_effect = RuntimeError('SECRET-MARK')
    with caplog.at_level('DEBUG'):
        _post(svc, _body())
        _post(_service(), _body(params={'external_platform': 'PARAM-MARK'}))
        _post(_service(claims=ValueError('SECRET-MARK')), _body())
    assert caplog.records
    for marker in (TOKEN, 'PARAM-MARK', 'SECRET-MARK'):
        assert marker not in caplog.text


def _routed_status(path, body):
    """Route a request through app_routing with the /gs route installed."""
    svc = _service()
    svc.endpoints = {}
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.registeredroutes = []
    svc.register_gs_route()
    env = get_test_web_env(path, input_data=jsonapi.dumps(body).encode(), method='POST',
                           CONTENT_TYPE='application/json')
    status = []
    svc.app_routing(env, lambda s, h: status.append(s))
    return int(status[0].split()[0]), svc


@pytest.mark.parametrize('path, expected', [
    ('/gs', 200), ('/gs/', 200), ('/gsx', 404), ('/gs/anything', 404), ('/gs\n', 404),
    ('/x/gs', 404),
])
def test_route_matches_only_gs(path, expected):
    status, svc = _routed_status(path, _body())
    assert status == expected
    assert len(_calls(svc)) == (1 if expected == 200 else 0)


def test_routed_handler_runs_once():
    # app_routing retries a callable with (env, data) after a TypeError, so a
    # three-argument handler signature would run the call twice.
    status, svc = _routed_status('/gs', _body())
    assert status == 200
    assert len(_calls(svc)) == 1


def test_allow_list_holds_only_ungated_control_exports():
    from volttron.platform.web.platform_web_service import GS_ALLOWED_CALLS
    allowed = GS_ALLOWED_CALLS
    assert set(allowed) == {('control', 'list_agents'), ('control', 'status_agents'),
                            ('control', 'peerlist')}
    for (identity, method), params in allowed.items():
        assert identity == 'control'
        assert params == frozenset()
        _assert_ungated_export(method)


def _assert_ungated_export(method):
    member = getattr(ControlService, method)
    assert annotations(member, set, 'rpc.exports'), f'{method} is not exported'
    assert not annotations(member, set, 'rpc.allow_capabilities'), \
        f'{method} requires a capability and cannot be on the /gs allow-list'


def test_gated_export_fails_the_allow_list_check():
    with pytest.raises(AssertionError):
        _assert_ungated_export('stop_agent')


def test_timeout_semantics_with_a_real_async_result(monkeypatch):
    from volttron.platform.vip.agent.results import AsyncResult
    from volttron.platform.web import platform_web_service
    monkeypatch.setattr(platform_web_service, 'GS_CALL_TIMEOUT', 0.05)
    svc = _service()
    svc.vip.rpc.call.return_value = AsyncResult()
    status, _ = _post(svc, _body())
    assert status == 504

    svc.vip.rpc.call.return_value = AsyncResult()
    with pytest.raises(gevent.Timeout):
        with gevent.Timeout(0.01):
            _post(svc, _body())

    done = AsyncResult()
    done.set(['an-agent'])
    svc.vip.rpc.call.return_value = done
    status, raw = _post(svc, _body())
    assert status == 200
    assert json.loads(raw)['result'] == ['an-agent']
