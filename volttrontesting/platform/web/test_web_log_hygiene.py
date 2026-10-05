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
"""Web service log lines carry no credentials, request bodies, or control
characters taken from a remote error."""

from unittest.mock import MagicMock

import pytest

from volttron.platform.jsonrpc import RemoteError
from volttron.platform.web.platform_web_service import PlatformWebService
from volttrontesting.utils.web_utils import get_test_web_env


def test_peer_endpoint_forwarding_logs_no_credentials_or_body(caplog):
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.vip.rpc.call.return_value.get.side_effect = RuntimeError('stop')
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.endpoints = {'/peer/thing': ('some.agent', 'jsonrpc')}
    svc.registeredroutes = []
    env = get_test_web_env('/peer/thing', input_data=b'{"password": "BODY-MARK"}', method='POST',
                           CONTENT_TYPE='application/json',
                           HTTP_AUTHORIZATION='Bearer TOKEN-MARK', HTTP_COOKIE='Bearer=COOKIE-MARK')
    with caplog.at_level('DEBUG'):
        with pytest.raises(RuntimeError):
            svc.app_routing(env, MagicMock())
    svc.vip.rpc.call.assert_called_once()
    assert svc.vip.rpc.call.call_args[0][:2] == ('some.agent', 'route.callback')
    assert caplog.records
    for marker in ('TOKEN-MARK', 'COOKIE-MARK', 'BODY-MARK'):
        assert marker not in caplog.text


@pytest.mark.parametrize('exc_type', ['KeyError\nFORGED line', 'KeyError\r\x1b[2J', 'K' * 500])
def test_remote_error_type_is_made_safe_for_one_log_line(exc_type):
    from volttron.platform.web import describe_call_error
    described = describe_call_error(RemoteError('m', exc_type=exc_type, exc_args=[]))
    assert described.isprintable()
    assert described.startswith('K')
    assert len(described) <= 100


def test_remote_error_type_is_kept_when_safe():
    from volttron.platform.web import describe_call_error
    assert describe_call_error(RemoteError('m', exc_type='builtins.KeyError', exc_args=[])) == \
        'builtins.KeyError'
    assert describe_call_error(ValueError('SECRET')) == 'ValueError'


@pytest.mark.parametrize('exc_type', [5, None, b'KeyError', ['KeyError']])
def test_remote_error_type_that_is_not_text_names_the_local_type(exc_type):
    from volttron.platform.web import describe_call_error
    assert describe_call_error(RemoteError('m', exc_type=exc_type, exc_args=[])) == 'RemoteError'


def test_routing_log_lines_stay_on_one_line(caplog):
    import re
    from volttron.platform.agent.web import Response
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.vip = MagicMock()
    svc.core = MagicMock()
    svc.core.messagebus = 'zmq'
    svc.endpoints = {}
    svc.registeredroutes = [
        (re.compile('^/x'), 'callable', lambda env, data: Response('ok', 200)),
        (re.compile('^/static'), 'path', '/nonexistent-root'),
    ]
    with caplog.at_level('DEBUG'):
        for path in ('/x\nFORGED line', '/static/../y\nFORGED\x1b[2J'):
            env = get_test_web_env(path, method='GET')
            svc.app_routing(env, MagicMock())
    assert len(caplog.records) >= 3
    for record in caplog.records:
        assert record.getMessage().isprintable(), record.getMessage()
