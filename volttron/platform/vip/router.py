# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}




import os
import logging
from typing import Optional

import zmq
from zmq import Frame, NOBLOCK, ZMQError, EINVAL, EHOSTUNREACH

from volttron.platform.agent.known_identities import IN_PROCESS_IDENTITIES
from volttron.platform.vip.servicepeer import ServicePeerNotifier
from volttron.utils.frame_serialization import ENCODE_FORMAT, serialize_frames

__all__ = ['BaseRouter', 'RouterSender', 'OUTGOING', 'INCOMING', 'UNROUTABLE',
           'ERROR', 'ORIGIN_INPROC', 'ORIGIN_NETWORK']

OUTGOING = 0
INCOMING = 1
UNROUTABLE = 2
ERROR = 3

# Where a message arrived: the inproc-only socket, or the socket every network
# and ipc peer connects to. Only the socket tells the two apart.
ORIGIN_INPROC = 'inproc'
ORIGIN_NETWORK = 'network'

# Bounds the sets that remember which senders were already logged, so a peer
# choosing new identities cannot grow them without limit.
_LOGGED_SENDERS_LIMIT = 1024

_log = logging.getLogger(__name__)

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}
_INVALID_SUBSYSTEM = (
    zmq.Frame(str(zmq.EPROTONOSUPPORT).encode('ascii')),
    zmq.Frame(os.strerror(zmq.EPROTONOSUPPORT).encode('ascii'))
)


def is_power_of_ten(count):
    """True for 10, 100, 1000, ...; 1 is excluded because the first
    occurrence is logged by name."""
    return count >= 10 and str(count).rstrip('0') == '1'


