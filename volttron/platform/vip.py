# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

'''VIP - VOLTTRON™ Interconnect Protocol implementation

See https://github.com/VOLTTRON/volttron/wiki/VIP for protocol
specification.
'''


from __future__ import absolute_import, print_function

from logging import CRITICAL, DEBUG, ERROR, WARNING

# If a parent module imported zmq.green, use it to avoid deadlock
try:
    import _vip_zmq as zmq
except ImportError:
    import zmq
from zmq import NOBLOCK, SNDMORE, ZMQError, EINVAL, DEALER, ROUTER, RCVMORE


__all__ = ['ProtocolError', 'Message', 'Socket', 'BaseRouter']


_GREEN = zmq.__name__.endswith('.green')


PROTO = b'VIP1'

# Create these static frames for non-copy sends as an optimization
_PROTO = zmq.Frame(PROTO)
_ERROR = zmq.Frame(b'error')
_PONG = zmq.Frame(b'pong')
_VERSION = zmq.Frame(b'1.0')
_WELCOME = zmq.Frame(b'welcome')

# Error code to message mapping
ERRORS = {
    30: 'Peer unknown',
    31: 'Peer temporarily unavailable',
    40: 'Bad request',
    41: 'Unauthorized',
    50: 'Internal error',
    51: 'Not implemented',
}

# Again, optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(code).encode('ascii')),
             zmq.Frame(ERRORS[code].encode('ascii')))
    for errnum, code in [(zmq.EHOSTUNREACH, 30), (zmq.EAGAIN, 31)]
}
_INVALID_SUBSYSTEM = (zmq.Frame(b'51'),
                      zmq.Frame(ERRORS[51].encode('ascii')))


class ProtocolError(Exception):
    '''Error raised for invalid use of Socket object.'''
    pass


class Message(object):
    '''Message object returned form Socket.recv_vip_obj().'''
    def __init__(self, **kwargs):
        self.__dict__ = kwargs
    def __repr__(self):
        return '{0.__class__.__name__}(**{0.__dict__!r})'.format(self)


