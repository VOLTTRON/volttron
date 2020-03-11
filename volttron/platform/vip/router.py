# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}




import os
import logging
import zmq
from zmq import Frame, NOBLOCK, ZMQError, EINVAL, EHOSTUNREACH

from volttron.utils.frame_serialization import serialize_frames

__all__ = ['BaseRouter', 'OUTGOING', 'INCOMING', 'UNROUTABLE', 'ERROR']

OUTGOING = 0
INCOMING = 1
UNROUTABLE = 2
ERROR = 3

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

class BaseRouter(object):
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

    def __init__(self, context=None, default_user_id=None):
        '''Initialize the object instance.

        If context is None (the default), the zmq global context will be
        used for socket creation.
        '''
        self.context = context or self._context_class.instance()
        self.default_user_id = default_user_id
        self.socket = None
        self._peers = set()
        self._poller = self._poller_class()
        self._ext_sockets = []
        self._socket_id_mapping = {}

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
        '''Close the socket.'''
        self.socket.close(linger)

    def setup(self):
        '''Called from start() method to setup the socket.

        Implement this method to bind the socket, set identities and
        options, etc.
        '''
        raise NotImplementedError()

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

    if zmq.zmq_version_info() >= (4, 1, 0):
        def lookup_user_id(self, sender, recipient, auth_token):
            '''Find and return a user identifier.

            Returns the UTF-8 encoded User-Id property from the sender
            frame or None if the authenticator did not set the User-Id
            metadata. May be extended to perform additional lookups.
            '''
            # pylint: disable=unused-argument
            # A user id might/should be set by the ZAP authenticator
            try:
                # _log.debug(f"THE TYPE IS:::::::: {type(recipient)}")
                # recipient.get('User-Id').encode('utf-8') returns sender !!!
                return sender
            except ZMQError as exc:
                if exc.errno != EINVAL:
                    raise
            return self.default_user_id
    else:
        def lookup_user_id(self, sender, recipient, auth_token):
            '''Find and return a user identifier.

            A no-op by default, this method must be overridden to map
            the sender and auth_token to a user ID. The returned value
            must be a string or None (if the token was not found).
            '''
            return self.default_user_id

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

    def _drop_peer(self, peer):
        try:
            self._peers.remove(peer)
        except KeyError:
            return
        self._distribute(b'peerlist', b'drop', peer)
        self._drop_pubsub_peers(peer)

    def route(self, frames):
        '''Route one message and return.

        One message is read from the socket and processed. If the
        recipient is the router (empty recipient), the standard hello
        and ping subsystems are handled. Other subsystems are sent to
        handle_subsystem() for processing. Messages destined for other
        entities are routed appropriately.
        '''
        socket = self.socket
        issue = self.issue

        issue(INCOMING, frames)
        # _log.debug(f"ROUTER Receiving frames: {frames}")
        if len(frames) < 6:
            # Cannot route if there are insufficient frames, such as
            # might happen with a router probe.
            if len(frames) == 2 and frames[0] and not frames[1]:
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
        user_id = self.lookup_user_id(sender, recipient, auth_token)
        if user_id is None:
            user_id = ''
        # _log.debug(f"user_id is {user_id}")
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
        socket = self.socket
        drop = []
        recipient, sender = frames[:2]
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        _log.info(f"BASE_ROUTER sending frames: {frames}")
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
                    socket.send_multipart(serialized_frames, flags=NOBLOCK, copy=False)
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
