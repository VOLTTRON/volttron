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

"""
.. _volttroncentral-agent:

The VolttronCentral(VCA) agent is used to manage remote VOLTTRON instances.
The VCA exposes a JSON-RPC based web api and a web enabled visualization
framework.  The web enabled framework is known as VOLTTRON
Central Management Console (VCMC).

In order for an instance to be able to be managed by VCMC a
:class:`vcplatform.agent.VolttronCentralPlatform` must be executing on the
instance.  If there is a :class:`vcplatform.agent.VolttronCentralPlatform`
running on the same instance as VCA it will be automatically registered as a
managed instance.  Otherwise, there are two different paths to registering an
instance with VCA.

1. Through the web api a call to the JSON-RPC method register_instance.
2. From an external platform through pub/sub.  this secondary method is
   preferred when deploying instances in the field that need to "phone home"
   to VCA after being deployed.

"""

import datetime
import logging
import math
import os
import os.path as p
import sys
from collections import namedtuple
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlparse

import gevent

from volttron.platform import jsonapi
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, PLATFORM_HISTORIAN, PLATFORM_WEB, AUTH)
from volttron.platform.agent.utils import (
    get_aware_utc_now, get_messagebus)
from volttron.platform.jsonrpc import (
    INVALID_REQUEST, METHOD_NOT_FOUND,
    UNHANDLED_EXCEPTION, UNAUTHORIZED,
    UNAVAILABLE_PLATFORM, INVALID_PARAMS,
    UNAVAILABLE_AGENT, INTERNAL_ERROR, RemoteError)
from volttron.platform.vip.agent import Agent, RPC, Unreachable
from .platforms import Platforms, PlatformHandler
from .sessions import SessionHandler

# must be after importing of utils which imports grequest.
import grequests

__version__ = "5.2"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))

SESSION_COOKIE = 'vcsession'
WS_PREFIX = '/vc/ws/'
LOGIN_CHECK_TIMEOUT = 10

# Largest accepted agent upload, before base64 encoding.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_ENCODED_UPLOAD = 4 * math.ceil(MAX_UPLOAD_BYTES / 3)

ANY_USER = 'user'
ADMIN = 'admin'

# Every JSON-RPC method VC accepts, with the group it needs. A name that is
# not here, exactly, is refused. Config reads and writes are admin only
# because config files hold historian credentials.
VC_METHODS = {
    'register_management_endpoint': ANY_USER,
    'list_platforms': ANY_USER,
    'list_performance': ANY_USER,
    'get_setting': ANY_USER,
    'get_setting_keys': ANY_USER,
    'set_setting': ADMIN,
    'enable_setup_mode': ADMIN,
    'disable_setup_mode': ADMIN,
}
HISTORIAN_METHODS = {
    'historian.query': ANY_USER,
    'historian.get_topic_list': ANY_USER,
}
# Methods VC runs on behalf of a platform. They are accepted bare, with the
# platform in the params, or as platforms.uuid.<uuid>.<method>.
PLATFORM_METHODS = {
    'list_agents': ANY_USER,
    'status_agents': ANY_USER,
    'get_devices': ANY_USER,
    'store_agent_config': ADMIN,
    'get_agent_config': ADMIN,
    'delete_agent_config': ADMIN,
    'list_agent_configs': ADMIN,
    'start_bacnet_scan': ADMIN,
    'publish_bacnet_props': ADMIN,
}
# Methods only the platforms.uuid.<uuid>.<method> form accepts; the managed
# platform's agent runs them.
PLATFORM_ONLY_METHODS = {
    'agent_status': ANY_USER,
    'start_agent': ADMIN,
    'stop_agent': ADMIN,
    'restart_agent': ADMIN,
    'remove_agent': ADMIN,
    'install': ADMIN,
}

Platform = namedtuple('Platform', ['instance_name', 'serverkey', 'vip_address'])
RequiredArgs = namedtuple('RequiredArgs', ['id', 'session_user',
                                           'platform_uuid'])


def _parse_method(method):
    """Map a JSON-RPC method name to (platform_uuid, name, required group).

    The name must be exactly one of the tables' entries, or exactly four
    dot-separated segments platforms.uuid.<uuid>.<method>. Returns None for
    anything else.
    """
    if not isinstance(method, str):
        return None
    for table in (VC_METHODS, HISTORIAN_METHODS, PLATFORM_METHODS):
        if method in table:
            return None, method, table[method]
    parts = method.split('.')
    if len(parts) == 4 and parts[0] == 'platforms' and parts[1] == 'uuid' \
            and parts[2]:
        for table in (PLATFORM_METHODS, PLATFORM_ONLY_METHODS):
            if parts[3] in table:
                return parts[2], parts[3], table[parts[3]]
    return None


