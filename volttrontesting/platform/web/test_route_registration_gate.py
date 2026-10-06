"""Registering web endpoints, routes, static paths and websockets requires the
register_web_routes capability, which only VolttronCentral is given at install."""

import ssl
from pathlib import Path
from unittest.mock import MagicMock

import gevent
import pytest
import requests
import websocket

from volttron.platform.agent.known_identities import (PLATFORM_WEB, VOLTTRON_CENTRAL,
                                                      VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.aip import AIPplatform
from volttron.platform.auth.auth_file import AuthFile
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent.decorators import annotations
from volttron.platform.web.platform_web_service import PlatformWebService

CAPABILITY = 'register_web_routes'

# Every RPC export of platform_web, by how it is protected. An export missing
# from this table fails test_every_export_is_classified.
GATED = {'register_endpoint', 'register_agent_route', 'register_path_route',
         'register_websocket'}
OWNER_SCOPED = {'unregister_all_agent_routes', 'unregister_websocket', 'websocket_send'}
READ_ONLY = {'get_user_claims', 'print_websocket_clients', 'get_bind_web_address',
             'get_serverkey', 'get_volttron_central_address'}


def _exported_methods():
    return {name for name, member in vars(PlatformWebService).items()
            if callable(member) and annotations(member, set, 'rpc.exports')}


def _required_capabilities(name):
    # The annotation rpc.py reads when it wraps an export in a capability check.
    return annotations(getattr(PlatformWebService, name), set, 'rpc.allow_capabilities')


def test_every_export_is_classified():
    assert _exported_methods() == GATED | OWNER_SCOPED | READ_ONLY


@pytest.mark.parametrize('name', sorted(GATED))
def test_registration_export_requires_the_capability(name):
    assert _required_capabilities(name) == {CAPABILITY}


@pytest.mark.parametrize('name', sorted(OWNER_SCOPED | READ_ONLY))
def test_other_exports_need_no_capability(name):
    # Unregister and send stay callable after a revoked grant; ownership
    # limits them to the caller's own entries instead.
    assert _required_capabilities(name) == set()


def _install_entry(tmp_path, monkeypatch, identity):
    monkeypatch.setenv('VOLTTRON_HOME', str(tmp_path))
    AIPplatform._authorize_agent_keys(MagicMock(), 'agent-uuid', identity, 'A' * 43)
    entries = [e for e in AuthFile().read_allow_entries() if e.user_id == identity]
    assert len(entries) == 1
    return entries[0]


def test_install_grants_the_capability_to_volttron_central(tmp_path, monkeypatch):
    entry = _install_entry(tmp_path, monkeypatch, VOLTTRON_CENTRAL)
    assert entry.identity == VOLTTRON_CENTRAL
    assert entry.capabilities == {'edit_config_store': {'identity': VOLTTRON_CENTRAL},
                                  'driver_write': None,
                                  CAPABILITY: None}


@pytest.mark.parametrize('identity', ['some.agent', VOLTTRON_CENTRAL_PLATFORM,
                                      'Volttron.Central', 'volttron.central2'])
def test_install_does_not_grant_the_capability_to_other_agents(tmp_path, monkeypatch, identity):
    entry = _install_entry(tmp_path, monkeypatch, identity)
    assert CAPABILITY not in entry.capabilities


def _answer(body, calls):
    def answer(env, data):
        calls.append(env['PATH_INFO'])
        return body
    return answer


def _get(instance, path):
    return requests.get(instance.bind_web_address + path, verify=False, timeout=10)


@pytest.mark.web
def test_registration_is_refused_without_the_capability(volttron_instance_web):
    instance = volttron_instance_web
    if not instance.auth_enabled:
        pytest.skip('the capability is only enforced with authentication enabled')

    denied = instance.build_agent(identity='probe.denied', enable_web=True)
    allowed = instance.build_agent(
        identity='probe.allowed', enable_web=True,
        capabilities={'edit_config_store': {'identity': 'probe.allowed'}, CAPABILITY: None})
    try:
        denied_calls, allowed_calls = [], []
        with pytest.raises(RemoteError) as refused:
            denied.vip.web.register_endpoint('/probe-denied/x',
                                             _answer({'served': 'denied'}, denied_calls))
        assert CAPABILITY in str(refused.value)

        allowed.vip.web.register_endpoint('/probe-allowed/x',
                                          _answer({'served': 'allowed'}, allowed_calls))
        gevent.sleep(0.5)

        response = _get(instance, '/probe-denied/x')
        assert response.status_code == 404
        assert denied_calls == []

        response = _get(instance, '/probe-allowed/x')
        assert response.status_code == 200
        assert response.json() == {'served': 'allowed'}
        assert allowed_calls == ['/probe-allowed/x']
    finally:
        allowed.vip.rpc.call(PLATFORM_WEB, 'unregister_all_agent_routes').get(timeout=10)
        denied.core.stop()
        allowed.core.stop()


def _connect(instance, path):
    url = instance.bind_web_address.replace('http', 'ws', 1) + path
    return websocket.create_connection(url, timeout=10, sslopt={'cert_reqs': ssl.CERT_NONE})


@pytest.mark.web
def test_routes_paths_and_websockets_need_the_capability(web_instance_with_static_root):
    instance = web_instance_with_static_root
    root = Path(instance.web_static_roots[-1])
    for name in ('probe-denied-files', 'probe-allowed-files'):
        (root / name).mkdir(exist_ok=True)
        (root / name / 'index.html').write_text(f'{name} page')

    denied = instance.build_agent(identity='probe.denied.kinds', enable_web=True)
    allowed = instance.build_agent(
        identity='probe.allowed.kinds', enable_web=True,
        capabilities={'edit_config_store': {'identity': 'probe.allowed.kinds'},
                      CAPABILITY: None})
    route_calls, opened = [], []
    allowed.vip.rpc.export(_answer({'served': 'route'}, route_calls), 'probe_route')
    try:
        refusals = [
            lambda: denied.vip.rpc.call(PLATFORM_WEB, 'register_agent_route',
                                        '^/probe-denied-route/', 'probe_route').get(timeout=10),
            lambda: denied.vip.web.register_path('^/probe-denied-files/', str(root)),
            lambda: denied.vip.web.register_websocket('/probe-denied-ws/x',
                                                      lambda ip, endpoint: True),
        ]
        for register in refusals:
            with pytest.raises(RemoteError) as refused:
                register()
            assert CAPABILITY in str(refused.value)

        allowed.vip.rpc.call(PLATFORM_WEB, 'register_agent_route',
                             '^/probe-allowed-route/', 'probe_route').get(timeout=10)
        allowed.vip.web.register_path('^/probe-allowed-files/', str(root))
        allowed.vip.web.register_websocket(
            '/probe-allowed-ws/x', lambda ip, endpoint: opened.append(endpoint) or True)
        gevent.sleep(0.5)

        assert _get(instance, '/probe-denied-route/x').status_code == 404
        assert _get(instance, '/probe-denied-files/index.html').status_code == 404
        with pytest.raises((websocket.WebSocketException, OSError)):
            _connect(instance, '/probe-denied-ws/x').close()

        response = _get(instance, '/probe-allowed-route/x')
        assert (response.status_code, response.json()) == (200, {'served': 'route'})
        assert route_calls == ['/probe-allowed-route/x']
        response = _get(instance, '/probe-allowed-files/index.html')
        assert (response.status_code, response.text) == (200, 'probe-allowed-files page')
        sock = _connect(instance, '/probe-allowed-ws/x')
        try:
            assert sock.getstatus() == 101
            gevent.sleep(0.5)
            assert opened == ['/probe-allowed-ws/x']
        finally:
            sock.close()
    finally:
        allowed.vip.rpc.call(PLATFORM_WEB, 'unregister_all_agent_routes').get(timeout=10)
        denied.core.stop()
        allowed.core.stop()
