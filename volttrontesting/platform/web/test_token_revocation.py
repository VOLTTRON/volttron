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

from volttron.platform import get_home
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.token_revocation import (ISSUED_BEFORE_KEY, RevokedSessions, REVOKED_SESSIONS_FILE,
                                                    SESSION_CLAIM, session_id)
from volttron.platform.web.vui_pubsub import VUIPubsubManager, VUIWebSocket
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


@pytest.mark.parametrize("content", ["not json", "[1, 2]", ""])
def test_damaged_revocation_file_is_quarantined_and_older_tokens_are_refused(tmp_path, content, caplog):
    path = tmp_path / "revoked.json"
    path.write_text(content)
    before = int(time.time())
    revoked = RevokedSessions(str(path))
    kept = [p for p in tmp_path.iterdir() if p.name.startswith("revoked.json.corrupt-")]
    assert len(kept) == 1 and kept[0].read_text() == content
    assert before <= revoked.issued_before <= time.time()
    old = {SESSION_CLAIM: "old", "iat": before - 10}
    fresh = {SESSION_CLAIM: "fresh", "iat": int(time.time()) + 1}
    assert not revoked.allows(old) and revoked.allows(fresh)
    assert not revoked.allows({SESSION_CLAIM: "noiat"}) and not revoked.allows({SESSION_CLAIM: "x", "iat": True})
    assert "could not be read" in caplog.text and kept[0].name in caplog.text
    # The cutoff is persisted, so a restart keeps refusing the older tokens, and the new file is a normal deny-list.
    reloaded = RevokedSessions(str(path))
    assert reloaded.issued_before == revoked.issued_before
    assert not reloaded.allows(old) and reloaded.allows(fresh)
    reloaded.revoke("later", time.time() + 3600)
    assert set(json.load(open(path))) == {"later", ISSUED_BEFORE_KEY}
    assert not RevokedSessions(str(path)).allows({SESSION_CLAIM: "later", "iat": int(time.time()) + 1})


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
def test_unreadable_revocation_file_is_treated_as_damaged(tmp_path):
    path = tmp_path / "revoked.json"
    path.write_text("{}")
    path.chmod(0)
    try:
        revoked = RevokedSessions(str(path))
    finally:
        for p in tmp_path.iterdir():
            p.chmod(0o600)
    assert revoked.issued_before is not None
    assert not revoked.allows({SESSION_CLAIM: "old", "iat": int(time.time()) - 10})


def test_cutoff_is_forgotten_after_the_retention_period(tmp_path):
    path = tmp_path / "revoked.json"
    path.write_text(json.dumps({ISSUED_BEFORE_KEY: time.time() - 8 * 24 * 3600, "kept": time.time() + 3600}))
    revoked = RevokedSessions(str(path))
    assert revoked.issued_before is None and revoked.is_revoked("kept")
    path.write_text(json.dumps({ISSUED_BEFORE_KEY: time.time() - 60}))
    assert RevokedSessions(str(path)).issued_before is not None


def test_odd_but_parseable_entries_are_skipped_without_quarantine(tmp_path):
    path = tmp_path / "revoked.json"
    path.write_text(json.dumps({"x": "notanumber", "y": True, "": 9e12, "_reserved": 9e12, "ok": 9e12}))
    revoked = RevokedSessions(str(path))
    assert revoked.issued_before is None and path.exists()
    assert revoked.is_revoked("ok")
    assert not any(revoked.is_revoked(sid) for sid in ("x", "y", "", "_reserved"))


@pytest.mark.parametrize("claims", [None, [], {}, {SESSION_CLAIM: ""}, {SESSION_CLAIM: 5}, {SESSION_CLAIM: "x" * 65},
                                    {SESSION_CLAIM: "_issued_before"}, {SESSION_CLAIM: "_x"}])
def test_unusable_session_ids_are_not_allowed(tmp_path, claims):
    revoked = RevokedSessions(str(tmp_path / "revoked.json"))
    assert session_id(claims) is None
    assert not revoked.allows(claims)
    with pytest.raises(ValueError):
        revoked.revoke(claims.get(SESSION_CLAIM) if isinstance(claims, dict) else claims, time.time() + 60)