def _session_cookie(cookie_header):
    if not isinstance(cookie_header, str):
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except CookieError:
        return None
    morsel = jar.get(SESSION_COOKIE)
    return morsel.value if morsel else None


def _ws_channel(path):
    """The channel id of /vc/ws/<channel>/<name>, or None."""
    if not isinstance(path, str) or not path.startswith(WS_PREFIX):
        return None
    parts = path[len(WS_PREFIX):].split('/')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0]


def _origin_allowed(request):
    """An Origin header, when sent, must name this request's own host.

    A browser sends the session cookie on a websocket opened by any site, so
    the page that opens it has to come from this host. 'null' and anything
    unparsable are refused.
    """
    if 'HTTP_ORIGIN' not in request:
        return True
    origin, host = request['HTTP_ORIGIN'], request.get('HTTP_HOST')
    if not isinstance(origin, str) or not isinstance(host, str) or not host:
        return False
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return (parsed.scheme in ('http', 'https')
            and parsed.netloc.lower() == host.lower())


def init_volttron_central(config_path, **kwargs):
    # Load the configuration into a dictionary
    config = utils.load_config(config_path)

    # Kept for backward compatibility with existing config files; no longer
    # used for login (see VolttronCentralAgent._configure).
    users = config.get('users', None)

    # Expose the webroot property to be customized through the config
    # file.
    webroot = config.get('webroot', DEFAULT_WEB_ROOT)
    if webroot.endswith('/'):
        webroot = webroot[:-1]

    topic_replace_list = config.get('topic-replace-list', [])

    return VolttronCentralAgent(webroot, users, topic_replace_list, **kwargs)


