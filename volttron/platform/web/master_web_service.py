# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import base64
import logging
import mimetypes
import os
import re
from urllib.parse import urlparse, parse_qs
import zlib
from collections import defaultdict

import gevent
import gevent.pywsgi
from cryptography.hazmat.primitives import serialization
from gevent import Greenlet
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ws4py.server.geventserver import WSGIServer

from .admin_endpoints import AdminEndpoints
from .authenticate_endpoint import AuthenticateEndpoints
from .csr_endpoints import CSREndpoints
from .webapp import WebApplicationWrapper
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import CONTROL
from ..agent.utils import get_fq_identity
from ..agent.web import Response, JsonResponse
from ..auth import AuthEntry, AuthFile, AuthFileEntryAlreadyExists
from ..certs import Certs, CertWrapper
from ..jsonrpc import (json_result,
                       json_validate_request,
                       INVALID_REQUEST, METHOD_NOT_FOUND,
                       UNHANDLED_EXCEPTION, UNAUTHORIZED,
                       UNAVAILABLE_PLATFORM, INVALID_PARAMS,
                       UNAVAILABLE_AGENT, INTERNAL_ERROR)

from ..vip.agent import Agent, Core, RPC, Unreachable
from ..vip.agent.subsystems import query
from ..vip.socket import encode_key
from ...platform import jsonapi, jsonrpc, get_platform_config
from ...platform.aip import AIPplatform
from ...utils import is_ip_private
from ...utils.rmq_config_params import RMQConfig

# must be after importing of utils which imports grequest.
import requests

_log = logging.getLogger(__name__)


class CouldNotRegister(Exception):
    pass


class DuplicateEndpointError(Exception):
    pass


__PACKAGE_DIR__ = os.path.dirname(os.path.abspath(__file__))
__TEMPLATE_DIR__ = os.path.join(__PACKAGE_DIR__, "templates")
__STATIC_DIR__ = os.path.join(__PACKAGE_DIR__, "static")


# Our admin interface will use Jinja2 templates based upon the above paths
# reference api for using Jinja2 http://jinja.pocoo.org/docs/2.10/api/
# Using the FileSystemLoader instead of the package loader in this case however.
tplenv = Environment(
    loader=FileSystemLoader(__TEMPLATE_DIR__),
    autoescape=select_autoescape(['html', 'xml'])
)


