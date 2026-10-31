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

"""A request body that is not the JSON it claims to be is answered with 400, not a 500."""

from unittest.mock import MagicMock

import pytest

from volttron.platform import jsonapi
from volttron.platform.web.platform_web_service import PlatformWebService
from volttrontesting.utils.web_utils import get_test_web_env


def _service():
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.endpoints = {}
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.registeredroutes = []
    svc.register_gs_route()
    return svc


def _route(body: bytes, content_type='application/json', path='/gs'):
    svc = _service()
    env = get_test_web_env(path, input_data=body, method='POST', CONTENT_TYPE=content_type)
    status, headers = [], []
    result = svc.app_routing(env, lambda s, h: (status.append(s), headers.append(h)))
    return int(status[0].split()[0]), b''.join(result), svc


@pytest.mark.parametrize('body', [b'{bad json', b'', b'[1, 2', b'nul'])
def test_malformed_json_body_is_400_and_reaches_no_route(body, caplog):
    status, payload, svc = _route(body)
    assert status == 400
    assert jsonapi.loads(payload) == {'error': 'Malformed JSON body'}
    svc.vip.rpc.call.assert_not_called()
    assert 'Malformed JSON body' in caplog.text
    assert not body or body.decode('latin-1') not in caplog.text    # the body itself is not logged


def test_non_utf8_body_is_400_and_reaches_no_route():
    status, payload, svc = _route(b'\xff\xfe{}')
    assert status == 400
    assert jsonapi.loads(payload) == {'error': 'Request body is not UTF-8'}
    svc.vip.rpc.call.assert_not_called()


def test_well_formed_json_body_still_reaches_the_route():
    # The /gs route then judges the request itself (here: refused as malformed); the body parse did not.
    status, payload, svc = _route(jsonapi.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'x'}).encode())
    assert jsonapi.loads(payload) != {'error': 'Malformed JSON body'}


def test_non_json_content_type_is_not_parsed():
    # The /gs route refuses the text itself, but the body is not parsed as JSON before the route runs.
    status, payload, svc = _route(b'{bad json', content_type='text/plain')
    assert jsonapi.loads(payload) != {'error': 'Malformed JSON body'}
