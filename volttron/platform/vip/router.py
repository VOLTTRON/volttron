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


from __future__ import absolute_import

from logging import CRITICAL, DEBUG, ERROR, WARNING
import os

import zmq
from zmq import NOBLOCK, ZMQError, EINVAL


__all__ = ['BaseRouter']


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
    routing, the log() method, which may be implemented, will be called
    to allow for debugging and logging. Custom subsystems may be
    implemented in the handle_subsystem() method. The socket will be
    closed when the stop() method is called.
    '''

    _context_class = zmq.Context
    _socket_class = zmq.Socket

    def __init__(self, context=None):
        '''Initialize the object instance.

        If context is None (the default), the zmq global context will be
        used for socket creation.
        '''
        self.context = context or self._context_class.instance()
        self.socket = None

    def start(self):
        '''Create the socket and call setup().

        The socket is save in the socket attribute. The setup() method
        is called at the end of the method to perform additional setup.
        '''
        self.socket = self._socket_class(self.context, zmq.ROUTER)
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
        if proto.bytes != b'VIP1':
            # Peer is not talking a protocol we understand
            log(ERROR, 'invalid protocol signature', frames)
            return
        user_id = self.lookup_user_id(sender, auth_token)
        if user_id is None:
            log(WARNING, 'missing user ID', frames)
            user_id = b''

        subsystem = frames[5]
        if not recipient.bytes:
            # Handle requests directed at the router
            name = subsystem.bytes
            if name == b'hello':
                frames = [sender, recipient, proto, user_id, msg_id,
                          b'welcome', b'1.0', socket.identity, sender]
            elif name == b'ping':
                frames[:6] = [
                    sender, recipient, proto, user_id, msg_id, b'pong']
            else:
                response = self.handle_subsystem(frames, user_id)
                if response is None:
                    # Handler does not know of the subsystem
                    log(ERROR, 'unknown subsystem', frames)
                    errnum, errmsg = _INVALID_SUBSYSTEM
                    frames = [sender, recipient, proto, b'', msg_id,
                              b'error', errnum, errmsg, subsystem]
                elif not response:
                    # Subsystem does not require a response
                    return
                else:
                    frames = response
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
                          b'error', errnum, errmsg, recipient, subsystem]
                try:
                    socket.send_multipart(frames, flags=NOBLOCK, copy=False)
                    log(DEBUG, 'outgoing error', frames)
                except ZMQError as exc:
                    # Be silent about most errors when sending errors
                    if exc.errno not in _ROUTE_ERRORS:
                        log(CRITICAL,
                            'unhandled exception: {}'.format(exc), frames)
                        raise
