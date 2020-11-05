# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

'''VIP - VOLTTRON™ Interconnect Protocol implementation

See https://volttron.readthedocs.io/en/develop/core_services/messagebus/VIP/VIP-Overview.html
for protocol specification.

This file contains an abstract _Socket class which should be extended to
provide missing features for different threading models. The standard
Socket class is defined in __init__.py. A gevent-friendly version is
defined in green.py.
'''




import base64
import binascii
from contextlib import contextmanager
import logging
import re
import sys
import urllib.request, urllib.parse, urllib.error
import urllib.parse
import uuid

from zmq import (SNDMORE, RCVMORE, NOBLOCK, POLLOUT, DEALER, ROUTER,
                 curve_keypair, Frame, ZMQError)
from zmq.error import Again
from zmq.utils import z85

from volttron.utils.frame_serialization import deserialize_frames, serialize_frames

__all__ = ['Address', 'ProtocolError', 'Message', 'nonblocking']

BASE64_ENCODED_CURVE_KEY_LEN = 43

_log = logging.getLogger(__name__)


@contextmanager
def nonblocking(sock):
    local = sock._Socket__local
    flags = getattr(local, 'flags', 0)
    local.flags = NOBLOCK
    yield sock
    local.flags = flags


def encode_key(key):
    '''Base64-encode and return a key in a URL-safe manner.'''
    # There is no easy way to test if key is already base64 encoded and ASCII decoded. This seems the best way.
    if len(key) % 4 != 0:
        return key
    key = key if isinstance(key, bytes) else key.encode("utf-8")
    try:
        assert len(key) in (32, 40)
    except AssertionError:
        raise AssertionError("Assertion error while encoding key:{}, len:{}".format(key, len(key)))
    if len(key) == 40:
        key = z85.decode(key)
    return base64.urlsafe_b64encode(key)[:-1].decode("ASCII")


def decode_key(key):
    '''Parse and return a Z85 encoded key from other encodings.'''
    if isinstance(key, str):
        key = key.encode("ASCII")
    length = len(key)
    if length == 40:
        return key
    elif length == 43:
        return z85.encode(base64.urlsafe_b64decode(key + '='.encode("ASCII")))
    elif length == 44:
        return z85.encode(base64.urlsafe_b64decode(key))
    elif length == 54:
        return base64.urlsafe_b64decode(key + '=='.encode("ASCII"))
    elif length == 56:
        return base64.urlsafe_b64decode(key)
    elif length == 64:
        return z85.encode(binascii.unhexlify(key))
    elif length == 80:
        return binascii.unhexlify(key)
    raise ValueError('unknown key encoding')


