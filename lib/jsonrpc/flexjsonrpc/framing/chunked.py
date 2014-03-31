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

'''Support for HTTP/1.1 chunked encoding for JSON-RPC framing.'''


__all__ = ['Error', 'Encoder', 'Decoder', 'Stream']


class Error(Exception):
    '''Raised when a lower-level and unrecoverable protocol error occurs.'''


def parse_chunk_length(line):
    '''Parse the chunk length (first) line of a chunked message.'''
    # Ensure a complete line exists
    if not line.endswith('\n'):
        raise Error('invalid chunk length line; missing CRLF')
    # Strip CRLF, strip extension, and parse hex integer
    try:
        return int(line.rstrip('\r\n').split(';', 1)[0], 16)
    except ValueError:
        raise Error('invalid chunk length: {!r}'.format(
                line[:20] + ('...' if len(line) > 20 else '')))


def read(rfile):
    '''Read chunk encoded data.'''
    # Read chunk length line (limited to reasonable maximum length)
    line = rfile.readline(1024)
    if not line:    # End of stream/file
        return ''
    length = parse_chunk_length(line)
    if length:
        chunk = rfile.read(length)
        if not chunk:
            raise Error('partial chunk read; unexpected end of file')
    else:
        chunk = ''
    end = rfile.readline(2)
    if end not in ['\r\n', '\n']:
        raise Error('invalid chunk termination; missing CRLF')
    return chunk


def write(wfile, chunk):
    '''Write chunk encoded data.'''
    wfile.writelines(['{:x}\r\n'.format(len(chunk)), chunk, '\r\n'])
    wfile.flush()


class EncodeMixin:
    '''Encoder implementation.'''
    def write_chunk(self, chunk):
        '''Write chunk encoded data.'''
        write(self.wfile, chunk)


class DecodeMixin:
    '''Decoder implementation.'''
    def read_chunk(self):
        '''Read chunk encoded data.'''
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

