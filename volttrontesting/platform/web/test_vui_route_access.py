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
"""Every VUI route, reached through the web service's request routing, needs a
token; a request other than GET takes it from the Authorization header only.
Nothing on the message bus is called when a request is refused."""

import re
from unittest import mock
from unittest.mock import MagicMock

import pytest

from volttron.platform.vip.agent.results import AsyncResult
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.vui_endpoints import VUIEndpoints
from volttrontesting.utils.web_utils import get_test_web_env

LOCAL = 'my_instance_name'
ADMIN = {'groups': ['vui', 'admin']}
WRITE_METHODS = ['POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']


class _Query:
    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result(LOCAL)
        return result


def _platform(claims=ADMIN):
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.endpoints = {}
    svc.get_user_claims = MagicMock(return_value=claims)
    with mock.patch('volttron.platform.web.vui_endpoints.Query', new=_Query):
        vui = VUIEndpoints(svc)
    svc.registeredroutes = vui.get_routes()
    return svc


def _status(svc, path, method, body=b'{}', **env_kwargs):
    env = get_test_web_env(path, input_data=body, method=method, **env_kwargs)
    status = []
    svc.app_routing(env, lambda s, h: status.append(s))
    return int(status[0].split()[0])


def _sample_path(pattern):
    path = pattern.lstrip('^').replace('/?$', '').replace('[^/]+', 'seg').replace('.*', 'a/b')
    assert re.fullmatch(pattern, path), pattern
    return path


def _route_paths():
    svc = _platform()
    return [_sample_path(pattern.pattern) for pattern, kind, handler in svc.registeredroutes]


ROUTE_PATHS = _route_paths()


def test_every_route_is_covered():
    # One sample path per route; a new route is covered without editing this file.
    assert len(ROUTE_PATHS) >= 22


@pytest.mark.parametrize('method', ['GET'] + WRITE_METHODS)
@pytest.mark.parametrize('path', ROUTE_PATHS)
def test_no_token_is_unauthorized_on_every_route(path, method):
    svc = _platform()
    assert _status(svc, path, method, CONTENT_TYPE='application/json') == 401
    assert svc.vip.mock_calls == []
    svc.get_user_claims.assert_not_called()


@pytest.mark.parametrize('method', WRITE_METHODS)
@pytest.mark.parametrize('path', ROUTE_PATHS)
def test_cookie_does_not_authorize_writes(path, method):
    svc = _platform()
    status = _status(svc, path, method, CONTENT_TYPE='text/plain', HTTP_COOKIE='Bearer=tok')
    assert status == 401
    assert svc.vip.mock_calls == []
    svc.get_user_claims.assert_not_called()


CONFIG_POST = f'/vui/platforms/{LOCAL}/agents/platform.driver/configs'


def test_cookie_config_post_does_not_write():
    svc = _platform()
    status = _status(svc, CONFIG_POST, 'POST', body=b'x', CONTENT_TYPE='text/plain',
                     HTTP_COOKIE='Bearer=tok', QUERY_STRING='config-name=x')
    assert status == 401
    assert svc.vip.mock_calls == []


def test_header_config_post_writes_once():
    svc = _platform()
    status = _status(svc, CONFIG_POST, 'POST', body=b'x', CONTENT_TYPE='text/plain',
                     HTTP_AUTHORIZATION='Bearer tok', QUERY_STRING='config-name=x')
    assert status == 201
    calls = [c for c in svc.vip.rpc.call.call_args_list if c[0][:2] == ('config.store', 'set_config')]
    assert len(calls) == 1
    svc.get_user_claims.assert_called_once_with('tok')


@pytest.mark.parametrize('path', ['/vui', f'/vui/platforms/{LOCAL}/agents', f'/vui/platforms/{LOCAL}/pubsub'])
def test_cookie_still_authorizes_reads(path):
    svc = _platform()
    svc.vip.rpc.call.return_value.get.return_value = []
    assert _status(svc, path, 'GET', HTTP_COOKIE='Bearer=tok') == 200
    svc.get_user_claims.assert_called_once_with('tok')


def test_empty_cookie_token_is_unauthorized():
    svc = _platform()
    assert _status(svc, f'/vui/platforms/{LOCAL}/agents', 'GET', HTTP_COOKIE='Bearer=') == 401
    svc.get_user_claims.assert_not_called()


def test_request_path_cannot_add_log_lines(caplog):
    svc = _platform()
    with caplog.at_level('DEBUG'):
        _status(svc, '/vui/platforms/x\nEXTRA line\r\x1b[2J', 'GET')
    assert caplog.records
    for record in caplog.records:
        assert record.getMessage().isprintable(), record.getMessage()