class Socket(zmq.Socket):
    '''Subclass of zmq.Socket to implement VIP protocol.

    Sockets are of type DEALER by default. If a ROUTER socket is used,
    an intermediary address must be used either as the first element or
    using the via argument, depending on what the method supports.

    A state machine is implemented by the send() and recv() methods to
    ensure the proper number, type, and ordering of frames. Protocol
    violations will raise ProtocolError exceptions.
    '''

    __slots__ = ['_send_state', '_recv_state']

    def __new__(cls, context=None, socket_type=DEALER, shadow=None):
        '''Create and return a new Socket object.

        If context is None, use global instance from
        zmq.Context.instance().  socket_type defaults to DEALER, but
        ROUTER may also be used.
        '''
        # pylint: disable=arguments-differ
        if socket_type not in [DEALER, ROUTER]:
            raise ValueError('socket_type must be DEALER or ROUTER')
        if context is None:
            context = zmq.Context.instance()
        # There are multiple backends which handle shadow differently.
        # It is best to send it as a positional to avoid problems.
        base = super(Socket, cls)
        if shadow is None:
            return base.__new__(cls, context, socket_type)
        return base.__new__(cls, context, socket_type, shadow)

    def __init__(self, context=None, socket_type=DEALER, shadow=None):
        '''Initialize the object and the send and receive state.'''
        if context is None:
            context = zmq.Context.instance()
        # There are multiple backends which handle shadow differently.
        # It is best to send it as a positional to avoid problems.
        base = super(Socket, self)
        if shadow is None:
            base.__init__(context, socket_type)
        else:
            base.__init__(context, socket_type, shadow)
        # Initialize send and receive states, which are mapped as:
        #    state:  -1    0   [  1  ]    2       3       4      5
        #    frame:  VIA  PEER [PROTO] USER_ID  MSG_ID  SUBSYS  ...
        self._send_state = self._recv_state = (
            -1 if self.type == ROUTER else 0)

    def reset_send(self):
        '''Clear send buffer and reset send state machine.

        This method should rarely need to be called and only if
        ProtocolError has been raised during a send operation. Any
        frames in the send buffer will be sent.
        '''
        state = -1 if self.type == ROUTER else 0
        if self._send_state != state:
            self._send_state = state
            super(Socket, self).send('')

    def send(self, frame, flags=0, copy=True, track=False):
        '''Send a single frame while enforcing VIP protocol.

        Expects frames to be sent in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARG]...

        If the socket is a ROUTER, an INTERMEDIARY must be sent before
        PEER. The VIP protocol signature, PROTO, is automatically sent
        between PEER and USER_ID. Zero or more ARG frames may be sent
        after SUBSYSTEM, which may not be empty. All frames up to
        SUBSYSTEM must be sent with the SNDMORE flag.
        '''
        state = self._send_state
        if state == 4:
            # Verify that subsystem has some non-space content
            subsystem = bytes(frame)
            if not subsystem.strip():
                raise ProtocolError('invalid subsystem: {!r}'.format(subsystem))
        if not flags & SNDMORE:
            # Must have SNDMORE flag until sending SUBSYSTEM frame.
            if state < 4:
                raise ProtocolError(
                    'expecting at least {} more frames'.format(4 - state - 1))
            # Reset the send state when the last frame is sent
            self._send_state = -1 if self.type == ROUTER else 0
        elif state < 5:
            if state == 1:
                # Automatically send PROTO frame
                super(Socket, self).send(PROTO, flags=flags|SNDMORE)
                state += 1
            self._send_state = state + 1
        super(Socket, self).send(frame, flags=flags, copy=copy, track=track)

    def send_vip(self, peer, subsystem, args=None, msg_id=b'',
                 user=b'', via=None, flags=0, copy=True, track=False):
        '''Send an entire VIP message by individual parts.

        This method will raise a ProtocolError exception if the previous
        send was made with the SNDMORE flag or if other protocol
        constraints are violated. If SNDMORE flag is used, additional
        arguments may be sent. via is required for ROUTER sockets.
        '''
        state = self._send_state
        if state > 0:
            raise ProtocolError('previous send operation is not complete')
        elif state == -1:
            if via is None:
                raise ValueError("missing 'via' argument "
                                 "required by ROUTER sockets")
            self.send(via, flags=flags|SNDMORE, copy=copy, track=track)
        more = SNDMORE if args else 0
        self.send_multipart([peer, user, msg_id, subsystem],
                            flags=flags|more, copy=copy, track=track)
        if args:
            self.send_multipart(args, flags=flags, copy=copy, track=track)

    def send_vip_dict(self, dct, flags=0, copy=True, track=False):
        '''Send VIP message from a dictionary.'''
        msg_id = dct.pop('id', b'')
        self.send_vip(flags=flags, copy=copy, track=track, msg_id=msg_id, **dct)

    def send_vip_obj(self, msg, flags=0, copy=True, track=False):
        '''Send VIP message from an object.'''
        dct = {
            'via': getattr(msg, 'via', None),
            'peer': msg.peer,
            'subsystem': msg.subsystem,
            'user': getattr(msg, 'user', b''),
            'msg_id': getattr(msg, 'id', b''),
            'args': getattr(msg, 'args', None),
        }
        self.send_vip(flags=flags, copy=copy, track=track, *dct)

    def recv(self, flags=0, copy=True, track=False):
        '''Receive and return a single frame while enforcing VIP protocol.

        Expects frames to be received in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARG]...

        If the socket is a ROUTER, an INTERMEDIARY must be received
        before PEER. The VIP protocol signature, PROTO, is automatically
        received and validated between PEER and USER_ID. It is not
        returned as part of the result. Zero or more ARG frames may be
        received after SUBSYSTEM, which may not be empty. Until the last
        ARG frame is received, the RCVMORE option will be set.
        '''
        state = self._recv_state
        if state == 1:
            # Automatically receive and check PROTO frame
            proto = super(Socket, self).recv(flags=flags)
            state += 1
            self._recv_state = state
            if proto != PROTO:
                raise ProtocolError('invalid protocol: {!r}{}'.format(
                    proto[:30], '...' if len(proto) > 30 else ''))
        result = super(Socket, self).recv(flags=flags, copy=copy, track=track)
        if not self.getsockopt(RCVMORE):
            # Ensure SUBSYSTEM is received
            if state < 4:
                raise ProtocolError(
                    'expected at least {} more frames'.format(4 - state - 1))
            self._recv_state = -1 if self.type == ROUTER else 0
        elif state < 5:
            self._recv_state = state + 1
        return result

    def reset_recv(self):
        '''Clear recv buffer and reset recv state machine.

        This method should rarely need to be called and only if
        ProtocolError has been raised during a receive operation. Any
        frames in the recv buffer will be discarded.
        '''
        self._recv_state = -1 if self.type == ROUTER else 0
        while self.getsockopt(RCVMORE):
            super(Socket, self).recv()

    def recv_vip(self, flags=0, copy=True, track=False):
        '''Receive a complete VIP message and return as a list.

        The list includes frames in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARGS]

        If socket is a ROUTER, INTERMEDIARY will be inserted before PEER
        in the returned list. ARGS is always a possibly empty list.
        '''
        state = self._recv_state
        if state > 0:
            raise ProtocolError('previous recv operation is not complete')
        message = self.recv_multipart(flags=flags, copy=copy, track=track)
        idx = 4 - state
        result = message[:idx]
        result.append(message[idx:])
        return result

    def recv_vip_dict(self, flags=0, copy=True, track=False):
        '''Receive a complete VIP message and return in a dict.'''
        state = self._recv_state
        frames = self.recv_vip(flags=flags, copy=copy, track=track)
        via = frames.pop(0) if state == -1 else None
        dct = dict(zip(('peer', 'user', 'id', 'subsystem', 'args'), frames))
        if via is not None:
            dct['via'] = via
        return dct

    def recv_vip_obj(self, flags=0, copy=True, track=False):
        '''Recieve a complete VIP message and return as an object.'''
        msg = Message()
        msg.__dict__ = self.recv_vip_dict(flags=flags, copy=copy, track=track)
        return msg


