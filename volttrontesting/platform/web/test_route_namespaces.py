"""Each agent's web paths live under a first path segment that the agent owns
and that no platform route uses; the platform's own routes always answer."""

import logging
import os
import re
from unittest.mock import MagicMock

import pytest

from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL
from volttron.platform.web import platform_web_service
from volttrontesting.platform.web.conftest import build_web_service, set_caller
from volttrontesting.utils.web_utils import get_test_web_env

KINDS = ('endpoint', 'agent_route', 'path_route', 'websocket')


def _register(service, kind, path, root):
    if kind == 'endpoint':
        service.register_endpoint(path, 'jsonrpc')
    elif kind == 'agent_route':
        service.register_agent_route(path, 'route_fn')
    elif kind == 'path_route':
        service.register_path_route(path, str(root))
    else:
        service.register_websocket(path)


def _tables(service):
    return (list(service.registeredroutes), dict(service.endpoints),
            dict(service.appContainer._wsregistry))


def _builtin_segments(service):
    """First segments the platform's own routes and packaged files answer on,
    read from the route table that startupagent built."""
    static = service.registeredroutes[-1]
    assert static[0].pattern == '^/.*$'
    names = {'favicon.ico', 'gs'} | set(os.listdir(static[2]))
    for pattern, _kind, _handler in service.registeredroutes[:-1]:
        names.add(re.match(r'\^?/([A-Za-z0-9_~-]+)', pattern.pattern).group(1))
    return names


def _calls_to(service, peer):
    return [c for c in service.vip.rpc.call.call_args_list if c[0][0] == peer]


def _request(service, path, **env):
    service.vip.rpc.call.return_value.get.return_value = {'from': 'agent'}
    status = []
    service.app_routing(get_test_web_env(path, **env), lambda s, h: status.append(s))
    return status[0]


@pytest.mark.parametrize('kind', KINDS)
def test_platform_names_are_refused(web_service, tmp_path, kind):
    set_caller(web_service, 'a')
    names = _builtin_segments(web_service)
    assert {'admin', 'authenticate', 'discovery', 'gs', 'vui', 'index.html', 'js'} <= names
    for name in sorted(names):
        before = _tables(web_service)
        with pytest.raises(PermissionError):
            _register(web_service, kind, f'/{name}', tmp_path)
        assert _tables(web_service) == before, name


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('name', ['Authenticate', 'ADMIN', 'administrator', 'authenticatex',
                                  'Gs', 'Index.HTML', 'FAVICON.ICO', 'JS', '.', '..'])
def test_names_a_platform_route_answers_on_are_refused(web_service, tmp_path, kind, name):
    set_caller(web_service, 'a')
    before = _tables(web_service)
    with pytest.raises(PermissionError):
        _register(web_service, kind, f'/{name}/x', tmp_path)
    assert _tables(web_service) == before


@pytest.mark.parametrize('kind', ['agent_route', 'path_route'])
@pytest.mark.parametrize('pattern', ['^/.*$', '', '/.*', '.*', '^/', '(^/a|^/admin)',
                                     '^/(probe)/', '^/probe|/admin', '^/probe(?=x)',
                                     '^/pro\\w+/', 'probe/x'])
def test_patterns_without_a_literal_first_segment_are_refused(web_service, tmp_path, kind,
                                                              pattern):
    set_caller(web_service, 'a')
    before = _tables(web_service)
    with pytest.raises(PermissionError):
        _register(web_service, kind, pattern, tmp_path)
    assert _tables(web_service) == before


@pytest.mark.parametrize('kind, path', [
    ('endpoint', '/probe'), ('endpoint', '/probe/x'), ('agent_route', '^/probe/.*'),
    ('agent_route', '/probe$'), ('path_route', '^/probe/.*'), ('path_route', '/probe'),
    ('websocket', '/probe/ws'),
])
def test_paths_in_a_free_namespace_are_accepted(web_service, tmp_path, kind, path):
    set_caller(web_service, 'a')
    before = _tables(web_service)
    _register(web_service, kind, path, tmp_path)
    assert _tables(web_service) != before


