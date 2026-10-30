"""Tests for web session revocation: ``DELETE /authenticate`` (CERT VU#173170.1, claim 6).

Every token minted at a login carries the same ``sid`` claim. Revoking the
session refuses all of them at once - on renewal, on the service's own claim
check that every endpoint and peer agent relies on, and for websockets that
were opened with them - and survives a restart of the web service.
"""

import json
import os
import stat
import time
from unittest.mock import MagicMock

import jwt
import pytest
from ws4py.websocket import WebSocket

from volttron.platform import get_home
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.token_revocation import (RevokedSessions, REVOKED_SESSIONS_FILE, SESSION_CLAIM,
                                                    session_id)
from volttron.platform.web.vui_pubsub import VUIPubsubManager
from volttron.utils import get_random_key
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home
from volttrontesting.utils.web_utils import get_test_web_env

USER = "revoke_user"
PASSWORD = "Pass123"


@pytest.fixture
def server():
    """Yields (endpoints, secret) with one vui/admin user stored in a fresh VOLTTRON_HOME."""
    with get_test_volttron_home(messagebus="zmq"):
        AdminEndpoints().add_user(USER, PASSWORD, groups=["admin", "vui"])
        secret = get_random_key()
        endpoints = AuthenticateEndpoints(web_secret_key=secret)
        try:
            yield endpoints, secret
        finally:
            endpoints._observer.stop()


def _login(endpoints):
    env = get_test_web_env("/authenticate", method="POST")
    response = endpoints.handle_authenticate(env, {"username": USER, "password": PASSWORD})
    assert "200 OK" in response.status
    return json.loads(response.response[0].decode("utf-8"))


def _renew(endpoints, refresh_token):
    env = get_test_web_env("/authenticate", method="PUT")
    env["HTTP_AUTHORIZATION"] = "BEARER " + refresh_token
    return endpoints.handle_authenticate(env, data={})


def _revoke(endpoints, token=None, **env_extra):
    env = get_test_web_env("/authenticate", method="DELETE", **env_extra)
    if token is not None:
        env["HTTP_AUTHORIZATION"] = "Bearer " + token
    return endpoints.handle_authenticate(env, data=None)


def _claims(token, secret):
    return jwt.decode(token, secret, algorithms=["HS256"])


def _service_with(endpoints, secret):
    """A PlatformWebService whose get_user_claims runs for real against the endpoints' deny-list."""
    svc = PlatformWebService.__new__(PlatformWebService)
    svc.core = MagicMock(messagebus="zmq")
    svc.web_ssl_cert = None
    svc._web_secret_key = secret
    svc._revoked_sessions = endpoints.revoked_sessions
    svc._vui_endpoints = None
    return svc


# ---------------------------------------------------------------- session ids

def test_login_tokens_share_one_session_id_and_renewal_inherits_it(server):
    endpoints, secret = server
    tokens = _login(endpoints)
    access, refresh = _claims(tokens["access_token"], secret), _claims(tokens["refresh_token"], secret)
    assert session_id(access) and session_id(access) == session_id(refresh)
    renewed = json.loads(_renew(endpoints, tokens["refresh_token"]).response[0])["access_token"]
    assert session_id(_claims(renewed, secret)) == session_id(access)
    # A second login is a different session.
    assert session_id(_claims(_login(endpoints)["access_token"], secret)) != session_id(access)


def test_token_without_session_id_is_refused_everywhere(server):
    endpoints, secret = server
    now = int(time.time())
    legacy = {"groups": ["admin", "vui"], "iat": now, "nbf": now, "exp": now + 600}
    legacy_access = jwt.encode(dict(legacy, grant_type="access_token"), secret, algorithm="HS256")
    legacy_refresh = jwt.encode(dict(legacy, grant_type="refresh_token"), secret, algorithm="HS256")
    assert "401" in _renew(endpoints, legacy_refresh).status
    assert _service_with(endpoints, secret).get_user_claims(legacy_access) == {}
    assert "401" in _revoke(endpoints, legacy_access).status


# ---------------------------------------------------------------- DELETE /authenticate

