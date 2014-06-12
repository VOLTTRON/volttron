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

# pylint: disable=W0142,W0403
#}}}

'''VOLTTRON platform™ messaging classes.'''

import collections

import zmq
from zmq.utils import jsonapi


__all__ = ['Headers', 'Socket']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


class Headers(collections.MutableMapping):
    '''Case-insensitive dictionary for HTTP-like headers.'''
    def __init__(self, *args, **kwargs):
        self._dict = dict((k.lower(), (k, v)) for k, v in
                          dict(*args, **kwargs).iteritems())
    @property
    def dict(self):
        '''Access the headers as a dict object.'''
        return dict(self.iteritems())
    def __getitem__(self, key):
        return self._dict[key.lower()][1]
    def __setitem__(self, key, value):
        self._dict[key.lower()] = key, value
    def __delitem__(self, key):
        del self._dict[key.lower()]
    def __iter__(self):
        return (key for key, value in self._dict.itervalues())
    def __len__(self):
        return len(self._dict)
    def iteritems(self):
        return self._dict.itervalues()
    def __repr__(self):
        return '{}({}{}{})'.format(self.__class__.__name__, '{', ', '.join(
                '{!r}: {!r}'.format(k, v) for k, v in self.iteritems()), '}')


class Socket(zmq.Socket):
    '''ØMQ socket with additional agent messaging methods.'''

    def __new__(cls, socket_type, context=None):
        if not context:
            context = zmq.Context.instance()
        return zmq.Socket.__new__(cls, context, socket_type)

    def __init__(self, socket_type, context=None):
        super(Socket, self).__init__(self.context, socket_type)

    # Override send_string to ensure copy defaults to True.
    # https://github.com/zeromq/pyzmq/pull/456
    def send_string(self, u, flags=0, copy=True, encoding='utf-8'):
        super(Socket, self).send_string(
                u, flags=flags, copy=copy, encoding=encoding)
    send_string.__doc__ = zmq.Socket.send_string.__doc__

    def recv_message(self, flags=0):
        '''Recieve a message as (topic, headers, message) tuple.'''
        topic = self.recv_string(flags)
        headers = self.recv_string(flags) if self.rcvmore else ''
        headers = jsonapi.loads(headers) if headers else {}
        message = self.recv_multipart(flags) if self.rcvmore else []
        return topic, Headers(headers), message

    def recv_message_ex(self, flags=0):
        '''Receive a message as (content type, message) tuples.
        
        Like recv_message(), returns a three tuple.  However, the final
        message component contains a list of 2-tuples instead of a list
        of messages.  These 2-tuples contain the content- type and the
        data.
        '''
        topic, headers, message = self.recv_message(flags)
        message = zip(headers['Content-Type'], message)
        return topic, headers, message

    def send_message(self, topic, headers, *msg_parts, **kwargs):
        '''Send a multipart message with topic and headers.

        Send a multipart message on the socket with topic being a UTF-8
        string, headers can be a dictionary or a Headers object, and
        msg_parts is the optional parts of the message.  The media or
        content type of each message component should be included in the
        'Content-Type' header which should be a list of MIME types or a
        string if there is only one message part.
        '''
        flags = kwargs.pop('flags', 0)
        if kwargs:
            raise TypeError('send_message() got unexpected keyword '
                            'arugment(s): ' + ', '.join(kwargs))
        if not isinstance(headers, Headers):
            headers = Headers(headers) if headers else Headers()
        self.send_string(topic, flags | zmq.SNDMORE)
        self.send_json(headers.dict, flags | (zmq.SNDMORE if msg_parts else 0))
        if msg_parts:
            self.send_multipart(msg_parts, flags)

    def send_message_ex(self, topic, headers, *msg_tuples, **kwargs):
        '''Send messages given as (content-type, message) tuples.

        Similar to the send_message method except that messages are given as
        2-tuples with the MIME type as the first element and the message
        data as the second element.
        '''
        headers = Headers(headers) if headers else Headers()
        headers['Content-Type'], msg_parts = zip(*msg_tuples)
        self.send_message(topic, headers.dict, *msg_parts, **kwargs)

