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
"""Admin API requests that change authorization state, and /discovery/allow,
take the token from the Authorization header only, never the cookie; reads keep
accepting the cookie. Nothing is changed on any refusal."""

import os
import re
from unittest.mock import MagicMock

import pytest

from volttron.platform import jsonapi
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.platform_web_service import PlatformWebService
from volttrontesting.utils.web_utils import get_test_web_env

ADMIN = {'groups': ['admin', 'vui']}
WRITES = {
    'approve_csr/x': 'approve_authorization',
    'deny_csr/x': 'deny_authorization',
    'delete_csr/x': 'delete_authorization',
    'approve_credential/x': 'approve_authorization',
    'deny_credential/x': 'deny_authorization',
    'delete_credential/x': 'delete_authorization',
}
VC_KEY = 'A' * 43


def _admin_service(claims=ADMIN):
    rpc = MagicMock()
    rpc.return_value.get.return_value = claims
    rpc.call.return_value.get.return_value = []
    admin = AdminEndpoints.__new__(AdminEndpoints)
    admin._rpc_caller = rpc
    admin._userdict = {'admin': {'hashed_password': 'x', 'groups': ['admin']}}
    admin._rmq_mgmt = None
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.endpoints = {}
    svc.registeredroutes = admin.get_routes()
    return svc, rpc


def _status(svc, path, method='GET', body=b'', **env_kwargs):
    env = get_test_web_env(path, input_data=body, method=method, **env_kwargs)
    status = []
    svc.app_routing(env, lambda s, h: status.append(s))
    return int(status[0].split()[0])


def _claims_resolved(rpc):
    return rpc.call_count


@pytest.mark.parametrize('method', ['GET', 'POST', 'HEAD'])
@pytest.mark.parametrize('endpoint', sorted(WRITES))
def test_admin_write_with_cookie_only_is_unauthorized(endpoint, method):
    svc, rpc = _admin_service()
    status = _status(svc, f'/admin/api/{endpoint}', method, HTTP_COOKIE='Bearer=tok')
    assert status == 401
    rpc.call.assert_not_called()
    assert _claims_resolved(rpc) == 0


@pytest.mark.parametrize('endpoint', sorted(WRITES))
def test_admin_write_with_header_token_changes_state_once(endpoint):
    svc, rpc = _admin_service()
    status = _status(svc, f'/admin/api/{endpoint}', 'GET', HTTP_AUTHORIZATION='Bearer tok')
    assert status == 200
    writes = [c for c in rpc.call.call_args_list if c[0][1] == WRITES[endpoint]]
    assert len(writes) == 1
    assert writes[0][0][2] == 'x'


def test_admin_write_by_non_admin_header_token_changes_nothing():
    svc, rpc = _admin_service(claims={'groups': ['vui']})
    status = _status(svc, '/admin/api/approve_credential/x', 'GET', HTTP_AUTHORIZATION='Bearer tok')
    assert status == 401
    rpc.call.assert_not_called()


@pytest.mark.parametrize('path', ['/admin/api/certs', '/admin/api/pending_csrs'])
def test_admin_reads_still_accept_the_cookie(path):
    svc, rpc = _admin_service()
    assert _status(svc, path, 'GET', HTTP_COOKIE='Bearer=tok') == 200
    rpc.assert_called_once()
    assert rpc.call.call_count == 1


def test_admin_pages_send_the_token_as_a_header_for_api_calls():
    # The pages read the script-readable Bearer cookie set at login and send
    # it as a header on /admin/api/ requests.
    import volttron.platform.web as web_pkg
    path = os.path.join(os.path.dirname(web_pkg.__file__), 'templates', 'base.html')
    text = open(path).read()
    assert "setRequestHeader('Authorization', 'Bearer ' + token)" in text
    assert "settings.url.indexOf('/admin/api/') === 0" in text


def _allow_service(claims=ADMIN):
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.endpoints = {}
    svc.get_user_claims = MagicMock(return_value=claims)
    svc.registeredroutes = [(re.compile('^/discovery/allow$'), 'callable', svc._allow)]
    return svc


ALLOW_BODY = jsonapi.dumpb({'jsonrpc': '2.0', 'id': 'allow-test', 'method': 'allowvc',
                            'params': {'vcpublickey': VC_KEY}})


def _auth_file_adds(svc):
    return [c for c in svc.vip.rpc.call.call_args_list if c[0][1] == 'auth_file.add']


@pytest.mark.parametrize('content_type', ['text/plain', 'application/json'])
def test_allow_with_cookie_only_is_unauthorized(content_type):
    svc = _allow_service()
    status = _status(svc, '/discovery/allow', 'POST', body=ALLOW_BODY, CONTENT_TYPE=content_type,
                     HTTP_COOKIE='Bearer=tok')
    assert status == 401
    assert _auth_file_adds(svc) == []
    svc.get_user_claims.assert_not_called()


@pytest.mark.parametrize('content_type', ['text/plain', 'text/plain; x=application/json', None])
def test_allow_needs_a_json_content_type(content_type):
    svc = _allow_service()
    kwargs = {} if content_type is None else {'CONTENT_TYPE': content_type}
    status = _status(svc, '/discovery/allow', 'POST', body=ALLOW_BODY,
                     HTTP_AUTHORIZATION='Bearer tok', **kwargs)
    assert status == 415
    assert _auth_file_adds(svc) == []


def test_allow_with_header_token_and_json_adds_one_entry():
    svc = _allow_service()
    status = _status(svc, '/discovery/allow', 'POST', body=ALLOW_BODY,
                     CONTENT_TYPE='application/json', HTTP_AUTHORIZATION='Bearer tok')
    assert status == 200
    adds = _auth_file_adds(svc)
    assert len(adds) == 1
    assert adds[0][0][2] == {'credentials': VC_KEY, 'identity': 'volttron.central'}
    svc.get_user_claims.assert_called_once_with('tok')
