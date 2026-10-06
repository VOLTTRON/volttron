# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import base64
import logging
import mimetypes
import os
import re
from types import MappingProxyType
from urllib.parse import urlparse, parse_qs
import zlib
from collections import defaultdict

import gevent
import gevent.pywsgi
import werkzeug
import jwt
from cryptography.hazmat.primitives import serialization
from gevent import Greenlet
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ws4py.server.geventserver import WSGIServer

from .admin_endpoints import AdminEndpoints
from .vui_endpoints import VUIEndpoints
from .authenticate_endpoint import AuthenticateEndpoints
from .csr_endpoints import CSREndpoints
from .webapp import WebApplicationWrapper
from .static_roots import configured_roots, file_to_serve, root_refusal
from volttron.platform.agent.known_identities import \
    CONTROL, VOLTTRON_CENTRAL, AUTH, REGISTER_WEB_ROUTES
from ..agent.utils import get_fq_identity
from ..agent.web import Response, JsonResponse
from volttron.platform.auth.auth_entry import AuthEntry
from volttron.platform.auth.auth_file import AuthFile, AuthFileEntryAlreadyExists
from volttron.platform.auth.certs import Certs, CertWrapper
from ..jsonrpc import (json_result,
                       json_validate_request,
                       INVALID_REQUEST,
                       UNHANDLED_EXCEPTION, UNAUTHORIZED,
                       UNAVAILABLE_PLATFORM, INVALID_PARAMS,
                       UNAVAILABLE_AGENT, INTERNAL_ERROR, RemoteError)

from ..vip.agent import Agent, Core, RPC, Unreachable
from ..vip.agent.subsystems import query
from ..vip.socket import encode_key
from ...platform import get_home, jsonapi, jsonrpc
from ...platform.aip import AIPplatform
from ...utils import is_ip_private
from ...utils.rmq_config_params import RMQConfig

_log = logging.getLogger(__name__)

# Calls the /gs gateway forwards, each mapped to the param keys it accepts.
# Every entry is an ungated, read-only ControlService export; there is no
# configuration hook, so widening the list is a reviewed code change.
GS_ALLOWED_CALLS = MappingProxyType({
    (CONTROL, 'list_agents'): frozenset(),
    (CONTROL, 'status_agents'): frozenset(),
    (CONTROL, 'peerlist'): frozenset(),
})
GS_CALL_TIMEOUT = 10
# \Z rather than $, which also matches before a trailing newline.
GS_ROUTE = re.compile(r'^/gs/?\Z')

# Kept from agents even where their routes are not served (/csr runs only on
# some platforms); their clients expect the platform to answer.
ALWAYS_RESERVED_NAMESPACES = frozenset({'gs', 'csr'})
# Held for the agent that serves them, so no other agent can claim them first.
IDENTITY_NAMESPACES = MappingProxyType({'vc': VOLTTRON_CENTRAL})
# The platform login pages keep the token in this cookie.
LOGIN_COOKIE = 'bearer'
# An endpoint or websocket path: /<namespace> or /<namespace>/...
_PATH_NAMESPACE = re.compile(r'/([A-Za-z0-9_.~-]+)(?:/|\Z)')
# An agent route pattern: ^/<namespace> or /<namespace>, then /, $ or the end.
_PATTERN_NAMESPACE = re.compile(r'\^?/([A-Za-z0-9_.~-]+)(?:/|\$|\Z)')
# A platform pattern's literal first segment; '.' is a wildcard there.
_BUILTIN_SEGMENT = re.compile(r'\^?/([A-Za-z0-9_~-]+)')


class AgentRoute(tuple):
    """A (pattern, kind, value) route table entry that an agent registered.

    The entry is consulted only for requests whose first path segment is its
    namespace, and only its owner removes it.
    """

    def __new__(cls, pattern, kind, value, owner, namespace):
        entry = super().__new__(cls, (pattern, kind, value))
        entry.owner = owner
        entry.namespace = namespace
        return entry


def builtin_namespaces(patterns):
    """Return the case-folded first path segment of each platform route.

    Raises ValueError for a pattern without a literal first segment, since
    agent namespaces could not be kept apart from it.
    """
    names = set()
    for pattern in patterns:
        match = _BUILTIN_SEGMENT.match(pattern.pattern)
        if match is None:
            raise ValueError(f'platform route {pattern.pattern!r} has no literal first path segment')
        names.add(match.group(1).casefold())
    return names


