import json
from weakref import WeakValueDictionary
from collections import defaultdict

from ws4py.server.geventserver import WebSocketWSGIApplication
from ws4py.websocket import WebSocket
import logging

_log = logging.getLogger()


class VUIPubsubManager:
    def __init__(self, agent):
        self._agent = agent
        self.subscription_websockets = WeakValueDictionary() # Websockets for all topics with current subscriptions.
        self.publication_websockets = {}  # Websockets for all topics with current publication queue.
        self.user_websockets = defaultdict(dict)  # References to all websockets for each user access_token.
        self.session_tokens = defaultdict(set)  # Access tokens that opened websockets, per login session id.

    def get_socket_routes(self, access_token, topic=None):
        _log.debug('In get_socket_routes. subscription_websockets is: ')
        _log.debug(self.subscription_websockets)
        return {t: str(w) for t, w in self.user_websockets[access_token].items()}

"""Websocket subscriptions of the VUI pubsub endpoints.

A subscription websocket belongs to the login session whose access token opened it. The
manager keeps the open sockets per session so that revoking the session closes them, and
each socket's message-bus subscription is released when the socket closes.

A socket lives no longer than its access token. The client keeps a long-lived subscription
by sending a renewed access token over the socket (a text frame ``{"access_token": "..."}``)
before the current one expires; a token of the same login session, or of a new login by the
same user, is accepted. A socket whose token has expired, or whose session has been revoked,
is closed with code 1008. A periodic sweep catches idle sockets that receive no messages.
"""

import json
import logging
import time
from collections import defaultdict

from volttron.platform.scheduling import periodic

from ws4py.server.wsgiutils import WebSocketWSGIApplication
from ws4py.websocket import WebSocket

from .token_revocation import session_id

_log = logging.getLogger(__name__)

# Close code for a socket the server closes for an authorization reason (RFC 6455 "policy violation").
POLICY_VIOLATION = 1008


class VUIPubsubManager:
    # How often idle sockets are re-checked against their token's expiry and revocation state. Bounds the time a
    # socket can outlive its token when no message arrives to trigger the check in on_topic.
    SWEEP_INTERVAL = 60

    def __init__(self, agent):
        self._agent = agent
        self._sockets = defaultdict(set)    # login session id -> open VUIWebSockets of that session
        self._sweeper = None

    # ------------------------------------------------------------------ tokens

    def verify_token(self, access_token):
        """Return the verified claims of a live access token in the ``vui`` group, or None.

        Goes through the web service's ``get_user_claims`` so that the signature, expiry, grant type and
        session revocation are all checked in one place. Never raises.
        """
        if not access_token:
            return None
        try:
            claims = self._agent.get_user_claims(access_token) or {}
        except Exception as e:
            _log.debug(f'Websocket token did not validate: {e.__class__.__name__}')
            return None
        groups = claims.get('groups')
        if not isinstance(groups, (list, tuple, set)) or 'vui' not in groups:
            return None
        return claims

    # ------------------------------------------------------------------ endpoint API

    def open_subscription_socket(self, access_token, topic, sid=None):
        """Return the WSGI application that completes the websocket handshake for ``topic``.

        The socket verifies its token and registers itself through :meth:`client_opened` once ws4py has opened it;
        ``access_token`` and ``sid`` are accepted for callers that pass them but nothing is recorded before then.
        """
        _log.debug(f'Opening subscription websocket for topic {topic!r}')
        return WebSocketWSGIApplication(handler_cls=VUIWebSocket)

    def get_socket_routes(self, access_token, topic=None, *, claims=None):
        """The topics with open websockets for the login session of ``access_token``.

        ``claims`` are the already verified claims of the token when the caller has them; otherwise the token is
        verified here.
        """
        if claims is None:
            claims = self.verify_token(access_token)
        sid = session_id(claims)
        return {ws.vui_topic: str(ws) for ws in self._sockets.get(sid, ()) if not ws.terminated}

    def publish(self, topic, headers, message):
        subscriber_count = self._agent.vip.pubsub.publish('pubsub', topic, headers=headers, message=message).get(timeout=5)
        return {'number_of_subscribers': subscriber_count}

    # ------------------------------------------------------------------ socket lifecycle

    @staticmethod
    def _apply_claims(ws, access_token, claims):
        """Record on the socket the token it is currently authorized by."""
        ws.vui_token = access_token
        ws.vui_sid = session_id(claims)
        sub = claims.get('sub')
        ws.vui_sub = sub if isinstance(sub, str) and sub else None
        exp = claims.get('exp')
        ws.vui_exp = float(exp) if isinstance(exp, (int, float)) and not isinstance(exp, bool) else None

    def client_opened(self, ws, topic, access_token, claims):
        """Record an opened socket under its login session and subscribe it to ``topic``."""
        ws.vui_topic = topic
        self._apply_claims(ws, access_token, claims)
        _log.debug(f'VUIPubsubManager: subscribing a websocket to {topic!r}')
        self._agent.vip.pubsub.subscribe('pubsub', topic, ws.on_topic)
        self._sockets[ws.vui_sid].add(ws)
        self._ensure_sweeper()

    def renew_socket(self, ws, access_token):
        """Re-authorize an open socket with a renewed access token. Returns True when accepted.

        The token must verify and belong either to the socket's login session or to a new login by the same
        user (``sub`` claim). A socket that has already been closed cannot be renewed.
        """
        claims = self.verify_token(access_token)
        if claims is None or ws not in self._sockets.get(getattr(ws, 'vui_sid', None), ()):
            return False
        new_sid, sub = session_id(claims), claims.get('sub')
        same_session = new_sid == ws.vui_sid
        same_user = isinstance(sub, str) and bool(sub) and sub == ws.vui_sub
        if not (same_session or same_user):
            _log.warning(f'Refused to renew a websocket for {ws.vui_topic!r} with a token of another user.')
            return False
        if not same_session:
            self._sockets[ws.vui_sid].discard(ws)
            if not self._sockets[ws.vui_sid]:
                del self._sockets[ws.vui_sid]
            self._sockets[new_sid].add(ws)
        self._apply_claims(ws, access_token, claims)
        return True

    def revalidate_sockets(self):
        """Close every open socket whose token has expired or no longer verifies. Returns the number closed."""
        now, closed = time.time(), 0
        for ws in [ws for sockets in list(self._sockets.values()) for ws in sockets]:
            if ws.terminated:
                self.client_closed(ws)
            elif ws.vui_exp is not None and now >= ws.vui_exp:
                closed += self.close_socket(ws, 'Token expired')
            elif self.verify_token(ws.vui_token) is None:
                closed += self.close_socket(ws, 'Not Authorized')
        if closed:
            _log.info(f'Closed {closed} websocket(s) whose access token expired or was revoked.')
        return closed

    def _ensure_sweeper(self):
        """Start the periodic re-validation once the first socket is open (not in __init__: the agent's core may
        not be running yet, and unit tests build managers without one)."""
        if self._sweeper is not None:
            return
        core = getattr(self._agent, 'core', None)
        if core is None:
            return
        try:
            self._sweeper = core.schedule(periodic(self.SWEEP_INTERVAL), self.revalidate_sockets)
        except Exception as e:
            _log.warning(f'Could not schedule websocket re-validation: {e.__class__.__name__}')

    def client_closed(self, ws):
        """Forget a socket and release its message-bus subscription. Idempotent; returns True when it did anything."""
        sid = getattr(ws, 'vui_sid', None)
        sockets = self._sockets.get(sid)
        if sockets is None or ws not in sockets:
            return False
        sockets.discard(ws)
        if not sockets:
            del self._sockets[sid]
        try:
            self._agent.vip.pubsub.unsubscribe('pubsub', ws.vui_topic, ws.on_topic)
        except Exception as e:
            _log.warning(f'Could not unsubscribe a closed websocket from {ws.vui_topic!r}: {e.__class__.__name__}')
        return True

    def close_socket(self, ws, reason, code=POLICY_VIOLATION):
        """Release a socket's subscription and close it. Returns True when a live socket was closed."""
        self.client_closed(ws)
        if ws.terminated:
            return False
        try:
            ws.close(code=code, reason=reason)
        except Exception as e:
            _log.warning(f'Could not close a websocket ({reason}): {e.__class__.__name__}')
            return False
        return True

    def close_session_sockets(self, sid):
        """Close every websocket of the revoked login session ``sid``. Returns the number closed."""
        return sum(1 for ws in list(self._sockets.get(sid, ())) if self.close_socket(ws, 'Session revoked'))


