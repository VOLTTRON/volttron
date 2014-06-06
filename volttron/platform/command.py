# 
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an 
# agency of the United States Government.  Neither the United States 
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization 
# that has cooperated in the development of these materials, makes 
# any warranty, express or implied, or assumes any legal liability 
# or responsibility for the accuracy, completeness, or usefulness or 
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or 
# service by trade name, trademark, manufacturer, or otherwise does 
# not necessarily constitute or imply its endorsement, recommendation, 
# r favoring by the United States Government or any agency thereof, 
# or Battelle Memorial Institute. The views and opinions of authors 
# expressed herein do not necessarily state or reflect those of the 
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#

import gevent
from gevent import socket

try:
    import simplejson as json
except ImportError:
    import json

import flexjsonrpc.green as jsonrpc
from flexjsonrpc.framing import raw as framing

from volttron.core.command import CommandParser
from environment import get_environment


__all__ = ['CommandParser', 'ControlConnector']


def dispatch_loop(stream, dispatcher):
    for chunk in stream:
        try:
            request = json.loads(chunk)
        except Exception as e:
            stream.write_chunk(json.dumps(jsonrpc.parse_error(str(e))))
            return
        response = dispatcher.dispatch(request)
        if response:
            stream.write_chunk(json.dumps(response))

class ControlConnector(jsonrpc.PyConnector):
    def __init__(self, config):
        address = config['control']['socket']
        if address[:1] == '@':
            address = '\x00' + address[1:]
        self._sock = sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(address)
        stream = framing.Stream(sock.makefile('rb', -1), sock.makefile('rw', 0))
        self._requester = requester = jsonrpc.Requester(
                lambda chunk: stream.write_chunk(json.dumps(chunk)))
        super(ControlConnector, self).__init__(requester)
        self._dispatcher = dispatcher = jsonrpc.Dispatcher(
                None, requester.handle_response)
        self._task = gevent.spawn(dispatch_loop, stream, dispatcher)