class BaseRouter(object):
    '''Abstract base class of VIP router implementation.

    Router implementers should inherit this class and implement the
    setup() method to bind to appropriate addresses, set identities,
    setup authentication, etc, etc. The socket will be created by the
    start() method, which will then call the setup() method.  Once
    started, the socket may be polled for incoming messages and those
    messages are handled/routed by calling the route() method.  During
    routing, the log() method, which may be implemented, will be called
    to allow for debugging and logging. Custom subsystems may be
    implemented in the handle_subsystem() method. The socket will be
    closed when the stop() method is called.
    '''

    __slots__ = ['context', 'socket']

    def __init__(self, context=None):
        '''Initialize the object instance.

        If context is None (the default), the zmq global context will be
        used for socket creation.
        '''
        self.context = context or zmq.Context.instance()
        self.socket = None

    def start(self):
        '''Create the socket and call setup().

        The socket is save in the socket attribute. The setup() method
        is called at the end of the method to perform additional setup.
        '''
        self.socket = self.context.socket(ROUTER)
        self.socket.router_mandatory = True
        if not _GREEN:
            # Only set if not using zmq.green to avoid user warning
            self.socket.sndtimeo = 0
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

    def log(self, level, message, frames):
        '''Log what is happening in the router.

        This method does nothing by default and is meant to be
        overridden by router implementers. level is the same as in the
        standard library logging module, message is a brief description,
        and frames, if not None, is a list of frames as received from
        the sending peer.
        '''
        pass

    if zmq.zmq_version_info() >= (4, 1, 0):
        def lookup_user_id(self, sender, auth_token):
            '''Find and return a user identifier.

            Returns the UTF-8 encoded User-Id property from the sender
            frame or None if the authenticator did not set the User-Id
            metadata. May be extended to perform additional lookups.
            '''
            # pylint: disable=unused-argument
            # A user id might/should be set by the ZAP authenticator
            try:
                return sender.get('User-Id').encode('utf-8')
            except ZMQError as exc:
                if exc.errno != EINVAL:
                    raise
    else:
        def lookup_user_id(self, sender, auth_token):
            '''Find and return a user identifier.

            A no-op by default, this method must be overridden to map
            the sender and auth_token to a user ID. The returned value
            must be a string or None (if the token was not found).
            '''
            pass

    def route(self):
        '''Route one message and return.

        One message is read from the socket and processed. If the
        recipient is the router (empty recipient), the standard hello
        and ping subsystems are handled. Other subsystems are sent to
        handle_subsystem() for processing. Messages destined for other
        entities are routed appropriately.
        '''
        socket = self.socket
        log = self.log
        # Expecting incoming frames:
        #   [SENDER, RECIPIENT, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        frames = socket.recv_multipart(copy=False)
        log(DEBUG, 'incoming message', frames)
        if len(frames) < 6:
            # Cannot route if there are insufficient frames, such as
            # might happen with a router probe.
            if len(frames) == 2 and frames[0] and not frames[1]:
                log(DEBUG, 'router probe', frames)
            else:
                log(ERROR, 'unroutable message', frames)
            return
        sender, recipient, proto, auth_token, msg_id = frames[:5]
        if proto.bytes != PROTO:
            # Peer is not talking a protocol we understand
            log(ERROR, 'invalid protocol signature', frames)
            return
        user_id = self.lookup_user_id(sender, auth_token)
        if user_id is None:
            log(WARNING, 'missing user ID', frames)
            user_id = b''

        if not recipient.bytes:
            # Handle requests directed at the router
            subsystem = frames[4]
            name = subsystem.bytes
            if name == b'hello':
                frames = [sender, recipient, proto, user_id, msg_id,
                          _WELCOME, _VERSION, socket.identity, sender]
            elif name == b'ping':
                frames[:5] = [
                    sender, recipient, proto, user_id, msg_id, _PONG]
            else:
                frames = self.handle_subsystem(frames, user_id)
                if frames is None:
                    # Handler does not know of the subsystem
                    log(ERROR, 'unknown subsystem', frames)
                    errnum, errmsg = _INVALID_SUBSYSTEM
                    frames = [sender, recipient, proto, b'', msg_id,
                              _ERROR, errnum, errmsg, subsystem]
                elif not frames:
                    # Subsystem does not require a response
                    return
        else:
            # Route all other requests to the recipient
            frames[:4] = [recipient, sender, proto, user_id]

        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        try:
            # Try sending the message to its recipient
            socket.send_multipart(frames, flags=NOBLOCK, copy=False)
            log(DEBUG, 'outgoing message', frames)
        except ZMQError as exc:
            try:
                errnum, errmsg = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                log(CRITICAL, 'unhandled exception: {}'.format(exc), frames)
                raise exc
            log(ERROR, 'send failure: {}'.format(errmsg.bytes), frames)
            if sender is not frames[0]:
                # Only send errors if the sender and recipient differ
                frames = [sender, b'', proto, user_id, msg_id,
                          _ERROR, errnum, errmsg, recipient]
                try:
                    socket.send_multipart(frames, flags=NOBLOCK, copy=False)
                    log(DEBUG, 'outgoing error', frames)
                except ZMQError as exc:
                    # Be silent about most errors when sending errors
                    if exc.errno not in _ROUTE_ERRORS:
                        log(CRITICAL,
                            'unhandled exception: {}'.format(exc), frames)
                        raise
