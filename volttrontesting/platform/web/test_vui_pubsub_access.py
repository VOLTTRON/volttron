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
"""The VUI pubsub endpoint requires a valid token: subscribing needs the vui
group, and publishing needs the admin group, a token in the Authorization
header and a JSON content type. Nothing is published or subscribed on any
refusal."""

import json
from unittest import mock
from unittest.mock import MagicMock

import gevent
import pytest

from volttron.platform.vip.agent.results import AsyncResult
from volttron.platform.web.vui_endpoints import VUIEndpoints
from volttron.platform.web.vui_pubsub import VUIPubsubManager
from volttrontesting.utils.web_utils import get_test_web_env

LOCAL = 'my_instance_name'
ADMIN = {'groups': ['vui', 'admin']}
VUI_ONLY = {'groups': ['vui']}
JSON = 'application/json'
TOPIC_PATH = f'/vui/platforms/{LOCAL}/pubsub/devices/campus/building/point'
LIST_PATH = f'/vui/platforms/{LOCAL}/pubsub'
BODY = {'message': 5, 'headers': {'h': 1}}


class _Query:
    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result(LOCAL)
        return result


def _vui(claims=ADMIN, real_manager=False):
    agent = MagicMock()
    if isinstance(claims, BaseException):
        agent.get_user_claims = MagicMock(side_effect=claims)
    else:
        agent.get_user_claims = MagicMock(return_value=claims)
    agent.vip.pubsub.publish.return_value.get.return_value = 1
    with mock.patch('volttron.platform.web.vui_endpoints.Query', new=_Query):
        vui = VUIEndpoints(agent)
    if not real_manager:
        vui.pubsub_manager = MagicMock()
        vui.pubsub_manager.publish.return_value = {'number_of_subscribers': 1}
        vui.pubsub_manager.get_socket_routes.return_value = {}
    return vui, agent


def _env(path, method, token='Bearer tok', content_type=JSON, **kwargs):
    extra = dict(kwargs)
    if token is not None:
        extra['HTTP_AUTHORIZATION'] = token
    if content_type is not None:
        extra['CONTENT_TYPE'] = content_type
    return get_test_web_env(path, method=method, **extra)


def _send(vui, path, method, data=None, **env_kwargs):
    env = _env(path, method, **env_kwargs)
    return vui.handle_platforms_pubsub(env, MagicMock(), BODY if data is None else data)


def _nothing_done(vui, agent):
    manager = vui.pubsub_manager
    return (agent.vip.pubsub.publish.call_count == 0
            and agent.vip.pubsub.subscribe.call_count == 0
            and manager.publish.call_count == 0
            and manager.open_subscription_socket.call_count == 0
            and manager.get_socket_routes.call_count == 0)


def test_admin_publish_publishes_once():
    vui, agent = _vui(real_manager=True)
    response = _send(vui, TOPIC_PATH, 'PUT')
    assert response.status_code == 200
    assert json.loads(response.get_data()) == {'number_of_subscribers': 1}
    agent.vip.pubsub.publish.assert_called_once_with('pubsub', 'devices/campus/building/point',
                                                     headers={'h': 1}, message=5)


def test_vui_subscribe_opens_one_socket():
    vui, agent = _vui(claims=VUI_ONLY)
    response = _send(vui, TOPIC_PATH, 'GET', token=None, content_type=None,
                     HTTP_COOKIE='Bearer=tok')
    assert isinstance(response, list)
    vui.pubsub_manager.open_subscription_socket.assert_called_once_with(
        'tok', 'devices/campus/building/point')


def test_vui_lists_its_sockets():
    vui, agent = _vui(claims=VUI_ONLY)
    response = _send(vui, LIST_PATH, 'GET')
    assert response.status_code == 200
    vui.pubsub_manager.get_socket_routes.assert_called_once_with('tok', '')


