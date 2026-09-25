"""Unit tests for VOLTTRON/volttron#3306.

Covers two production paths in VolttronCentralAgent that must no longer rely
on the removed SHA-512 local-user authenticator:

1. A failed platform login must return the normal "invalid credentials"
   error, with no local fallback and no session created.
2. A config carrying a `users` key must be accepted, logged once as ignored,
   and never surfaced in the log message.

Both agents are built with `object.__new__`, bypassing `Agent.__init__`
(and therefore the VIP connection), so these tests need no running platform.
"""
import hashlib
import logging
from unittest import mock

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from services.core.VolttronCentral.volttroncentral.sessions import SessionHandler


class _LegacyLocalAuthenticator:
    """Reproduces the pre-fix local-user check (VOLTTRON/volttron#3306): an
    unsalted SHA-512 comparison that raises TypeError for a str password on
    Python 3. Kept local to this test so it has no dependency on the removed
    production module; it exists only to prove the fallback is never reached.
    """

    def __init__(self, users):
        self._users = users

    def authenticate(self, username, password):
        if username in self._users:
            if self._users[username]['password'] == hashlib.sha512(password).hexdigest():
                return self._users[username]['groups']
        return None


def _make_agent():
    """A VolttronCentralAgent with no VIP subsystem: only the attributes
    jsonrpc()/_configure() read are set."""
    agent = vc_agent.VolttronCentralAgent.__new__(vc_agent.VolttronCentralAgent)
    agent._authenticated_sessions = SessionHandler(
        _LegacyLocalAuthenticator({'reader': {'password': 'x', 'groups': ['reader']}}))
    agent._websocket_endpoints = set()
    return agent


def _failed_platform_login_chain():
    """A grequests chain whose .send().response looks like a failed platform login."""
    response = mock.Mock(ok=False, text=None)
    chain = mock.Mock()
    chain.send.return_value = chain
    chain.response = response
    return chain


def test_failed_platform_login_returns_invalid_credentials(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(vc_agent.grequests, "post",
                        lambda *a, **k: _failed_platform_login_chain())

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
        'params': {'username': 'reader', 'password': 'whatever'},
    }

    result = agent.jsonrpc(env, data)

    assert result['error']['message'] == "Invalid username/password specified."
    assert agent._authenticated_sessions._sessions == {}


def test_configure_with_users_key_logs_one_warning_and_ignores_it(monkeypatch, caplog):
    agent = _make_agent()
    agent._default_config = {
        'webroot': '/tmp/webroot',
        'users': {},
        'topic_replace_list': [],
    }
    agent.vip = mock.Mock()
    monkeypatch.setattr(vc_agent.gevent, "spawn_later", lambda *a, **k: None)

    legacy_hash = ("2d7349c51a3914cd6f5dc28e23c417ace074400d7c3e176bcf5"
                   "da72fdbeb6ce7ed767ca00c6c1fb754b8df5114fc0b903960e7"
                   "f3befe3a338d4a640c05dfaf2d")
    contents = {
        'users': {
            'reader': {'password': legacy_hash, 'groups': ['reader']},
            'admin': {'password': legacy_hash, 'groups': ['admin']},
        }
    }

    with caplog.at_level(logging.WARNING, logger=vc_agent._log.name):
        agent._configure('config', 'NEW', contents)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert '2' in warnings[0]
    assert legacy_hash not in warnings[0]
