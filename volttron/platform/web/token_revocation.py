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

A deny-list file that cannot be read is treated as damaged: it is moved aside
and every token issued before that moment is refused, so a revoked session cannot
come back through a damaged file. Users logged in before the damage log in again;
nothing issued afterwards is affected. The cutoff is persisted in the new file
under a reserved key so that a further restart does not forget it.
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
# Reserved key in the deny-list file: tokens issued before this time (seconds since the epoch) are refused.
# Session ids never start with an underscore, so the key cannot collide with one.
ISSUED_BEFORE_KEY = '_issued_before'
# How long the cutoff is kept; longer than any token lifetime.
_ISSUED_BEFORE_RETENTION = 7 * 24 * 3600


def new_session_id():
    return uuid.uuid4().hex


def session_id(claims):
    """Return the session id of a decoded token, or None when it has none.

    Only a non-empty str of bounded length that does not start with an underscore
    counts: the claim becomes a dict key and a file entry, so it must not be an
    arbitrary object, unbounded, or one of the file's reserved keys.
    """
    if not isinstance(claims, dict):
        return None
    sid = claims.get(SESSION_CLAIM)
    if not isinstance(sid, str) or not sid or len(sid) > _MAX_SESSION_ID_LENGTH or sid.startswith('_'):
        return None
    return sid


def _is_time(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class RevokedSessions:
    """Deny-list of session ids with their expiry, persisted as a JSON file.

    The file is rewritten atomically (temp file + rename, mode 0600) on every
    revocation. Reading is an in-memory lookup.
    """

    def __init__(self, path):
        self._path = path
        self._expiry = {}
        self._issued_before = None
        self._cutoff_unsaved = False
        self._load()

    @property
    def path(self):
        return self._path

    @property
    def issued_before(self):
        """Tokens issued before this time are refused (set after the file was found damaged), else None."""
        return self._issued_before

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
        support and could never be revoked. After the deny-list file was found
        damaged, a token issued before that moment (or without an ``iat``) is
        refused as well, since it may belong to a session that had been revoked.
        """
        sid = session_id(claims)
        if sid is None or self.is_revoked(sid):
            return False
        if self._issued_before is not None:
            self._persist_cutoff()
            iat = claims.get('iat')
            if not _is_time(iat) or iat < self._issued_before:
                return False
        return True

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
        self._cutoff_unsaved = False

    def _prune(self, now):
        stale = [sid for sid, expires_at in self._expiry.items() if expires_at <= now]
        for sid in stale:
            del self._expiry[sid]
        if self._issued_before is not None and now - self._issued_before > _ISSUED_BEFORE_RETENTION:
            self._issued_before = None

    def _load(self):
        try:
            with open(self._path, encoding='utf-8') as fp:
                stored = json.load(fp)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as err:
            self._quarantine(f'{type(err).__name__}')
            return
        if not isinstance(stored, dict):
            self._quarantine('not a JSON object')
            return
        now = time.time()
        cutoff = stored.pop(ISSUED_BEFORE_KEY, None)
        if _is_time(cutoff) and now - cutoff <= _ISSUED_BEFORE_RETENTION:
            # A cutoff ahead of the clock (the clock was corrected backwards) would refuse every new login.
            self._issued_before = min(float(cutoff), now)
        for sid, expires_at in stored.items():
            if session_id({SESSION_CLAIM: sid}) is None:
                continue
            if _is_time(expires_at) and expires_at > now:
                self._expiry[sid] = float(expires_at)

    def _quarantine(self, problem):
        """Treat an unreadable deny-list as damaged: keep the file aside and refuse every token issued so far.

        Failing open would let a revoked session come back; refusing all sessions until an operator intervenes
        would lock everyone out on a disk error. Refusing the tokens issued before now forces one re-login and
        nothing more. Whole seconds, like the ``iat`` claim.
        """
        self._issued_before = float(int(time.time()))
        kept = None
        if os.path.exists(self._path):
            kept = f'{self._path}.corrupt-{int(self._issued_before)}'
            try:
                os.replace(self._path, kept)
            except OSError as err:
                _log.error(f'Could not move the damaged revoked web sessions file aside: {type(err).__name__}')
                kept = None
        _log.error(f'The revoked web sessions file {self._path} could not be read ({problem}). Every web token '
                   f'issued before now is refused until its holder logs in again'
                   + (f'; the damaged file was kept as {kept}.' if kept else '.'))
        self._cutoff_unsaved = True
        self._persist_cutoff()

    def _persist_cutoff(self):
        """Write the cutoff recorded by :meth:`_quarantine`; retried on every check until it succeeds, so a
        write failure right after the damage does not lose the cutoff at the next restart."""
        if not self._cutoff_unsaved:
            return
        try:
            self._save()
            self._cutoff_unsaved = False
        except OSError as err:
            _log.error(f'Could not write a new revoked web sessions file: {type(err).__name__}')

    def _save(self):
        directory = os.path.dirname(self._path) or '.'
        fd, tmp_path = tempfile.mkstemp(prefix='.' + os.path.basename(self._path) + '.', dir=directory)
        try:
            data = dict(self._expiry)
            if self._issued_before is not None:
                data[ISSUED_BEFORE_KEY] = self._issued_before
            with os.fdopen(fd, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, sort_keys=True)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
