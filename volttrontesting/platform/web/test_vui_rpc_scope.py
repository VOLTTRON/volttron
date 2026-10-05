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
"""VUI agent RPC endpoints reach only ordinary agents and undotted methods,
invoking a method requires the admin group and a token in the Authorization
header, and nothing is called on any refusal."""

import json
from unittest import mock
from unittest.mock import MagicMock

import gevent
import pytest

from volttron.platform.agent.known_identities import CONTROL_CONNECTION, PROCESS_IDENTITIES
from volttron.platform.jsonrpc import MethodNotFound
from volttron.platform.vip.agent.results import AsyncResult
from volttron.platform.web.vui_endpoints import VUIEndpoints
from volttrontesting.utils.web_utils import get_test_web_env

LOCAL = 'my_instance_name'
ADMIN = {'groups': ['vui', 'admin']}
VUI_ONLY = {'groups': ['vui']}
JSON = 'application/json'


class _Query:
    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result(LOCAL)
        return result


def _vui(claims=ADMIN, result=None):
    agent = MagicMock()
    agent.get_user_claims = MagicMock(return_value=claims)
    agent.vip.rpc.call.return_value.get.return_value = result if result is not None else {'methods': []}
    with mock.patch('volttron.platform.web.vui_endpoints.Query', new=_Query):
        return VUIEndpoints(agent), agent


def _calls(agent):
    return list(agent.vip.rpc.call.call_args_list) + list(agent.vip.rpc.call_args_list)


def _env(path, method='POST', token='Bearer tok', content_type=JSON, **kwargs):
    extra = dict(kwargs)
    if token is not None:
        extra['HTTP_AUTHORIZATION'] = token
    if content_type is not None:
        extra['CONTENT_TYPE'] = content_type
    return get_test_web_env(path, method=method, **extra)


def _invoke(vui, path, data=None, **env_kwargs):
    env = _env(path, **env_kwargs)
    response = vui.handle_platforms_agents_rpc_method(env, {} if data is None else data)
    return response.status_code, response.get_data()


def _method_path(identity, method, platform=LOCAL):
    return f'/vui/platforms/{platform}/agents/{identity}/rpc/{method}'


def test_handlers_use_the_real_endpoint_wrapper():
    assert hasattr(VUIEndpoints.handle_platforms_agents_rpc_method, '__wrapped__')
    assert hasattr(VUIEndpoints.handle_platforms_agents_rpc, '__wrapped__')


def test_admin_post_to_an_agent_makes_one_call():
    vui, agent = _vui(result=[1, 2])
    status, raw = _invoke(vui, _method_path('some.agent', 'do_thing'), {'args': [1], 'b': 2})
    assert status == 200
    assert json.loads(raw) == [1, 2]
    assert len(_calls(agent)) == 1
    assert agent.vip.rpc.call.call_args == mock.call('some.agent', 'do_thing', 1, b=2)


def test_admin_post_to_a_remote_platform_passes_the_url_platform():
    vui, agent = _vui(result=1)
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing', platform='other'), [1])
    assert status == 200
    assert agent.vip.rpc.call.call_args == mock.call('some.agent', 'do_thing', 1,
                                                     external_platform='other')


SERVICE_IDENTITIES = sorted(set(PROCESS_IDENTITIES) | {CONTROL_CONNECTION})


@pytest.mark.parametrize('platform', [LOCAL, 'other'])
@pytest.mark.parametrize('identity', SERVICE_IDENTITIES)
def test_post_to_a_platform_service_is_forbidden(identity, platform):
    vui, agent = _vui()
    status, raw = _invoke(vui, _method_path(identity, 'some_method', platform), {})
    assert status == 403
    assert json.loads(raw) == {'error': 'Forbidden'}
    assert _calls(agent) == []


@pytest.mark.parametrize('identity', SERVICE_IDENTITIES)
def test_get_on_a_platform_service_is_forbidden(identity):
    vui, agent = _vui()
    env = _env(f'/vui/platforms/{LOCAL}/agents/{identity}/rpc/', method='GET')
    assert vui.handle_platforms_agents_rpc(env, {}).status_code == 403
    env = _env(_method_path(identity, 'status_agents'), method='GET')
    assert vui.handle_platforms_agents_rpc_method(env, {}).status_code == 403
    assert _calls(agent) == []


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_dotted_method_is_forbidden(method):
    vui, agent = _vui()
    env = _env(_method_path('some.agent', 'auth.update'), method=method)
    assert vui.handle_platforms_agents_rpc_method(env, {}).status_code == 403
    assert _calls(agent) == []


