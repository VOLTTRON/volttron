import logging
from unittest import mock

import gevent
import pytest

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from services.core.VolttronCentral.volttroncentral.sessions import IDLE_TIMEOUT
from volttron.platform.agent.known_identities import PLATFORM_WEB
from volttron.platform.jsonrpc import INVALID_PARAMS, UNAUTHORIZED
from volttron.platform.vip.agent import Unreachable
from vc_agent_factory import (
    IP, PASSWORD, env, login, make_agent, rpc, set_login_answer)

BAD_LOGIN = "Invalid username/password specified."


@pytest.fixture
def agent(monkeypatch):
    return make_agent(monkeypatch)


def _use_pair(agent, cookie, channel, method='list_platforms', ip=IP):
    return agent.jsonrpc(env(cookie=cookie, ip=ip), rpc(method, authorization=channel))


def test_login_asks_the_platform_and_returns_the_cookie_and_channel(agent):
    cookie, channel = login(agent, user='admin', groups=['admin', 'ops'])

    agent.vip.rpc.call.assert_called_once_with(
        PLATFORM_WEB, 'authenticate_web_user', 'admin', PASSWORD)
    agent.vip.rpc.call.return_value.get.assert_called_once_with(timeout=10)
    name, session_id = cookie.split('=')
    assert name == 'vcsession'
    assert len(session_id) == 43
    assert len(channel) == 22
    session = agent._authenticated_sessions.check_session(session_id, IP, channel=channel)
    assert session == {'user': 'admin', 'groups': ['admin', 'ops'],
                       'ip': IP, 'channel': channel}


def test_session_user_is_the_name_the_platform_returned(agent):
    set_login_answer(agent, {'user': 'admin', 'groups': ['admin']})

    agent.jsonrpc(env(), rpc('get_authorization',
                             {'username': 'ADMIN', 'password': PASSWORD}))

    assert list(agent._authenticated_sessions._sessions) == ['admin']


def test_login_response_is_the_three_element_list_with_cookie_attributes(agent):
    set_login_answer(agent, {'user': 'admin', 'groups': ['admin']})

    status, body, headers = agent.jsonrpc(
        env(), rpc('get_authorization', {'username': 'admin', 'password': PASSWORD}))

    assert status == '200 OK'
    assert all(isinstance(header, tuple) and len(header) == 2 for header in headers)
    headers = dict(headers)
    assert headers['Content-Type'] == 'application/json'
    session_id = headers['Set-Cookie'].split(';')[0].split('=')[1]
    assert headers['Set-Cookie'] == (
        'vcsession={}; HttpOnly; SameSite=Strict; Path=/vc'.format(session_id))
    assert session_id not in body
    assert vc_agent.jsonapi.loads(body)['id'] == '1'


def test_cookie_is_secure_only_on_an_https_request(agent):
    _, _ = login(agent, scheme='http')
    set_login_answer(agent, {'user': 'other', 'groups': []})
    _, _, https_headers = agent.jsonrpc(
        env(scheme='https'), rpc('get_authorization',
                                 {'username': 'other', 'password': PASSWORD}))

    assert dict(https_headers)['Set-Cookie'].endswith('; Path=/vc; Secure')


def test_login_makes_no_http_call(agent, monkeypatch):
    post = mock.Mock(side_effect=AssertionError('login made an http request'))
    monkeypatch.setattr(vc_agent.grequests, 'post', post)
    monkeypatch.setattr(vc_agent.grequests, 'request', post, raising=False)

    login(agent)

    post.assert_not_called()


def test_login_registers_only_the_management_socket_under_the_channel(agent):
    _, channel = login(agent)

    paths = [call.args[0] for call in agent.vip.web.register_websocket.call_args_list]
    assert paths == ['/vc/ws/{}/management'.format(channel)]


