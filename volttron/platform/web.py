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
# }}}

from collections import defaultdict
import logging
import os
import re
import requests
from urlparse import urlparse, urljoin

from gevent import pywsgi
import mimetypes

from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from zmq.utils import jsonapi

from .auth import AuthEntry, AuthFile
from .vip.agent import Agent, Core, RPC
from .vip.agent.subsystems import query
from .jsonrpc import (
    json_result, json_error, json_validate_request, UNAUTHORIZED)
from .vip.socket import encode_key

_log = logging.getLogger(__name__)


class CouldNotRegister(StandardError):
    pass


class DiscoveryError(StandardError):
    """ Raised when a different volttron central tries to register.
    """
    pass


class DiscoveryInfo(object):
    """ A DiscoveryInfo class.

    The DiscoveryInfo class provides a wrapper around the return values from
    a call to the /discovery/ endpoint of the `volttron.platform.web.
    """

    def __init__(self, **kwargs):

        self.discovery_address = kwargs.pop('discovery_address')
        self.vip_address = kwargs.pop('vip-address')
        self.serverkey = kwargs.pop('serverkey')
        assert len(kwargs) == 0

    @staticmethod
    def request_discovery_info(discovery_address):
        """  Construct a `DiscoveryInfo` object.

        Requests a response from discovery_address and constructs a
        `DiscoveryInfo` object with the returned json.

        :param discovery_address: An http(s) address with volttron running.
        :return:
        """

        try:
            parsed = urlparse(discovery_address)

            assert parsed.scheme
            assert not parsed.path

            real_url = urljoin(discovery_address, "/discovery/")
            _log.info('Connecting to: {}'.format(real_url))
            response = requests.get(real_url)

            if not response.ok:
                raise DiscoveryError(
                    "Invalid discovery response from {}".format(real_url)
                )
        except AttributeError as e:
            raise DiscoveryError(
                "Invalid discovery_address passed {}"
                .format(discovery_address)
            )
        except (ConnectionError, NewConnectionError) as e:
            raise DiscoveryError(
                "Connection to {} not available".format(real_url)
            )
        except Exception as e:
            raise DiscoveryError("Unhandled exception {}".format(e))

        return DiscoveryInfo(
            discovery_address=discovery_address, **(response.json()))

    def __str__(self):
        dk = {
            'discovery_address': self.discovery_address,
            'vip_address': self.vip_address,
            'serverkey': self.serverkey
        }

        return jsonapi.dumps(dk)


def is_ip_private(vip_address):
    """ Determines if the passed vip_address is a private ip address or not.

    :param vip_address: A valid ip address.
    :return: True if an internal ip address.
    """
    ip = vip_address.strip().lower().split("tcp://")[1]

    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) is not None or priv_24.match(
        ip) is not None or priv_20.match(ip) is not None or priv_16.match(
        ip) is not None