def test_identity_comparison_is_exact():
    vui, agent = _vui(result=1)
    status, _ = _invoke(vui, _method_path('Control', 'do_thing'), {})
    assert status == 200
    assert agent.vip.rpc.call.call_args[0][0] == 'Control'


@pytest.mark.parametrize('data', [{'external_platform': 'x'}, {'args': [], 'external_platform': 'x'},
                                  {1: 'x'}])
def test_body_keys_cannot_steer_the_call(data):
    vui, agent = _vui()
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), data)
    assert status == 403
    assert _calls(agent) == []


def test_post_without_admin_is_forbidden():
    vui, agent = _vui(claims=VUI_ONLY)
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), {})
    assert status == 403
    assert _calls(agent) == []


def test_get_inspect_needs_only_vui():
    vui, agent = _vui(claims=VUI_ONLY, result={'params': {}})
    env = _env(_method_path('some.agent', 'do_thing'), method='GET')
    assert vui.handle_platforms_agents_rpc_method(env, {}).status_code == 200
    assert agent.vip.rpc.call.call_args[0][:2] == ('some.agent', 'do_thing.inspect')


@pytest.mark.parametrize('claims', [{}, {'groups': None}, {'groups': 'vui admin'}, None],
                         ids=['no-groups', 'groups-none', 'groups-str', 'claims-none'])
@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_missing_or_malformed_groups_is_forbidden(claims, method):
    vui, agent = _vui(claims=claims)
    env = _env(_method_path('some.agent', 'do_thing'), method=method)
    assert vui.handle_platforms_agents_rpc_method(env, {}).status_code == 403
    assert _calls(agent) == []


def test_cookie_token_does_not_authorize_a_post():
    vui, agent = _vui()
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), {}, token=None,
                        HTTP_COOKIE='Bearer=tok')
    assert status == 401
    assert _calls(agent) == []
    agent.get_user_claims.assert_not_called()


def test_cookie_post_with_a_disguised_json_type_is_refused():
    vui, agent = _vui()
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), {}, token=None,
                        HTTP_COOKIE='Bearer=tok', content_type='text/plain; x=application/json')
    assert 400 <= status < 500
    assert _calls(agent) == []


@pytest.mark.parametrize('content_type', ['text/plain; x=application/json', 'text/plain',
                                          'application/json-patch', None])
def test_post_needs_a_json_content_type(content_type):
    vui, agent = _vui()
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), {}, content_type=content_type)
    assert status == 415
    assert _calls(agent) == []


@pytest.mark.parametrize('content_type', ['application/json; charset=utf-8', 'Application/JSON'])
def test_json_content_type_parameters_are_accepted(content_type):
    vui, agent = _vui(result=1)
    status, _ = _invoke(vui, _method_path('some.agent', 'do_thing'), {}, content_type=content_type)
    assert status == 200
    assert len(_calls(agent)) == 1


def test_get_still_accepts_the_cookie():
    vui, agent = _vui(result={'params': {}})
    env = _env(_method_path('some.agent', 'do_thing'), method='GET', token=None,
               HTTP_COOKIE='Bearer=tok')
    assert vui.handle_platforms_agents_rpc_method(env, {}).status_code == 200


@pytest.mark.parametrize('error, expected', [
    (RuntimeError('SECRET-MARK'), 500),
    (MethodNotFound(-32601, 'SECRET-MARK'), 400),
    (ValueError('SECRET-MARK'), 400),
    (gevent.Timeout(), 504),
])
def test_call_errors_return_fixed_bodies(error, expected):
    vui, agent = _vui()
    agent.vip.rpc.call.return_value.get.side_effect = error
    status, raw = _invoke(vui, _method_path('some.agent', 'do_thing'), {})
    assert status == expected
    assert b'SECRET-MARK' not in raw


def test_malformed_body_returns_a_fixed_error():
    vui, agent = _vui()
    status, raw = _invoke(vui, _method_path('some.agent', 'do_thing'), 'SECRET-MARK')
    assert status == 400
    assert b'SECRET-MARK' not in raw
    assert _calls(agent) == []


@pytest.mark.parametrize('header, expected', [
    ('Bearer tok', 'tok'), ('bearer tok', 'tok'), ('Basic tok', None), ('Bearer', None),
    ('Bearer ', None), ('Bearer a b', None), ('', None), (None, None),
])
def test_authorization_header_parsing(header, expected):
    from volttron.platform.web import get_authorization_bearer
    env = {} if header is None else {'HTTP_AUTHORIZATION': header}
    env['HTTP_COOKIE'] = 'Bearer=cookie-token'
    assert get_authorization_bearer(env) == expected