@pytest.mark.parametrize('answer', [
    {}, None, 'yes', [], {'user': 'admin'}, {'groups': ['admin']},
    {'user': 'admin', 'groups': 'admin'}, {'user': 'admin', 'groups': ['a', 5]},
    {'user': '', 'groups': ['admin']}, {'user': 5, 'groups': ['admin']},
])
def test_login_without_a_valid_answer_creates_no_session(agent, answer):
    set_login_answer(agent, answer)

    result = agent.jsonrpc(
        env(), rpc('get_authorization', {'username': 'admin', 'password': PASSWORD}))

    assert result['error']['code'] == UNAUTHORIZED
    assert result['error']['message'] == BAD_LOGIN
    assert agent._authenticated_sessions._sessions == {}
    assert agent._authenticated_sessions._session_tokens == {}
    agent.vip.web.register_websocket.assert_not_called()


@pytest.mark.parametrize('failure', [
    Unreachable(113, 'host unreachable', PLATFORM_WEB, 'rpc'),
    gevent.Timeout(0.01),
    vc_agent.RemoteError('only volttron.central may call it'),
], ids=['unreachable', 'timeout', 'remote error'])
def test_login_fails_closed_when_the_platform_cannot_answer(agent, failure):
    set_login_answer(agent, failure)

    result = agent.jsonrpc(
        env(), rpc('get_authorization', {'username': 'admin', 'password': PASSWORD}))

    assert result['error']['code'] == UNAUTHORIZED
    assert agent._authenticated_sessions._session_tokens == {}


@pytest.mark.parametrize('params', [
    None, [], 'x', {}, {'username': 'a'}, {'password': 'p'},
    {'username': 5, 'password': 'p'}, {'username': 'a', 'password': ['p']},
])
def test_login_with_non_string_credentials_is_invalid_params(agent, params):
    result = agent.jsonrpc(env(), rpc('get_authorization', params))

    assert result['error']['code'] == INVALID_PARAMS
    agent.vip.rpc.call.assert_not_called()


def test_login_never_logs_the_password_or_the_session_id(agent, caplog):
    with caplog.at_level(logging.DEBUG):
        cookie, channel = login(agent)
        _use_pair(agent, cookie, channel)
        _use_pair(agent, cookie, 'wrong-channel')
    session_id = cookie.split('=')[1]

    text = '\n'.join(record.getMessage() for record in caplog.records)
    assert caplog.records
    assert PASSWORD not in text
    assert session_id not in text


def test_request_with_the_cookie_and_channel_is_served(agent):
    cookie, channel = login(agent)

    response = _use_pair(agent, cookie, channel)

    assert response['result'] == agent._platforms.get_platform_list.return_value


@pytest.mark.parametrize('case', [
    'no cookie', 'unknown cookie', 'wrong channel', 'no channel',
    'channel is not a string', 'other ip', 'cookie of another session',
    'garbled cookie header',
])
def test_every_request_needs_the_matching_cookie_and_channel(agent, case):
    cookie, channel = login(agent, user='admin')
    other_cookie, other_channel = login(agent, user='reader', groups=['reader'])
    sent_cookie, sent_channel, ip = cookie, channel, IP
    if case == 'no cookie':
        sent_cookie = None
    elif case == 'unknown cookie':
        sent_cookie = 'vcsession=not-a-session'
    elif case == 'wrong channel':
        sent_channel = 'wrong-channel'
    elif case == 'no channel':
        sent_channel = None
    elif case == 'channel is not a string':
        sent_channel = 5
    elif case == 'other ip':
        ip = '10.9.9.9'
    elif case == 'cookie of another session':
        sent_cookie = other_cookie
    elif case == 'garbled cookie header':
        sent_cookie = 'vcsession'
    agent._platforms.reset_mock()

    response = _use_pair(agent, sent_cookie, sent_channel, ip=ip)

    assert response['error']['code'] == UNAUTHORIZED
    assert response['error']['message'] == "Invalid authentication token"
    assert agent._platforms.mock_calls == []


def test_channel_alone_is_not_a_credential(agent):
    _, channel = login(agent)

    response = _use_pair(agent, None, channel)

    assert response['error']['code'] == UNAUTHORIZED