@pytest.mark.parametrize('kind', ['endpoint', 'websocket'])
@pytest.mark.parametrize('path', ['', 'probe', '/', '//probe', '/probe x'])
def test_exact_paths_must_start_with_a_namespace(web_service, tmp_path, kind, path):
    set_caller(web_service, 'a')
    before = _tables(web_service)
    with pytest.raises(PermissionError):
        _register(web_service, kind, path, tmp_path)
    assert _tables(web_service) == before


def test_endpoint_cannot_take_a_platform_route(web_service):
    set_caller(web_service, 'a')
    with pytest.raises(PermissionError):
        web_service.register_endpoint('/authenticate', 'jsonrpc')
    _request(web_service, '/authenticate', HTTP_AUTHORIZATION='Bearer TOKEN-MARK')
    assert web_service.vip.rpc.call.call_count == 0


def test_agent_route_is_only_consulted_in_its_own_namespace(web_service):
    set_caller(web_service, 'a')
    web_service.register_agent_route('^/probe/|/admin', 'route_fn')

    _request(web_service, '/admin', HTTP_AUTHORIZATION='Bearer TOKEN-MARK')
    assert _calls_to(web_service, 'a') == []

    assert _request(web_service, '/probe/x').startswith('200')
    calls = _calls_to(web_service, 'a')
    assert len(calls) == 1
    assert calls[0][0][1] == 'route_fn'


def test_another_agent_cannot_register_in_an_owned_namespace(web_service, tmp_path):
    set_caller(web_service, 'a')
    web_service.register_endpoint('/probe/one', 'jsonrpc')
    set_caller(web_service, 'b')
    for kind in KINDS:
        before = _tables(web_service)
        with pytest.raises(PermissionError):
            _register(web_service, kind, '/Probe/two', tmp_path)
        assert _tables(web_service) == before, kind

    set_caller(web_service, 'a')
    web_service.unregister_all_agent_routes()
    set_caller(web_service, 'b')
    web_service.register_endpoint('/probe/two', 'jsonrpc')
    assert web_service.endpoints == {'/probe/two': ('b', 'jsonrpc')}


def test_an_agent_may_own_several_namespaces(web_service, tmp_path):
    set_caller(web_service, 'a')
    web_service.register_endpoint('/probe/one', 'jsonrpc')
    web_service.register_path_route('/probe-files', str(tmp_path))
    web_service.register_endpoint('/probe/two', 'raw')
    assert web_service.endpoints == {'/probe/one': ('a', 'jsonrpc'), '/probe/two': ('a', 'raw')}


def test_volttron_central_namespace_is_held_for_volttron_central(web_service, tmp_path):
    set_caller(web_service, 'some.agent')
    with pytest.raises(PermissionError):
        web_service.register_endpoint('/vc/jsonrpc', 'jsonrpc')
    set_caller(web_service, VOLTTRON_CENTRAL)
    web_service.register_endpoint('/vc/jsonrpc', 'jsonrpc')
    web_service.register_path_route('^/vc/.*', str(tmp_path))
    web_service.register_websocket('/vc/ws/token/management')
    assert web_service.endpoints == {'/vc/jsonrpc': (VOLTTRON_CENTRAL, 'jsonrpc')}
    assert web_service.appContainer._wsregistry == {'/vc/ws/token/management': VOLTTRON_CENTRAL}


def test_user_must_be_the_peer_when_auth_is_enabled(web_service):
    set_caller(web_service, 'a', peer='b')
    with pytest.raises(PermissionError):
        web_service.register_endpoint('/probe/x', 'jsonrpc')
    assert web_service.endpoints == {}
    set_caller(web_service, 'b', peer='b')
    web_service.register_endpoint('/probe/x', 'jsonrpc')
    assert web_service.endpoints == {'/probe/x': ('b', 'jsonrpc')}