class BaseRouter:
    '''Abstract base class of VIP router implementation.

    Router implementers should inherit this class and implement the
    setup() method to bind to appropriate addresses, set identities,
    setup authentication, etc, etc. The socket will be created by the
    start() method, which will then call the setup() method.  Once
    started, the socket may be polled for incoming messages and those
    messages are handled/routed by calling the route() method.  During
    routing, the issue() method, which may be implemented, will be
    called to allow for debugging and logging. Custom subsystems may be
    implemented in the handle_subsystem() method. The socket will be
    closed when the stop() method is called.
    '''

    _context_class = zmq.Context
    _socket_class = zmq.Socket
    _poller_class = zmq.Poller

    # Whether a message's user comes from the connection. Router sets it from
    # the platform option; any other subclass is held to the strict rule.
    enable_auth = True

    def __init__(self, context=None, default_user_id=None, service_notifier=Optional[ServicePeerNotifier]):
        '''Initialize the object instance.

        If context is None (the default), the zmq global context will be
        used for socket creation.
        '''
        self.context = context or self._context_class.instance()
        self.default_user_id = default_user_id
        self.socket = None
        # In-process peers arrive on this socket. None until a subclass binds it.
        self.inproc_socket = None
        self._identity_sockets = {}
        self._logged_senders = {}
        self._suppression_logged = set()
        self._drop_counts = {}
        self._peers = set()
        self._poller = self._poller_class()
        self._ext_sockets = []
        self._socket_id_mapping = {}
        self._service_notifier = service_notifier

    def run(self):
        '''Main router loop.'''
        self.start()
        try:
            while True:
                self.poll_sockets()
        finally:
            self.stop()

    def start(self):
        '''Create the socket and call setup().

        The socket is save in the socket attribute. The setup() method
        is called at the end of the method to perform additional setup.
        '''
        self.socket = sock = self._socket_class(self.context, zmq.ROUTER)
        sock.router_mandatory = True
        sock.sndtimeo = 0
        sock.tcp_keepalive = True
        sock.tcp_keepalive_idle = 180
        sock.tcp_keepalive_intvl = 20
        sock.tcp_keepalive_cnt = 6
        self.context.set(zmq.MAX_SOCKETS, 30690)
        sock.set_hwm(6000)
        _log.debug("ROUTER SENDBUF: {0}, {1}".format(sock.getsockopt(zmq.SNDBUF), sock.getsockopt(zmq.RCVBUF)))
        self.setup()

    def stop(self, linger=1):
        '''Close the sockets.'''
        self.socket.close(linger)
        if self.inproc_socket is not None:
            self.inproc_socket.close(linger)

    def setup(self):
        '''Called from start() method to setup the socket.

        Implement this method to bind the socket, set identities and
        options, etc.
        '''
        raise NotImplementedError()

    def socket_for(self, identity):
        '''Return the socket a message for identity must be sent on.

        A peer is reached on the socket it last arrived on. An identity not
        seen yet is reached on the inproc socket if it is an in-process
        identity and on the network socket otherwise, so an unknown peer
        fails with EHOSTUNREACH as before.
        '''
        mapped = self._identity_sockets.get(identity)
        if mapped is not None:
            return mapped
        if self.inproc_socket is not None and identity in IN_PROCESS_IDENTITIES:
            return self.inproc_socket
        return self.socket

    def _origin_socket(self, origin):
        if origin == ORIGIN_INPROC:
            return self.inproc_socket if self.inproc_socket is not None else self.socket
        if origin == ORIGIN_NETWORK:
            return self.socket
        raise ValueError('unknown message origin: {!r}'.format(origin))

    def _log_once(self, kind, sender, message, *args):
        """Warn once per sender and kind.

        `message` is a %-format string whose first argument is the sender;
        `args` fill the rest.
        """
        seen = self._logged_senders.setdefault(kind, set())
        if sender in seen:
            return
        if len(seen) >= _LOGGED_SENDERS_LIMIT:
            if kind not in self._suppression_logged:
                self._suppression_logged.add(kind)
                _log.warning(
                    'Further "%s" warnings are suppressed after %d senders',
                    kind, _LOGGED_SENDERS_LIMIT)
            return
        seen.add(sender)
        _log.warning(message, sender, *args)

    def _count_drop(self, kind):
        """Count a dropped message and return the count for its kind.

        The count includes senders whose warning is suppressed. A summary is
        logged at each power of ten, so a sustained drop stays visible
        without a line per message.
        """
        count = self._drop_counts[kind] = self._drop_counts.get(kind, 0) + 1
        if is_power_of_ten(count):
            _log.warning('%d messages dropped so far: %s', count, kind)
        return count

    def _claim_identity(self, sender, origin):
        '''Record the socket sender arrived on, or refuse the message.

        Returns False when the message must be dropped: a network peer using
        an in-process identity, or one whose identity is already held by the
        inproc socket. An identity first seen on the network that then
        appears on the inproc socket moves to the inproc socket.
        '''
        sock = self._origin_socket(origin)
        if origin == ORIGIN_NETWORK and sender in IN_PROCESS_IDENTITIES:
            self._log_once(
                'reserved', sender,
                'Dropping network message from reserved in-process identity %r')
            return False
        held = self._identity_sockets.get(sender)
        if held is None or held is sock:
            self._identity_sockets[sender] = sock
            return True
        if origin == ORIGIN_NETWORK:
            self._log_once(
                'taken', sender,
                'Dropping network message from %r: identity is in use on the inproc socket')
            return False
        self._log_once(
            'moved', sender,
            'Identity %r moved from the network socket to the inproc socket')
        self._identity_sockets[sender] = sock
        return True

    def poll_sockets(self):
        '''Called inside run method

        Implement this method to poll for sockets for incoming messages.
        '''
        raise NotImplementedError()

    @property
    def poll(self):
        '''Returns the underlying socket's poll method.'''
        return self.socket.poll

    def handle_subsystem(self, frames, user_id):
        '''Handle additional subsystems and provide a response.

        This method does nothing by default and may be implemented by
        subclasses to provide additional subsystems.

        frames is a list of zmq.Frame objects with the following
        elements:

          [SENDER, RECIPIENT, PROTOCOL, USER_ID, MSG_ID, SUBSYSTEM, ...]

        The return value should be None, if the subsystem is unknown, an
        empty list or False (or other False value) if the message was
        handled but does not require/generate a response, or a list of
        containing the following elements:

          [RECIPIENT, SENDER, PROTOCOL, USER_ID, MSG_ID, SUBSYSTEM, ...]

        '''
        pass

    def issue(self, topic, frames, extra=None):
        pass

    def lookup_user_id(self, sender, recipient, auth_token, origin,
                       raw_frames=None):
        '''Find and return the user identifier of a message's sender.

        With auth off the user is the sender. With auth on, a message from the
        inproc socket has the sender as its user, and a message from the
        network socket has the User-Id the ZAP handler set on the connection,
        read from raw_frames. A network message with no User-Id gets '' and
        one warning per sender. Nothing else yields the sender.
        '''
        # pylint: disable=unused-argument
        if not self.enable_auth:
            return sender
        if origin == ORIGIN_INPROC:
            return sender
        if origin != ORIGIN_NETWORK:
            raise ValueError('unknown message origin: {!r}'.format(origin))
        user_id = _connection_user_id(raw_frames)
        if user_id is None:
            self._log_once(
                'no-user', sender,
                'Network peer %r has no authenticated user; using the empty user')
            return ''
        return user_id

    def _distribute(self, *parts):
        drop = set()
        empty = ''
        frames = [empty, empty, 'VIP1', empty, empty]
        frames.extend(parts)
        # _log.debug(f"_distribute {parts}")
        for peer in self._peers:
            frames[0] = peer
            drop.update(self._send(frames))
        for peer in drop:
            self._drop_peer(peer)
            if self._service_notifier:
                self._service_notifier.peer_dropped(peer)

    def _drop_pubsub_peers(self, peer):
        '''Drop peers for pubsub subsystem. To be handled by subclasses'''
        pass

    def _add_pubsub_peers(self, peer):
        '''Add peers for pubsub subsystem. To be handled by subclasses'''
        pass

    def _add_peer(self, peer):
        if peer in self._peers:
            return
        self._distribute('peerlist', 'add', peer)
        self._peers.add(peer)
        self._add_pubsub_peers(peer)
        if self._service_notifier:
            self._service_notifier.peer_added(peer)

    def _drop_peer(self, peer):
        try:
            self._peers.remove(peer)
        except KeyError:
            return
        self._identity_sockets.pop(peer, None)
        self._distribute(b'peerlist', b'drop', peer)
        self._drop_pubsub_peers(peer)

    def route(self, frames, origin, raw_frames=None):
        '''Route one message and return.

        origin says which socket the message arrived on (ORIGIN_INPROC or
        ORIGIN_NETWORK) and has no default. raw_frames are the received frame
        objects, read for the connection's User-Id before they were decoded.

        One message is read from the socket and processed. If the
        recipient is the router (empty recipient), the standard hello
        and ping subsystems are handled. Other subsystems are sent to
        handle_subsystem() for processing. Messages destined for other
        entities are routed appropriately.
        '''
        socket = self._origin_socket(origin)
        issue = self.issue

        issue(INCOMING, frames)
        # _log.debug(f"ROUTER Receiving frames: {frames}")
        # Frames are JSON-decoded, so a peer can send a sender that cannot be
        # a dict key or a set member.
        if frames and not isinstance(frames[0], str):
            issue(UNROUTABLE, frames, 'sender is not text')
            return
        if len(frames) < 6:
            # Cannot route if there are insufficient frames, such as
            # might happen with a router probe.
            if len(frames) == 2 and frames[0] and not frames[1]:
                if not self._claim_identity(frames[0], origin):
                    issue(UNROUTABLE, frames, 'identity not allowed on socket')
                    return
                issue(UNROUTABLE, frames, 'router probe')
                self._add_peer(frames[0])
            else:
                issue(UNROUTABLE, frames, 'too few frames')
            return
        sender, recipient, proto, auth_token, msg_id = frames[:5]
        # _log.debug(f"routing {sender}, {recipient}, {proto}, {auth_token}, {msg_id}")
        if proto != 'VIP1':
            # Peer is not talking a protocol we understand
            issue(UNROUTABLE, frames, 'bad VIP signature')
            return
        if not self._claim_identity(sender, origin):
            issue(UNROUTABLE, frames, 'identity not allowed on socket')
            return
        user_id = self.lookup_user_id(sender, recipient, auth_token, origin,
                                      raw_frames)
        if user_id is None:
            user_id = ''
        self._add_peer(sender)
        subsystem = frames[5]
        if not recipient:
            # Handle requests directed at the router
            name = subsystem
            if name == 'hello':
                frames = [sender, recipient, proto, user_id, msg_id,
                          'hello', 'welcome', '1.0', socket.identity, sender]
            elif name == 'ping':
                frames[:7] = [
                    sender, recipient, proto, user_id, msg_id, 'ping', 'pong']
            elif name == 'peerlist':
                try:
                    op = frames[6]
                except IndexError:
                    op = None
                frames = [sender, recipient, proto, '', msg_id, subsystem]
                if op == 'list':
                    frames.append('listing')
                    frames.extend(self._peers)
                else:
                    error = ('unknown' if op else 'missing') + ' operation'
                    frames.extend(['error', error])
            elif name == 'error':
                return
            else:
                # Whatever USER_ID the peer wrote is replaced, so a response
                # built from the frames carries the router's value.
                frames[3] = user_id
                response = self.handle_subsystem(frames, user_id)
                if response is None:
                    # Handler does not know of the subsystem
                    errnum, errmsg = error = _INVALID_SUBSYSTEM
                    issue(ERROR, frames, error)
                    frames = [sender, recipient, proto, '', msg_id,
                              'error', errnum, errmsg, '', subsystem]
                elif not response:
                    # Subsystem does not require a response
                    return
                else:
                    frames = response
        else:
            # Route all other requests to the recipient
            frames[:4] = [recipient, sender, proto, user_id]
        for peer in self._send(frames):
            self._drop_peer(peer)

    def _send(self, frames):
        issue = self.issue
        drop = []
        recipient, sender = frames[:2]
        socket = self.socket_for(recipient)
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        try:
            # Try sending the message to its recipient
            # This is a zmq socket so we need to serialize it before sending
            serialized_frames = serialize_frames(frames)
            socket.send_multipart(serialized_frames, flags=NOBLOCK, copy=False)
            issue(OUTGOING, serialized_frames)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                error = None
            if error is None:
                raise
            issue(ERROR, frames, error)
            if exc.errno == EHOSTUNREACH:
                drop.append(recipient)
            if exc.errno != EHOSTUNREACH or sender is not frames[0]:
                # Only send errors if the sender and recipient differ
                proto, user_id, msg_id, subsystem = frames[2:6]
                frames = [sender, '', proto, user_id, msg_id,
                          'error', errnum, errmsg, recipient, subsystem]
                serialized_frames = serialize_frames(frames)
                try:
                    self.socket_for(sender).send_multipart(
                        serialized_frames, flags=NOBLOCK, copy=False)
                    issue(OUTGOING, serialized_frames)
                except ZMQError as exc:
                    try:
                        errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
                    except KeyError:
                        error = None
                    if error is None:
                        raise
                    issue(ERROR, serialized_frames, error)
                    if exc.errno == EHOSTUNREACH:
                        drop.append(sender)
        return drop


def _connection_user_id(raw_frames):
    """Return the User-Id the ZAP handler set on the connection the frames
    arrived on, or None when the connection carries none."""
    if not raw_frames:
        return None
    try:
        return raw_frames[0].get('User-Id')
    except ZMQError as exc:
        if exc.errno != EINVAL:
            raise
    except (AttributeError, NotImplementedError):
        # Bytes, or a libzmq without connection metadata: no User-Id to read.
        pass
    return None


class RouterSender:
    """The send side of the router's sockets for the services built on it.

    Each message goes on the socket its recipient is reached on, so a service
    cannot write to the wrong socket.
    """

    def __init__(self, router):
        self._router = router

    def send_multipart(self, frames, flags=0, copy=True):
        recipient = frames[0]
        if isinstance(recipient, Frame):
            recipient = recipient.bytes
        if isinstance(recipient, bytes):
            recipient = recipient.decode(ENCODE_FORMAT)
        self._router.socket_for(recipient).send_multipart(
            frames, flags=flags, copy=copy)