class MasterWebService(Agent):
    """The service that is responsible for managing and serving registered pages

    Agents can register either a directory of files to serve or an rpc method
    that will be called during the request process.
    """

    def __init__(self, serverkey, identity, address, bind_web_address, aip,
                 volttron_central_address=None):
        """Initialize the discovery service with the serverkey

        serverkey is the public key in order to access this volttron's bus.
        """
        super(MasterWebService, self).__init__(identity, address)

        self.bind_web_address = bind_web_address
        # if the web address is bound then we need to allow the web agent
        # to be discoverable.  That means we need to allow connections to
        # the message bus in some known addresses if they aren't already
        # specified.
        if self.bind_web_address:
            authfile = AuthFile()
            entries, _, _ = authfile.read()
            if not entries:
                _log.debug(
                    'Adding default curve credentials for discoverability.')
                authfile.add(AuthEntry(credentials="/CURVE:.*/"))

        self.serverkey = serverkey
        self.registeredroutes = []
        self.peerroutes = defaultdict(list)
        self.pathroutes = defaultdict(list)
        self.aip = aip

        self.volttron_central_address = volttron_central_address

        # If vc is this instance then make the vc address the same as
        # the web address.
        if not self.volttron_central_address:
            self.volttron_central_address = bind_web_address


        if not mimetypes.inited:
            mimetypes.init()

        authentry = AuthEntry(credentials="/CURVE:.*/")
        authfile = AuthFile()
        authfile.add(authentry)

    @RPC.export
    def get_bind_web_address(self):
        return self.bind_web_address

    @RPC.export
    def get_serverkey(self):
        return self.serverkey

    @RPC.export
    def get_volttron_central_address(self):
        """Return address of external Volttron Central

        Note: this only applies to Volltron Central agents that are
        running on a different platform.
        """
        return self.volttron_central_address

    @RPC.export
    def register_agent_route(self, regex, peer, fn):
        """ Register an agent route to an exported function.

        When a http request is executed and matches the passed regular
        expression then the function on peer is executed.
        """
        _log.info(
            'Registering agent route expression: {} peer: {} function: {}'
                .format(regex, peer, fn))
        compiled = re.compile(regex)
        self.peerroutes[peer].append(compiled)
        self.registeredroutes.insert(0, (compiled, 'peer_route', (peer, fn)))

    @RPC.export
    def unregister_all_agent_routes(self, peer):
        _log.info('Unregistering agent routes for: {}'.format(peer))
        for regex in self.peerroutes[peer]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.peerroutes[peer]
        for regex in self.pathroutes[peer]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.pathroutes[peer]

    @RPC.export
    def register_path_route(self, peer, regex, root_dir):
        _log.info('Registiering path route: {}'.format(root_dir))
        compiled = re.compile(regex)
        self.pathroutes[peer].append(compiled)
        self.registeredroutes.append((compiled, 'path', root_dir))

    def _redirect_index(self, env, start_response, data=None):
        """ Redirect to the index page.
        @param env:
        @param start_response:
        @param data:
        @return:
        """
        start_response('302 Found', [('Location', '/index.html')])
        return ['1']

    def _allow(self, environ, start_response, data=None):
        _log.info('Allowing new vc instance to connect to server.')
        jsondata = jsonapi.loads(data)
        json_validate_request(jsondata)

        assert jsondata.get('method') == 'allowvc'
        assert jsondata.get('params')

        params = jsondata.get('params')
        if isinstance(params, list):
            vcpublickey = params[0]
        else:
            vcpublickey = params.get('vcpublickey')

        assert vcpublickey
        assert len(vcpublickey) == 43

        authfile = AuthFile()
        authentry = AuthEntry(
            credentials="CURVE:{}".format(vcpublickey)
        )

        authfile.add(authentry)
        start_response('200 OK',
                       [('Content-Type', 'application/json')])
        return jsonapi.dumps(
            json_result(jsondata['id'], "Added")
        )

    def _get_discovery(self, environ, start_response, data=None):
        q = query.Query(self.core)
        result = q.query('addresses').get(timeout=60)
        external_vip = None
        for x in result:
            if not is_ip_private(x):
                external_vip = x
                break
        peers = self.vip.peerlist().get(timeout=60)

        return_dict = {}

        if self.serverkey:
            return_dict['serverkey'] = encode_key(self.serverkey)
        else:
            sk = None

        return_dict['vip-address'] = external_vip

        start_response('200 OK', [('Content-Type', 'application/json')])
        return jsonapi.dumps(return_dict)

    def app_routing(self, env, start_response):
        """The main routing function that maps the incoming request to a response.

        Depending on the registered routes map the request data onto an rpc function
        or a specific named file.
        """
        path_info = env['PATH_INFO']

        if path_info.startswith('/http://'):
            path_info = path_info[path_info.index('/', len('/http://')):]
            _log.debug('Path info is: {}'.format(path_info))
        # only expose a partial list of the env variables to the registered
        # agents.
        envlist = ['HTTP_USER_AGENT', 'PATH_INFO', 'QUERY_STRING',
                   'REQUEST_METHOD', 'SERVER_PROTOCOL', 'REMOTE_ADDR']
        data = env['wsgi.input'].read()
        passenv = dict(
            (envlist[i], env[envlist[i]]) for i in range(0, len(envlist)) if envlist[i] in env.keys())
        for k, t, v in self.registeredroutes:
            if k.match(path_info):
                _log.debug("MATCHED:\npattern: {}, path_info: {}\n v: {}"
                           .format(k.pattern, path_info, v))
                _log.debug('registered route t is: {}'.format(t))
                if t == 'callable':  # Generally for locally called items.
                    return v(env, start_response, data)
                elif t == 'peer_route':  # RPC calls from agents on the platform.
                    _log.debug('Matched peer_route with pattern {}'.format(
                        k.pattern))
                    peer, fn = (v[0], v[1])
                    res = self.vip.rpc.call(peer, fn, passenv, data).get(
                        timeout=60)
                    if isinstance(res, dict):
                        _log.debug('res is a dictionary.')
                        if 'error' in res.keys():
                            if res['error']['code'] == UNAUTHORIZED:
                                start_response('401 Unauthorized', [
                                    ('Content-Type', 'text/html')])
                                message = res['error']['message']
                                code = res['error']['code']
                                return [b'<h1>{}</h1>\n<h2>CODE:{}</h2>'
                                            .format(message, code)]
                    start_response('200 OK',
                                   [('Content-Type', 'application/json')])
                    _log.debug('RESPONSE WEB: {}'.format(res))
                    return jsonapi.dumps(res)
                elif t == 'path':  # File service from agents on the platform.
                    server_path = v + path_info  # os.path.join(v, path_info)
                    _log.debug('Serverpath: {}'.format(server_path))
                    return self._sendfile(env, start_response, server_path)

        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return [b'<h1>Not Found</h1>']

    def _sendfile(self, env, start_response, filename):
        from wsgiref.util import FileWrapper
        status = '200 OK'
        _log.debug('SENDING FILE: {}'.format(filename))
        guess = mimetypes.guess_type(filename)[0]
        _log.debug('MIME GUESS: {}'.format(guess))

        if not os.path.exists(filename):
            start_response('404 Not Found', [('Content-Type', 'text/html')])
            return [b'<h1>Not Found</h1>']

        if not guess:
            guess = 'text/plain'

        response_headers = [
            ('Content-type', guess),
        ]
        start_response(status, response_headers)

        return FileWrapper(open(filename, 'r'))

    @Core.receiver('onstart')
    def startupagent(self, sender, **kwargs):

        if not self.bind_web_address:
            _log.info('Web server not started.')
            return
        import urlparse
        parsed = urlparse.urlparse(self.bind_web_address)
        hostname = parsed.hostname
        port = parsed.port

        _log.info('Starting web server binding to {}:{}.' \
                   .format(hostname, port))
        self.registeredroutes.append((re.compile('^/discovery/$'), 'callable',
                                      self._get_discovery))
        self.registeredroutes.append((re.compile('^/discovery/allow$'),
                                      'callable',
                                      self._allow))
        self.registeredroutes.append((re.compile('^/$'), 'callable',
                                      self._redirect_index))
        port = int(port)
        vhome = os.environ.get('VOLTTRON_HOME')
        logdir = os.path.join(vhome, "log")
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        with open(os.path.join(logdir, 'web.access.log'), 'wb') as accesslog:
            with open(os.path.join(logdir, 'web.error.log'), 'wb') as errlog:
                server = pywsgi.WSGIServer((hostname, port), self.app_routing,
                                       log=accesslog, error_log=errlog)
                server.serve_forever()


def build_vip_address_string(vip_root, serverkey, publickey, secretkey):
    """ Build a full vip address string based upon the passed arguments

    All arguments are required to be non-None in order for the string to be
    created successfully.

    :raises ValueError if one of the parameters is None.
    """
    _log.debug("root: {}, serverkey: {}, publickey: {}, secretkey: {}".format(
        vip_root, serverkey, publickey, secretkey))
    if not (serverkey and publickey and secretkey and vip_root):
        raise ValueError("All parameters must be entered.")

    root = "{}?serverkey={}&publickey={}&secretkey={}".format(
        vip_root, serverkey, publickey, secretkey
    )

    return root