class MasterWebService(Agent):
    """The service that is responsible for managing and serving registered pages

    Agents can register either a directory of files to serve or an rpc method
    that will be called during the request process.
    """

    def __init__(self, serverkey, identity, address, bind_web_address,
                 volttron_central_address=None, volttron_central_rmq_address=None,
                 web_ssl_key=None, web_ssl_cert=None, web_secret_key=None, **kwargs):
        """
        Initialize the configuration of the base web service integration within the platform.

        """
        super(MasterWebService, self).__init__(identity, address, **kwargs)

        # no matter what we need to have a bind_web_address passed to us.
        if not bind_web_address:
            raise ValueError("Invalid bind web address.")

        self.bind_web_address = bind_web_address
        self.serverkey = serverkey
        self.instance_name = None
        self.registeredroutes = []
        self.peerroutes = defaultdict(list)
        self.pathroutes = defaultdict(list)
        # These will be used if set rather than the
        # any of the internal agent's certificates
        self.web_ssl_key = web_ssl_key
        self.web_ssl_cert = web_ssl_cert
        self._web_secret_key = web_secret_key

        # Maps from endpoint to peer.
        self.endpoints = {}

        self.volttron_central_address = volttron_central_address
        self.volttron_central_rmq_address = volttron_central_rmq_address

        # If vc is this instance then make the vc address the same as
        # the web address.
        if not self.volttron_central_address:
            self.volttron_central_address = bind_web_address

        if not mimetypes.inited:
            mimetypes.init()

        self._certs = Certs()
        # noinspection PyTypeChecker
        self._csr_endpoints: CSREndpoints = None
        # noinspection PyTypeChecker
        self.appContainer: WebApplicationWrapper = None
        # noinspection PyTypeChecker
        self._server_greenlet: Greenlet = None
        # noinspection PyTypeChecker
        self._admin_endpoints: AdminEndpoints = None


    # pylint: disable=unused-argument
    @Core.receiver('onsetup')
    def onsetup(self, sender, **kwargs):
        self.vip.rpc.export(self._auto_allow_csr, 'auto_allow_csr')
        self.vip.rpc.export(self._is_auto_allow_csr, 'is_auto_allow_csr')

    def _is_auto_allow_csr(self):
        return self._csr_endpoints.auto_allow_csr

    def _auto_allow_csr(self, auto_allow_csr):
        self._csr_endpoints.auto_allow_csr = auto_allow_csr

    def remove_unconnnected_routes(self):
        peers = self.vip.peerlist().get()

        for p in self.peerroutes:
            if p not in peers:
                del self.peerroutes[p]

    @RPC.export
    def get_user_claims(self, bearer):
        from volttron.platform.web import get_user_claim_from_bearer
        if self.core.messagebus == 'rmq':
            return get_user_claim_from_bearer(bearer,
                                              tls_public_key=self._certs.get_cert_public_key(
                                                           get_fq_identity(self.core.identity)))
        if self.web_ssl_cert is not None:
            return get_user_claim_from_bearer(bearer,
                                              tls_public_key=CertWrapper.get_cert_public_key(self.web_ssl_cert))
        elif self._web_secret_key is not None:
            return get_user_claim_from_bearer(bearer, web_secret_key=self._web_secret_key)

        else:
            raise ValueError("Configuration error secret key or web ssl cert must be not None.")

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

        Note: this only applies to Volttron Central agents that are
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
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer
        _log.debug('Registering route with endpoint: {}'.format(endpoint))
        _log.debug('Route is associated with peer: {}'.format(identity))

        if endpoint in self.endpoints:
            _log.error("Attempting to register an already existing endpoint.")
            _log.error("Ignoring registration.")
            raise DuplicateEndpointError(
                "Endpoint {} is already an endpoint".format(endpoint))

        self.endpoints[endpoint] = (identity, res_type)

    @RPC.export
    def register_agent_route(self, regex, fn):
        """ Register an agent route to an exported function.

        When a http request is executed and matches the passed regular
        expression then the function on peer is executed.
        """
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer

        _log.info(
            'Registering agent route expression: {} peer: {} function: {}'
                .format(regex, identity, fn))

        # TODO: inspect peer for function

        compiled = re.compile(regex)
        self.peerroutes[identity].append(compiled)
        self.registeredroutes.insert(0, (compiled, 'peer_route', (identity, fn)))

    @RPC.export
    def unregister_all_agent_routes(self):
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer

        _log.info('Unregistering agent routes for: {}'.format(identity))
        for regex in self.peerroutes[identity]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.peerroutes[identity]
        for regex in self.pathroutes[identity]:
            out = [cp for cp in self.registeredroutes if cp[0] != regex]
            self.registeredroutes = out
        del self.pathroutes[identity]

        _log.debug(self.endpoints)
        endpoints = self.endpoints.copy()
        endpoints = {i:endpoints[i] for i in endpoints if endpoints[i][0] != identity}
        _log.debug(endpoints)
        self.endpoints = endpoints

    @RPC.export
    def register_path_route(self, regex, root_dir):
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer

        _log.info(f'Registering web path route from {identity} regex: {regex} dir: {root_dir}')

        compiled = re.compile(regex)
        self.pathroutes[identity].append(compiled)
        # in order for this agent to pass against the default route we want this
        # to be before the last route which will resolve to .*
        self.registeredroutes.insert(len(self.registeredroutes) - 1, (compiled, 'path', root_dir))

    @RPC.export
    def register_websocket(self, endpoint):
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer

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
        # Get calling identity from whom the request came from
        identity = self.vip.rpc.context.vip_message.peer

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
        return [b'1']

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
        return [jsonapi.dumpb(
            json_result(jsondata['id'], "Added")
        )]

    def _get_discovery(self, environ, start_response, data=None):
        q = query.Query(self.core)

        self.instance_name = q.query('instance-name').get(timeout=60)
        addreses = q.query('addresses').get(timeout=60)
        external_vip = None
        for x in addreses:
            try:
                if not is_ip_private(x):
                    external_vip = x
                    break
            except IndexError:
                pass

        return_dict = {}

        # Only send vip and serverkey if the platform has specified
        # a tcp address in the <VOLTTRON_HOME>/config or --vip-address command line argument.
        if external_vip and self.serverkey:
            return_dict['serverkey'] = encode_key(self.serverkey)
            return_dict['vip-address'] = external_vip
        elif not external_vip:
            _log.warning("There was no external vip-address specified in config file or command line.")

        if self.instance_name:
            return_dict['instance-name'] = self.instance_name

        if self.core.messagebus == 'rmq':
            config = RMQConfig()
            rmq_address = None
            if config.is_ssl:
                rmq_address = "amqps://{host}:{port}/{vhost}".format(host=config.hostname, port=config.amqp_port_ssl,
                                                                     vhost=config.virtual_host)
            else:
                rmq_address = "amqp://{host}:{port}/{vhost}".format(host=config.hostname, port=config.amqp_port,
                                                                    vhost=config.virtual_host)
            return_dict['rmq-address'] = rmq_address
            return_dict['rmq-ca-cert'] = self._certs.cert(self._certs.root_ca_name).public_bytes(
                serialization.Encoding.PEM).decode("utf-8")
        return Response(jsonapi.dumps(return_dict), content_type="application/json")
        # return JsonResponse(return_dict)

    def app_routing(self, env, start_response):
        """
        The main routing function that maps the incoming request to a response.

        Depending on the registered routes map the request data onto an rpc
        function or a specific named file.
        """
        path_info = env['PATH_INFO']

        if path_info.startswith('/http://'):
            path_info = path_info[path_info.index('/', len('/http://')):]

        # only expose a partial list of the env variables to the registered
        # agents.
        envlist = ['HTTP_USER_AGENT', 'PATH_INFO', 'QUERY_STRING',
                   'REQUEST_METHOD', 'SERVER_PROTOCOL', 'REMOTE_ADDR',
                   'HTTP_ACCEPT_ENCODING', 'HTTP_COOKIE', 'CONTENT_TYPE',
                   'HTTP_AUTHORIZATION', 'SERVER_NAME', 'wsgi.url_scheme',
                   'HTTP_HOST']
        data = env['wsgi.input'].read().decode('utf-8')
        passenv = dict(
            (envlist[i], env[envlist[i]]) for i in range(0, len(envlist)) if envlist[i] in env.keys())

        _log.debug('path_info is: {}'.format(path_info))
        # Get the peer responsible for dealing with the endpoint.  If there
        # isn't a peer then fall back on the other methods of routing.
        (peer, res_type) = self.endpoints.get(path_info, (None, None))
        _log.debug('Peer path_info is associated with: {}'.format(peer))

        if self.is_json_content(env):
            data = jsonapi.loads(data)

        # Only if https available and rmq for the admin area.
        if env['wsgi.url_scheme'] == 'https' and self.core.messagebus == 'rmq':
            # Load the publickey that was used to sign the login message through the env
            # parameter so agents can use it to verify the Bearer has specific
            # jwt claims
            passenv['WEB_PUBLIC_KEY'] = env['WEB_PUBLIC_KEY'] = self._certs.get_cert_public_key(
                get_fq_identity(self.core.identity)).decode('utf-8')

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

        env['JINJA2_TEMPLATE_ENV'] = tplenv

        # if ws4pi.socket is set then this connection is a web socket
        # and so we return the websocket response.
        if 'ws4py.socket' in env:
            return env['ws4py.socket'](env, start_response)

        for k, t, v in self.registeredroutes:
            if k.match(path_info):
                _log.debug("MATCHED:\npattern: {}, path_info: {}\n v: {}"
                           .format(k.pattern, path_info, v))
                _log.debug('registered route t is: {}'.format(t))
                if t == 'callable':  # Generally for locally called items.
                    # Changing signature of the "locally" called points to return
                    # a Response object. Our response object then will in turn
                    # be processed and the response will be written back to the
                    # calling client.
                    try:
                        retvalue = v(env, start_response, data)
                    except TypeError:
                        response = v(env, data)
                        return response(env, start_response)
                        # retvalue = self.process_response(start_response, v(env, data))

                    if isinstance(retvalue, Response):
                        return retvalue(env, start_response)
                        #return self.process_response(start_response, retvalue)
                    elif isinstance(retvalue, Response):  # werkzueg Response
                        for d in retvalue(env, start_response):
                            print(d)
                        return retvalue(env, start_response)
                    else:
                        return retvalue[0]

                elif t == 'peer_route':  # RPC calls from agents on the platform
                    _log.debug('Matched peer_route with pattern {}'.format(
                        k.pattern))
                    peer, fn = (v[0], v[1])
                    res = self.vip.rpc.call(peer, fn, passenv, data).get(
                        timeout=120)
                    _log.debug(res)
                    return self.create_response(res, start_response)

                elif t == 'path':  # File service from agents on the platform.
                    if path_info == '/':
                        return self._redirect_index(env, start_response)
                    server_path = v + path_info  # os.path.join(v, path_info)
                    _log.debug('Serverpath: {}'.format(server_path))
                    return self._sendfile(env, start_response, server_path)

        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return [b'<h1>Not Found</h1>']

    def is_json_content(self, env):
        ct = env.get('CONTENT_TYPE')
        if ct is not None and 'application/json' in ct:
            return True
        return False

    def process_response(self, start_response, response):
        # if we are using the original response, then morph it into a werkzueg response.
        # response = MasterWebService.convert_response_to_werkzueg(response)
        # return response()
        # process the response
        start_response(response.status, response.headers)

        if isinstance(response.content, str):
            return [response.content.encode('utf-8')]
        return [response.content]

    def create_raw_response(self, res, start_response):
        # If this is a tuple then we know we are going to have a response
        # and a headers portion of the data.
        if isinstance(res, tuple) or isinstance(res, list):
            if len(res) == 1:
                status, = res
                headers = ()
            elif len(res) == 2:
                headers = ()
                status, response = res
            elif len(res) == 3:
                status, response, headers = res
            else:
                raise Exception("Couldn't process raw response {}".format(res))
            start_response(status.encode('utf-8'), headers)
            return [base64.b64decode(response)]
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
                    return ['<h1>{}</h1>\n<h2>CODE:{}</h2>'.format(message, code).encode('utf-8')]

            start_response('200 OK',
                           [('Content-Type', 'application/json')])
            return [jsonapi.dumpb(res)]
        elif isinstance(res, list):
            _log.debug('list implies [content, headers] or [status, content, headers]')
            if len(res) == 2:
                start_response('200 OK',
                               res[1])
                return res[0]
            elif len(res) == 3:
                start_response(res[0], res[2])
                if isinstance(res[1], str):
                    return [res[1].encode('utf-8')]
                return [res[1]]

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
                return [data]
            else:
                return [response]
        else:
            start_response('200 OK',
                           [('Content-Type', 'application/json')])
            return [jsonapi.dumpb(res)]

    def _sendfile(self, env, start_response, filename):
        from wsgiref.util import FileWrapper
        status = '200 OK'
        _log.debug('SENDING FILE: {}'.format(filename))
        guess = mimetypes.guess_type(filename)[0]
        _log.debug('MIME GUESS: {}'.format(guess))

        basename = os.path.dirname(filename)

        if not os.path.exists(basename):
            start_response('404 Not Found', [('Content-Type', 'text/html')])
            return [b'<h1>Not Found</h1>']
        elif not os.path.isfile(filename):
            start_response('404 Not Found', [('Content-Type', 'text/html')])
            return [b'<h1>Not Found</h1>']

        if not guess:
            guess = 'text/plain'

        response_headers = [
            ('Content-type', guess),
        ]
        start_response(status, response_headers)

        return FileWrapper(open(filename, 'rb'))

    def _to_jsonrpc_obj(self, jsonrpcstr):
        """ Convert data string into a JsonRpcData named tuple.

        :param object data: Either a string or a dictionary representing a json document.
        """
        return jsonrpc.JsonRpcData.parse(jsonrpcstr)

    def jsonrpc(self, env, data):
        """ The main entry point for ^jsonrpc data

        This method will only accept rpcdata.  The first time this method
        is called, per session, it must be using get_authorization.  That
        will return a session token that must be included in every
        subsequent request.  The session is tied to the ip address
        of the caller.

        :param object env: Environment dictionary for the request.
        :param object data: The JSON-RPC 2.0 method to call.
        :return object: An JSON-RPC 2.0 response.
        """
        if env['REQUEST_METHOD'].upper() != 'POST':
            return JsonResponse(jsonapi.dumps(jsonrpc.json_error('NA', INVALID_REQUEST,
                                      'Invalid request method, only POST allowed')))

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))

            # Authenticate rpc call
            if 'authentication' in rpcdata.params:
                if self.jsonrpc_verify_and_dispatch(rpcdata.params['authentication']):
                    del rpcdata.params['authentication']
                else:
                    return JsonResponse(jsonapi.dumps(jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                                           "Invalid username/password specified.")))
            else:
                return JsonResponse(jsonapi.dumps(jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                                       "Authentication parameter missing.")))

            _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))
            if not rpcdata.method:
                return JsonResponse(jsonapi.dumps(jsonrpc.json_error(
                    'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data))))
            else:
                if rpcdata.params:
                    result_or_error = self.vip.rpc(rpcdata.id, rpcdata.method, **rpcdata.params).get()
                else:
                    result_or_error = self.vip.rpc(rpcdata.id, rpcdata.method).get()

        except AssertionError:
            return JsonResponse(jsonapi.dumps(jsonrpc.json_error(
                'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data))))
        except Unreachable:
            return JsonResponse(jsonapi.dumps(jsonrpc.json_error(
                rpcdata.id, UNAVAILABLE_PLATFORM,
                "Couldn't reach platform with method {} params: {}".format(
                    rpcdata.method,
                    rpcdata.params))))
        except Exception as e:

            return JsonResponse(jsonapi.dumps(jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, e
            )))

        return JsonResponse(jsonapi.dumps(self._get_jsonrpc_response(rpcdata.id, result_or_error)))

    def _get_jsonrpc_response(self, id, result_or_error):
        """ Wrap the response in either a json-rpc error or result.

        :param id:
        :param result_or_error:
        :return:
        """
        if isinstance(result_or_error, dict):
            if 'jsonrpc' in result_or_error:
                return result_or_error

        if result_or_error is not None and isinstance(result_or_error, dict):
            if 'error' in result_or_error:
                error = result_or_error['error']
                _log.debug("RPC RESPONSE ERROR: {}".format(error))
                return jsonrpc.json_error(id, error['code'], error['message'])
        return jsonrpc.json_result(id, result_or_error)

    def jsonrpc_verify_and_dispatch(self, authentication):
        """ Verify that the user is an admin

        :param authentication: authentication generated by successful authentication
        :return: Boolean
        """
        from volttron.platform.web import NotAuthorized
        try:
            claims = self.get_user_claims(authentication)
        except NotAuthorized:
            _log.error("Unauthorized user attempted to connect to platform.")
            return False
        return True



    @Core.receiver('onstart')
    def startupagent(self, sender, **kwargs):

        from urllib.parse import urlparse
        parsed = urlparse(self.bind_web_address)

        ssl_key = self.web_ssl_key
        ssl_cert = self.web_ssl_cert
        rpc_caller = self.vip.rpc
        if parsed.scheme == 'https':
            # Admin interface is only availble to rmq at present.
            if self.core.messagebus == 'rmq':
                self._admin_endpoints = AdminEndpoints(rmq_mgmt=self.core.rmq_mgmt,
                                                       ssl_public_key=self._certs.get_cert_public_key(
                                                           get_fq_identity(self.core.identity)),
                                                       rpc_caller=rpc_caller)
            if ssl_key is None or ssl_cert is None:
                # Because the master.web service certificate is a client to rabbitmq we
                # can't use it directly therefore we use the -server on the file to specify
                # the server based file.
                base_filename = get_fq_identity(self.core.identity) + "-server"
                ssl_cert = self._certs.cert_file(base_filename)
                ssl_key = self._certs.private_key_file(base_filename)

                if not os.path.isfile(ssl_cert) or not os.path.isfile(ssl_key):
                    self._certs.create_signed_cert_files(base_filename, cert_type='server')

            if ssl_key is not None and ssl_cert is not None and self._admin_endpoints is None:
                self._admin_endpoints = AdminEndpoints(ssl_public_key=CertWrapper.get_cert_public_key(ssl_cert),
                                                       rpc_caller=rpc_caller)
        else:
            self._admin_endpoints = AdminEndpoints(rpc_caller=rpc_caller)

        hostname = parsed.hostname
        port = parsed.port

        _log.info('Starting web server binding to {}://{}:{}.'.format(parsed.scheme,
                                                                      hostname, port))
        # Handle the platform.web routes here.
        self.registeredroutes.append((re.compile('^/discovery/$'), 'callable', self._get_discovery))
        self.registeredroutes.append((re.compile('^/discovery/allow$'), 'callable', self._allow))
        self.registeredroutes.append((re.compile(r'/gs'), 'callable', self.jsonrpc))
        # these routes are only available for rmq based message bus
        # at present.
        if self.core.messagebus == 'rmq':
            # We need reference to the object so we can change the behavior of
            # whether or not to have auto certs be created or not.
            self._csr_endpoints = CSREndpoints(self.core)
            for rt in self._csr_endpoints.get_routes():
                self.registeredroutes.append(rt)

        # Register the admin endpoints regardless of whether there is an ssl context
        # or not.
        for rt in self._admin_endpoints.get_routes():
            self.registeredroutes.append(rt)

        # Allow authentication endpoint from any https connection
        if parsed.scheme == 'https':
            if self.core.messagebus == 'rmq':
                ssl_private_key = self._certs.get_pk_bytes(get_fq_identity(self.core.identity))
            else:
                ssl_private_key = CertWrapper.get_private_key(ssl_key)
            for rt in AuthenticateEndpoints(tls_private_key=ssl_private_key).get_routes():
                self.registeredroutes.append(rt)
        else:
            # We don't have a private ssl key if we aren't using ssl.
            for rt in AuthenticateEndpoints(web_secret_key=self._web_secret_key).get_routes():
                self.registeredroutes.append(rt)

        static_dir = os.path.join(os.path.dirname(__file__), "static")
        self.registeredroutes.append((re.compile('^/.*$'), 'path', static_dir))

        port = int(port)

        self.appContainer = WebApplicationWrapper(self, hostname, port)
        if ssl_key and ssl_cert:
            svr = WSGIServer((hostname, port), self.appContainer,
                             certfile=ssl_cert,
                             keyfile=ssl_key)
        else:
            svr = WSGIServer((hostname, port), self.appContainer)
        self._server_greenlet = gevent.spawn(svr.serve_forever)

    def _authenticate_route(self, env, start_response, data):
        scheme = env.get('wsgi.url_scheme')

        if scheme != 'https':
            _log.warning("Authentication should be through https")
            start_response("401 Unauthorized", [('Content-Type', 'text/html')])
            return "<html><body><h1>401 Unauthorized</h1></body></html>"

        from pprint import pprint
        pprint(env)

        import jwt

        jwt.encode()

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        _log.debug("Stopping web agent.")
        if not self._server_greenlet.dead:
            self._server_greenlet.join(timeout=10)
