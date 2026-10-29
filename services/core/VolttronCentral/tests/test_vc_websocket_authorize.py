import ast
import os

import pytest

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from services.core.VolttronCentral.volttroncentral.sessions import IDLE_TIMEOUT
from vc_agent_factory import IP, env, login, make_agent, rpc

HOST = 'localhost:8443'


@pytest.fixture
def agent(monkeypatch):
    agent = make_agent(monkeypatch)
    agent._platforms.is_registered.return_value = True
    return agent


@pytest.fixture
def session(agent):
    cookie, channel = login(agent)
    return cookie, channel


def _request(cookie, channel, suffix='management', ip=IP, origin=None, host=HOST):
    request = {'REMOTE_ADDR': ip, 'PATH_INFO': '/vc/ws/{}/{}'.format(channel, suffix),
               'HTTP_HOST': host}
    if cookie is not None:
        request['HTTP_COOKIE'] = cookie
    if origin is not None:
        request['HTTP_ORIGIN'] = origin
    return request


def test_a_live_session_on_its_own_channel_is_allowed(agent, session):
    cookie, channel = session

    assert agent._authorize_ws(_request(cookie, channel)) is True
    assert agent._authorize_ws(_request(cookie, channel, suffix='iam')) is True
    assert agent._authorize_ws(_request(cookie, channel, suffix='configure')) is True


def test_cookie_may_sit_among_other_cookies(agent, session):
    cookie, channel = session

    request = _request('theme=dark; {}; other=1'.format(cookie), channel)

    assert agent._authorize_ws(request) is True


@pytest.mark.parametrize('origin', [
    'http://localhost:8443', 'https://localhost:8443', 'https://LOCALHOST:8443',
])
def test_origin_with_the_same_host_and_port_is_allowed(agent, session, origin):
    cookie, channel = session

    assert agent._authorize_ws(_request(cookie, channel, origin=origin)) is True


@pytest.mark.parametrize('origin', [
    'null', '', 'https://evil.example', 'https://localhost:9999',
    'https://localhost', 'https://localhost:8443.evil.example',
    'ftp://localhost:8443', 'localhost:8443', 'https://user@localhost:8443',
    5, ['https://localhost:8443'],
])
def test_origin_that_is_not_this_host_is_refused(agent, session, origin):
    cookie, channel = session

    assert agent._authorize_ws(_request(cookie, channel, origin=origin)) is False


def test_origin_without_a_host_is_refused(agent, session):
    cookie, channel = session
    request = _request(cookie, channel, origin='https://localhost:8443')
    del request['HTTP_HOST']

    assert agent._authorize_ws(request) is False


def test_no_origin_is_allowed_for_a_client_that_sends_none(agent, session):
    cookie, channel = session
    request = _request(cookie, channel)
    assert 'HTTP_ORIGIN' not in request

    assert agent._authorize_ws(request) is True


@pytest.mark.parametrize('case', [
    'no cookie', 'unknown cookie', 'other ip', 'no ip', 'other session cookie',
    'other session channel', 'unknown channel', 'garbled cookie',
    'cookie is not a string',
])
def test_missing_or_mismatched_session_is_refused(agent, session, case):
    cookie, channel = session
    other_cookie, other_channel = login(agent, user='reader', groups=['reader'])
    # Logging in as another user ends nothing: users have one session each.
    kwargs = dict(cookie=cookie, channel=channel)
    request = _request(**kwargs)
    if case == 'no cookie':
        request = _request(None, channel)
    elif case == 'unknown cookie':
        request = _request('vcsession=not-a-session', channel)
    elif case == 'other ip':
        request = _request(cookie, channel, ip='10.9.9.9')
    elif case == 'no ip':
        del request['REMOTE_ADDR']
    elif case == 'other session cookie':
        request = _request(other_cookie, channel)
    elif case == 'other session channel':
        request = _request(cookie, other_channel)
    elif case == 'unknown channel':
        request = _request(cookie, 'nope')
    elif case == 'garbled cookie':
        request = _request('vcsession', channel)
    elif case == 'cookie is not a string':
        request['HTTP_COOKIE'] = 5

    assert agent._authorize_ws(request) is False


@pytest.mark.parametrize('path', [
    '/vc/ws/{channel}', '/vc/ws/{channel}/', '/vc/ws//management',
    '/vc/ws/{channel}/management/extra', '/vc/{channel}/management',
    '/other/ws/{channel}/management', '/vc/xx/{channel}/management',
    '{channel}/management', '', None, 5,
])
def test_malformed_websocket_paths_are_refused(agent, session, path):
    cookie, channel = session
    request = _request(cookie, channel)
    request['PATH_INFO'] = path.format(channel=channel) if isinstance(path, str) else path

    assert agent._authorize_ws(request) is False


@pytest.mark.parametrize('request_value', [None, 'text', [], 5])
def test_a_request_that_is_not_a_dict_is_refused(agent, request_value):
    assert agent._authorize_ws(request_value) is False


def test_expired_session_is_refused(agent, session):
    cookie, channel = session
    created = next(iter(agent._authenticated_sessions._session_tokens.values()))['created']
    agent._authenticated_sessions._clock = lambda: created + IDLE_TIMEOUT + 1

    assert agent._authorize_ws(_request(cookie, channel)) is False


