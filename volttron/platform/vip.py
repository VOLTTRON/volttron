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
import sys

# If a parent module imported zmq.green, use it to avoid deadlock
try:
    import _vip_zmq as zmq
except ImportError:
    import zmq
from zmq import NOBLOCK, SNDMORE, ZMQError, EINVAL


#_GREEN = zmq.__name__.endswith('green')

PROTO = b'VIP1'

# Create these static frames for non-copy sends as an optimization
F_PROTO = zmq.Frame(PROTO)
F_ERROR = zmq.Frame(b'error')
F_PONG = zmq.Frame(b'pong')
F_VERSION = zmq.Frame(b'1.0')
F_WELCOME = zmq.Frame(b'welcome')

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
ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(code).encode('ascii')),
             zmq.Frame(ERRORS[code].encode('ascii')))
    for errnum, code in [(zmq.EHOSTUNREACH, 30), (zmq.EAGAIN, 31)]
}
INVALID_SUBSYSTEM = (zmq.Frame(b'51'),
                     zmq.Frame(ERRORS[51].encode('ascii')))


class MessageError(ValueError):
    '''Error raised for invalid VIP messages when failing validation.

    Inherits from ValueError and adds the frames attribute which
    contains a list of message elements. Each element can be an instance
    of either zmq.Frame or bytes (str).
    '''
    def __init__(self, message, frames):
        super(MessageError, self).__init__(message)
        self.frames = frames


class Message(object):
    '''Class representing VIP message components.'''

    __slots__ = ('peer', 'proto', 'user', 'id', 'subsystem', 'args')

    def __init__(self, *args, **kwargs):
        '''Create a Message from frames and/or keyword arguments.

        Takes 0 or 1 positional arguments and 0 to 6 keyword arguments
        defined in __slots__.  If the positional argument is given, it
        must be a list-like object, that supports slicing and has at
        least 5 elements, which will be used to initialize attributes.
        Otherwise, object attributes will be set to empty values. Any
        keyword arguments will then be used to update object attributes
        with the same names.
        '''
        # pylint: disable=invalid-name
        if args:
            if len(args) != 1:
                raise TypeError('__init__() takes at most 2 positional '
                                'arguments ({} given)'.format(len(args) + 1))
            frames = args[0]
            (self.peer, self.proto,
             self.user, self.id, self.subsystem) = frames[:5]
            args = frames[6:]
            if not isinstance(args, list):
                args = list(args)
            self.args = args
        else:
            self.peer = self.user = self.id = self.subsystem = b''
            self.proto = PROTO
            self.args = []
        for name, value in kwargs.iteritems():
            if name not in self.__slots__:
                raise TypeError('__init__() got an unexpected keyword '
                                'argument {!r}'.format(name))
            setattr(self, name, value)

    def __repr__(self):
        args = ', '.join('{}={!r}'.format(name, getattr(self, name))
                         for name in self.__slots__)
        return '{}({})'.format(self.__class__.__name__, args)

    def frames(self):
        '''Reassemble attributes into a list and return it.'''
        result = [self.peer, self.proto, self.user, self.id, self.subsystem]
        result.extend(self.args)
        return result


def _validate_frames(frames):
    '''Validate message frames against basic criteria for VIP.

    Raises MessageError if validation fails.
    '''
    if len(frames) < 5:
        raise MessageError('insufficient frames', frames)
    proto = bytes(frames[1])
    if proto != PROTO:
        # Peer is not talking a protocol we understand
        if len(proto > 30):
            proto = proto[:30] + '...'
        raise MessageError('invalid protocol version: {}'.format(proto), frames)
    subsystem = bytes(frames[4]).strip()
    if not subsystem:
        raise MessageError('empty subsystem: {}'.format(subsystem), frames)


def recv_frames(socket, flags=0, copy=True, track=False):
    '''Receive and return a list of validated frames from socket.

    Expects frames [SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...].

    Raises MessageError if validation fails.
    '''
    frames = socket.recv_multipart(flags, copy, track)
    _validate_frames(frames)
    return frames


def recv_frames_via(socket, flags=0, copy=True, track=False):
    '''Receive and return validated frames via an intermediary.

    socket should be a ROUTER socket, which will automatically prepend
    the frames with the intermediary address. Returns the 2-tuple
    (intermediary, frames) where intermediary is the identity of the
    sending peer and frames is a list as returned from recv_frames().
    '''
    intermediary = socket.recv(flags, copy, track)
    assert socket.more
    frames = recv_frames(socket, flags, copy, track)
    return intermediary, frames


def recv_message(socket, flags=0, copy=True, track=False):
    '''Receive frames and return as Message object.'''
    return Message(recv_frames(socket, flags, copy, track))


def recv_message_via(socket, flags=0, copy=True, track=False):
    '''Receive frames via intermediary and return as Message object.'''
    intermediary, frames = recv_frames_via(socket, flags, copy, track)
    return intermediary, Message(frames)


def send_frames(socket, frames, flags=0, copy=True, track=False):
    '''Send frames, validating them first.'''
    _validate_frames(frames)
    return socket.send_multipart(frames, flags, copy, track)


def send_frames_via(socket, intermediary, frames,
                    flags=0, copy=True, track=False):
    '''Send frames via an intermediary, validating them first.'''
    _validate_frames(frames)
    socket.send(intermediary, flags|SNDMORE, copy)
    return socket.send_multipart(frames, flags, copy, track)


def send_message(socket, message, flags=0, copy=True, track=False):
    '''Extract frames from Message object and send.'''
    return send_frames(socket, message.frames(), flags, copy, track)


def send_message_via(socket, intermediary, message,
                     flags=0, copy=True, track=False):
    '''Extract frames from Message object and send via intermediary.'''
    return send_frames_via(
        socket, intermediary, message.frames(), flags, copy, track)


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
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.router_mandatory = True
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
                          F_WELCOME, F_VERSION, socket.identity, sender]
            elif name == b'ping':
                frames[:5] = [
                    sender, recipient, proto, user_id, msg_id, F_PONG]
            else:
                frames = self.handle_subsystem(frames, user_id)
                if frames is None:
                    # Handler does not know of the subsystem
                    log(ERROR, 'unknown subsystem', frames)
                    errnum, errmsg = INVALID_SUBSYSTEM
                    frames = [sender, recipient, proto, b'', msg_id,
                              F_ERROR, errnum, errmsg, subsystem]
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
                errnum, errmsg = ROUTE_ERRORS[exc.errno]
            except KeyError:
                log(CRITICAL, 'unhandled exception: {}'.format(exc), frames)
                raise exc
            log(ERROR, 'send failure: {}'.format(errmsg.bytes), frames)
            if sender is not frames[0]:
                # Only send errors if the sender and recipient differ
                frames = [sender, b'', proto, user_id, msg_id,
                          F_ERROR, errnum, errmsg, recipient]
                try:
                    socket.send_multipart(frames, flags=NOBLOCK, copy=False)
                    log(DEBUG, 'outgoing error', frames)
                except ZMQError as exc:
                    # Be silent about most errors when sending errors
                    if exc.errno not in ROUTE_ERRORS:
                        log(CRITICAL,
                            'unhandled exception: {}'.format(exc), frames)
                        raise
