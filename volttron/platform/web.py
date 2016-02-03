# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

import logging
import os
import re

from gevent import pywsgi
from zmq.utils import jsonapi as json

from .vip.agent import Agent, Core, RPC
from .vip.socket import encode_key

_log = logging.getLogger(__name__)


class MasterWebService(Agent):
    """The service that is responsible for managing and serving registered pages

    Agents can register either a directory of files to serve or an rpc method
    that will be called during the request process.
    """

    def __init__(self, serverkey, identity, address):
        """Initialize the discovery service with the serverkey

        serverkey is the public key in order to access this volttron's bus.
        """
        super(MasterWebService, self).__init__(identity, address)

        self.serverkey = serverkey
        self.registeredroutes = []

    @RPC.export
    def register_agent_route(self, regex, peer, fn):
        _log.debug('Registering agent rount expression: {}'.format(regex))
        compiled = re.compile(regex)
        self.registeredroutes.append((compiled, 'peer_route', (peer, fn)))

    @RPC.export
    def register_path_route(self, regex, root_dir):
        _log.debug('Path location: {}'.format(root_dir))
        compiled = re.compile(regex)
        self.registeredroutes.append((compiled, 'path', root_dir))

    @RPC.export
    def register(self, regex, root_or_callable):

        try:
            _log.debug('Registering uri expression: {}'.format(regex))
            compiled = re.compile(regex)
            # callablle was removed in 3.0 but added back to the language
            # in python 3.2
            if callable(root_or_callable):
                print('Callable is true')
                self.registeredroutes.append((compiled, 'callable', root_or_callable))
            else:
                print('Is Not Callable.')
                if os.path.exists(root_or_callable):
                    self.registeredroutes.append((compiled, 'path', root_or_callable))
                else:
                    raise AttributeError(root +' is not available')
        except OSError as exc:
            print('An error occured')

    def get_serverkey(self, environ, start_response):
        start_response('200 OK', [('Content-Type', 'application/json')])
        return json.dumps({"serverkey": encode_key(self.serverkey)})

    def app_routing(self, env, start_response):

        path_info = env['PATH_INFO']
        _log.debug("PATHINFO: {}".format(path_info))
        if path_info.startswith('/http://'):
            path_info = path_info[path_info.index('/', len('/http://')):]
            _log.debug('Path info is: {}'.format(path_info))
        envlist = ['HTTP_USER_AGENT', 'PATH_INFO', 'QUERY_STRING',
            'REQUEST_METHOD', 'SERVER_PROTOCOL']
        passenv = dict((envlist[i], env[envlist[i]]) for i in range(0, len(envlist)))
        for k, t, v in self.registeredroutes:
            _log.debug("pattern: {}, path_info: {}\n v: {}".format(k.pattern, path_info, v))

            if k.match(path_info):
                if t == 'peer_route':
                    peer, fn = (v[0], v[1])
                    res = self.vip.rpc.call(peer, fn, passenv).get(timeout=4)
                    _log.debug('RES is {}'.format(res))
                    start_response('200 OK', [('Content-Type', 'application/json')])
                    return [res]
                else:
                    _log.debug('V is: {} MATCHED: {}'.format(v, k.pattern))
                    server_path = v + path_info #os.path.join(v, path_info)
                    _log.debug("SERVER_PATH: {}".format(server_path))
                    return self._sendfile(env, start_response, server_path)

                    #start_response('200 OK', [('Content-Type', 'text/html')])
                    #return [b'{}'.format(env)]

        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return [b'<h1>Not Found</h1>']

    def _sendfile(self, env, start_response, filename):
        from wsgiref.util import FileWrapper
        status = '200 OK'
        _log.debug('SENDING FILE: {}'.format(filename))
        if not os.path.exists(filename):
            status = ''
        #fname = os.path.join(os.path.dirname(__file__), "hello.txt")
        f = open(filename, 'rb')

        response_headers = [
            ('Content-type', 'text/plain'),
        ]
        start_response(status, response_headers)

        return FileWrapper(open(filename, 'r'))

    @Core.receiver('onstart')
    def startupagent(self, sender, **kwargs):
        _log.debug('Starting web server.')
        self.register('^/discovery/$', self.get_serverkey)
        #self.register('/$', '/home/vdev/git/volttron/services/core/VolttronCentral/volttroncentral/webroot')
        self.server = pywsgi.WSGIServer(('0.0.0.0', 8080), self.app_routing)
        self.server.serve_forever()