@pytest.mark.parametrize("presented", ["refresh_token", "access_token"])
def test_revoking_either_token_refuses_the_whole_session(server, presented):
    endpoints, secret = server
    tokens = _login(endpoints)
    svc = _service_with(endpoints, secret)
    assert svc.get_user_claims(tokens["access_token"]).get("groups") == ["admin", "vui"]
    renewed = json.loads(_renew(endpoints, tokens["refresh_token"]).response[0])["access_token"]

    response = _revoke(endpoints, tokens[presented])
    assert "204" in response.status
    assert response.response in ([], [b""])

    assert "401" in _renew(endpoints, tokens["refresh_token"]).status
    assert svc.get_user_claims(tokens["access_token"]) == {}
    assert svc.get_user_claims(renewed) == {}
    # Other sessions are untouched.
    other = _login(endpoints)
    assert svc.get_user_claims(other["access_token"]).get("groups") == ["admin", "vui"]
    assert "200" in _renew(endpoints, other["refresh_token"]).status


def test_revocation_is_idempotent(server):
    endpoints, _ = server
    tokens = _login(endpoints)
    assert "204" in _revoke(endpoints, tokens["refresh_token"]).status
    assert "204" in _revoke(endpoints, tokens["refresh_token"]).status
    assert "204" in _revoke(endpoints, tokens["access_token"]).status
    assert len(endpoints.revoked_sessions) == 1


def test_revocation_requires_a_valid_token_in_the_authorization_header(server):
    endpoints, secret = server
    tokens = _login(endpoints)
    other_key = jwt.encode(_claims(tokens["access_token"], secret), get_random_key(), algorithm="HS256")
    expired_claims = dict(_claims(tokens["access_token"], secret), exp=int(time.time()) - 5)
    expired = jwt.encode(expired_claims, secret, algorithm="HS256")

    assert "401" in _revoke(endpoints).status
    assert "401" in _revoke(endpoints, "not.a.token").status
    assert "401" in _revoke(endpoints, other_key).status
    assert "401" in _revoke(endpoints, expired).status
    # The cookie alone never revokes: a browser attaches it to requests other sites make.
    assert "401" in _revoke(endpoints, HTTP_COOKIE="Bearer=" + tokens["access_token"]).status
    assert len(endpoints.revoked_sessions) == 0
    assert "200" in _renew(endpoints, tokens["refresh_token"]).status


def test_revocation_entry_outlives_every_token_of_the_session(server):
    endpoints, secret = server
    tokens = _login(endpoints)
    issued = _claims(tokens["access_token"], secret)["iat"]
    _revoke(endpoints, tokens["access_token"])
    sid = session_id(_claims(tokens["access_token"], secret))
    stored = endpoints.revoked_sessions._expiry[sid]
    assert stored >= issued + (endpoints.refresh_token_timeout + endpoints.access_token_timeout) * 60


def test_on_revoke_hook_runs_and_its_failure_does_not_undo_the_revocation(server):
    endpoints, secret = server
    hook = MagicMock(side_effect=RuntimeError("boom"))
    endpoints._on_revoke = hook
    tokens = _login(endpoints)
    assert "204" in _revoke(endpoints, tokens["access_token"]).status
    hook.assert_called_once_with(session_id(_claims(tokens["access_token"], secret)))
    assert not endpoints.revoked_sessions.allows(_claims(tokens["access_token"], secret))


# ---------------------------------------------------------------- persistence

def test_revocations_persist_across_restart_with_private_file(server):
    endpoints, secret = server
    tokens = _login(endpoints)
    _revoke(endpoints, tokens["refresh_token"])
    path = os.path.join(get_home(), REVOKED_SESSIONS_FILE)
    assert endpoints.revoked_sessions.path == path
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    reloaded = RevokedSessions(path)
    assert not reloaded.allows(_claims(tokens["access_token"], secret))
    assert "401" in _renew(AuthenticateEndpoints(web_secret_key=secret, revoked_sessions=reloaded),
                           tokens["refresh_token"]).status


