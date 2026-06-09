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
"""Regression tests for the admin-authorization gate on the platform_web
allow-list endpoint (``_allow``).

GHSA-j9rp-3mvh-v57x / VO-001: ``_allow`` admits a CURVE key into the auth
file under the privileged VOLTTRON_CENTRAL identity. Before this fix the
handler performed no authentication, so a web-reachable platform could be
turned into a fully trusted bus peer by an unauthenticated caller.

These tests exercise the authorization gate in isolation: the handler must
reject any caller that is not a member of the ``admin`` group BEFORE any
mutation of the auth file occurs, and must let a legitimate admin through.
"""

import pytest
from mock import MagicMock

from volttron.platform.web import NotAuthorized
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform import jsonapi
from volttrontesting.utils.web_utils import get_test_web_env

# A syntactically valid 43-char CURVE public key (passes the len()==43 assert).
VALID_CURVE_KEY = "A" * 43


def _make_service(claims=None, raise_not_authorized=False):
    """Build a PlatformWebService without running its agent __init__.

    ``vip.rpc.call`` (the auth_file.add path) and ``get_user_claims`` (the
    bearer-decode path) are replaced with mocks so the test exercises only the
    authorization gate, not the bus or JWT machinery.
    """
    svc = PlatformWebService.__new__(PlatformWebService)

    # auth_file.add is reached through self.vip.rpc.call(...).get()
    svc.vip = MagicMock()

    def _get_user_claims(_bearer):
        if raise_not_authorized:
            raise NotAuthorized()
        return claims or {}

    # get_user_claims is the service's own decode method; stub it so we control
    # the claims the gate sees without minting real JWTs.
    svc.get_user_claims = MagicMock(side_effect=_get_user_claims)
    return svc


def _allow_request_body():
    return jsonapi.dumpb({
        "jsonrpc": "2.0",
        "id": "vo-001-test",
        "method": "allowvc",
        "params": {"vcpublickey": VALID_CURVE_KEY},
    })


def _call_allow(svc, env):
    start_response = MagicMock()
    body = svc._allow(env, start_response, data=_allow_request_body())
    return start_response, body


def _status_of(start_response):
    assert start_response.call_count == 1, "start_response should be called exactly once"
    return start_response.call_args[0][0]


@pytest.mark.web
def test_allow_rejects_unauthenticated_and_does_not_mutate_auth_file():
    # No bearer in the environment at all -> get_bearer raises NotAuthorized.
    svc = _make_service(raise_not_authorized=True)
    env = get_test_web_env('/discovery/allow', method='POST')

    start_response, _body = _call_allow(svc, env)

    status = _status_of(start_response)
    assert status.startswith('401') or status.startswith('403'), \
        f"unauthenticated caller must be rejected, got {status!r}"
    # The deny path must NOT touch the auth file (data-invariant: no trust
    # state is changed for an unauthorized caller).
    svc.vip.rpc.call.assert_not_called()


@pytest.mark.web
def test_allow_rejects_non_admin_jwt_and_does_not_mutate_auth_file():
    # Valid token, but the caller is not in the admin group.
    svc = _make_service(claims={"groups": ["vui", "read_only"]})
    env = get_test_web_env('/discovery/allow', method='POST',
                           HTTP_AUTHORIZATION='Bearer sometoken')

    start_response, _body = _call_allow(svc, env)

    status = _status_of(start_response)
    assert status.startswith('401') or status.startswith('403'), \
        f"non-admin caller must be rejected, got {status!r}"
    svc.vip.rpc.call.assert_not_called()


@pytest.mark.web
def test_allow_rejects_when_groups_claim_missing_fail_closed():
    # Token decodes but carries no groups claim -> must fail closed, not crash
    # and not allow.
    svc = _make_service(claims={"grant_type": "access_token"})
    env = get_test_web_env('/discovery/allow', method='POST',
                           HTTP_AUTHORIZATION='Bearer sometoken')

    start_response, _body = _call_allow(svc, env)

    status = _status_of(start_response)
    assert status.startswith('401') or status.startswith('403'), \
        f"missing-groups claim must fail closed, got {status!r}"
    svc.vip.rpc.call.assert_not_called()


@pytest.mark.web
def test_allow_accepts_admin_jwt_and_adds_auth_entry():
    svc = _make_service(claims={"groups": ["admin", "vui"]})
    env = get_test_web_env('/discovery/allow', method='POST',
                           HTTP_AUTHORIZATION='Bearer admintoken')

    start_response, body = _call_allow(svc, env)

    status = _status_of(start_response)
    assert status.startswith('200'), f"admin caller must be allowed, got {status!r}"
    # The legitimate admin path still performs the auth_file.add with the
    # supplied CURVE key under the VOLTTRON_CENTRAL identity.
    svc.vip.rpc.call.assert_called_once()
    call_args = svc.vip.rpc.call.call_args[0]
    assert call_args[1] == "auth_file.add"
    authentry = call_args[2]
    assert authentry["credentials"] == VALID_CURVE_KEY