class Address(object):
    """Parse and hold a URL-style address.

    The URL given by address may contain optional query string
    parameters and a URL fragment which, if given, will be interpreted
    as the socket identity for the given address.

    Valid parameters:
        server:    Server authentication method; must be one of NULL,
                   PLAIN, or CURVE.
        domain:    ZAP domain for server authentication.
        serverkey: Encoded CURVE server public key.
        secretkey: Encoded CURVE secret key.
        publickey: Encoded CURVE public key.
        ipv6:      Boolean value indicating use of IPv6.
        username:  Username to use with PLAIN authentication.
        password:  Password to use with PLAIN authentication.
    """

    _KEYS = ('domain', 'server', 'secretkey', 'publickey',
             'serverkey', 'ipv6', 'username', 'password')
    _MASK_KEYS = ('secretkey', 'password')

    def __init__(self, address, **defaults):
        for name in self._KEYS:
            setattr(self, name, None)
        for name, value in defaults.items():
            setattr(self, name, value)

        url = urllib.parse.urlparse(address, 'tcp')

        # Old versions of python don't correctly parse queries for unknown
        # schemes. This can cause ipc failures on outdated installations.
        if not url.query and '?' in url.path:
            path, query = url.path.split('?')
            url = url._replace(path=path)
            url = url._replace(query=query)
        self.publickey = None
        self.secretkey = None
        self.base = '%s://%s%s' % url[:3]
        if url.fragment:
            self.identity = url.fragment
        elif address.endswith('#'):
            self.identity = ''
        else:
            self.identity = defaults.get('identity')
        if url.scheme not in ['tcp', 'ipc', 'inproc']:
            raise ValueError('unknown address scheme: %s' % url.scheme)
        for name, value in urllib.parse.parse_qsl(url.query, True):
            name = name.lower()
            if name in self._KEYS:
                if value and name.endswith('key'):
                    value = decode_key(value)
                elif name == 'server':
                    value = value.upper().strip()
                    if value not in ['NULL', 'PLAIN', 'CURVE']:
                        raise ValueError(
                            'bad value for server parameter: %r' % value)
                elif name == 'ipv6':
                    value = bool(re.sub(
                        r'\s*(0|false|no|off)\s*', r'', value, flags=re.I))
                setattr(self, name, value)

    @property
    def qs(self):
        params = ((name, getattr(self, name)) for name in self._KEYS)
        return urllib.parse.urlencode(
            {name: ('XXXXX' if name in self._MASK_KEYS and value else value)
             for name, value in params if value is not None})

    def __str__(self):
        parts = [self.base]
        qs = self.qs
        if qs:
            parts.extend(['?', qs])
        if self.identity is not None:
            parts.extend(['#', urllib.parse.quote(self.identity)])
        return ''.join(parts)

    def __repr__(self):
        return '%s.%s(%r)' % (
            self.__class__.__module__, self.__class__.__name__, str(self))

    def _set_sock_identity(self, sock):
        if self.identity:
            if isinstance(self.identity, str):
                sock.identity = self.identity.encode('utf-8')
            else:
                sock.identity = self.identity
        elif not sock.identity:
            self.identity = str(uuid.uuid4())
            sock.identity = self.identity.encode('utf-8')

    def bind(self, sock, bind_fn=None):
        """Extended zmq.Socket.bind() to include options in the address."""
        if not self.domain:
            raise ValueError('Address domain must be set')
        sock.zap_domain = self.domain.encode("utf-8") or b''
        self._set_sock_identity(sock)
        sock.ipv6 = self.ipv6 or False
        if self.server == 'CURVE':
            if not self.secretkey:
                raise ValueError('CURVE server used without secretkey')
            sock.curve_server = True
            sock.curve_secretkey = self.secretkey
        elif self.server == 'PLAIN':
            sock.plain_server = True
        else:
            sock.curve_server = False
            sock.plain_server = False
            if self.serverkey:
                sock.curve_serverkey = self.serverkey
                if not (self.publickey and self.secretkey):
                    self.publickey, self.secretkey = curve_keypair()
                sock.curve_secretkey = self.secretkey
                sock.curve_publickey = self.publickey
            elif self.username:
                sock.plain_username = self.username
                sock.plain_password = self.password or b''
        try:
            (bind_fn or sock.bind)(self.base)
            self.base = sock.last_endpoint.decode("utf-8")
        except ZMQError:
            message = 'Attempted to bind Volttron to already bound address {}, stopping'
            message = message.format(self.base)
            _log.error(message)
            print("\n" + message + "\n")
            sys.exit(1)

    def connect(self, sock, connect_fn=None):
        """Extended zmq.Socket.connect() to include options in the address."""
        self._set_sock_identity(sock)
        sock.ipv6 = self.ipv6 or False
        if self.serverkey:
            sock.curve_serverkey = self.serverkey
            if not (self.publickey and self.secretkey):
                self.publickey, self.secretkey = curve_keypair()
            sock.curve_secretkey = self.secretkey
            sock.curve_publickey = self.publickey
        elif self.username and self.password is not None:
            sock.plain_username = self.username
            sock.plain_password = self.password
        (connect_fn or sock.connect)(self.base)

    def reset(self, sock):
        sock.zap_domain = b''
        sock.ipv6 = False
        sock.curve_server = False
        sock.plain_server = False


class ProtocolError(Exception):
    """Error raised for invalid use of Socket object."""
    pass


class Message(object):
    """Message object returned form Socket.recv_vip_object()."""
    def __init__(self, **kwargs):
        self.__dict__ = kwargs

    def __repr__(self):
        attrs = ', '.join('%r: %r' % (
            name, [x for x in value]
            if isinstance(value, (list, tuple))
            else value) for name, value in
                self.__dict__.items())
        return '%s(**{%s})' % (self.__class__.__name__, attrs)


