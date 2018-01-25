# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

from collections import defaultdict
import logging
import os
import re
import requests
import base64
from urlparse import urlparse, urljoin

import gevent
import gevent.pywsgi
from ws4py.websocket import WebSocket

from ws4py.server.geventserver import (WebSocketWSGIApplication,
                                       WSGIServer)
import zlib

import mimetypes

from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from volttron.platform.agent import json as jsonapi

from .auth import AuthEntry, AuthFile, AuthFileEntryAlreadyExists
from .vip.agent import Agent, Core, RPC
from .vip.agent.subsystems import query
from .jsonrpc import (
    json_result, json_validate_request, UNAUTHORIZED)
from .vip.socket import encode_key

_log = logging.getLogger(__name__)


class CouldNotRegister(StandardError):
    pass


class DuplicateEndpointError(StandardError):
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
        self.instance_name = kwargs.pop('instance-name')
        assert len(kwargs) == 0

    @staticmethod
    def request_discovery_info(web_address):
        """  Construct a `DiscoveryInfo` object.

        Requests a response from discovery_address and constructs a
        `DiscoveryInfo` object with the returned json.

        :param web_address: An http(s) address with volttron running.
        :return:
        """

        try:
            parsed = urlparse(web_address)

            assert parsed.scheme
            assert not parsed.path

            real_url = urljoin(web_address, "/discovery/")
            _log.info('Connecting to: {}'.format(real_url))
            response = requests.get(real_url)

            if not response.ok:
                raise DiscoveryError(
                    "Invalid discovery response from {}".format(real_url)
                )
        except AttributeError as e:
            raise DiscoveryError(
                "Invalid web_address passed {}"
                .format(web_address)
            )
        except (ConnectionError, NewConnectionError) as e:
            raise DiscoveryError(
                "Connection to {} not available".format(real_url)
            )
        except Exception as e:
            raise DiscoveryError("Unhandled exception {}".format(e))

        return DiscoveryInfo(
            discovery_address=web_address, **(response.json()))

    def __str__(self):
        dk = {
            'discovery_address': self.discovery_address,
            'vip_address': self.vip_address,
            'serverkey': self.serverkey,
            'instance_name': self.instance_name
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


class WebResponse(object):
    """ The WebResponse object is a serializable representation of
    a response to an http(s) client request that can be transmitted
    through the RPC subsystem to the appropriate platform's MasterWebAgent
    """

    def __init__(self, status, data, headers):
        self.status = status
        self.headers = self.process_headers(headers)
        self.data = self.process_data(data)

    def process_headers(self, headers):
        return [(key, value) for key, value in headers.items()]

    def process_data(self, data):
        if type(data) == bytes:
            self.base64 = True
            data = base64.b64encode(data)
        elif type(data) == str:
            self.base64 = False
        else:
            raise TypeError("Response data is neither bytes nor string type")
        return data



class VolttronWebSocket(WebSocket):

    def __init__(self, *args, **kwargs):
        super(VolttronWebSocket, self).__init__(*args, **kwargs)
        self._log = logging.getLogger(self.__class__.__name__)

    def _get_identity_and_endpoint(self):
        identity = self.environ['identity']
        endpoint = self.environ['PATH_INFO']
        return identity, endpoint

    def opened(self):
        self._log.info('Socket opened')
        app = self.environ['ws4py.app']
        identity, endpoint = self._get_identity_and_endpoint()
        app.client_opened(self, endpoint, identity)

    def received_message(self, m):
        # self.clients is set from within the server
        # and holds the list of all connected servers
        # we can dispatch to
        self._log.debug('Socket received message: {}'.format(m))
        app = self.environ['ws4py.app']
        identity, endpoint = self._get_identity_and_endpoint()
        ip = self.environ['']
        app.client_received(endpoint, m)

    def closed(self, code, reason="A client left the room without a proper explanation."):
        self._log.info('Socket closed!')
        app = self.environ.pop('ws4py.app')
        identity, endpoint = self._get_identity_and_endpoint()
        app.client_closed(self, endpoint, identity, reason)

        # if self in app.clients:
        #     app.clients.remove(self)
        #     for client in app.clients:
        #         try:
        #             client.send(reason)
        #         except:
        #             pass


class WebApplicationWrapper(object):
    """ A container class that will hold all of the applications registered
    with it.  The class provides a contianer for managing the routing of
    websocket, static content, and rpc function calls.
    """
    def __init__(self, masterweb, host, port):
        self.masterweb = masterweb
        self.port = port
        self.host = host
        self.ws = WebSocketWSGIApplication(handler_cls=VolttronWebSocket)
        self.clients = []
        self.endpoint_clients = {}
        self._wsregistry = {}
        self._log = logging.getLogger(self.__class__.__name__)

    def favicon(self, environ, start_response):
        """
        Don't care about favicon, let's send nothing.
        """
        status = '200 OK'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return ""

    def client_opened(self, client, endpoint, identity):

        ip = client.environ['REMOTE_ADDR']
        should_open = self.masterweb.vip.rpc.call(identity, 'client.opened',
                                                  ip, endpoint)
        if not should_open:
            self._log.error("Authentication failure, closing websocket.")
            client.close(reason='Authentication failure!')
            return

        # In order to get into endpoint_clients create_ws must be called.
        if endpoint not in self.endpoint_clients:
            self._log.error('Unknown endpoint detected: {}'.format(endpoint))
            client.close(reason="Unknown endpoint! {}".format(endpoint))
            return

        if (identity, client) in  self.endpoint_clients[endpoint]:
            self._log.debug("IDENTITY,CLIENT: {} already in endpoint set".format(identity))
        else:
            self._log.debug("IDENTITY,CLIENT: {} added to endpoint set".format(identity))
            self.endpoint_clients[endpoint].add((identity, client))

    def client_received(self, endpoint, message):
        clients = self.endpoint_clients.get(endpoint, [])
        for identity, _ in clients:
            self.masterweb.vip.rpc.call(identity, 'client.message',
                                        str(endpoint), str(message))

    def client_closed(self, client, endpoint, identity,
                      reason="Client left without proper explaination"):

        client_set = self.endpoint_clients.get(endpoint, set())

        try:
            key = (identity, client)
            client_set.remove(key)
        except KeyError:
            pass
        else:
            self.masterweb.vip.rpc.call(identity, 'client.closed', endpoint)

    def create_ws_endpoint(self, endpoint, identity):
        #_log.debug()print(endpoint, identity)
        # if endpoint in self.endpoint_clients:
        #     peers = self.masterweb.vip.peerlist.get()
        #     old_identity = self._wsregistry[endpoint]
        #     if old_identity not in peers:
        #         for client in self.endpoint_clients.values():
        #             client.close()
        #         r

        if endpoint not in self.endpoint_clients:
            self.endpoint_clients[endpoint] = set()
        self._wsregistry[endpoint] = identity

    def destroy_ws_endpoint(self, endpoint):
        clients = self.endpoint_clients.get(endpoint, [])
        for identity, client in clients:
            client.close(reason="Endpoint closed.")
        try:
            del self.endpoint_clients[endpoint]
        except KeyError:
            pass

    def websocket_send(self, endpoint, message):
        self._log.debug('Sending message to clients!')
        clients = self.endpoint_clients.get(endpoint, [])
        if not clients:
            self._log.warn("There were no clients for endpoint {}".format(
                endpoint))
        for c in clients:
            identity, client = c
            self._log.debug('Sending endpoint&&message {}&&{}'.format(
                endpoint, message))
            client.send(message)

    def __call__(self, environ, start_response):
        """
        Good ol' WSGI application. This is a simple demo
        so I tried to stay away from dependencies.
        """
        if environ['PATH_INFO'] == '/favicon.ico':
            return self.favicon(environ, start_response)

        path = environ['PATH_INFO']
        if path in self._wsregistry:
            environ['ws4py.app'] = self
            environ['identity'] = self._wsregistry[environ['PATH_INFO']]
            return self.ws(environ, start_response)

        return self.masterweb.app_routing(environ, start_response)


class MasterWebService(Agent):
    """The service that is responsible for managing and serving registered pages

    Agents can register either a directory of files to serve or an rpc method
    that will be called during the request process.
    """

    def __init__(self, serverkey, identity, address, bind_web_address, aip,
                 volttron_central_address=None, **kwargs):
        """Initialize the discovery service with the serverkey

        serverkey is the public key in order to access this volttron's bus.
        """
        super(MasterWebService, self).__init__(identity, address, **kwargs)

        self.bind_web_address = bind_web_address
        self.serverkey = serverkey
        self.instance_name = None
        self.registeredroutes = []
        self.peerroutes = defaultdict(list)
        self.pathroutes = defaultdict(list)

        # Maps from endpoint to peer.
        self.endpoints = {}
        self.aip = aip

        self.volttron_central_address = volttron_central_address

        # If vc is this instance then make the vc address the same as
        # the web address.
        if not self.volttron_central_address:
            self.volttron_central_address = bind_web_address

        if not mimetypes.inited:
            mimetypes.init()

        self.appContainer = None
        self._server_greenlet = None

    def remove_unconnnected_routes(self):
        peers = self.vip.peerlist().get()

        for p in self.peerroutes:
            if p not in peers:
                del self.peerroutes[p]



    @RPC.export
    def websocket_send(self, endpoint, message):
        _log.debug("Sending data to {} with message {}".format(endpoint,
                                                               message))
        self.appContainer.websocket_send(endpoint, message)

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
    def register_endpoint(self, endpoint, res_type):
        """
        RPC method to register a dynamic route.

        :param endpoint:
        :return:
        """
        _log.debug('Registering route with endpoint: {}'.format(endpoint))
        # Get calling peer from the rpc context
        peer = bytes(self.vip.rpc.context.vip_message.peer)
        _log.debug('Route is associated with peer: {}'.format(peer))

        if endpoint in self.endpoints:
            _log.error("Attempting to register an already existing endpoint.")
            _log.error("Ignoring registration.")
            raise DuplicateEndpointError(
                "Endpoint {} is already an endpoint".format(endpoint))

        self.endpoints[endpoint] = (peer, res_type)

    @RPC.export
    def register_agent_route(self, regex, fn):
        """ Register an agent route to an exported function.

        When a http request is executed and matches the passed regular
        expression then the function on peer is executed.
        """

        # Get calling peer from the rpc context
        peer = bytes(self.vip.rpc.context.vip_message.peer)

        _log.info(
            'Registering agent route expression: {} peer: {} function: {}'
            .format(regex, peer, fn))

        compiled = re.compile(regex)
        self.peerroutes[peer].append(compiled)
        self.registeredroutes.insert(0, (compiled, 'peer_route', (peer, fn)))

    @RPC.export
    def unregister_all_agent_routes(self):

        # Get calling peer from the rpc context
        peer = bytes(self.vip.rpc.context.vip_message.peer)

        _log.info('Unregistering agent routes for: {}'.format(peer))
        for regex in self.peerroutes[peer]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.peerroutes[peer]
        for regex in self.pathroutes[peer]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.pathroutes[peer]

        _log.debug(self.endpoints)
        endpoints = self.endpoints.copy()
        endpoints = {i:endpoints[i] for i in endpoints if endpoints[i][0] != peer}
        _log.debug(endpoints)
        self.endpoints = endpoints

    @RPC.export
    def register_path_route(self, regex, root_dir):
        _log.info('Registering path route: {}'.format(root_dir))

        # Get calling peer from the rpc context
        peer = bytes(self.vip.rpc.context.vip_message.peer)

        compiled = re.compile(regex)
        self.pathroutes[peer].append(compiled)
        self.registeredroutes.append((compiled, 'path', root_dir))

    @RPC.export
    def register_websocket(self, endpoint):
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        _log.debug('Caller identity: {}'.format(identity))
        _log.debug('REGISTERING ENDPOINT: {}'.format(endpoint))
        if self.appContainer:
            self.appContainer.create_ws_endpoint(endpoint, identity)
        else:
            _log.error('Attempting to register endpoint without web'
                       'subsystem initialized')
            raise AttributeError("self does not contain"
                                 " attribute appContainer")

    @RPC.export
    def unregister_websocket(self, endpoint):
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        _log.debug('Caller identity: {}'.format(identity))
        self.appContainer.destroy_ws_endpoint(endpoint)

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
        authentry = AuthEntry(credentials=vcpublickey)

        try:
            authfile.add(authentry)
        except AuthFileEntryAlreadyExists:
            pass

        start_response('200 OK',
                       [('Content-Type', 'application/json')])
        return jsonapi.dumps(
            json_result(jsondata['id'], "Added")
        )

    def _get_discovery(self, environ, start_response, data=None):
        q = query.Query(self.core)

        self.instance_name = q.query('instance-name').get(timeout=60)
        print("Discovery instance: {}".format(self.instance_name))
        addreses = q.query('addresses').get(timeout=60)
        external_vip = None
        for x in addreses:
            if not is_ip_private(x):
                external_vip = x
                break
        peers = self.vip.peerlist().get(timeout=60)

        return_dict = {}


        if self.serverkey:
            return_dict['serverkey'] = encode_key(self.serverkey)
        else:
            sk = None

        if self.instance_name:
            return_dict['instance-name'] = self.instance_name

        return_dict['vip-address'] = external_vip

        start_response('200 OK', [('Content-Type', 'application/json')])
        return jsonapi.dumps(return_dict)

    def app_routing(self, env, start_response):
        """
        The main routing function that maps the incoming request to a response.

        Depending on the registered routes map the request data onto an rpc
        function or a specific named file.
        """
        path_info = env['PATH_INFO']

        if path_info.startswith('/http://'):
            path_info = path_info[path_info.index('/', len('/http://')):]
            _log.debug('Path info is: {}'.format(path_info))
        # only expose a partial list of the env variables to the registered
        # agents.
        envlist = ['HTTP_USER_AGENT', 'PATH_INFO', 'QUERY_STRING',
                   'REQUEST_METHOD', 'SERVER_PROTOCOL', 'REMOTE_ADDR',
                   'HTTP_ACCEPT_ENCODING']
        data = env['wsgi.input'].read()
        passenv = dict(
            (envlist[i], env[envlist[i]]) for i in range(0, len(envlist)) if envlist[i] in env.keys())

        _log.debug('PATH IS: {}'.format(path_info))
        # Get the peer responsible for dealing with the endpoint.  If there
        # isn't a peer then fall back on the other methods of routing.
        (peer, res_type) = self.endpoints.get(path_info, (None, None))
        _log.debug('Peer we path_info is associated with: {}'.format(peer))

        # if we have a peer then we expect to call that peer's web subsystem
        # callback to perform whatever is required of the method.
        if peer:
            _log.debug('Calling peer {} back with env={} data={}'.format(
                peer, passenv, data
            ))
            res = self.vip.rpc.call(peer, 'route.callback',
                                    passenv, data).get(timeout=60)
            if res_type == "jsonrpc":
                return self.create_response(res, start_response)
            elif res_type == "raw":
                return self.create_raw_response(res, start_response)

        for k, t, v in self.registeredroutes:
            if k.match(path_info):
                _log.debug("MATCHED:\npattern: {}, path_info: {}\n v: {}"
                           .format(k.pattern, path_info, v))
                _log.debug('registered route t is: {}'.format(t))
                if t == 'callable':  # Generally for locally called items.
                    return v(env, start_response, data)
                elif t == 'peer_route':  # RPC calls from agents on the platform
                    _log.debug('Matched peer_route with pattern {}'.format(
                        k.pattern))
                    peer, fn = (v[0], v[1])
                    res = self.vip.rpc.call(peer, fn, passenv, data).get(
                        timeout=120)
                    _log.debug(res)
                    return self.create_response(res, start_response)

                elif t == 'path':  # File service from agents on the platform.
                    server_path = v + path_info  # os.path.join(v, path_info)
                    _log.debug('Serverpath: {}'.format(server_path))
                    return self._sendfile(env, start_response, server_path)

        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return [b'<h1>Not Found</h1>']

    def create_raw_response(self, res, start_response):
        # If this is a tuple then we know we are going to have a response
        # and a headers portion of the data.
        if isinstance(res, tuple) or isinstance(res, list):
            if len(res) == 1:
                status, = res
                headers = ()
            if len(res) == 2:
                headers = ()
                status, response = res
            if len(res) == 3:
                status, response, headers = res
            start_response(status, headers)
            return base64.b64decode(response)
        else:
            start_response("500 Programming Error",
                           [('Content-Type', 'text/html')])
            _log.error("Invalid length of response tuple (must be 1-3)")
            return [b'Invalid response tuple (must contain 1-3 elements)']

    def create_response(self, res, start_response):

        # Dictionaries are going to be treated as if they are meant to be json
        # serialized with Content-Type of application/json
        if isinstance(res, dict):
            # Note this is specific to volttron central agent and should
            # probably not be at this level of abstraction.
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
            return jsonapi.dumps(res)

        # If this is a tuple then we know we are going to have a response
        # and a headers portion of the data.
        if isinstance(res, tuple) or isinstance(res, list):
            if len(res) != 2:
                start_response("500 Programming Error",
                               [('Content-Type', 'text/html')])
                _log.error("Invalid length of response tuple (must be 2)")
                return [b'Invalid response tuple (must contain 2 elements)']

            response, headers = res
            header_dict = dict(headers)
            if header_dict.get('Content-Encoding', None) == 'gzip':
                gzip_compress = zlib.compressobj(9, zlib.DEFLATED,
                                                 zlib.MAX_WBITS | 16)
                data = gzip_compress.compress(response) + gzip_compress.flush()
                start_response('200 OK', headers)
                return data
            else:
                return response
        else:
            start_response('200 OK',
                           [('Content-Type', 'application/json')])
            return jsonapi.dumps(res)

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

        self.appContainer = WebApplicationWrapper(self, hostname, port)
        svr = WSGIServer((hostname, port), self.appContainer)
        self._server_greenlet = gevent.spawn(svr.serve_forever)

        # with open(os.path.join(logdir, 'web.access.log'), 'wb') as accesslog:
        #     with open(os.path.join(logdir, 'web.error.log'), 'wb') as errlog:
        #         server = pywsgi.WSGIServer((hostname, port), self.app_routing,
        #                                    log=accesslog, error_log=errlog)
        #         try:
        #             server.serve_forever()
        #         except Exception as e:
        #             message = 'bind-web-address {} is not available, stopping'
        #             message = message.format(self.bind_web_address)
        #             _log.error(message)
        #             print message
        #             sys.exit(1)

                    # svr = WSGIServer((host, port))
        # with open(os.path.join(logdir, 'web.access.log'), 'wb') as accesslog:
        #     with open(os.path.join(logdir, 'web.error.log'), 'wb') as errlog:
        #         server = pywsgi.WSGIServer((hostname, port), self.app_routing,
        #                                log=accesslog, error_log=errlog)
        #         server.serve_forever()


def build_vip_address_string(vip_root, serverkey, publickey, secretkey):
    """ Build a full vip address string based upon the passed arguments

    All arguments are required to be non-None in order for the string to be
    created successfully.

    :raises ValueError if one of the parameters is None.
    """
    _log.debug("root: {}, serverkey: {}, publickey: {}, secretkey: {}".format(
        vip_root, serverkey, publickey, secretkey))
    parsed = urlparse(vip_root)
    if parsed.scheme == 'tcp':
        if not (serverkey and publickey and secretkey and vip_root):
            raise ValueError("All parameters must be entered.")

        root = "{}?serverkey={}&publickey={}&secretkey={}".format(
            vip_root, serverkey, publickey, secretkey)

    elif parsed.scheme == 'ipc':
        root = vip_root
    else:
        raise ValueError('Invalid vip root specified!')

    return root