@pytest.mark.parametrize('method', ['GET', 'PUT', 'POST'])
@pytest.mark.parametrize('path', [TOPIC_PATH, LIST_PATH])
def test_missing_token_is_unauthorized(method, path):
    vui, agent = _vui()
    response = _send(vui, path, method, token=None)
    assert response.status_code == 401
    assert _nothing_done(vui, agent)
    agent.get_user_claims.assert_not_called()


@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_invalid_token_is_unauthorized(method):
    vui, agent = _vui(claims=ValueError('not a token'))
    response = _send(vui, TOPIC_PATH, method, token='Bearer not-a-jwt')
    assert response.status_code == 401
    assert _nothing_done(vui, agent)


def test_invalid_token_does_not_publish_through_the_real_manager():
    vui, agent = _vui(claims=ValueError('not a token'), real_manager=True)
    response = _send(vui, TOPIC_PATH, 'PUT', token='Bearer not-a-jwt')
    assert response.status_code == 401
    agent.vip.pubsub.publish.assert_not_called()
    assert len(vui.pubsub_manager.subscription_websockets) == 0
    assert len(vui.pubsub_manager.user_websockets) == 0


@pytest.mark.parametrize('claims', [{'groups': ['admin']}, {'groups': []}, {}, {'groups': None}])
@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_vui_group_is_required(claims, method):
    vui, agent = _vui(claims=claims)
    response = _send(vui, TOPIC_PATH, method)
    assert response.status_code == 403
    assert _nothing_done(vui, agent)


@pytest.mark.parametrize('method', ['PUT', 'POST'])
def test_publish_needs_admin(method):
    vui, agent = _vui(claims=VUI_ONLY)
    response = _send(vui, TOPIC_PATH, method)
    assert response.status_code == 403
    assert _nothing_done(vui, agent)


@pytest.mark.parametrize('content_type', [JSON, 'text/plain; x=application/json'])
def test_publish_does_not_accept_the_cookie(content_type):
    vui, agent = _vui()
    response = _send(vui, TOPIC_PATH, 'PUT', token=None, HTTP_COOKIE='Bearer=tok',
                     content_type=content_type)
    assert response.status_code == 401
    assert _nothing_done(vui, agent)


@pytest.mark.parametrize('content_type', ['text/plain; x=application/json', 'text/plain', None])
def test_publish_needs_a_json_content_type(content_type):
    vui, agent = _vui()
    response = _send(vui, TOPIC_PATH, 'PUT', content_type=content_type)
    assert response.status_code == 415
    assert _nothing_done(vui, agent)


@pytest.mark.parametrize('data', [[1, 2], 'text', 5])
def test_publish_body_must_be_an_object(data):
    vui, agent = _vui()
    response = _send(vui, TOPIC_PATH, 'PUT', data=data)
    assert response.status_code == 400
    assert _nothing_done(vui, agent)


def test_unimplemented_method_publishes_nothing():
    vui, agent = _vui()
    response = _send(vui, TOPIC_PATH, 'POST')
    assert response.status_code == 501
    assert _nothing_done(vui, agent)


@pytest.mark.parametrize('error, expected', [(RuntimeError('SECRET-MARK'), 500),
                                             (gevent.Timeout(), 504)])
def test_publish_errors_return_fixed_bodies(error, expected):
    vui, agent = _vui(real_manager=True)
    agent.vip.pubsub.publish.return_value.get.side_effect = error
    response = _send(vui, TOPIC_PATH, 'PUT')
    assert response.status_code == expected
    assert b'SECRET-MARK' not in response.get_data()


def test_manager_does_not_log_tokens(caplog):
    manager = VUIPubsubManager(MagicMock())
    with caplog.at_level('DEBUG'):
        manager.open_subscription_socket('TOKEN-MARK', 'devices/x')
        manager.open_subscription_socket('TOKEN-MARK', 'devices/x')
        manager.get_socket_routes('TOKEN-MARK')
    assert caplog.records
    assert 'TOKEN-MARK' not in caplog.text
