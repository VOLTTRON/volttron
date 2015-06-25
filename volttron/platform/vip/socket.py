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

import base64
import binascii
import urlparse

from zmq import SNDMORE, RCVMORE, DEALER, ROUTER, curve_keypair
from zmq.utils import z85


__all__ = ['ProtocolError', 'Message']


def encode_key(key):
    '''Base64-encode and return a key in a URL-safe manner.'''
    assert len(key) in (32, 40)
    if len(key) == 40:
        key = z85.decode(key)
    return base64.urlsafe_b64encode(key)[:-1]


def decode_key(key):
    '''Parse and return a Z85 encoded key from other encodings.'''
    length = len(key)
    if length == 40:
        return key
    elif length == 43:
        return z85.encode(base64.urlsafe_b64decode(key + '='))
    elif length == 44:
        return z85.encode(base64.urlsafe_b64decode(key))
    elif length == 54:
        return base64.urlsafe_b64decode(key + '==')
    elif length == 56:
        return base64.urlsafe_b64decode(key)
    elif length == 64:
        return z85.encode(binascii.unhexlify(key))
    elif length == 80:
        return binascii.unhexlify(key)
    raise ValueError('unknown key encoding')


class ProtocolError(Exception):
    '''Error raised for invalid use of Socket object.'''
    pass


class Message(object):
    '''Message object returned form Socket.recv_vip_object().'''
    def __init__(self, **kwargs):
        self.__dict__ = kwargs
    def __repr__(self):
        attrs = ', '.join('%r: %r' % (name, bytes(value)) for name, value in
                          self.__dict__.iteritems())
        return '%s(**{%s})' % (self.__class__.__name__, attrs)