def _path_namespace(path):
    match = _PATH_NAMESPACE.match(path) if isinstance(path, str) else None
    return match.group(1) if match else None


def _pattern_namespace(regex):
    match = _PATTERN_NAMESPACE.match(regex) if isinstance(regex, str) else None
    return match.group(1) if match else None


def _first_segment(path):
    return path.split('/', 2)[1] if path.startswith('/') else ''


def _without_login_cookie(cookie_header):
    kept = (c.strip() for c in cookie_header.split(';')
            if c.split('=', 1)[0].strip().casefold() != LOGIN_COOKIE)
    return '; '.join(c for c in kept if c)


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


class PlatformWebService(Agent):
    """The service that is responsible for managing and serving registered pages

    Agents can register either a directory of files to serve or an rpc method
    that will be called during the request process.
    """

    def __init__(self, serverkey, identity, address, bind_web_address,
                 volttron_central_address=None, volttron_central_rmq_address=None,
                 web_ssl_key=None, web_ssl_cert=None, web_secret_key=None,
                 web_static_roots=None, **kwargs):
        """
        Initialize the configuration of the base web service integration within the platform.

        """
        super(PlatformWebService, self).__init__(identity, address, **kwargs)

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
        self._static_roots = configured_roots(web_static_roots, get_home())

        # Maps from endpoint to peer.
        self.endpoints = {}
        # Case-folded namespace to the identity that registered in it first.
        self._namespace_owners = {}
        # Set by startupagent once the platform routes are in the table; until
        # then every agent registration is refused.
        self._reserved_namespaces = None
        self._builtin_patterns = ()

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

        self._vui_endpoints: VUIEndpoints = None

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
            claims = get_user_claim_from_bearer(bearer,
                                                tls_public_key=self._certs.get_cert_public_key(
                                                    get_fq_identity(self.core.identity)))
        elif self.web_ssl_cert is not None:
            claims = get_user_claim_from_bearer(bearer,
                                                tls_public_key=CertWrapper.get_cert_public_key(self.web_ssl_cert))
        elif self._web_secret_key is not None:
            claims = get_user_claim_from_bearer(bearer, web_secret_key=self._web_secret_key)

        else:
            raise ValueError("Configuration error secret key or web ssl cert must be not None.")

        return claims if claims.get('grant_type') == 'access_token' else {}

    @RPC.export
    def websocket_send(self, endpoint, message):
        identity = self._caller('websocket_send', endpoint)
        _log.debug("Sending data to {} with message {}".format(endpoint,
                                                               message))
        if self.appContainer is None:
            _log.info('web server is not running; nothing sent to %r', endpoint)
            return
        try:
            self.appContainer.websocket_send(endpoint, message, identity)
        except PermissionError:
            self._refuse('websocket_send', identity, endpoint,
                         'the websocket belongs to another agent')

    @RPC.export
    def print_websocket_clients(self):
        _log.debug(self.appContainer.endpoint_clients)

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
    @RPC.allow(capabilities=REGISTER_WEB_ROUTES)
    def register_endpoint(self, endpoint, res_type):
        """
        RPC method to register a dynamic route.

        :param endpoint:
        :return:
        """
        identity = self._caller('register_endpoint', endpoint)
        namespace = self._check_namespace('register_endpoint', identity, endpoint,
                                          _path_namespace(endpoint))
        _log.debug('Registering route with endpoint: {}'.format(endpoint))
        _log.debug('Route is associated with peer: {}'.format(identity))

        if endpoint in self.endpoints:
            _log.error("Attempting to register an already existing endpoint.")
            _log.error("Ignoring registration.")
            raise DuplicateEndpointError(
                "Endpoint {} is already an endpoint".format(endpoint))

        self._namespace_owners[namespace] = identity
        self.endpoints[endpoint] = (identity, res_type)

    @RPC.export
    @RPC.allow(capabilities=REGISTER_WEB_ROUTES)
    def register_agent_route(self, regex, fn):
        """ Register an agent route to an exported function.

        When a http request is executed and matches the passed regular
        expression then the function on peer is executed.
        """
        identity = self._caller('register_agent_route', regex)
        namespace = _pattern_namespace(regex)
        key = self._check_namespace('register_agent_route', identity, regex, namespace)

        _log.info(
            'Registering agent route expression: {} peer: {} function: {}'
                .format(regex, identity, fn))

        # TODO: inspect peer for function

        compiled = re.compile(regex)
        self._namespace_owners[key] = identity
        self.peerroutes[identity].append(compiled)
        self.registeredroutes.insert(
            0, AgentRoute(compiled, 'peer_route', (identity, fn), identity, namespace))

    @RPC.export
    def unregister_all_agent_routes(self):
        identity = self._caller('unregister_all_agent_routes', None)

        _log.info('Unregistering agent routes for: {}'.format(identity))
        # By owner, never by pattern: re.compile hands back one cached object
        # for equal pattern strings, including those of platform routes.
        self.registeredroutes = [entry for entry in self.registeredroutes
                                 if getattr(entry, 'owner', None) != identity]
        self.peerroutes.pop(identity, None)
        self.pathroutes.pop(identity, None)
        if self.appContainer:
            self.appContainer.destroy_owner_endpoints(identity)

        _log.debug(self.endpoints)
        endpoints = self.endpoints.copy()
        endpoints = {i:endpoints[i] for i in endpoints if endpoints[i][0] != identity}
        _log.debug(endpoints)
        self.endpoints = endpoints
        self._namespace_owners = {ns: owner for ns, owner in self._namespace_owners.items()
                                  if owner != identity}

    @RPC.export
    @RPC.allow(capabilities=REGISTER_WEB_ROUTES)
    def register_path_route(self, regex, root_dir):
        identity = self._caller('register_path_route', regex)
        namespace = _pattern_namespace(regex)
        key = self._check_namespace('register_path_route', identity, regex, namespace)

        _log.info(f'Registering web path route from {identity} regex: {regex} dir: {root_dir}')

        compiled = re.compile(regex)
        if not isinstance(root_dir, str) or not os.path.isabs(root_dir):
            self._refuse('register_path_route', identity, root_dir,
                         'the root must be an absolute path')
        resolved = os.path.realpath(root_dir)
        if not os.path.isdir(resolved):
            self._refuse('register_path_route', identity, root_dir, 'the root is not a directory')
        reason = root_refusal(resolved, identity, get_home(), self._static_roots)
        if reason:
            self._refuse('register_path_route', identity, root_dir, reason)
        # Stored resolved and never re-resolved when serving.
        root_dir = resolved
        self._namespace_owners[key] = identity
        self.pathroutes[identity].append(compiled)
        # in order for this agent to pass against the default route we want this
        # to be before the last route which will resolve to .*
        self.registeredroutes.insert(len(self.registeredroutes) - 1,
                                     AgentRoute(compiled, 'path', root_dir, identity, namespace))

    @RPC.export
    @RPC.allow(capabilities=REGISTER_WEB_ROUTES)
    def register_websocket(self, endpoint):
        identity = self._caller('register_websocket', endpoint)
        namespace = self._check_namespace('register_websocket', identity, endpoint,
                                          _path_namespace(endpoint))

        _log.debug('Caller identity: {}'.format(identity))
        _log.debug('REGISTERING ENDPOINT: {}'.format(endpoint))
        if self.appContainer:
            try:
                self.appContainer.create_ws_endpoint(endpoint, identity)
            except PermissionError:
                self._refuse('register_websocket', identity, endpoint,
                             'the websocket belongs to another agent')
            self._namespace_owners[namespace] = identity
        else:
            _log.error('Attempting to register endpoint without web'
                       'subsystem initialized')
            raise AttributeError("self does not contain"
                                 " attribute appContainer")

    @RPC.export
    def unregister_websocket(self, endpoint):
        identity = self._caller('unregister_websocket', endpoint)

        _log.debug('Caller identity: {}'.format(identity))
        if self.appContainer is None:
            _log.info('web server is not running; no websocket to remove at %r', endpoint)
            return
        try:
            self.appContainer.destroy_ws_endpoint(endpoint, identity)
        except PermissionError:
            self._refuse('unregister_websocket', identity, endpoint,
                         'the websocket belongs to another agent')

    def _caller(self, action, path):
        """Return the identity of the agent calling an export.

        Callbacks go to the peer, so with authentication enabled the
        authenticated user must be that same agent.
        """
        message = self.vip.rpc.context.vip_message
        peer = message.peer
        if self.core.enable_auth is not False and str(message.user) != str(peer):
            self._refuse(action, f'{message.user} as {peer}', path,
                         'the authenticated user is not the calling agent')
        return peer

    def _check_namespace(self, action, identity, path, namespace):
        """Refuse a namespace the caller may not register in, before any table
        changes; return the key its owner is recorded under."""
        if self._reserved_namespaces is None:
            self._refuse(action, identity, path, 'the platform routes are not ready')
        if namespace is None or namespace in ('.', '..'):
            self._refuse(action, identity, path,
                         'the path must start with a literal first segment')
        key = namespace.casefold()
        probes = {f'/{name}{end}' for name in (namespace, key) for end in ('', '/')}
        if key in self._reserved_namespaces or any(
                pattern.match(probe) for pattern in self._builtin_patterns for probe in probes):
            self._refuse(action, identity, path, 'the first segment is used by the platform')
        holder = IDENTITY_NAMESPACES.get(key, self._namespace_owners.get(key))
        if holder is not None and holder != identity:
            self._refuse(action, identity, path, 'the first segment belongs to another agent')
        return key

    @staticmethod
    def _refuse(action, identity, path, rule):
        from volttron.platform.web import printable_text
        _log.warning('%s refused for %r at %r: %s', action, identity, printable_text(path), rule)
        raise PermissionError(f'{rule}: {path!r}')

    def _redirect_index(self, env, start_response, data=None):
        """ Redirect to the index page.
        @param env:
        @param start_response:
        @param data:
        @return:
        """
        start_response('302 Found', [('Location', '/index.html')])
        return [b'1']

    def _require_admin(self, environ):
        """Resolve the caller's claims and confirm admin-group membership.

        Returns the decoded claims dict when the caller presents a valid JWT
        whose ``groups`` claim contains ``admin``. Returns an HTTP status
        string (``'401 Unauthorized'`` / ``'403 Forbidden'``) when the caller
        must be rejected. Fail-closed: a missing/invalid token, an
        indeterminate claims set, or a missing ``groups`` claim all deny.
        The token is read from the Authorization header only, never the
        cookie, which a browser sends on requests other sites make.
        """
        from volttron.platform.web import get_authorization_bearer, NotAuthorized
        bearer = get_authorization_bearer(environ)
        if not bearer:
            return '401 Unauthorized'
        try:
            claims = self.get_user_claims(bearer)
        except NotAuthorized:
            return '401 Unauthorized'
        except jwt.ExpiredSignatureError:
            return '401 Unauthorized'
        except Exception:
            # Fail closed on indeterminate auth: any failure to resolve claims
            # is a denial, never an open door.
            _log.error("Failed to resolve claims for allow-list request.")
            return '401 Unauthorized'
        if not isinstance(claims, dict):
            return '403 Forbidden'
        if 'admin' not in (claims.get('groups') or []):
            return '403 Forbidden'
        return claims

    def _unauthorized(self, environ, start_response, status, request_id='NA'):
        start_response(status,
                       [('Content-Type', 'application/json')])
        return [jsonapi.dumpb(
            jsonrpc.json_error(request_id, UNAUTHORIZED, status))]

    def _allow(self, environ, start_response, data=None):
        _log.info('Allowing new vc instance to connect to server.')
        # GHSA-j9rp-3mvh-v57x (VO-001): the allow-list mutates platform trust
        # state (adds a CURVE key under the VOLTTRON_CENTRAL identity), so the
        # caller must prove admin authorization BEFORE any auth-file write.
        gate = self._require_admin(environ)
        if isinstance(gate, str):
            return self._unauthorized(environ, start_response, gate)
        from volttron.platform.web import get_media_type
        if get_media_type(environ) != 'application/json':
            return self._unauthorized(environ, start_response, '415 Unsupported Media Type')
        # app_routing has already decoded a JSON body.
        jsondata = data if isinstance(data, dict) else jsonapi.loads(data)
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

        authentry = {"credentials": vcpublickey, "identity": VOLTTRON_CENTRAL}
        try:
            self.vip.rpc.call(AUTH, "auth_file.add", authentry).get()
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
        elif external_vip:
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
        if 'HTTP_COOKIE' in passenv:
            passenv['HTTP_COOKIE'] = _without_login_cookie(passenv['HTTP_COOKIE'])
            if not passenv['HTTP_COOKIE']:
                del passenv['HTTP_COOKIE']

        from volttron.platform.web import printable_text
        _log.debug('path_info is: {}'.format(printable_text(path_info)))
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
            # Not the env or body: they carry the Authorization header, cookie and form data.
            _log.debug('Calling peer {} back for {}'.format(peer, printable_text(path_info)))
            res = self.vip.rpc.call(peer, 'route.callback',
                                    passenv, data).get(timeout=60)

            if res_type == "jsonrpc":
                return self.create_response(res, start_response)
            elif res_type == "raw":
                return self.create_raw_response(res, start_response)

        env['JINJA2_TEMPLATE_ENV'] = tplenv

        # if ws4pi.socket is set then this connection is a web socket
        # and so we return the websocket response.

        if 'ws4py.socket' in env and 'vui' not in path_info:
            return env['ws4py.socket'](env, start_response)

        first_segment = _first_segment(path_info)
        for entry in self.registeredroutes:
            k, t, v = entry
            namespace = getattr(entry, 'namespace', None)
            if namespace is not None and namespace != first_segment:
                continue
            if k.match(path_info):
                _log.debug("MATCHED: pattern: {}, path_info: {}, v: {}"
                           .format(k.pattern, printable_text(path_info), v))
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
                        #_log.debug(f'VUI:  Response at app_routing is: {response.response}')
                        return response(env, start_response)
                        # retvalue = self.process_response(start_response, v(env, data))

                    if isinstance(retvalue, werkzeug.Response):
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
                    server_path = file_to_serve(v, path_info)
                    _log.debug('Serverpath: {}'.format(printable_text(str(server_path))))
                    if server_path is None:
                        start_response('403 Forbidden', [('Content-Type', 'text/html')])
                        return [b'<h1>403 Forbidden</h1>']
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
        # response = PlatformWebService.convert_response_to_werkzueg(response)
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
        from volttron.platform.web import printable_text
        _log.debug('SENDING FILE: {}'.format(printable_text(filename)))
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

    def register_gs_route(self):
        self.registeredroutes.append((GS_ROUTE, 'callable', self.jsonrpc))

    def jsonrpc(self, env, data):
        """ Handle a JSON-RPC 2.0 request to /gs.

        The request ``id`` names the target identity and ``method`` the call;
        the admin token travels in ``params.authentication``. Only POST from
        an admin, for a pair in GS_ALLOWED_CALLS, reaches the bus.

        The (env, data) signature matters: app_routing retries a callable with
        these two arguments after a TypeError, and a handler taking three
        would run twice.

        :param object env: Environment dictionary for the request.
        :param object data: The request body, as a str or decoded JSON.
        :return object: A JSON-RPC 2.0 response.
        """
        if env['REQUEST_METHOD'].upper() != 'POST':
            return self._gs_refuse(None, 405, INVALID_REQUEST, 'only POST is allowed', 'method')

        request = self._gs_parse(data)
        if request is None:
            ident = data.get('id') if isinstance(data, dict) else None
            return self._gs_refuse(ident if isinstance(ident, str) else None, 400,
                                   INVALID_REQUEST, 'invalid request', 'malformed')
        ident, method, params = request

        token = params.pop('authentication', None)
        if not isinstance(token, str) or not token:
            return self._gs_refuse(ident, 401, UNAUTHORIZED, 'not authorized', 'no token')
        try:
            claims = self.get_user_claims(token)
        except Exception as e:
            # Fail closed: any failure to resolve the token denies the call.
            _log.error('/gs could not resolve claims: %s', type(e).__name__)
            return self._gs_refuse(ident, 401, UNAUTHORIZED, 'not authorized', 'bad token')

        from volttron.platform.web import get_claim_groups
        groups = get_claim_groups(claims)
        if groups is None or 'admin' not in groups:
            return self._gs_refuse(ident, 403, UNAUTHORIZED, 'forbidden', 'not admin')

        allowed_params = GS_ALLOWED_CALLS.get((ident, method))
        if allowed_params is None:
            return self._gs_refuse(ident, 403, UNAUTHORIZED, 'forbidden', 'call not allowed',
                                   method)
        if not set(params) <= allowed_params:
            return self._gs_refuse(ident, 403, UNAUTHORIZED, 'forbidden', 'params not allowed',
                                   method)

        from volttron.platform.web import describe_call_error
        try:
            pending = self.vip.rpc.call(ident, method, **params)
            # wait() rather than get(timeout=...): catching gevent.Timeout here
            # would also swallow a timeout set by an enclosing greenlet.
            pending.wait(GS_CALL_TIMEOUT)
            if not pending.ready():
                return self._gs_refuse(ident, 504, INTERNAL_ERROR, 'timed out', 'timeout', method)
            result = pending.get(block=False)
        except Unreachable:
            return self._gs_refuse(ident, 502, UNAVAILABLE_AGENT, 'agent unavailable',
                                   'unreachable', method)
        except Exception as e:
            _log.error('/gs call %r %r failed: %s', ident, method, describe_call_error(e))
            return self._gs_refuse(ident, 500, INTERNAL_ERROR, 'call failed', 'failed', method)

        _log.info('/gs call %r %r allowed', ident, method)
        return Response(jsonapi.dumps(jsonrpc.json_result(ident, result)), 200,
                        content_type='application/json')

    @staticmethod
    def _gs_parse(data):
        """Return (id, method, params) for a well-formed request, else None."""
        if isinstance(data, (str, bytes)):
            try:
                data = jsonapi.loads(data)
            except ValueError:
                return None
        if not isinstance(data, dict) or data.get('jsonrpc') != '2.0':
            return None
        ident, method, params = data.get('id'), data.get('method'), data.get('params', {})
        if params is None:
            params = {}
        if not isinstance(ident, str) or not isinstance(method, str) or not isinstance(params, dict):
            return None
        if not all(isinstance(k, str) for k in params):
            return None
        return ident, method, dict(params)

    @staticmethod
    def _gs_refuse(ident, status, code, message, reason, method=None):
        # Fixed messages only: never the body, params, token or exception text.
        if method is None:
            _log.info('/gs request refused: %s', reason)
        else:
            _log.info('/gs call %r %r refused: %s', ident, method, reason)
        return Response(jsonapi.dumps(jsonrpc.json_error(ident, code, message)), status,
                        content_type='application/json')

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
                # Because the  platform.web service certificate is a client to rabbitmq we
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
        self.register_gs_route()
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

        # Register VUI endpoints:
        self._vui_endpoints = VUIEndpoints(self)
        #_log.debug(f'VUI: adding routes - {self._vui_endpoints.get_routes()}')
        self.registeredroutes.extend(self._vui_endpoints.get_routes())

        # Allow authentication endpoint from any https connection
        if parsed.scheme == 'https':
            if self.core.messagebus == 'rmq':
                ssl_private_key = self._certs.get_pk_bytes(get_fq_identity(self.core.identity))
                ssl_public_key = self._certs.get_cert_public_key(get_fq_identity(self.core.identity))
            else:
                ssl_private_key = CertWrapper.get_private_key(ssl_key)
                ssl_public_key = CertWrapper.get_cert_public_key(self.web_ssl_cert)
            for rt in AuthenticateEndpoints(tls_private_key=ssl_private_key, tls_public_key=ssl_public_key).get_routes():
                self.registeredroutes.append(rt)
        else:
            # We don't have a private ssl key if we aren't using ssl.
            for rt in AuthenticateEndpoints(web_secret_key=self._web_secret_key).get_routes():
                self.registeredroutes.append(rt)

        static_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "static"))
        self._builtin_patterns = tuple(pattern for pattern, _, _ in self.registeredroutes)
        try:
            builtin = builtin_namespaces(self._builtin_patterns)
        except ValueError as err:
            _log.error('web server not started: %s', err)
            raise
        self._reserved_namespaces = frozenset(
            builtin
            | {name.casefold() for name in os.listdir(static_dir)}
            | {'favicon.ico'} | ALWAYS_RESERVED_NAMESPACES)
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
        if self._server_greenlet is None:
            _log.info('web server is not running; nothing to stop')
            return
        if not self._server_greenlet.dead:
            self._server_greenlet.join(timeout=10)