class _Socket(object):
    """Subclass of zmq.Socket to implement VIP protocol.

    Sockets are of type DEALER by default. If a ROUTER socket is used,
    an intermediary address must be used either as the first element or
    using the via argument, depending on what the method supports.

    A state machine is implemented by the send() and recv() methods to
    ensure the proper number, type, and ordering of frames. Protocol
    violations will raise ProtocolError exceptions.
    """

    def __new__(cls, context=None, socket_type=DEALER, shadow=None):
        """Create and return a new Socket object.

        If context is None, use global instance from
        zmq.Context.instance().  socket_type defaults to DEALER, but
        ROUTER may also be used.
        """
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
        """Initialize the object and the send and receive state."""
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
        object.__setattr__(self, '_Socket__local', self._local_class())
        self.immediate = True
        # Enable TCP keepalive with idle time of 3 minutes and 6
        # retries spaced 20 seconds apart, for a total of ~5 minutes.
        self.tcp_keepalive = True
        self.tcp_keepalive_idle = 180
        self.tcp_keepalive_intvl = 20
        self.tcp_keepalive_cnt = 6

    def reset_send(self):
        """Clear send buffer and reset send state machine.

        This method should rarely need to be called and only if
        ProtocolError has been raised during a send operation. Any
        frames in the send buffer will be sent.
        """
        state = -1 if self.type == ROUTER else 0
        if self._send_state != state:
            self._send_state = state
            super(_Socket, self).send('')

    @contextmanager
    def _sending(self, flags):
        flags |= getattr(self._Socket__local, 'flags', 0)
        yield flags

    def send(self, frame, flags=0, copy=True, track=False):
        """ Send a single frame while enforcing VIP protocol.

        Expects frames to be sent in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARG]...

        If the socket is a ROUTER, an INTERMEDIARY must be sent before
        PEER. The VIP protocol signature, PROTO, is automatically sent
        between PEER and USER_ID. Zero or more ARG frames may be sent
        after SUBSYSTEM, which may not be empty. All frames up to
        SUBSYSTEM must be sent with the SNDMORE flag.


        :param frame:
        :param flags:
        :param copy:
        :param track:
        :return:
        """
        with self._sending(flags) as flags:
            state = self._send_state
            if state == 4:
                # Verify that subsystem has some non-space content
                subsystem = bytes(frame)
                if not subsystem.strip():
                    raise ProtocolError('invalid subsystem: %s' % subsystem)
            if not flags & SNDMORE:
                # Must have SNDMORE flag until sending SUBSYSTEM frame.
                if state < 4:
                    raise ProtocolError(
                        'expecting at least %d more frames' % (4 - state - 1))
                # Reset the send state when the last frame is sent
                self._send_state = -1 if self.type == ROUTER else 0
            elif state < 5:
                if state == 1:
                    # Automatically send PROTO frame
                    super(_Socket, self).send(b'VIP1', flags=flags|SNDMORE)
                    state += 1
                self._send_state = state + 1
            try:
                super(_Socket, self).send(
                    frame, flags=flags, copy=copy, track=track)
            except Exception:
                self._send_state = state
                raise

    def send_multipart(self, msg_parts, flags=0, copy=True, track=False):
        parts = serialize_frames(msg_parts)
        # _log.debug("Sending parts on multiparts: {}".format(parts))
        with self._sending(flags) as flags:
            super(_Socket, self).send_multipart(
                parts, flags=flags, copy=copy, track=track)

    def send_vip(self, peer, subsystem, args=None, msg_id='',
                 user='', via=None, flags=0, copy=True, track=False):
        """Send an entire VIP multipartmessage by individual parts.

        This method will raise a ProtocolError exception if the previous
        send was made with the SNDMORE flag or if other protocol
        constraints are violated. If SNDMORE flag is used, additional
        arguments may be sent. via is required for ROUTER sockets.

        :param peer:
            The peer to send to, can be either a string or a byte object.
        :param subsystem:
            The subsystem to send the request to
        :param args:
            Any arguments to the subsystem
        :param msg_id:
            A message id to allow tracking this is usually an entry in the ResultsDictionary.ident
        :param user:
        :param via:
        :param flags:
        :param copy:
            Should a copy be made of the message be made for each send
        :param track:
        """

        peer = peer
        msg_id = msg_id

        # _log.debug("SEND VIP: peer={}, subsystem={}, args={}, msg_id={}, user={}, type(msg_id)={}".format(
        #     peer, subsystem, args, msg_id, user, type(msg_id)
        # ))
        with self._sending(flags) as flags:
            state = self._send_state
            if state > 0:
                raise ProtocolError('previous send operation is not complete')
            elif state == -1:
                if via is None:
                    raise ValueError("missing 'via' argument "
                                     "required by ROUTER sockets")
                self.send(via, flags=flags | SNDMORE, copy=copy, track=track)

            if user is None:
                user = ''

            more = SNDMORE if args else 0
            self.send_multipart([peer, user, msg_id, subsystem],
                                flags=flags|more, copy=copy, track=track)
            if args:
                send = (self.send if isinstance(args, (bytes, str))
                        else self.send_multipart)
                send(args, flags=flags, copy=copy, track=track)

    def send_vip_dict(self, dct, flags=0, copy=True, track=False):
        """Send VIP message from a dictionary."""
        msg_id = dct.pop('id', '')
        self.send_vip(flags=flags, copy=copy, track=track, msg_id=msg_id, **dct)

    def send_vip_object(self, msg, flags=0, copy=True, track=False):
        """Send VIP message from an object."""
        dct = {
            'via': getattr(msg, 'via', None),
            'peer': msg.peer,
            'subsystem': msg.subsystem,
            'user': getattr(msg, 'user', ''),
            'msg_id': getattr(msg, 'id', ''),
            'args': getattr(msg, 'args', None),
        }
        self.send_vip(flags=flags, copy=copy, track=track, **dct)

    def recv(self, flags=0, copy=True, track=False):
        """ Receive and return a single frame while enforcing VIP protocol.

        Expects frames to be received in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARG]...

        If the socket is a ROUTER, an INTERMEDIARY must be received
        before PEER. The VIP protocol signature, PROTO, is automatically
        received and validated between PEER and USER_ID. It is not
        returned as part of the result. Zero or more ARG frames may be
        received after SUBSYSTEM, which may not be empty. Until the last
        ARG frame is received, the RCVMORE option will be set.


        :param flags:
        :param copy:
        :param track:
        :return:
        """

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
        """Clear recv buffer and reset recv state machine.

        This method should rarely need to be called and only if
        ProtocolError has been raised during a receive operation. Any
        frames in the recv buffer will be discarded.
        """
        self._recv_state = -1 if self.type == ROUTER else 0
        while self.getsockopt(RCVMORE):
            super(_Socket, self).recv()

    def recv_vip(self, flags=0, copy=True, track=False):
        """ Receive a complete VIP message and return as a list.

        The list includes frames in the following order:

           PEER USER_ID MESSAGE_ID SUBSYSTEM [ARGS]

        If socket is a ROUTER, INTERMEDIARY will be inserted before PEER
        in the returned list. ARGS is always a possibly empty list.

        :param flags:
        :param copy:
        :param track:
        :return:
            A VIP message
        """
        state = self._recv_state
        if state > 0:
            raise ProtocolError('previous recv operation is not complete')
        message = self.recv_multipart(flags=flags, copy=copy, track=track)
        idx = 4 - state
        result = message[:idx]
        result.append(message[idx:])
        return result

    def recv_vip_dict(self, flags=0, copy=True, track=False):
        """Receive a complete VIP message and return in a dict."""
        state = self._recv_state
        frames = self.recv_vip(flags=flags, copy=copy, track=track)
        via = frames.pop(0) if state == -1 else None
        # from volttron.utils.frame_serialization import decode_frames
        # decoded = decode_frames(frames)

        myframes = deserialize_frames(frames)
        dct = dict(zip(('peer', 'user', 'id', 'subsystem', 'args'), myframes))
        if via is not None:
            dct['via'] = via
        return dct

    def recv_vip_object(self, flags=0, copy=True, track=False):
        """Recieve a complete VIP message and return as an object."""
        msg = Message()
        msg.__dict__ = self.recv_vip_dict(flags=flags, copy=copy, track=track)
        return msg

    def bind(self, addr):
        """Extended zmq.Socket.bind() to include options in addr."""
        if not isinstance(addr, Address):
            addr = Address(addr)
        addr.bind(self, super(_Socket, self).bind)

    def connect(self, addr):
        """Extended zmq.Socket.connect() to include options in addr."""
        if not isinstance(addr, Address):
            addr = Address(addr)
        addr.connect(self, super(_Socket, self).connect)