class _Socket(object):
    '''Subclass of zmq.Socket to implement VIP protocol.

    Sockets are of type DEALER by default. If a ROUTER socket is used,
    an intermediary address must be used either as the first element or
    using the via argument, depending on what the method supports.

    A state machine is implemented by the send() and recv() methods to
    ensure the proper number, type, and ordering of frames. Protocol
    violations will raise ProtocolError exceptions.
    '''

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
            context = cls._context_class.instance()
        # There are multiple backends which handle shadow differently.
        # It is best to send it as a positional to avoid problems.
        base = super(_Socket, cls)
        if shadow is None:
            return base.__new__(cls, context, socket_type)
        return base.__new__(cls, context, socket_type, shadow)

    def __init__(self, context=None, socket_type=DEALER, shadow=None):
        '''Initialize the object and the send and receive state.'''
        if context is None:
            context = self._context_class.instance()
        # There are multiple backends which handle shadow differently.
        # It is best to send it as a positional to avoid problems.
        base = super(_Socket, self)
        if shadow is None:
            base.__init__(context, socket_type)
        else:
            base.__init__(context, socket_type, shadow)
        # Initialize send and receive states, which are mapped as:
        #    state:  -1    0   [  1  ]    2       3       4      5
        #    frame:  VIA  PEER [PROTO] USER_ID  MSG_ID  SUBSYS  ...
        state = -1 if self.type == ROUTER else 0
        object.__setattr__(self, '_send_state', state)
        object.__setattr__(self, '_recv_state', state)
        self.immediate = True

    def reset_send(self):
        '''Clear send buffer and reset send state machine.

        This method should rarely need to be called and only if
        ProtocolError has been raised during a send operation. Any
        frames in the send buffer will be sent.
        '''
        state = -1 if self.type == ROUTER else 0
        if self._send_state != state:
            self._send_state = state
            super(_Socket, self).send('')

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
                super(_Socket, self).send(b'VIP1', flags=flags|SNDMORE)
                state += 1
            self._send_state = state + 1
        super(_Socket, self).send(frame, flags=flags, copy=copy, track=track)

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
        if msg_id is None:
            msg_id = b''
        if user is None:
            user = b''
        more = SNDMORE if args else 0
        self.send_multipart([peer, user, msg_id, subsystem],
                            flags=flags|more, copy=copy, track=track)
        if args:
            send = (self.send if isinstance(args, basestring)
                    else self.send_multipart)
            send(args, flags=flags, copy=copy, track=track)

    def send_vip_dict(self, dct, flags=0, copy=True, track=False):
        '''Send VIP message from a dictionary.'''
        msg_id = dct.pop('id', b'')
        self.send_vip(flags=flags, copy=copy, track=track, msg_id=msg_id, **dct)

    def send_vip_object(self, msg, flags=0, copy=True, track=False):
        '''Send VIP message from an object.'''
        dct = {
            'via': getattr(msg, 'via', None),
            'peer': msg.peer,
            'subsystem': msg.subsystem,
            'user': getattr(msg, 'user', b''),
            'msg_id': getattr(msg, 'id', b''),
            'args': getattr(msg, 'args', None),
        }
        self.send_vip(flags=flags, copy=copy, track=track, **dct)

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
            proto = super(_Socket, self).recv(flags=flags)
            state += 1
            self._recv_state = state
            if proto != b'VIP1':
                raise ProtocolError('invalid protocol: {!r}{}'.format(
                    proto[:30], '...' if len(proto) > 30 else ''))
        result = super(_Socket, self).recv(flags=flags, copy=copy, track=track)
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
            super(_Socket, self).recv()

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

    def recv_vip_object(self, flags=0, copy=True, track=False):
        '''Recieve a complete VIP message and return as an object.'''
        msg = Message()
        msg.__dict__ = self.recv_vip_dict(flags=flags, copy=copy, track=track)
        return msg

    def bind(self, addr):
        '''Extended zmq.Socket.bind() to include options in addr.

        The URL given by addr may optionally contain the query
        parameters and a URL fragment. If given, the fragment will be
        used as the socket identity.

        Valid query parameters:
            secretkey: curve secret key. If set, the socket
                       ZMQ_CURVE_SERVER option will be set on the
                       socket and ZMQ_CURVE_SECRETKEY will be set
                       to the parameter value after it is decode
                       by decode_key().

        Note: subsequent binds will use the values of the previous bind
              unless explicitly included in the address.
        '''
        url = urlparse.urlparse(addr)
        if url.fragment:
            self.identity = url.fragment
        params = urlparse.parse_qs(url.query)
        if url.scheme == 'tcp':
            secretkey = params.get('secretkey')
            if secretkey:
                secretkey = decode_key(secretkey[0])
                self.curve_server = True
                self.curve_secretkey = secretkey
        addr = '%s://%s%s' % url[:3]
        super(_Socket, self).bind(addr)

    def connect(self, addr):
        '''Extended zmq.Socket.connect() to include options in addr.

        The URL given by addr may optionally contain the query
        parameters and a URL fragment. If given, the fragment will be
        used as the socket identity.

        Valid query parameters:
            serverkey: curve server public key (ZMQ_CURVE_SERVERKEY)
            keypair: curve client key pair, concatenated
                     (ZMQ_CURVE_PUBLICKEY, ZMQ_CURVE_SECRETKEY)

        All keys are first parsed by decode_key() and then set on the
        appropriate socket option. If serverkey is given but not
        keypair, a key pair is automatically generated and used.

        Note: subsequent connects will use the values of the previous
              connect unless explicitly included in the address.
        '''
        url = urlparse.urlparse(addr)
        if url.fragment:
            self.identity = url.fragment
        if url.scheme == 'tcp':
            params = urlparse.parse_qs(url.query)
            serverkey = params.get('serverkey')
            if serverkey:
                serverkey = decode_key(serverkey[0])
                keypair = params.get('keypair')
                if keypair:
                    keypair = keypair[0]
                    mid = len(keypair) // 2
                    publickey = decode_key(keypair[:mid])
                    secretkey = decode_key(keypair[mid:])
                else:
                    publickey, secretkey = keypair = curve_keypair()
                self.curve_serverkey = serverkey
                self.curve_secretkey = secretkey
                self.curve_publickey = publickey
        addr = '%s://%s%s' % url[:3]
        super(_Socket, self).connect(addr)
