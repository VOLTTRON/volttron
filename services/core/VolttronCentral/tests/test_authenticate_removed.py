"""Unit tests for VOLTTRON/volttron#3306.

Covers the production paths in VolttronCentralAgent that must no longer rely
on the removed SHA-512 local-user authenticator:

1. A failed platform login must return the normal "invalid credentials"
   error, with no local fallback and no session created.
2. A config carrying a `users` key of any truthy type must configure and
   register routes normally: a dict warns with a count, any other truthy
   value warns without one, and the value itself is never logged.
3. The same "no local fallback" property holds when the agent is built
   through the real `_configure`, not just a hand-built stand-in.

Agents are built with `object.__new__`, bypassing `Agent.__init__` (and
therefore the VIP connection), so these tests need no running platform.
"""
import logging
from unittest import mock

import pytest

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from services.core.VolttronCentral.volttroncentral.sessions import SessionHandler

_NO_COUNT_WARNING = (
    "VolttronCentral config 'users' key is no longer used for login; "
    "ignored. VolttronCentral users are managed through the platform "
    "web user store.")

# SHA-512 hex digest of the dummy password "whatever", precomputed so this
# file calls no hashing library. Lets a reintroduced local-fallback
# comparison succeed on this fixture the same way it would on a real hash.
_WHATEVER_SHA512 = (
    "ae3d347982977b422948b64011ac14ac76c9ab15898fb562a66a136733aa645fb3a9"
    "ccd9bee00cc578c2f44f486af47eb254af7c174244086d174cc52341e63a")


def _make_agent():
    """A VolttronCentralAgent with no VIP subsystem: only the attributes
    jsonrpc()/_configure() read are set. _authenticated_sessions starts at
    None, matching a real agent before _configure runs."""
    agent = vc_agent.VolttronCentralAgent.__new__(vc_agent.VolttronCentralAgent)
    agent._authenticated_sessions = None
    agent._websocket_endpoints = set()
    return agent


def _failed_platform_login_chain():
    """A grequests chain whose .send().response looks like a failed platform login."""
    response = mock.Mock(ok=False, text=None)
    chain = mock.Mock()
    chain.send.return_value = chain
    chain.response = response
    return chain


def _get_authorization_call(username, password):
    env = {
        'REQUEST_METHOD': 'POST',
        'wsgi.url_scheme': 'http',
        'HTTP_HOST': 'localhost',
        'REMOTE_ADDR': '127.0.0.1',
    }
    data = {
        'jsonrpc': '2.0',
        'id': '1',
        'method': 'get_authorization',
        'params': {'username': username, 'password': password},
    }
    return env, data


def test_failed_platform_login_returns_invalid_credentials(monkeypatch):
    agent = _make_agent()
    agent._authenticated_sessions = SessionHandler()
    monkeypatch.setattr(vc_agent.grequests, "post",
                        lambda *a, **k: _failed_platform_login_chain())
    # Stands in for any code path that would still create a session; a
    # local-login regression would call this.
    add_session = mock.Mock()
    monkeypatch.setattr(agent._authenticated_sessions, "_add_session", add_session)

    env, data = _get_authorization_call('reader', 'whatever')
    result = agent.jsonrpc(env, data)

    assert result['error']['message'] == "Invalid username/password specified."
    add_session.assert_not_called()
    assert agent._authenticated_sessions._sessions == {}
    assert agent._authenticated_sessions._session_tokens == {}


def test_configure_with_users_key_logs_one_warning_and_ignores_it(monkeypatch, caplog):
    agent = _make_agent()
    agent._default_config = {
        'webroot': '/tmp/webroot',
        'users': {},
        'topic_replace_list': [],
    }
    agent.vip = mock.Mock()
    monkeypatch.setattr(vc_agent.gevent, "spawn_later", lambda *a, **k: None)

    sentinel_password = "sentinel-value-not-a-real-password"
    contents = {
        'users': {
            'reader': {'password': sentinel_password, 'groups': ['reader']},
            'admin': {'password': sentinel_password, 'groups': ['admin']},
        }
    }

    with caplog.at_level(logging.WARNING, logger=vc_agent._log.name):
        agent._configure('config', 'NEW', contents)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0] == (
        "VolttronCentral config 'users' key is no longer used for login; "
        "2 user(s) ignored. VolttronCentral users are managed through the "
        "platform web user store.")
    assert sentinel_password not in warnings[0]
    assert 'reader' not in warnings[0]
    assert 'admin' not in warnings[0]


@pytest.mark.parametrize(
    "users,expected_warning_count,expected_message",
    [
        (5, 1, _NO_COUNT_WARNING),
        (True, 1, _NO_COUNT_WARNING),
        (1.5, 1, _NO_COUNT_WARNING),
        ("nonempty", 1, _NO_COUNT_WARNING),
        ([1, 2], 1, _NO_COUNT_WARNING),
        ({'reader': {}}, 1,
         "VolttronCentral config 'users' key is no longer used for login; "
         "1 user(s) ignored. VolttronCentral users are managed through the "
         "platform web user store."),
        ({}, 0, None),
        (None, 0, None),
    ],
)
def test_configure_accepts_every_users_type_and_registers_routes(
        users, expected_warning_count, expected_message, monkeypatch, caplog):
    agent = _make_agent()
    agent._default_config = {
        'webroot': '/tmp/webroot',
        'users': {},
        'topic_replace_list': [],
    }
    agent.vip = mock.Mock()
    monkeypatch.setattr(vc_agent.gevent, "spawn_later", lambda *a, **k: None)

    with caplog.at_level(logging.WARNING, logger=vc_agent._log.name):
        agent._configure('config', 'NEW', {'users': users})

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == expected_warning_count
    if expected_message is not None:
        assert warnings[0] == expected_message

    agent.vip.web.register_endpoint.assert_called_once_with(
        r'/vc/jsonrpc', agent.jsonrpc)


def test_configure_then_failed_platform_login_creates_no_session(monkeypatch):
    """The "no local fallback" property must hold when the session handler
    comes from the real _configure, not a hand-built stand-in."""
    agent = _make_agent()
    agent._default_config = {
        'webroot': '/tmp/webroot',
        'users': {'reader': {'password': _WHATEVER_SHA512, 'groups': ['reader']}},
        'topic_replace_list': [],
    }
    agent.vip = mock.Mock()
    monkeypatch.setattr(vc_agent.gevent, "spawn_later", lambda *a, **k: None)
    agent._configure('config', 'NEW', {})

    monkeypatch.setattr(vc_agent.grequests, "post",
                        lambda *a, **k: _failed_platform_login_chain())

    env, data = _get_authorization_call('reader', 'whatever')
    result = agent.jsonrpc(env, data)

    assert result['error']['message'] == "Invalid username/password specified."
    assert agent._authenticated_sessions._sessions == {}
    assert agent._authenticated_sessions._session_tokens == {}