def test_peer_owns_the_entry_when_auth_is_disabled(tmp_path, monkeypatch):
    service = build_web_service(tmp_path, monkeypatch, enable_auth=False)
    set_caller(service, '', peer='a')
    service.register_endpoint('/probe/x', 'jsonrpc')
    assert service.endpoints == {'/probe/x': ('a', 'jsonrpc')}
    with pytest.raises(PermissionError):
        service.register_endpoint('/admin', 'jsonrpc')


def test_registration_before_the_route_table_is_built_is_refused(tmp_path, monkeypatch):
    service = build_web_service(tmp_path, monkeypatch, start=False)
    service.appContainer = MagicMock()
    set_caller(service, 'a')
    for kind in KINDS:
        with pytest.raises(PermissionError):
            _register(service, kind, '/probe/x', tmp_path)
    assert service.endpoints == {}
    assert service.registeredroutes == []
    assert service.appContainer.create_ws_endpoint.call_count == 0


def test_a_refusal_logs_one_warning(web_service, caplog):
    set_caller(web_service, 'a')
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(PermissionError):
            web_service.register_endpoint('/admin', 'jsonrpc')
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "'a'" in warnings[0].getMessage()
    assert "'/admin'" in warnings[0].getMessage()


def test_unregister_keeps_platform_routes(web_service):
    discovery = re.compile('^/discovery/$')
    builtin = [e for e in web_service.registeredroutes if e[0] is discovery]
    assert len(builtin) == 1

    set_caller(web_service, 'a')
    try:
        web_service.register_agent_route('^/discovery/$', 'route_fn')
    except PermissionError:
        pass
    web_service.register_agent_route('^/probe/', 'route_fn')
    web_service.unregister_all_agent_routes()

    assert [e for e in web_service.registeredroutes if e[0] is discovery] == builtin
    assert not any(e[2] == ('a', 'route_fn') for e in web_service.registeredroutes)


def test_login_cookie_is_not_forwarded_to_agents(web_service):
    set_caller(web_service, 'a')
    web_service.register_endpoint('/probe/x', 'jsonrpc')
    web_service.register_agent_route('^/probe/route', 'route_fn')

    _request(web_service, '/probe/x', HTTP_COOKIE='theme=dark; Bearer=COOKIE-MARK; lang=en',
             HTTP_AUTHORIZATION='Bearer HEADER-MARK')
    _request(web_service, '/probe/route', HTTP_COOKIE='Bearer=COOKIE-MARK')

    endpoint_call, route_call = _calls_to(web_service, 'a')
    assert endpoint_call[0][1] == 'route.callback'
    assert endpoint_call[0][2]['HTTP_COOKIE'] == 'theme=dark; lang=en'
    assert endpoint_call[0][2]['HTTP_AUTHORIZATION'] == 'Bearer HEADER-MARK'
    assert route_call[0][1] == 'route_fn'
    assert 'HTTP_COOKIE' not in route_call[0][2]


@pytest.mark.parametrize('patterns, expected', [
    (['^/discovery/allow$', '^/csr/request_new$', '^/admin.*', '^/gs/?\\Z', '/vui'],
     {'discovery', 'csr', 'admin', 'gs', 'vui'}),
])
def test_builtin_namespaces_are_read_from_each_pattern(patterns, expected):
    compiled = [re.compile(p) for p in patterns]
    assert platform_web_service.builtin_namespaces(compiled) == expected


@pytest.mark.parametrize('pattern', ['^/.*$', '^/(admin|vui)', '', '^/\\w+'])
def test_a_platform_route_without_a_first_segment_stops_startup(pattern):
    with pytest.raises(ValueError):
        platform_web_service.builtin_namespaces([re.compile('^/admin.*'), re.compile(pattern)])
