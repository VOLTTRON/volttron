"""Revocation of web login sessions (``DELETE /authenticate``).

Web tokens are stateless JWTs, so revocation is a deny-list. The unit of
revocation is the login session: every token minted at one login carries the
same ``sid`` claim, and access tokens renewed from the refresh token inherit
it. Revoking the session invalidates all of them at once, which is what a
logout or a response to a stolen token needs.

Entries are kept only until the longest-lived token of the session can have
expired, and are persisted under VOLTTRON_HOME so that a restart of the web
service does not resurrect a revoked session. A token without a ``sid`` claim
cannot be revoked, so such tokens are never accepted.
"""

import json
import logging
import os
import tempfile
import time
import uuid

_log = logging.getLogger(__name__)

SESSION_CLAIM = 'sid'
REVOKED_SESSIONS_FILE = 'web-revoked-sessions.json'
_MAX_SESSION_ID_LENGTH = 64


def new_session_id():
    return uuid.uuid4().hex


def session_id(claims):
    """Return the session id of a decoded token, or None when it has none.

    Only a non-empty str of bounded length counts: the claim becomes a dict
    key and a file entry, so it must not be an arbitrary object or unbounded.
    """
    if not isinstance(claims, dict):
        return None
    sid = claims.get(SESSION_CLAIM)
    if not isinstance(sid, str) or not sid or len(sid) > _MAX_SESSION_ID_LENGTH:
        return None
    return sid


class RevokedSessions:
    """Deny-list of session ids with their expiry, persisted as a JSON file.

    The file is rewritten atomically (temp file + rename, mode 0600) on every
    revocation. Reading is an in-memory lookup.
    """

    def __init__(self, path):
        self._path = path
        self._expiry = {}
        self._load()

    @property
    def path(self):
        return self._path

    def __len__(self):
        return len(self._expiry)

    def __contains__(self, sid):
        return self.is_revoked(sid)

    def is_revoked(self, sid):
        expires_at = self._expiry.get(sid)
        if expires_at is None:
            return False
        if expires_at <= time.time():
            # Every token of the session has expired; the entry is only stale.
            self._expiry.pop(sid, None)
            return False
        return True

    def allows(self, claims):
        """True when the decoded claims belong to a session that is not revoked.

        A token without a usable ``sid`` is refused: it predates revocation
        support and could never be revoked.
        """
        sid = session_id(claims)
        return sid is not None and not self.is_revoked(sid)

    def revoke(self, sid, expires_at):
        """Deny ``sid`` until ``expires_at`` (seconds since the epoch).

        Idempotent; a repeat revocation keeps the later expiry.
        """
        if session_id({SESSION_CLAIM: sid}) is None:
            raise ValueError('invalid session id')
        now = time.time()
        self._prune(now)
        if expires_at <= now:
            return
        self._expiry[sid] = max(self._expiry.get(sid, 0), float(expires_at))
        self._save()

    def _prune(self, now):
        stale = [sid for sid, expires_at in self._expiry.items() if expires_at <= now]
        for sid in stale:
            del self._expiry[sid]

    def _load(self):
        try:
            with open(self._path, encoding='utf-8') as fp:
                stored = json.load(fp)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as err:
            # Nothing safe can be recovered from a damaged deny-list; say so
            # loudly rather than fail to start the web service.
            _log.error('Could not read revoked web sessions from %s: %s', self._path, type(err).__name__)
            return
        if not isinstance(stored, dict):
            _log.error('Ignoring revoked web sessions file %s: not a JSON object', self._path)
            return
        now = time.time()
        for sid, expires_at in stored.items():
            if session_id({SESSION_CLAIM: sid}) is None:
                continue
            if isinstance(expires_at, (int, float)) and not isinstance(expires_at, bool) and expires_at > now:
                self._expiry[sid] = float(expires_at)

    def _save(self):
        directory = os.path.dirname(self._path) or '.'
        fd, tmp_path = tempfile.mkstemp(prefix='.' + os.path.basename(self._path) + '.', dir=directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fp:
                json.dump(self._expiry, fp, sort_keys=True)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
