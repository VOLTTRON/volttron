import errno
import hmac
import os
import secrets
import time
from copy import deepcopy

# 240 minutes is the platform refresh-token lifetime.
IDLE_TIMEOUT = 30 * 60
ABSOLUTE_TIMEOUT = 240 * 60

_ANY_CHANNEL = object()


class SessionHandler:
    """A cache of sessions authenticated by the platform web login.

    Callers add a session with `_add_session` once the platform has
    confirmed a login; this class does not authenticate on its own. Each
    session has two random values: a session id, which the browser holds as a
    cookie, and a channel id, which may appear in websocket paths and topics.
    Both are bound to the ip address the login came from.
    """
    def __init__(self, on_end=None, clock=time.monotonic):
        self._sessions = {}
        self._session_tokens = {}
        self._channels = {}
        self._stored_session_path = None
        self._on_end = on_end
        self._clock = clock

    def clear(self):
        for session in list(self._session_tokens.values()):
            self._end(session)
        self._sessions.clear()
        self._session_tokens.clear()
        self._channels.clear()

    def _add_session(self, user, ip, groups):
        """Add a user session; returns (session_id, channel).

        A second login for the same user ends the first session.
        """
        previous = self._sessions.get(user)
        if previous is not None:
            self._end(previous)
        now = self._clock()
        session = {'user': user, 'ip': ip, 'groups': groups,
                   'id': secrets.token_urlsafe(32),
                   'channel': secrets.token_urlsafe(16),
                   'created': now, 'last_seen': now}
        self._sessions[user] = session
        self._session_tokens[session['id']] = session
        self._channels[session['channel']] = session
        return session['id'], session['channel']

    def _end(self, session):
        if self._sessions.get(session['user']) is session:
            del self._sessions[session['user']]
        self._session_tokens.pop(session['id'], None)
        self._channels.pop(session['channel'], None)
        if self._on_end is not None:
            self._on_end(session['channel'])

    def _is_expired(self, session):
        now = self._clock()
        return (now - session['last_seen'] >= IDLE_TIMEOUT
                or now - session['created'] >= ABSOLUTE_TIMEOUT)

    def expire(self):
        """End every session past a limit."""
        for session in list(self._session_tokens.values()):
            if self._is_expired(session):
                self._end(session)

    def check_session(self, token, ip, channel=_ANY_CHANNEL):
        """Check if a session id has been authenticated.

        When `channel` is given it must also be the session's channel id.

        @return:
            A users session information or False.
        """
        if not self._session_tokens:
            self._load_auths()
        session = self._session_tokens.get(token) if isinstance(token, str) else None
        if not session:
            return False
        if self._is_expired(session):
            self._end(session)
            return False
        if session['ip'] != ip:
            return False
        if channel is not _ANY_CHANNEL and not self._channel_matches(session, channel):
            return False
        session['last_seen'] = self._clock()
        return {'user': session['user'], 'groups': deepcopy(session['groups']),
                'ip': session['ip'], 'channel': session['channel']}

    @staticmethod
    def _channel_matches(session, channel):
        return (isinstance(channel, str)
                and hmac.compare_digest(channel.encode('utf-8'),
                                        session['channel'].encode('utf-8')))

    def check_channel(self, channel, ip):
        """True when `channel` belongs to a live session opened from `ip`.

        This does not count as activity, because a channel id is not a
        credential.
        """
        session = self._channels.get(channel) if isinstance(channel, str) else None
        if not session:
            return False
        if self._is_expired(session):
            self._end(session)
            return False
        return session['ip'] == ip

    def _store_session(self):
        # Disable the storing of sessions to disk.
        return
        # if not self._stored_session_path:
        #     self._get_auth_storage()
        #
        # with open(self._stored_session_path, 'wb') as file:
        #     file.write(jsonapi.dumps(self._sessions))

    def _load_auths(self):
        self._sessions = {}
        return
        #
        # if not self._stored_session_path:
        #     self._get_auth_storage()
        # try:
        #     with open(self._stored_session_path) as file:
        #         self._sessions = jsonapi.loads(file.read())
        #
        #     self._session_tokens.clear()
        #     for k, v in self._sessions.items():
        #         self._session_tokens[v['token']] = v
        # except IOError:
        #     pass

    def _get_auth_storage(self):
        if not os.environ.get('VOLTTRON_HOME', None):
            raise ValueError('VOLTTRON_HOME environment must be set!')

        db_path = os.path.join(os.environ.get('VOLTTRON_HOME'),
                               'data/volttron.central.sessions')
        db_dir  = os.path.dirname(db_path)
        try:
            os.makedirs(db_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                raise
        self._stored_session_path = db_path