def test_expired_entries_are_dropped_on_load_check_and_revoke(tmp_path):
    path = str(tmp_path / "revoked.json")
    revoked = RevokedSessions(path)
    revoked.revoke("gone", time.time() - 1)
    assert len(revoked) == 0 and not os.path.exists(path)
    revoked.revoke("soon", time.time() + 0.2)
    revoked.revoke("later", time.time() + 3600)
    assert revoked.is_revoked("soon") and len(RevokedSessions(path)) == 2
    time.sleep(0.3)
    assert not revoked.is_revoked("soon")
    assert len(RevokedSessions(path)) == 1
    revoked.revoke("other", time.time() + 3600)
    assert set(json.load(open(path))) == {"later", "other"}


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '{"x": "notanumber", "y": true, "": 9e12, "ok": 9e12}'])
def test_damaged_or_odd_revocation_file_is_tolerated(tmp_path, content):
    path = tmp_path / "revoked.json"
    path.write_text(content)
    revoked = RevokedSessions(str(path))
    assert revoked.is_revoked("ok") == ("ok" in content)
    assert not revoked.is_revoked("x") and not revoked.is_revoked("y") and not revoked.is_revoked("")


@pytest.mark.parametrize("claims", [None, [], {}, {SESSION_CLAIM: ""}, {SESSION_CLAIM: 5}, {SESSION_CLAIM: "x" * 65}])
def test_unusable_session_ids_are_not_allowed(tmp_path, claims):
    revoked = RevokedSessions(str(tmp_path / "revoked.json"))
    assert session_id(claims) is None
    assert not revoked.allows(claims)
    with pytest.raises(ValueError):
        revoked.revoke(claims.get(SESSION_CLAIM) if isinstance(claims, dict) else claims, time.time() + 60)


# ---------------------------------------------------------------- websockets

class _FakeSocket(WebSocket):
    # ws4py's ``terminated`` property reads these two flags.
    def __init__(self):
        self.client_terminated = self.server_terminated = False
        self.closed_with = None

    def close(self, code=1000, reason=""):
        self.closed_with = reason
        self.client_terminated = self.server_terminated = True


def _open(manager, token, topic, sid, sock=None):
    """Open a subscription as the endpoint does, then stand in a fake socket for the WSGI application."""
    manager.open_subscription_socket(token, topic, sid=sid)
    if sock is not None:
        manager.user_websockets[token][topic] = sock


def test_close_session_sockets_closes_only_the_revoked_session():
    manager = VUIPubsubManager(MagicMock())
    doomed_a, doomed_b, kept, legacy = _FakeSocket(), _FakeSocket(), _FakeSocket(), _FakeSocket()
    _open(manager, "doomed-token", "devices/a", "doomed", doomed_a)
    _open(manager, "doomed-token", "devices/b", "doomed", doomed_b)
    _open(manager, "kept-token", "devices/a", "kept", kept)
    _open(manager, "legacy-token", "devices/a", None, legacy)  # opened without a session id
    # A pending entry still holds the WSGI application, not a socket.
    _open(manager, "doomed-token-2", "devices/c", "doomed")

    assert manager.close_session_sockets("doomed") == 2
    assert doomed_a.closed_with == "Session revoked" and doomed_b.terminated
    assert kept.closed_with is None and legacy.closed_with is None
    assert "doomed-token" not in manager.user_websockets and "doomed-token-2" not in manager.user_websockets
    assert "kept-token" in manager.user_websockets and "legacy-token" in manager.user_websockets
    assert "doomed" not in manager.session_tokens
    assert manager.close_session_sockets("doomed") == 0
    assert manager.close_session_sockets("never-seen") == 0


def test_service_closes_websockets_of_a_revoked_session(server):
    endpoints, secret = server
    svc = _service_with(endpoints, secret)
    endpoints._on_revoke = svc._session_revoked
    svc._session_revoked("nobody-listening")  # no VUI endpoints yet: nothing to do, no error
    svc._vui_endpoints = MagicMock()
    svc._vui_endpoints.pubsub_manager = VUIPubsubManager(MagicMock())
    tokens = _login(endpoints)
    sock = _FakeSocket()
    sid = session_id(jwt.decode(tokens["access_token"], secret, algorithms=["HS256"]))
    _open(svc._vui_endpoints.pubsub_manager, tokens["access_token"], "devices/a", sid, sock)

    assert "204" in _revoke(endpoints, tokens["refresh_token"]).status
    assert sock.terminated


def test_pubsub_manager_without_sockets_is_fine(server):
    endpoints, secret = server
    svc = _service_with(endpoints, secret)
    svc._vui_endpoints = MagicMock(spec=[])  # VUIEndpoints built without the pubsub route
    svc._session_revoked("whatever")
