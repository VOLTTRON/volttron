# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

NOBLOCK = 1
SNDMORE = 2
RCVMORE = 13

POLLIN = 1
POLLOUT = 2

PUB = 1
SUB = 2
DEALER = 5
ROUTER = 6
PULL = 7
PUSH = 8
XPUB = 9

EAGAIN = 11
EINVAL = 22
EHOSTUNREACH = 113
EPROTONOSUPPORT = 93


class ZMQError(Exception):
    pass

class Again(ZMQError):
    pass

class Context(object):
    def instance(self):
        return Context()


class Poller(object):
    def register(self, socket, flags=POLLIN|POLLOUT):
        pass

    def poll(self, timeout=None):
        return []


class Socket(object):
    def __new__(cls, socket_type, context=None):
        return object.__new__(cls, socket_type, context=context)

    def bind(self, addr):
        pass

    def connect(self, addr):
        pass

    def disconnect(self, addr):
        pass

    def close(self, linger=None):
        pass

    @property
    def closed(self):
        return True

    @property
    def rcvmore(self):
        return 0

    @property
    def context(self):
        return Context()

    @property
    def type(self):
        return 0

    @context.setter
    def context(self, value):
        pass

    def poll(self, timeout=None, flags=1):
        return 0

    def send_string(self, u, flags=0, copy=True, encoding='utf-8'):
        pass

    def recv_string(self, flags=0, encoding='utf-8'):
        return u''

    def send_multipart(self, msg_parts, flags=0, copy=True, track=False):
        pass

    def recv_multipart(self, flags=0, copy=True, track=False):
        return []

    def send_json(self, obj, flags=0, **kwargs):
        pass

    def recv_json(self, flags=0, **kwargs):
        return {}

    def getsockopt(self, option):
        return 0

green = __import__('sys').modules[__name__]
