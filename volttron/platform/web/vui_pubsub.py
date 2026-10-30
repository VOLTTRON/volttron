"""Websocket subscriptions of the VUI pubsub endpoints.

A subscription websocket belongs to the login session whose access token opened it. The
manager keeps the open sockets per session so that revoking the session closes them.

The manager holds one message-bus subscription per topic, shared by every socket subscribed
to that topic, and releases it when the last of those sockets closes. (Unsubscribing a single
callback is not safe in every core: the Monolithic pubsub subsystem tells the router to drop
the prefix whenever any callback is removed, which would starve the other sockets.)

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


class _TopicDispatcher:
    """The one pubsub callback the manager registers for a topic; fans each message out to the topic's sockets.

    One persistent object per topic, so that re-subscribing after a release registers the same callable (the
    cores keep callbacks in a set) and no message is ever delivered twice.
    """

    def __init__(self, manager, topic):
        self._manager = manager
        self.topic = topic

    def __call__(self, peer, sender, bus, topic, headers, message):
        self._manager.deliver(self.topic, message)

    def __repr__(self):
        return f'<subscription dispatcher for {self.topic!r}>'


class VUIPubsubManager:
    # How often idle sockets are re-checked against their token's expiry and revocation state. Bounds the time a
    # socket can outlive its token when no message arrives to trigger the check on delivery.
    SWEEP_INTERVAL = 60

    def __init__(self, agent):
        self._agent = agent
        self._sockets = defaultdict(set)    # login session id -> open VUIWebSockets of that session
        self._topics = defaultdict(set)     # topic -> open VUIWebSockets subscribed to it
        self._dispatchers = {}              # topic -> its _TopicDispatcher (kept once created)
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
        return {ws.vui_topic: 'open' for ws in self._sockets.get(sid, ()) if not ws.terminated}

    def publish(self, topic, headers, message):
        subscriber_count = self._agent.vip.pubsub.publish('pubsub', topic, headers=headers, message=message).get(timeout=5)
        return {'number_of_subscribers': subscriber_count}

    # ------------------------------------------------------------------ bus subscriptions

    def dispatcher(self, topic):
        """The callback registered on the bus for ``topic`` (created once, reused for the topic's lifetime)."""
        dispatcher = self._dispatchers.get(topic)
        if dispatcher is None:
            dispatcher = self._dispatchers[topic] = _TopicDispatcher(self, topic)
        return dispatcher

    def _subscribe(self, topic):
        _log.debug(f'VUIPubsubManager: subscribing to {topic!r}')
        self._agent.vip.pubsub.subscribe('pubsub', topic, self.dispatcher(topic))

    def _release(self, topic):
        try:
            self._agent.vip.pubsub.unsubscribe('pubsub', topic, self.dispatcher(topic))
        except Exception as e:
            _log.warning(f'Could not unsubscribe from {topic!r}: {e.__class__.__name__}')

    def deliver(self, topic, message):
        """Forward a bus message to the open sockets of ``topic``; drop sockets whose token has expired."""
        sockets = self._topics.get(topic)
        if not sockets:
            # The subscribe for this topic completed after its last socket had already closed (the core's
            # subscribe is asynchronous), so the release at close time found nothing. Release it now.
            self._release(topic)
            return
        now = time.time()
        for ws in list(sockets):
            if ws.terminated:
                self.client_closed(ws)
            elif ws.vui_exp is not None and now >= ws.vui_exp:
                self.close_socket(ws, 'Token expired')
            else:
                ws.deliver(message)

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
        """Record an opened socket under its login session and topic; subscribe the topic on its first socket."""
        ws.vui_topic = topic
        self._apply_claims(ws, access_token, claims)
        first_on_topic = not self._topics[topic]
        self._topics[topic].add(ws)
        self._sockets[ws.vui_sid].add(ws)
        if first_on_topic:
            self._subscribe(topic)
        self._ensure_sweeper()

    def client_closed(self, ws):
        """Forget a socket; release the topic's subscription when it was the last socket on that topic.

        Idempotent; returns True when it did anything.
        """
        sid, topic = getattr(ws, 'vui_sid', None), getattr(ws, 'vui_topic', None)
        sockets = self._sockets.get(sid)
        if sockets is None or ws not in sockets:
            return False
        sockets.discard(ws)
        if not sockets:
            del self._sockets[sid]
        on_topic = self._topics.get(topic)
        if on_topic is not None:
            on_topic.discard(ws)
            if not on_topic:
                del self._topics[topic]
                self._release(topic)
        return True

    def close_socket(self, ws, reason, code=POLICY_VIOLATION):
        """Release a socket and close it. Returns True when a live socket was closed."""
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


class VUIWebSocket(WebSocket):
    """One client's subscription to one topic."""

    RENEWAL_HELP = 'Unrecognised message. Send {"access_token": "<renewed access token>"} to keep the subscription open.'

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

    def received_message(self, m):
        """The only message a client may send is a renewed access token, as a JSON text frame."""
        if self.server_terminated or self.client_terminated:
            return    # the close handshake is under way; nothing may be sent after a close frame
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

    def deliver(self, message):
        """Send a bus message to the client (the manager has already checked the token's expiry)."""
        if self.terminated:
            return
        try:
            self.send(json.dumps(message))
        except Exception as e:
            _log.warning(f'Error sending subscription data: {e.__class__.__name__}')
