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

import os.path
import sys

from gevent.server import StreamServer

try:
    import simplejson as json
except ImportError:
    import json

from flexjsonrpc.green import *
from flexjsonrpc.framing import detect as framing
from flexjsonrpc import util


class Handler(BaseHandler):
    def hello(self):
        return 'Hello World!'

    def echo(self, string):
        return 'You said: {!r}'.format(string)


def handle(sock, address):
    print 'Connection accepted from {}:{}'.format(*address)
    rfile, wfile = sock.makefile('rb', -1), sock.makefile('wb', 0)
    stream = framing.Stream(rfile, wfile)
    dispatcher = Dispatcher(Handler())
    logger = lambda data, direction=None: sys.stdout.write(
            '{} {}\n'.format('<--' if direction == 'in' else '-->', data))
    util.dispatch_loop(stream, dispatcher, json, logger)


def usage(prog):
    sys.stderr.write('Usage: {} address port\n'.format(prog))
    sys.exit(1)


def main(argv):
    prog = os.path.split(argv[0])[-1]
    if len(argv) == 3:
        try:
            addr = (argv[1], int(argv[2]))
        except ValueError:
            sys.stderr.write('{}: invalid port number\n'.format(prog))
            usage(prog)
    else:
        sys.stderr.write('{}: wrong number of arguments\n'.format(prog))
        usage(prog)
    print 'Listening on {}:{}'.format(*addr)
    StreamServer(addr, handle).serve_forever()


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        pass