def test_second_check_after_the_upgrade_needs_the_channel_and_the_ip(agent, session):
    _, channel = session
    endpoint = '/vc/ws/{}/management'.format(channel)

    assert agent.open_authenticate_ws_endpoint('10.9.9.9', endpoint) is False
    assert endpoint not in agent._websocket_endpoints
    assert agent.open_authenticate_ws_endpoint(IP, '/vc/ws/nope/management') is False
    assert agent.open_authenticate_ws_endpoint(IP, 'management') is False
    assert agent.open_authenticate_ws_endpoint(IP, endpoint) is True
    assert endpoint in agent._websocket_endpoints


def test_second_check_refuses_a_channel_whose_session_was_replaced(agent, session):
    _, old_channel = session
    login(agent)

    assert agent.open_authenticate_ws_endpoint(
        IP, '/vc/ws/{}/management'.format(old_channel)) is False


def _registered(agent):
    return {call.args[0]: call.kwargs
            for call in agent.vip.web.register_websocket.call_args_list}


def _assert_full_callbacks(agent, kwargs):
    assert kwargs['opened'] == agent.open_authenticate_ws_endpoint
    assert kwargs['closed'] == agent._ws_closed
    assert kwargs['authorize'] == agent._authorize_ws
    assert callable(kwargs['received'])


def test_all_four_registration_sites_pass_the_authorize_callback(agent, monkeypatch):
    cookie, channel = login(agent)
    scheduled = []
    monkeypatch.setattr(vc_agent.gevent, 'spawn_later',
                        lambda delay, fn, *a, **k: scheduled.append((delay, fn, a, k)))

    def call(method, params):
        response = agent.jsonrpc(env(cookie=cookie), rpc(method, params, channel))
        assert 'error' not in response, response

    call('register_management_endpoint', None)
    call('publish_bacnet_props', {'platform_uuid': 'vcp-abc', 'device_id': '5'})
    call('start_bacnet_scan', {'platform_uuid': 'vcp-abc', 'scan_length': 1})

    registered = _registered(agent)
    assert sorted(registered) == sorted(
        '/vc/ws/{}/{}'.format(channel, name)
        for name in ('management', 'configure', 'iam'))
    # The login registered the management path and the later request did it again.
    paths = [c.args[0] for c in agent.vip.web.register_websocket.call_args_list]
    assert paths.count('/vc/ws/{}/management'.format(channel)) == 2
    for kwargs in agent.vip.web.register_websocket.call_args_list:
        _assert_full_callbacks(agent, kwargs.kwargs)


def test_register_management_endpoint_returns_the_registered_path(agent):
    cookie, channel = login(agent)

    response = agent.jsonrpc(env(cookie=cookie),
                             rpc('register_management_endpoint', None, channel))

    assert response['result'] == '/vc/ws/{}/management'.format(channel)


def test_scan_unregisters_the_path_it_registered_when_it_ends(agent, monkeypatch):
    cookie, channel = login(agent)
    scheduled = []
    monkeypatch.setattr(vc_agent.gevent, 'spawn_later',
                        lambda delay, fn, *a, **k: scheduled.append((delay, fn, a, k)))
    agent.jsonrpc(env(cookie=cookie), rpc(
        'start_bacnet_scan', {'platform_uuid': 'vcp-abc', 'scan_length': 1}, channel))
    platform = agent._platforms.get_platform.return_value

    # Run start_scan, then the close_socket it schedules, then the delayed unregister.
    for _ in range(3):
        delay, fn, args, kwargs = scheduled.pop(0)
        fn(*args, **kwargs)
    assert scheduled == []

    platform.call.assert_called_once_with(
        'start_bacnet_scan', 'iam/{}'.format(channel), scan_length=1.0)
    agent.vip.web.unregister_websocket.assert_called_once_with(
        '/vc/ws/{}/iam'.format(channel))
    assert '/vc/ws/{}/iam'.format(channel) not in agent._session_ws_paths.get(channel, set())


def _enclosing_function(tree, lineno):
    """Name of the innermost function whose body holds `lineno`, or None."""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.lineno <= lineno <= node.end_lineno:
            if best is None or node.lineno > best.lineno:
                best = node
    return best.name if best else None


def test_only_the_helper_registers_websockets_and_four_places_call_it():
    package = os.path.dirname(vc_agent.__file__)
    register_sites = []
    helper_sites = []
    parsed = 0
    for name in sorted(os.listdir(package)):
        if not name.endswith('.py'):
            continue
        with open(os.path.join(package, name), encoding='utf-8') as source:
            tree = ast.parse(source.read())
        parsed += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                where = (name, _enclosing_function(tree, node.lineno))
                if node.func.attr == 'register_websocket':
                    register_sites.append(where)
                elif node.func.attr == '_register_session_ws':
                    helper_sites.append(where)

    assert parsed >= 3
    assert register_sites == [('agent.py', '_register_session_ws')]
    assert sorted(helper_sites) == sorted([
        ('agent.py', '_login'), ('agent.py', '_handle_bacnet_props'),
        ('agent.py', '_handle_bacnet_scan'),
        ('agent.py', '_handle_management_endpoint')])