class VUIWebSocket(WebSocket):
    """One client's subscription to one topic."""

    def _get_topic(self):
        from volttron.platform.web import get_bearer
        topic = self.environ['PATH_INFO'].split('/pubsub/')[1]
        try:
            access_token = get_bearer(self.environ)
        except Exception:    # no token, or a malformed Authorization header
            access_token = None
        return topic, access_token

    def opened(self):
        app = self.environ['ws4py.app']
        topic, access_token = self._get_topic()
        # The HTTP upgrade request was authorized by the VUI endpoint, but the websocket outlives the request.
        # Verify again here so a socket is never subscribed for a token that does not carry the vui group.
        claims = app.verify_token(access_token)
        if claims is None:
            _log.warning(f'Closing websocket for {topic!r}: token did not validate or lacks the vui group.')
            self.close(code=POLICY_VIOLATION, reason='Not Authorized')
            return
        app.client_opened(self, topic, access_token, claims)

    RENEWAL_HELP = 'Unrecognised message. Send {"access_token": "<renewed access token>"} to keep the subscription open.'

    def received_message(self, m):
        """The only message a client may send is a renewed access token, as a JSON text frame."""
        app = self.environ.get('ws4py.app')
        try:
            body = json.loads(m.data.decode('utf-8') if isinstance(m.data, bytes) else m.data)
        except (ValueError, AttributeError, UnicodeDecodeError):
            body = None
        token = body.get('access_token') if isinstance(body, dict) else None
        if not isinstance(token, str) or app is None:
            self._reply({'error': self.RENEWAL_HELP})
        elif app.renew_socket(self, token):
            self._reply({'renewed': True, 'expires': int(self.vui_exp) if self.vui_exp else None})
        else:
            self._reply({'error': 'Not Authorized'})

    def _reply(self, body):
        try:
            self.send(json.dumps(body))
        except Exception as e:
            _log.warning(f'Error replying on a subscription websocket: {e.__class__.__name__}')

    def closed(self, code, reason=None):
        app = self.environ.get('ws4py.app') if hasattr(self, 'environ') else None
        if app is not None:
            app.client_closed(self)

    def on_topic(self, peer, sender, bus, topic, headers, message):
        if self.terminated:
            return
        exp = getattr(self, 'vui_exp', None)
        if exp is not None and time.time() >= exp:
            app = self.environ.get('ws4py.app')
            if app is not None:
                app.close_socket(self, 'Token expired')
            else:
                self.close(code=POLICY_VIOLATION, reason='Token expired')
            return
        try:
            self.send(json.dumps(message))
        except Exception as e:
            _log.warning(f'Error sending subscription data: {e}')
