# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
import os
import os.path as p
import sys
from collections import namedtuple

import gevent

from volttron.platform import jsonapi
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, PLATFORM_HISTORIAN, AUTH)
from volttron.platform.agent.utils import (
    get_aware_utc_now, get_messagebus)
from volttron.platform.auth import AuthEntry
from volttron.platform.jsonrpc import (
    INVALID_REQUEST, METHOD_NOT_FOUND,
    UNHANDLED_EXCEPTION, UNAUTHORIZED,
    UNAVAILABLE_PLATFORM, INVALID_PARAMS,
    UNAVAILABLE_AGENT, INTERNAL_ERROR)
from volttron.platform.vip.agent import Agent, RPC, Unreachable
from .authenticate import Authenticate
from .platforms import Platforms, PlatformHandler
from .sessions import SessionHandler

# must be after importing of utils which imports grequest.
import requests

__version__ = "5.2"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))

Platform = namedtuple('Platform', ['instance_name', 'serverkey', 'vip_address'])
RequiredArgs = namedtuple('RequiredArgs', ['id', 'session_user',
                                           'platform_uuid'])


def init_volttron_central(config_path, **kwargs):
    # Load the configuration into a dictionary
    config = utils.load_config(config_path)

    # Required users
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

        # Sessions that have been authentication with the system.
        self._authenticated_sessions = None

    def _configure(self, config_name, action, contents):
        """
        The main configuration for volttron central.  This is where validation
        will occur.

        Note this method is called:

            1. When the agent first starts (with the params from packaged agent
               file)
            2. When 'store' is called through the volttron-ctl config command
               line with 'config' as the name.

        Required Configuration:

        The volttron central requires a user mapping.

        :param config_name:
        :param action:
        :param contents:
        """
        config = self._default_config.copy()

        config.update(contents)

        users = config.get("users", None)

        if self._authenticated_sessions:
            self._authenticated_sessions.clear()

        if users is None:
            users = {}
            _log.warning("No users are available for logging in!")

        # Unregister all routes for vc and then re-add down below.
        self.vip.web.unregister_all_routes()

        self._authenticated_sessions = SessionHandler(Authenticate(users))

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

        next_platform_scan = VolttronCentralAgent._get_next_time_seconds()

        # reschedule the next scan.
        self._platform_scan_event = self.core.schedule(
            next_platform_scan, self._scan_platform_connect_disconnect)

    def configure_platforms(self, config_name, action, contents):
        _log.debug('Platform configuration updated.')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))

    def open_authenticate_ws_endpoint(self, fromip, endpoint):
        """
        Callback method from when websockets are opened.  The endpoint must
        be '/' delimited with the second to last section being the session
        of a logged in user to volttron central itself.

        :param fromip:
        :param endpoint:
            A string representing the endpoint of the websocket.
        :return:
        """
        _log.debug("OPENED ip: {} endpoint: {}".format(fromip, endpoint))
        try:
            session = endpoint.split('/')[-2]
        except IndexError:
            _log.error("Malformed endpoint. Must be delimited by '/'")
            _log.error(
                'Endpoint must have valid session in second to last position')
            return False

        if not self._authenticated_sessions.check_session(session, fromip):
            _log.error("Authentication error for session!")
            return False

        _log.debug('Websocket allowed.')
        self._websocket_endpoints.add(endpoint)

        return True

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
            return jsonrpc.json_error('NA', INVALID_REQUEST,
                                      'Invalid request method, only POST allowed')

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))

            if rpcdata.method == 'get_authorization':

                # Authentication url
                # This does not need to be local, however for now we are going to
                # make it so assuming only one level of authentication.
                auth_url = "{url_scheme}://{HTTP_HOST}/authenticate".format(
                    url_scheme=env['wsgi.url_scheme'],
                    HTTP_HOST=env['HTTP_HOST'])
                user = rpcdata.params['username']
                args = {'username': rpcdata.params['username'],
                        'password': rpcdata.params['password'],
                        'ip': env['REMOTE_ADDR']}
                resp = requests.post(auth_url, json=args, verify=False)

                if resp.ok and resp.text:
                    claims = self.vip.web.get_user_claims(resp.text)
                    # Because the web-user.json has the groups under a key and the
                    # groups is just passed into the session we need to make sure
                    # we pass in the proper thing to the _add_sesion function.
                    assert 'groups' in claims
                    authentication_token = resp.text
                    sess = authentication_token
                    self._authenticated_sessions._add_session(user=user,
                                                              groups=claims['groups'],
                                                              token=authentication_token,
                                                              ip=env['REMOTE_ADDR'])
                else:
                    sess = self._authenticated_sessions.authenticate(**args)

                if not sess:
                    _log.info('Invalid username/password for {}'.format(
                        rpcdata.params['username']))
                    return jsonrpc.json_error(
                        rpcdata.id, UNAUTHORIZED,
                        "Invalid username/password specified.")
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))
                self.vip.web.register_websocket(
                    "/vc/ws/{}/management".format(sess),
                    self.open_authenticate_ws_endpoint,
                    self._ws_closed,
                    self._received_data)
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))

                gevent.sleep(1)
                return jsonrpc.json_result(rpcdata.id, sess)

            token = rpcdata.authorization
            ip = env['REMOTE_ADDR']
            _log.debug('REMOTE_ADDR: {}'.format(ip))
            session_user = self._authenticated_sessions.check_session(token, ip)
            _log.debug('SESSION_USER IS: {}'.format(session_user))
            if not session_user:
                _log.debug("Session Check Failed for Token: {}".format(token))
                return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                          "Invalid authentication token")
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

            return jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, str(e)
            )

        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

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

        configure_topic = "{}/configure".format(session_user['token'])
        ws_socket_topic = "/vc/ws/{}".format(configure_topic)

        if configure_topic not in self._websocket_endpoints:
            self.vip.web.register_websocket(ws_socket_topic,
                                            self.open_authenticate_ws_endpoint,
                                            self._ws_closed, self._ws_received)

        def start_sending_props():
            response_topic = "configure/{}".format(session_user['token'])
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
            iam_topic = "{}/iam".format(session_user['token'])
            ws_socket_topic = "/vc/ws/{}".format(iam_topic)
            self.vip.web.register_websocket(ws_socket_topic,
                                            self.open_authenticate_ws_endpoint,
                                            self._ws_closed, self._ws_received)

            def start_scan():
                # We want the datatype (iam) to be second in the response so
                # we need to reposition the iam and the session id to the topic
                # that is passed to the rpc function on vcp
                iam_session_topic = "iam/{}".format(session_user['token'])
                platform.call("start_bacnet_scan", iam_session_topic, **params)

                def close_socket():
                    _log.debug('Closing bacnet scan for {}'.format(
                        platform_uuid))
                    gevent.spawn_later(2,
                                       self.vip.web.unregister_websocket,
                                       iam_session_topic)

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
        entries = self.vip.rpc.call(AUTH, "auth_file.find_by_credentials", ".*")
        if len(entries) > 0:
            return "SUCCESS"

        entry = {"credentials": "/.*/",
                 "comments": "Un-Authenticated connections allowed here",
                 "user_id": "unknown"
                }
        self.vip.rpc.call(AUTH, "auth_file.add", entry)
        return "SUCCESS"

    def _disable_setup_mode(self, session_user, params):
        id = params.pop('message_id')
        if 'admin' not in session_user['groups']:
            _log.debug('Returning json_error disable_setup_mode')
            return jsonrpc.json_error(
                id, UNAUTHORIZED,
                "Admin access is required to disable setup mode")
        self.vip.rpc.call(AUTH, "auth_file.remove_by_credentials", "/.*/")
        return "SUCCESS"

    def _handle_management_endpoint(self, session_user, params):
        ws_topic = "/vc/ws/{}/management".format(session_user.get('token'))
        self.vip.web.register_websocket(ws_topic,
                                        self.open_authenticate_ws_endpoint,
                                        self._ws_closed, self._ws_received)
        return ws_topic

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

        :param session_user:
            The authenticated user's session info.
        :param id:
            JSON-RPC id field.
        :param method:
        :param params:
        :return:
        """
        _log.debug(
            'inside _route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        self.send_management_message(method)

        method_split = method.split('.')
        # The last part of the jsonrpc method is the actual method to be called.
        method_check = method_split[-1]

        # These functions will be sent to a platform.agent on either this
        # instance or another.  All of these functions have the same interface
        # and can be collected into a dictionary rather than an if tree.
        platform_methods = dict(
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

        # These methods are specifically to be handled by the platform not any
        # agents on the platform that is why we have the length requirement.
        #
        # The jsonrpc method looks like the following
        #
        #   platform.uuid.<dynamic entry>.method_on_vcp
        if method_check in platform_methods:

            platform_uuid = None
            if isinstance(params, dict):
                platform_uuid = params.pop('platform_uuid', None)

            if platform_uuid is None:
                if method_split[0] == 'platforms' and method_split[1] == 'uuid':
                    platform_uuid = method_split[2]

            if not platform_uuid:
                return err("Invalid platform_uuid specified as parameter"
                           .format(platform_uuid),
                           INVALID_PARAMS)

            if not self._platforms.is_registered(platform_uuid):
                return err("Unknown or unavailable platform {} specified as "
                           "parameter".format(platform_uuid),
                           UNAVAILABLE_PLATFORM)

            try:
                _log.debug('Calling {} on platform {}'.format(
                    method_check, platform_uuid
                ))
                class_method = platform_methods[method_check]
                platform = self._platforms.get_platform(platform_uuid)
                # Determine whether the method to call is on the current class
                # or on the platform object.
                if isinstance(class_method, str):
                    method_ref = getattr(platform, class_method)
                else:
                    method_ref = class_method
                    # Put the platform_uuid in the params so it can be used
                    # inside the method
                    params['platform_uuid'] = platform_uuid

            except AttributeError or KeyError:
                return jsonrpc.json_error(id, INTERNAL_ERROR,
                                          "Attempted calling function "
                                          "{} was unavailable".format(
                                              class_method
                                          ))

            except ValueError:
                return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                          "Couldn't connect to platform "
                                          "{}".format(platform_uuid))
            else:
                # pass the id through the message_id parameter.
                if not params:
                    params = dict(message_id=id)
                else:
                    params['message_id'] = id

                # Methods will all have the signature
                #   method(session, params)
                #
                return method_ref(session_user, params)

        vc_methods = dict(
            register_management_endpoint=self._handle_management_endpoint,
            list_platforms=self._platforms.get_platform_list,
            list_performance=self._platforms.get_performance_list,

            # Settings
            set_setting=self.set_setting,
            get_setting=self.get_setting,
            get_setting_keys=self.get_setting_keys,

            # Setup mode
            enable_setup_mode=self._enable_setup_mode,
            disable_setup_mode=self._disable_setup_mode
        )

        if method in vc_methods:
            if not params:
                params = dict(message_id=id)
            else:
                params['message_id'] = id
            response = vc_methods[method](session_user, params)
            _log.debug("Response is {}".format(response))
            return response  # vc_methods[method](session_user, params)

        if method == 'register_instance':
            if isinstance(params, list):
                return self._register_instance(*params)
            else:
                return self._register_instance(**params)
        elif method == 'unregister_platform':
            return self.unregister_platform(params['instance_uuid'])

        elif 'historian' in method:
            has_platform_historian = PLATFORM_HISTORIAN in \
                                     self.vip.peerlist().get(timeout=30)
            if not has_platform_historian:
                return err(
                    'The VOLTTRON Central platform historian is unavailable.',
                    UNAVAILABLE_AGENT)
            _log.debug('Trapping platform.historian to vc.')
            _log.debug('has_platform_historian: {}'.format(
                has_platform_historian))
            if 'historian.query' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'query', **params).get(timeout=30)
            elif 'historian.get_topic_list' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'get_topic_list').get(timeout=30)

        # This isn't known as a proper method on vc or a platform.
        if len(method_split) < 3:
            return err('Unknown method {}'.format(method))
        if method_split[0] != 'platforms' or method_split[1] != 'uuid':
            return err('Invalid format for instance must start with '
                       'platforms.uuid')
        instance_uuid = method_split[2]
        _log.debug('Instance uuid is: {}'.format(instance_uuid))
        if not self._platforms.is_registered(instance_uuid):
            return err('Unknown platform {}'.format(instance_uuid))
        platform_method = '.'.join(method_split[3:])
        _log.debug("Platform method is: {}".format(platform_method))
        platform = self._platforms.get_platform(instance_uuid)
        if not platform:
            return jsonrpc.json_error(id,
                                      UNAVAILABLE_PLATFORM,
                                      "cannot connect to platform."
                                      )

        if platform_method.startswith('install'):
            if 'admin' not in session_user['groups']:
                return jsonrpc.json_error(
                    id, UNAUTHORIZED,
                    "Admin access is required to install agents")

        return platform.route_to_agent_method(id, platform_method, params)

    def _validate_config_params(self, config):
        """
        Validate the configuration parameters of the default/updated parameters.

        This method will return a list of "problems" with the configuration.
        If there are no problems then an empty list is returned.

        :param config: Configuration parameters for the volttron central agent.
        :type config: dict
        :return: The problems if any, [] if no problems
        :rtype: list
        """
        problems = []
        webroot = config.get('webroot')
        if not webroot:
            problems.append('Invalid webroot in configuration.')
        elif not os.path.exists(webroot):
            problems.append(
                'Webroot {} does not exist on machine'.format(webroot))

        users = config.get('users')
        if not users:
            problems.append('A users node must be specified!')
        else:
            has_admin = False

            try:
                for user, item in users.items():
                    if 'password' not in item.keys():
                        problems.append('user {} must have a password!'.format(
                            user))
                    elif not item['password']:
                        problems.append('password for {} is blank!'.format(
                            user
                        ))

                    if 'groups' not in item:
                        problems.append('missing groups key for user {}'.format(
                            user
                        ))
                    elif not isinstance(item['groups'], list):
                        problems.append('groups must be a list of strings.')
                    elif not item['groups']:
                        problems.append(
                            'user {} must belong to at least one group.'.format(
                                user))

                    # See if there is an adminstator present.
                    if not has_admin and isinstance(item['groups'], list):
                        has_admin = 'admin' in item['groups']
            except AttributeError:
                problems.append('invalid user node.')

            if not has_admin:
                problems.append("One user must be in the admin group.")

        return problems


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