# ---------------------------------------------------------------- websockets

class _FakeSocket(VUIWebSocket):
    # ws4py's ``terminated`` property reads these two flags.
    def __init__(self):
        self.client_terminated = self.server_terminated = False
        self.closed_with = None
        self.environ = {}

    def close(self, code=1000, reason=""):
        self.closed_with = reason
        self.client_terminated = self.server_terminated = True


def _open(manager, sid, topic, sock=None):
    """Register a socket with the manager the way VUIWebSocket.opened does once the token has verified."""
    sock = sock or _FakeSocket()
    manager.client_opened(sock, topic, f"token-{sid}", {SESSION_CLAIM: sid, "groups": ["vui"]})
    return sock


def test_close_session_sockets_closes_only_the_revoked_session():
    agent = MagicMock()
    manager = VUIPubsubManager(agent)
    doomed_a, doomed_b = _open(manager, "doomed", "devices/a"), _open(manager, "doomed", "devices/b")
    kept = _open(manager, "kept", "devices/a")

    assert manager.close_session_sockets("doomed") == 2
    assert doomed_a.closed_with == "Session revoked" and doomed_b.terminated
    assert kept.closed_with is None
    # The revoked sockets' subscriptions are released, the kept one's is not.
    unsubscribed = {(c.args[1], c.args[2]) for c in agent.vip.pubsub.unsubscribe.call_args_list}
    assert unsubscribed == {("devices/a", doomed_a.on_topic), ("devices/b", doomed_b.on_topic)}
    assert "doomed" not in manager._sockets and kept in manager._sockets["kept"]
    assert manager.close_session_sockets("doomed") == 0
    assert manager.close_session_sockets("never-seen") == 0


def test_service_closes_websockets_of_a_revoked_session(server):
    endpoints, secret = server
    svc = _service_with(endpoints, secret)
    endpoints._on_revoke = svc._session_revoked
    svc._session_revoked("nobody-listening")  # no VUI endpoints yet: nothing to do, no error
    svc._vui_endpoints = MagicMock()
    manager = svc._vui_endpoints.pubsub_manager = VUIPubsubManager(MagicMock())
    tokens = _login(endpoints)
    sock = _FakeSocket()
    claims = jwt.decode(tokens["access_token"], secret, algorithms=["HS256"])
    assert claims["sub"] == USER    # the user is named independently of the session
    manager.client_opened(sock, "devices/a", tokens["access_token"], claims)

    assert "204" in _revoke(endpoints, tokens["refresh_token"]).status
    assert sock.terminated and sock.closed_with == "Session revoked"


def test_pubsub_manager_without_sockets_is_fine(server):
    endpoints, secret = server
    svc = _service_with(endpoints, secret)
    svc._vui_endpoints = MagicMock(spec=[])  # VUIEndpoints built without the pubsub route
    svc._session_revoked("whatever")


def test_a_cutoff_from_the_future_is_clamped_to_now(tmp_path):
    path = tmp_path / "revoked.json"
    path.write_text(json.dumps({ISSUED_BEFORE_KEY: time.time() + 3600}))
    revoked = RevokedSessions(str(path))
    assert revoked.issued_before <= time.time()
    assert revoked.allows({SESSION_CLAIM: "new", "iat": int(time.time()) + 1})


def test_cutoff_is_persisted_later_when_the_first_write_fails(tmp_path, monkeypatch):
    path = tmp_path / "revoked.json"
    path.write_text("not json")
    import volttron.platform.web.token_revocation as module
    real_replace = module.os.replace
    calls = {"n": 0}

    def failing_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:          # the quarantine rename succeeds, the first save's rename fails
            raise OSError("disk full")
        return real_replace(src, dst)

    monkeypatch.setattr(module.os, "replace", failing_replace)
    revoked = RevokedSessions(str(path))
    assert revoked.issued_before is not None and not path.exists()
    # The next check persists the cutoff, and a restart therefore still refuses the older tokens.
    assert not revoked.allows({SESSION_CLAIM: "old", "iat": int(time.time()) - 10})
    assert path.exists()
    assert RevokedSessions(str(path)).issued_before == revoked.issued_before
