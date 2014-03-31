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

'''Support for raw JSON-RPC framing using brackets to delimit messages.'''


__all__ = ['Error', 'Encoder', 'Decoder', 'Stream']


def read(rfile):
    '''Read raw JSON data.'''
    data = []
    stack = []
    # Find opening bracket, skipping whitespace
    while True:
        c = rfile.read(1)
        if not c:
            return
        elif c == '{':
            stack.append('}')
            break
        elif c == '[':
            stack.append(']')
            break
        elif not c.isspace():
            raise ValueError('expected a list or object')
    data.append(c)

    quote = None
    escape = False
    # Find closing bracket
    while True:
        c = rfile.read(1)
        if not c:
            raise ValueError('unexpected end-of-file')
        data.append(c)
        if escape:
            escape = False
        elif c == '\\':
            escape = True
        elif c == quote:
            quote = None
        elif quote:
            pass
        elif c in '\'"':
            quote = c
        elif c in ']}':
            if stack.pop() != c:
                raise ValueError('unbalenced brackets')
            if not stack:
                break
        elif c == '{':
            stack.append('}')
        elif c == '[':
            stack.append(']')
    return ''.join(data)


def write(wfile, chunk):
    '''Write raw JSON data.'''
    wfile.writelines([chunk, '\n'])
    wfile.flush()


class Error(Exception):
    '''Raised when a lower-level and unrecoverable protocol error occurs.'''


class EncodeMixin:
    '''Encoder implementation.'''

    def write_chunk(self, chunk):
        '''Write raw JSON data.'''
        write(self.wfile, chunk)


class DecodeMixin:
    '''Decoder implementation.'''

    def read_chunk(self):
        '''Read raw JSON data.'''
        return read(self.rfile)

    def __iter__(self):
        '''Make file iterable.'''
        return self

    def next(self):
        '''Iterate by chunks.'''
        chunk = self.read_chunk()
        if not chunk:
            raise StopIteration()
        return chunk


class Encoder(object, EncodeMixin):
    __slots__ = ['wfile']

    def __init__(self, file):
        self.wfile = file


class Decoder(object, DecodeMixin):
    __slots__ = ['rfile']

    def __init__(self, file):
        self.rfile = file


class Stream(object, EncodeMixin, DecodeMixin):
    __slots__ = ['rfile', 'wfile']

    def __init__(self, file, wfile=None):
        self.rfile = file
        self.wfile = wfile or file