def test_failed_check_does_not_log_the_cookie_or_channel(agent, caplog):
    cookie, channel = login(agent)

    with caplog.at_level(logging.DEBUG):
        _use_pair(agent, cookie, 'guess-' + channel)
        _use_pair(agent, 'vcsession=guess-' + cookie.split('=')[1], channel)

    text = '\n'.join(record.getMessage() for record in caplog.records)
    assert cookie.split('=')[1] not in text
    assert 'guess-' not in text


def test_login_again_ends_the_old_pair_and_closes_its_routes(agent):
    old_cookie, old_channel = login(agent)

    new_cookie, new_channel = login(agent)

    assert _use_pair(agent, old_cookie, old_channel)['error']['code'] == UNAUTHORIZED
    assert _use_pair(agent, new_cookie, new_channel)['result'] is not None
    agent.vip.web.unregister_websocket.assert_called_once_with(
        '/vc/ws/{}/management'.format(old_channel))


def test_idle_session_is_refused_and_its_sockets_closed(agent):
    cookie, channel = login(agent)
    clock = mock.Mock(return_value=0.0)
    agent._authenticated_sessions._clock = clock
    for session in agent._authenticated_sessions._session_tokens.values():
        session['created'] = session['last_seen'] = 0.0

    clock.return_value = IDLE_TIMEOUT + 1
    response = _use_pair(agent, cookie, channel)

    assert response['error']['code'] == UNAUTHORIZED
    agent.vip.web.unregister_websocket.assert_called_once_with(
        '/vc/ws/{}/management'.format(channel))


def test_platform_scan_expires_idle_sessions(agent):
    _, channel = login(agent)
    created = next(iter(agent._authenticated_sessions._session_tokens.values()))['created']
    agent._authenticated_sessions._clock = lambda: created + IDLE_TIMEOUT + 1
    agent.vip.peerlist.return_value.get.return_value = []
    agent._platforms.get_platform_vip_identities.return_value = set()
    agent._platform_scan_event = None
    agent.core = mock.Mock()

    agent._scan_platform_connect_disconnect()

    assert agent._authenticated_sessions._session_tokens == {}
    agent.vip.web.unregister_websocket.assert_called_once_with(
        '/vc/ws/{}/management'.format(channel))


def test_reconfigure_ends_every_session_and_its_routes(agent):
    login(agent, user='admin')
    _, channel = login(agent, user='reader', groups=['reader'])

    agent._configure('config', 'UPDATE', {})

    assert agent._authenticated_sessions._session_tokens == {}
    unregistered = [call.args[0] for call in
                    agent.vip.web.unregister_websocket.call_args_list]
    assert '/vc/ws/{}/management'.format(channel) in unregistered
    assert len(unregistered) == 2


def _install(encoded):
    return {'files': [{'file_name': 'a.whl', 'file': encoded}]}


def test_install_over_the_encoded_bound_is_refused_before_anything_is_relayed(agent):
    cookie, channel = login(agent, groups=['admin'])
    agent._platforms.is_registered.return_value = True
    platform = agent._platforms.get_platform.return_value
    limit = vc_agent.MAX_ENCODED_UPLOAD

    refused = agent.jsonrpc(env(cookie=cookie), rpc(
        'platforms.uuid.vcp-abc.install', _install('A' * (limit + 1)), channel))

    assert refused['error']['code'] == INVALID_PARAMS
    assert 'larger than 67108864 bytes' in refused['error']['message']
    platform.route_to_agent_method.assert_not_called()


def test_install_at_the_encoded_bound_is_relayed(agent):
    cookie, channel = login(agent, groups=['admin'])
    agent._platforms.is_registered.return_value = True
    platform = agent._platforms.get_platform.return_value
    platform.route_to_agent_method.return_value = {'result': 'ok'}
    limit = vc_agent.MAX_ENCODED_UPLOAD

    agent.jsonrpc(env(cookie=cookie), rpc(
        'platforms.uuid.vcp-abc.install', _install('A' * limit), channel))

    platform.route_to_agent_method.assert_called_once()


def test_encoded_bound_is_base64_of_64_mib():
    assert vc_agent.MAX_ENCODED_UPLOAD == 89478488
    assert vc_agent.MAX_UPLOAD_BYTES == 64 * 1024 * 1024