class VolttronCentralAgent(Agent):
    """ Agent for managing many volttron instances from a central web ui.

    During the


    """

    def __init__(self, webroot=DEFAULT_WEB_ROOT, users={},
                 topic_replace_list=[], **kwargs):
        """ Creates a `VolttronCentralAgent` object to manage instances.

         Each instances that is registered must contain a running
         `VolttronCentralPlatform`.  Through this conduit the
         `VolttronCentralAgent` is able to communicate securly and
         efficiently.

        :param config_path:
        :param kwargs:
        :return:
        """
        _log.info("{} constructing...".format(self.__class__.__name__))

        super(VolttronCentralAgent, self).__init__(enable_web=True, **kwargs)

        # Create default configuration to be used in case of problems in the
        # packaged agent configuration file.
        self._default_config = dict(
            webroot=os.path.abspath(webroot),
            users=users,
            topic_replace_list=topic_replace_list
        )

        self.vip.config.set_default("config", self._default_config)

        # Start using config store.
        self.vip.config.subscribe(self._configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")



        #
        # # During the configuration update/new/delete action this will be
        # # updated to the current configuration.
        # self.runtime_config = None
        #
        # # Start using config store.
        # self.vip.config.set_default("config", config)
        # self.vip.config.subscribe(self.configure_main,
        #                           actions=['NEW', 'UPDATE', 'DELETE'],
        #                           pattern="config")
        #
        # # Use config store to update the settings of a platform's configuration.
        # self.vip.config.subscribe(self.configure_platforms,
        #                           actions=['NEW', 'UPDATE', 'DELETE'],
        #                           pattern="platforms/*")
        #
        # # mapping from the real topic into the replacement.
        # self.replaced_topic_map = {}
        #
        # # mapping from md5 hash of address to the actual connection to the
        # # remote instance.
        # self.vcp_connections = {}
        #
        # # Current sessions available to the
        # self.web_sessions = None
        #
        # # Platform health based upon device driver publishes
        # self.device_health = defaultdict(dict)
        #
        # # Used to hold scheduled reconnection event for vcp agents.
        # self._vcp_reconnect_event = None
        #
        # # the registered socket endpoints so we can send out management
        # # events to all the registered session.
        self._websocket_endpoints = set()

        self._platforms = Platforms(self)

        self._platform_scan_event = None
        self._platform_scan_running = False
        self._platform_scan_skip_logged = False

        # Sessions that have been authentication with the system.
        self._authenticated_sessions = None

        # channel id -> websocket paths registered for that session.
        self._session_ws_paths = {}

    def _configure(self, config_name, action, contents):
        """
        The main configuration for volttron central.  This is where validation
        will occur.

        Note this method is called:

            1. When the agent first starts (with the params from packaged agent
               file)
            2. When 'store' is called through the volttron-ctl config command
               line with 'config' as the name.

        VolttronCentral users are managed through the platform web user
        store; no local user mapping is required.

        :param config_name:
        :param action:
        :param contents:
        """
        config = self._default_config.copy()

        config.update(contents)

        users = config.get("users", None)

        if self._authenticated_sessions:
            self._authenticated_sessions.clear()

        # The local-user "users" config key predates platform login: VC
        # users come from the platform web user store now. Accept the key
        # for compatibility and only warn; never log its contents.
        if users:
            if isinstance(users, dict):
                _log.warning(
                    "VolttronCentral config 'users' key is no longer used "
                    "for login; %d user(s) ignored. VolttronCentral users "
                    "are managed through the platform web user store.",
                    len(users))
            else:
                _log.warning(
                    "VolttronCentral config 'users' key is no longer used "
                    "for login; ignored. VolttronCentral users are "
                    "managed through the platform web user store.")

        # Unregister all routes for vc and then re-add down below.
        self.vip.web.unregister_all_routes()

        self._session_ws_paths = {}
        self._authenticated_sessions = SessionHandler(
            on_end=self._session_ended)

        self.vip.web.register_endpoint(r'/vc/jsonrpc', self.jsonrpc)

        self.vip.web.register_path(r'^/vc/.*',
                                   config.get('webroot'))

        # Start scanning for new platforms connections as well as for
        # disconnects that happen.
        gevent.spawn_later(1, self._scan_platform_connect_disconnect)

    @staticmethod
    def _get_next_time_seconds(seconds=10):
        now = get_aware_utc_now()
        next_time = now + datetime.timedelta(seconds=seconds)
        return next_time

    def _handle_platform_connection(self, platform_vip_identity):
        _log.info("Handling new platform connection {}".format(
            platform_vip_identity))

        platform = self._platforms.add_platform(platform_vip_identity)

    def _handle_platform_disconnect(self, platform_vip_identity):
        _log.warning("Handling disconnection of connection from identity: {}".format(
            platform_vip_identity
        ))
        # TODO send alert that there was a platform disconnect.
        self._platforms.disconnect_platform(platform_vip_identity)

    def _scan_platform_connect_disconnect(self):
        """
        Scan the local bus for peers that start with 'vcp-'.  Handle the
        connection and disconnection events here.
        """
        if self._platform_scan_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._platform_scan_event.cancel()

        # Schedule first so no error below can end the sweep for good.
        self._platform_scan_event = self.core.schedule(
            VolttronCentralAgent._get_next_time_seconds(),
            self._scan_platform_connect_disconnect)

        try:
            if self._authenticated_sessions is not None:
                self._authenticated_sessions.expire()
        except Exception:
            _log.exception("Expiring sessions failed")

        # A platform connect can block longer than the sweep interval; a
        # second scan would see the same platform as new and connect it twice.
        if self._platform_scan_running:
            if not self._platform_scan_skip_logged:
                self._platform_scan_skip_logged = True
                _log.warning("Previous platform scan still running; "
                             "skipping until it finishes")
            return

        self._platform_scan_running = True
        self._platform_scan_skip_logged = False
        try:
            self._scan_platforms()
        except (Exception, gevent.Timeout):
            _log.exception("Scanning for platform connections failed")
        finally:
            self._platform_scan_running = False

    def _scan_platforms(self):
        # Identities of all platform agents that are connecting to us should
        # have an identity of platform.md5hash.
        connected_platforms = set([x for x in self.vip.peerlist().get(timeout=5)
                                   if x.startswith('vcp-') or x.endswith('.platform.agent')])

        _log.debug("Connected: {}".format(connected_platforms))
        disconnected = self._platforms.get_platform_vip_identities() - connected_platforms

        for vip_id in disconnected:
            self._handle_platform_disconnect(vip_id)

        not_known = connected_platforms - self._platforms.get_platform_vip_identities()
        for vip_id in not_known:
            self._handle_platform_connection(vip_id)

    def configure_platforms(self, config_name, action, contents):
        _log.debug('Platform configuration updated.')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))

    def open_authenticate_ws_endpoint(self, fromip, endpoint):
        """
        Callback from when a websocket is opened, after the upgrade. It is a
        second check behind `_authorize_ws`: the endpoint's channel id must
        belong to a live session opened from the same ip address.

        :param fromip:
        :param endpoint:
            A string representing the endpoint of the websocket.
        :return:
        """
        _log.debug("OPENED ip: {} endpoint: {}".format(fromip, endpoint))
        channel = _ws_channel(endpoint)
        if channel is None:
            _log.error("Malformed websocket endpoint.")
            return False

        if not self._authenticated_sessions.check_channel(channel, fromip):
            _log.error("Authentication error for session!")
            return False

        _log.debug('Websocket allowed.')
        self._websocket_endpoints.add(endpoint)

        return True

    def _authorize_ws(self, request):
        """
        Called by the platform before a websocket is upgraded. The request is
        a dict of REMOTE_ADDR, PATH_INFO, HTTP_HOST, HTTP_ORIGIN and
        HTTP_COOKIE. Only True lets the upgrade through: the origin must be
        this host's, the session cookie must name a live session opened from
        the request's ip address, and the path's channel must be that
        session's channel.
        """
        if not isinstance(request, dict) or not _origin_allowed(request):
            return False
        channel = _ws_channel(request.get('PATH_INFO'))
        session_id = _session_cookie(request.get('HTTP_COOKIE'))
        if channel is None or session_id is None:
            return False
        session = self._authenticated_sessions.check_session(
            session_id, request.get('REMOTE_ADDR'), channel=channel)
        return bool(session)

    def _register_session_ws(self, channel, name, received):
        """Register /vc/ws/<channel>/<name>; the only place VC registers a
        websocket, so every one carries the same callbacks and is closed with
        its session."""
        path = "{}{}/{}".format(WS_PREFIX, channel, name)
        self.vip.web.register_websocket(
            path,
            opened=self.open_authenticate_ws_endpoint,
            closed=self._ws_closed,
            received=received,
            authorize=self._authorize_ws)
        self._session_ws_paths.setdefault(channel, set()).add(path)
        return path

    def _unregister_session_ws(self, channel, path):
        paths = self._session_ws_paths.get(channel)
        if paths is not None:
            paths.discard(path)
            if not paths:
                del self._session_ws_paths[channel]
        try:
            self.vip.web.unregister_websocket(path)
        except (RemoteError, Unreachable, gevent.Timeout) as err:
            _log.error("Could not unregister websocket %s: %s", path, err)

    def _session_ended(self, channel):
        """Close the routes and sockets of a session that expired or was
        replaced."""
        paths = self._session_ws_paths.pop(channel, set())
        # The platform closes these sockets without telling VC, so VC must
        # stop sending to them here.
        self._websocket_endpoints.difference_update(paths)
        for path in paths:
            gevent.spawn(self._unregister_session_ws, channel, path)

    def _ws_closed(self, endpoint):
        _log.debug("CLOSED endpoint: {}".format(endpoint))
        try:
            self._websocket_endpoints.remove(endpoint)
        except KeyError:
            pass # This should never happen but protect against it anyways.

    def _ws_received(self, endpoint, message):
        _log.debug("RECEIVED endpoint: {} message: {}".format(endpoint,
                                                              message))

    @RPC.export
    def is_registered(self, address_hash=None, address=None):
        if address_hash is None and address is None:
            return False

        if address_hash is None:
            address_hash = PlatformHandler.address_hasher(address)

        return self._platforms.is_registered(address_hash)

    @RPC.export
    def get_publickey(self):
        """
        RPC method allowing the caller to retrieve the publickey of this agent.

        This method is available for allowing :class:`VolttronCentralPlatform`
        agents to allow this agent to be able to connect to its instance.

        :return: The publickey of this volttron central agent.
        :rtype: str
        """
        return self.core.publickey

    def _to_jsonrpc_obj(self, jsonrpcstr):
        """ Convert data string into a JsonRpcData named tuple.

        :param object data: Either a string or a dictionary representing a json document.
        """
        return jsonrpc.JsonRpcData.parse(jsonrpcstr)

    def jsonrpc(self, env: dict, data: dict):
        """ The main entry point for ^jsonrpc data

        This method will only accept rpcdata.  The first time this method
        is called, per session, it must be using get_authorization.  That
        sets the vcsession cookie and returns a channel id; every
        subsequent request must carry both, as the cookie and as the
        authorization field.  The session is tied to the ip address
        of the caller.

        :param object env: Environment dictionary for the request.
        :param object data: The JSON-RPC 2.0 method to call.
        :return object: An JSON-RPC 2.0 response.
        """
        if env['REQUEST_METHOD'].upper() != 'POST':
            return jsonrpc.json_error('NA', INVALID_REQUEST,
                                      'Invalid request method, only POST allowed')

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))

            if rpcdata.method == 'get_authorization':
                return self._login(env, rpcdata)

            ip = env['REMOTE_ADDR']
            _log.debug('REMOTE_ADDR: {}'.format(ip))
            session_id = _session_cookie(env.get('HTTP_COOKIE'))
            session_user = self._authenticated_sessions.check_session(
                session_id, ip, channel=rpcdata.authorization)
            if not session_user:
                return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                          "Invalid authentication token")
            _log.debug('SESSION_USER IS: {}'.format(session_user['user']))
            _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))

            # Route any other method that isn't
            result_or_error = self._route_request(session_user,
                                                  rpcdata.id, rpcdata.method,
                                                  rpcdata.params)

        except AssertionError:
            return jsonrpc.json_error(
                'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data))
        except Unreachable:
            return jsonrpc.json_error(
                rpcdata.id, UNAVAILABLE_PLATFORM,
                "Couldn't reach platform with method {} params: {}".format(
                    rpcdata.method,
                    rpcdata.params))
        except Exception as e:
            _log.error(f"Unhandled exception: {e}")
            return jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, str(e)
            )

        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

    def _authenticate_web_user(self, username, password):
        """Ask the platform web service to check a login.

        :return: (user, groups) for a valid login, otherwise None.
        """
        try:
            answer = self.vip.rpc.call(
                PLATFORM_WEB, 'authenticate_web_user', username,
                password).get(timeout=LOGIN_CHECK_TIMEOUT)
        except (RemoteError, Unreachable, gevent.Timeout) as err:
            _log.error("Web login check failed: %s", type(err).__name__)
            return None
        if not isinstance(answer, dict):
            return None
        user, groups = answer.get('user'), answer.get('groups')
        if not isinstance(user, str) or not user or \
                not isinstance(groups, list) or \
                not all(isinstance(group, str) for group in groups):
            return None
        return user, list(groups)

    def _login(self, env, rpcdata):
        """Handle get_authorization.

        The platform checks the credentials and VC never sees a platform
        token. The session id goes to the browser as a cookie; the channel id
        is the JSON-RPC result.
        """
        params = rpcdata.params
        username = params.get('username') if isinstance(params, dict) else None
        password = params.get('password') if isinstance(params, dict) else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonrpc.json_error(
                rpcdata.id, INVALID_PARAMS,
                "username and password must be strings")

        login = self._authenticate_web_user(username, password)
        if login is None:
            _log.info('Invalid username/password for {}'.format(username))
            return jsonrpc.json_error(
                rpcdata.id, UNAUTHORIZED,
                "Invalid username/password specified.")

        user, groups = login
        session_id, channel = self._authenticated_sessions._add_session(
            user=user, ip=env['REMOTE_ADDR'], groups=groups)
        _log.info('Session created for {}'.format(user))
        self._register_session_ws(channel, 'management', self._received_data)

        cookie = '{}={}; HttpOnly; SameSite=Strict; Path=/vc'.format(
            SESSION_COOKIE, session_id)
        if env.get('wsgi.url_scheme') == 'https':
            cookie += '; Secure'

        gevent.sleep(1)
        return ['200 OK',
                jsonapi.dumps(jsonrpc.json_result(rpcdata.id, channel)),
                [('Content-Type', 'application/json'),
                 ('Set-Cookie', cookie)]]

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

    def _get_agents(self, instance_uuid, groups):
        """ Retrieve the list of agents on a specific platform.

        :param instance_uuid:
        :param groups:
        :return:
        """
        _log.debug('_get_agents with groups: {}'.format(groups))
        connected_to_pa = self._platform_connections[instance_uuid]

        agents = connected_to_pa.agent.vip.rpc.call(
            'platform.agent', 'list_agents').get(timeout=30)

        for a in agents:
            if 'admin' in groups:
                if "platformagent" in a['name'] or \
                                "volttroncentral" in a['name']:
                    a['vc_can_start'] = False
                    a['vc_can_stop'] = False
                    a['vc_can_restart'] = True
                else:
                    a['vc_can_start'] = True
                    a['vc_can_stop'] = True
                    a['vc_can_restart'] = True
            else:
                # Handle the permissions that are not admin.
                a['vc_can_start'] = False
                a['vc_can_stop'] = False
                a['vc_can_restart'] = False

        _log.debug('Agents returned: {}'.format(agents))
        return agents

    def _setupexternal(self):
        _log.debug(self.vip.ping('', "PING ROUTER?").get(timeout=3))

    def _configure_agent(self, endpoint, message):
        _log.debug('Configure agent: {} message: {}'.format(endpoint, message))

    def _received_data(self, endpoint, message):
        print('Received from endpoint {} message: {}'.format(endpoint, message))
        self.vip.web.send(endpoint, message)

    def set_setting(self, session_user, params):
        """
        Sets or removes a setting from the config store.  If the value is None
        then the item will be removed from the store.  If there is an error in
        saving the value then a jsonrpc.json_error object is returned.

        :param session_user: Unused
        :param params: Dictionary that must contain 'key' and 'value' keys.
        :return: A 'SUCCESS' string or a jsonrpc.json_error object.
        """
        if 'key' not in params or not params['key']:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid parameter key not set')
        if 'value' not in params:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid parameter key not set')

        config_key = "settings/{}".format(params['key'])
        value = params['value']

        if value is None:
            try:
                self.vip.config.delete(config_key)
            except KeyError:
                pass
        else:
            # We handle empt string here because the config store doesn't allow
            # empty strings to be set as a config store.  I wasn't able to
            # trap the ValueError that is raised on the server side.
            if value == "":
                return jsonrpc.json_error(params['message_id'],
                                          INVALID_PARAMS,
                                          'Invalid value set (empty string?)')
            self.vip.config.set(config_key, value)

        return 'SUCCESS'

    def get_setting(self, session_user, params):
        """
        Retrieve a value from the passed setting key.  The params object must
        contain a "key" to return from the settings store.

        :param session_user: Unused
        :param params: Dictionary that must contain a 'key' key.
        :return: The value or a jsonrpc error object.
        """
        config_key = "settings/{}".format(params['key'])
        try:
            value = self.vip.config.get(config_key)
        except KeyError:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid key specified')
        else:
            return value

    def get_setting_keys(self, session_user, params):
        """
        Returns a list of all of the settings keys so the caller can know
        what settings to request.

        :param session_user: Unused
        :param params: Unused
        :return: A list of settings available to the caller.
        """

        prefix = "settings/"
        keys = [x[len(prefix):] for x in self.vip.config.list()
                if x.startswith(prefix)]
        return keys or []

    def _handle_bacnet_props(self, session_user, params):
        platform_uuid = params.pop('platform_uuid')
        id = params.pop('message_id')
        _log.debug('Handling bacnet_props platform: {}'.format(platform_uuid))

        self._register_session_ws(session_user['channel'], 'configure',
                                  self._ws_received)

        def start_sending_props():
            response_topic = "configure/{}".format(session_user['channel'])
            # Two ways we could have handled this is to pop the identity off
            # of the params and then passed both the identity and the response
            # topic.  Or what I chose to do and to put the argument in a
            # copy of the params.
            cp = params.copy()
            cp['publish_topic'] = response_topic
            cp['device_id'] = int(cp['device_id'])
            platform = self._platforms.get_platform(platform_uuid)
            _log.debug('PARAMS: {}'.format(cp))
            platform.call("publish_bacnet_props", **cp)

        gevent.spawn_later(2, start_sending_props)

    def _handle_bacnet_scan(self, session_user, params):
        platform_uuid = params.pop('platform_uuid')
        id = params.pop('message_id')
        _log.debug('Handling bacnet_scan platform: {}'.format(platform_uuid))

        if not self._platforms.is_registered(platform_uuid):
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "Couldn't connect to platform {}".format(
                                          platform_uuid
                                      ))

        scan_length = params.pop('scan_length', 5)

        try:
            scan_length = float(scan_length)
            params['scan_length'] = scan_length
            platform = self._platforms.get_platform(platform_uuid)
            channel = session_user['channel']
            ws_socket_path = self._register_session_ws(channel, 'iam',
                                                       self._ws_received)

            def start_scan():
                # We want the datatype (iam) to be second in the response so
                # we need to reposition the iam and the session id to the topic
                # that is passed to the rpc function on vcp
                iam_session_topic = "iam/{}".format(channel)
                platform.call("start_bacnet_scan", iam_session_topic, **params)

                def close_socket():
                    _log.debug('Closing bacnet scan for {}'.format(
                        platform_uuid))
                    gevent.spawn_later(2, self._unregister_session_ws,
                                       channel, ws_socket_path)

                gevent.spawn_later(scan_length, close_socket)

            # By starting the scan a second later we allow the websocket
            # client to subscribe to the newly available endpoint.
            gevent.spawn_later(2, start_scan)
        except ValueError:
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "Couldn't connect to platform {}".format(
                                          platform_uuid
                                      ))
        except KeyError:
            return jsonrpc.json_error(id, UNAUTHORIZED,
                                      "Invalid user session token")

    def _enable_setup_mode(self, session_user, params):
        id = params.pop('message_id')
        if 'admin' not in session_user['groups']:
            _log.debug('Returning json_error enable_setup_mode')
            return jsonrpc.json_error(
                id, UNAUTHORIZED,
                "Admin access is required to enable setup mode")
        entry = {"credentials": "/.*/",
                 "comments": "Un-Authenticated connections allowed here",
                 "user_id": "unknown"
                }
        try:
            auth_data = self.vip.rpc.call(AUTH, "auth_file.read").get(
                timeout=30)
        except (RemoteError, Unreachable, gevent.Timeout) as err:
            _log.error("enable setup mode failed at auth_file.read: %s", err)
            return jsonrpc.json_error(id, INTERNAL_ERROR,
                                      "Setup mode could not be enabled")
        if any(allowed.get("credentials") == entry["credentials"]
               for allowed in auth_data["allow_list"]):
            return "SUCCESS"
        try:
            self.vip.rpc.call(AUTH, "auth_file.add", entry).get(timeout=30)
        except RemoteError as err:
            _log.error("enable setup mode failed at auth_file.add: %s", err)
            return jsonrpc.json_error(id, INTERNAL_ERROR,
                                      "Setup mode could not be enabled")
        except (Unreachable, gevent.Timeout) as err:
            # The add may still have been applied, so do not report it as
            # not enabled.
            _log.error("enable setup mode not confirmed at auth_file.add: "
                       "%s", err)
            return jsonrpc.json_error(
                id, INTERNAL_ERROR,
                "Setup mode could not be confirmed enabled")
        return "SUCCESS"

    def _disable_setup_mode(self, session_user, params):
        id = params.pop('message_id')
        if 'admin' not in session_user['groups']:
            _log.debug('Returning json_error disable_setup_mode')
            return jsonrpc.json_error(
                id, UNAUTHORIZED,
                "Admin access is required to disable setup mode")
        try:
            self.vip.rpc.call(AUTH, "auth_file.remove_by_credentials",
                              "/.*/").get(timeout=30)
        except (RemoteError, Unreachable, gevent.Timeout) as err:
            _log.error("disable setup mode failed: %s", err)
            return jsonrpc.json_error(
                id, INTERNAL_ERROR,
                "Setup mode could not be confirmed disabled")
        return "SUCCESS"

    def _handle_management_endpoint(self, session_user, params):
        return self._register_session_ws(session_user['channel'], 'management',
                                         self._ws_received)

    def send_management_message(self, type, data={}):
        """
        Send a message to any socket that has connected to the management
        socket.

        The payload sent to the client is like the following::

            {
                "type": "UPDATE_DEVICE_STATUS",
                "data": "this is data that was passed"
            }

        :param type:
            A string defining a unique type for sending to the websockets.
        :param data:
            An object that str can be called on.

        :type type: str
        :type data: serializable
        """
        management_sockets = [s for s in self._websocket_endpoints
                              if s.endswith("management")]
        # Nothing to send if we don't have any management sockets open.
        if len(management_sockets) <= 0:
            return

        if data is None:
            data = {}

        payload = dict(
            type=type,
            data=str(data)
        )

        payload = jsonapi.dumps(payload)
        for s in management_sockets:
            self.vip.web.send(s, payload)

    def _route_request(self, session_user, id, method, params):
        """ Handle the methods volttron central can or pass off to platforms.

        The method must be one the tables name exactly, and the session's
        groups must include the group that method needs.

        :param session_user:
            The authenticated user's session info.
        :param id:
            JSON-RPC id field.
        :param method:
        :param params:
        :return:
        """
        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        parsed = _parse_method(method)
        if parsed is None:
            return err('Unknown method')
        platform_uuid, name, group = parsed
        if group == ADMIN and 'admin' not in session_user['groups']:
            return jsonrpc.json_error(
                id, UNAUTHORIZED, "Admin access is required for this method")

        self.send_management_message(method)

        if method in HISTORIAN_METHODS:
            return self._route_historian(name, params, err)

        if name in VC_METHODS:
            return self._call_with_message_id(
                self._vc_method(name), session_user, id, params)

        return self._route_platform_request(
            session_user, id, platform_uuid, name, params, err)

    def _vc_method(self, name):
        return dict(
            register_management_endpoint=self._handle_management_endpoint,
            list_platforms=self._platforms.get_platform_list,
            list_performance=self._platforms.get_performance_list,
            set_setting=self.set_setting,
            get_setting=self.get_setting,
            get_setting_keys=self.get_setting_keys,
            enable_setup_mode=self._enable_setup_mode,
            disable_setup_mode=self._disable_setup_mode,
        )[name]

    @staticmethod
    def _call_with_message_id(method_ref, session_user, id, params):
        """Run a handler with the signature method(session, params)."""
        if not params:
            params = dict(message_id=id)
        elif isinstance(params, dict):
            params['message_id'] = id
        else:
            return jsonrpc.json_error(id, INVALID_PARAMS,
                                      "params must be an object")
        response = method_ref(session_user, params)
        _log.debug("Handler returned a %s", type(response).__name__)
        return response

    def _route_historian(self, name, params, err):
        has_platform_historian = PLATFORM_HISTORIAN in \
                                 self.vip.peerlist().get(timeout=30)
        if not has_platform_historian:
            return err(
                'The VOLTTRON Central platform historian is unavailable.',
                UNAVAILABLE_AGENT)
        _log.debug('Trapping platform.historian to vc.')
        if name == 'historian.query':
            if not isinstance(params, dict):
                return err('params must be an object', INVALID_PARAMS)
            return self.vip.rpc.call(
                PLATFORM_HISTORIAN, 'query', **params).get(timeout=30)
        return self.vip.rpc.call(
            PLATFORM_HISTORIAN, 'get_topic_list').get(timeout=30)

    def _route_platform_request(self, session_user, id, platform_uuid, name,
                                params, err):
        handlers = dict(
            # bacnet related
            start_bacnet_scan=self._handle_bacnet_scan,
            publish_bacnet_props=self._handle_bacnet_props,
            # config store related
            store_agent_config="store_agent_config",
            get_agent_config="get_agent_config",
            delete_agent_config="delete_agent_config",
            list_agent_configs="get_agent_config_list",
            # management related
            list_agents="get_agent_list",
            get_devices="get_devices",
            status_agents="status_agents"
        )

        # A bare method name names its platform in the params.
        if isinstance(params, dict):
            param_uuid = params.pop('platform_uuid', None)
            platform_uuid = platform_uuid or param_uuid
        if not platform_uuid or not isinstance(platform_uuid, str):
            return err("Invalid platform_uuid specified as parameter",
                       INVALID_PARAMS)

        if not self._platforms.is_registered(platform_uuid):
            return err("Unknown or unavailable platform {} specified as "
                       "parameter".format(platform_uuid),
                       UNAVAILABLE_PLATFORM)
        platform = self._platforms.get_platform(platform_uuid)
        if not platform:
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "cannot connect to platform.")

        if name in handlers:
            class_method = handlers[name]
            if isinstance(class_method, str):
                method_ref = getattr(platform, class_method)
            else:
                method_ref = class_method
                # The handler reads the platform from the params.
                params = dict(params or {}, platform_uuid=platform_uuid)
            return self._call_with_message_id(
                method_ref, session_user, id, params)

        if name == 'install':
            too_big = self._install_too_big(params)
            if too_big:
                return jsonrpc.json_error(id, INVALID_PARAMS, too_big)

        return platform.route_to_agent_method(id, name, params)

    @staticmethod
    def _install_too_big(params):
        """A message when an upload's encoded file is over the bound."""
        files = params.get('files') if isinstance(params, dict) else None
        if not isinstance(files, list):
            return None
        for fileargs in files:
            encoded = fileargs.get('file') if isinstance(fileargs, dict) else None
            if isinstance(encoded, str) and len(encoded) > MAX_ENCODED_UPLOAD:
                return "Upload is larger than {} bytes".format(MAX_UPLOAD_BYTES)
        return None


def main(argv=sys.argv):
    """
    Main method called by the eggsecutable.

    :param argv:
    :return:
    """
    utils.vip_main(init_volttron_central, identity=VOLTTRON_CENTRAL,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
