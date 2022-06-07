import functools
import os
import re
import json
from os.path import normpath, join
from gevent.timeout import Timeout
from collections import defaultdict
from typing import List, Union

from werkzeug import Response
from werkzeug.urls import url_decode

from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.jsonrpc import MethodNotFound, RemoteError
from volttron.platform.web.topic_tree import DeviceTree, TopicTree
from volttron.platform.web.vui_pubsub import VUIPubsubManager


import logging
_log = logging.getLogger(__name__)


class OverrideError(Exception):
    """Error raised by driver when the user tries to set/revert point when global override is set."""
    pass


class LockError(Exception):
    """Error raised by actuator when the user does not have a device scheduled
    and tries to use methods that require exclusive access."""
    pass


def endpoint(func):
    @functools.wraps(func)
    def verify_and_dispatch(self, env, data):
        from volttron.platform.web import get_bearer
        try:
            claims = self._agent.get_user_claims(get_bearer(env))
        except Exception as e:
            _log.warning(f"Unauthorized user attempted to connect to {env.get('PATH_INFO')}. Caught Exception: {e}")
            return Response(json.dumps({'error': 'Not Authorized'}), 401, content_type='app/json')

        # Only allow only users with API permissions:
        if 'vui' not in claims.get('groups'):
            _log.warning(f"Unauthorized user attempted to connect with 'vui' claim to {env.get('PATH_INFO')}.")
            return Response(json.dumps({'error': 'Not Authorized'}), 403, content_type='app/json')

        # Dispatch endpoint:
        try:
            response = func(self, env, data)
            if not response:
                message = f"Endpoint {env['REQUEST_METHOD']} {env['PATH_INFO']} is not implemented."
                return Response(json.dumps({"error": message}), status=501, content_type='application/json')
            else:
                return response
        except TimeoutError as e:
            return Response(json.dumps({'error': f'Request Timed Out: {e}'}), 504, content_type='application/json')
        except Exception as e:
            return Response(json.dumps({'error': f'Unexpected Error: {e}'}), 500, content_type='application/json')
    return verify_and_dispatch


class VUIEndpoints:
    def __init__(self, agent):
        self._agent = agent
        q = Query(self._agent.core)
        self.local_instance_name = q.query('instance-name').get(timeout=5)
        # TODO: Load active_routes from configuration. Default can just be {'vui': {'endpoint-active': False}}
        self.active_routes = {
            'vui': {
                'endpoint-active': True,
                'platforms': {
                    'endpoint-active': True,
                    'agents': {
                        'endpoint-active': True,
                        'configs': {
                            'endpoint-active': True,
                        },
                        'enabled': {
                            'endpoint-active': True,
                        },
                        'front-ends': {
                            'endpoint-active': False,
                        },
                        'health': {
                            'endpoint-active': False,
                        },
                        'pubsub': {
                            'endpoint-active': False,
                        },
                        'rpc': {
                            'endpoint-active': True,
                        },
                        'running': {
                            'endpoint-active': True,
                        },
                        'status': {
                            'endpoint-active': True,
                        },
                        'tag': {
                            'endpoint-active': True,
                        }
                    },
                    'auths': {
                        'endpoint-active': False,
                    },
                    'configs': {
                        'endpoint-active': False,
                    },
                    'devices': {
                        'endpoint-active': True,
                    },
                    'groups': {
                        'endpoint-active': False,
                    },
                    'health': {
                        'endpoint-active': False,
                    },
                    'historians': {
                        'endpoint-active': True,
                    },
                    'known-hosts': {
                        'endpoint-active': False,
                    },
                    'pubsub': {
                        'endpoint-active': True,
                    },
                    'roles': {
                        'endpoint-active': False,
                    },
                    'status': {
                        'endpoint-active': True,
                    },
                    'statistics': {
                        'endpoint-active': False,
                    }
                },
                'devices': {
                    'endpoint-active': False,
                },
                'historians': {
                    'endpoint-active': False,
                }
            }
        }
        if self.active_routes['vui']['platforms']['pubsub']:
            self.pubsub_manager = VUIPubsubManager(self._agent)

    def get_routes(self):
        """
        Returns a list of tuples with the routes for the administration endpoints
        available in it.

        :return:
        """
        # TODO: Break this up into appends to allow configuration of which endpoints are available.
        return [
            (re.compile('^/vui/?$'), 'callable', self.handle_vui_root),
            (re.compile('^/vui/platforms/?$'), 'callable', self.handle_platforms),
            (re.compile('^/vui/platforms/[^/]+/?$'), 'callable', self.handle_platforms_platform),
            (re.compile('^/vui/platforms/[^/]+/agents/?$'), 'callable', self.handle_platforms_agents),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/?$'), 'callable', self.handle_platforms_agents_agent),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/configs/?$'), 'callable', self.handle_platforms_agents_configs),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/configs/.*/?$'), 'callable', self.handle_platforms_agents_configs),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/enabled/?$'), 'callable', self.handle_platforms_agents_enabled),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/rpc/?$'), 'callable', self.handle_platforms_agents_rpc),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/rpc/[^/]+/?$'), 'callable', self.handle_platforms_agents_rpc_method),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/running/?$'), 'callable', self.handle_platforms_agents_running),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/status/?$'), 'callable', self.handle_platforms_agents_status),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/tag/?$'), 'callable', self.handle_platforms_agents_tag),
            (re.compile('^/vui/platforms/[^/]+/devices/?$'), 'callable', self.handle_platforms_devices),
            (re.compile('^/vui/platforms/[^/]+/devices/.*/?$'), 'callable', self.handle_platforms_devices),
            (re.compile('^/vui/platforms/[^/]+/historians/?$'), 'callable', self.handle_platforms_historians),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/?$'), 'callable', self.handle_platforms_historians_historian),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/topics/?$'), 'callable', self.handle_platforms_historians_historian_topics),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/topics/.*/?$'), 'callable', self.handle_platforms_historians_historian_topics),
            (re.compile('^/vui/platforms/[^/]+/pubsub/?$'), 'callable', self.handle_platforms_pubsub),
            (re.compile('^/vui/platforms/[^/]+/pubsub/.*/?$'), 'callable', self.handle_platforms_pubsub),
            (re.compile('^/vui/platforms/[^/]+/status/?$'), 'callable', self.handle_platforms_status),
            # (re.compile('^/vui/devices/?$'), 'callable', self.handle_vui_devices),
            # (re.compile('^/vui/devices/.+/?$'), 'callable', self.handle_vui_devices_topic),
            # (re.compile('^/vui/devices/hierarchy/?$'), 'callable', self.handle_vui_devices_hierarchy),
            # (re.compile('^/vui/devices/hierarchy/.+/?$'), 'callable', self.handle_vui_devices_hierarchy_topic),
            # (re.compile('^/vui/historians/?$'), 'callable', self.handle_vui_historians),
            # (re.compile('^/vui/history/?$), 'callable', self.handle_vui_history)
        ]

    @endpoint
    def handle_vui_root(self, env: dict, data: dict) -> Response:
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            response = json.dumps(self._find_active_sub_routes(['vui'], path_info=path_info))
            return Response(response, 200, content_type='application/json')

    @endpoint
    def handle_platforms(self, env: dict, data: dict) -> Response:
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            platforms = self._get_platforms()
            response = json.dumps(self._route_options(path_info, platforms))
            return Response(response, 200, content_type='application/json')

    @endpoint
    def handle_platforms_platform(self, env: dict, data: dict) -> Response:
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            platform = re.match('^/vui/platforms/([^/]+)/?$', path_info).groups()[0]
            if platform in self._get_platforms():
                return Response(json.dumps(self._find_active_sub_routes(['vui', 'platforms'], path_info=path_info)),
                                200, content_type='application/json')
            else:
                return Response(json.dumps({f'error': f'Unknown platform: {platform}'}),
                                400, content_type='application/json')

    @endpoint
    def handle_platforms_agents(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])
        platform = re.match('^/vui/platforms/([^/]+)/agents/?$', path_info).groups()[0]
        if request_method == 'GET':
            include_hidden = self._to_bool(query_params.get('include-hidden', False))
            agent_state = query_params.get('agent-state', 'running')
            if agent_state not in ['running', 'installed']:
                error = {'error': f'Unknown agent-state: {agent_state} -- must be "running", "installed",'
                                  f' or "packaged". Default is "running".'}
                return Response(json.dumps(error), 400, content_type='application/json')
            if platform not in self._get_platforms():
                error = {'error': f'Unknown platform: {platform}'}
                return Response(json.dumps(error), 400, content_type='application/json')
            else:
                agents = self._get_agents(platform, agent_state, include_hidden)
                return Response(json.dumps(self._route_options(path_info, agents)), 200,
                                content_type='application/json')

    @endpoint
    def handle_platforms_agents_running(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/running
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])
        restart = self._to_bool(query_params.get('restart', 'false'))
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/running/?$', path_info).groups()
        uuid = self._rpc('control', 'identity_exists', vip_identity, external_platform=platform)
        if not uuid:
            return Response(json.dumps({'error': f'Agent "{vip_identity}" not found.'}), 400,
                            content_type='application/json')

        def _agent_running(vip_identity):
            peerlist = self._rpc('control', 'peerlist', external_platform=platform)
            return True if vip_identity in peerlist else False

        if request_method == 'GET':
            status = _agent_running(vip_identity)
            return Response(json.dumps({'running': status}), 200, content_type='application/json')

        elif request_method == 'PUT':
            if restart:
                self._rpc('control', 'restart_agent', uuid, external_platform=platform)
            else:
                if _agent_running(vip_identity):
                    return Response(json.dumps({'error': f'Agent: {vip_identity} is already running.'}), 400,
                                    content_type='application/json')
                self._rpc('control', 'start_agent', uuid, external_platform=platform)
            return Response(status=204)

        elif request_method == 'DELETE':
            self._rpc('control', 'stop_agent', uuid, external_platform=platform)
            return Response(status=204)

    @endpoint
    def handle_platforms_agents_agent(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/?$', path_info).groups()
        if request_method == 'GET':
            active_routes = self._find_active_sub_routes(['vui', 'platforms', 'agents'], path_info=path_info)
            # If RPC endpoint is enabled, check if agent is running and disallow if it is not.
            if 'rpc' in active_routes['route_options'].keys():
                if vip_identity not in self._get_agents(platform, 'running'):
                    active_routes['route_options'].pop('rpc')
            return Response(json.dumps(active_routes), 200, content_type='application/json')

    @endpoint
    def handle_platforms_agents_configs(self, env: dict, data: dict) -> Response:
        """
                Endpoints for /vui/platforms/:platform/agents/:vip_identity/configs/:file_name
                :param env:
                :param data:
                :return:
                """
        _log.debug('VUI: In handle_platforms_agents_configs_config')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        config_type = env.get('CONTENT_TYPE')

        no_config_name = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/configs/?$', path_info)
        if no_config_name:
            platform, vip_identity, config_name = tuple(no_config_name.groups()) + ('',)
            query_params = url_decode(env['QUERY_STRING'])
            config_name = query_params.get('config-name')
        else:
            platform, vip_identity, config_name = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/configs/(.*)/?$',
                                                           path_info).groups()
            config_name = config_name[:-1] if config_name[-1] == '/' else config_name
        if request_method == 'GET':
            try:
                if no_config_name:
                    if vip_identity != '-':
                        setting_list = self._rpc('config.store', 'manage_list_configs', vip_identity,
                                                 external_platform=platform)
                        route_dict = self._route_options(path_info, setting_list)
                        return Response(json.dumps(route_dict), 200, content_type='application/json')
                    else:
                        list_of_agents = self._rpc('config.store', 'manage_list_stores', external_platform=platform)
                        return Response(json.dumps(list_of_agents), 200, content_type='application/json')
                elif not no_config_name:
                    setting_dict = self._rpc('config.store', 'manage_get', vip_identity, config_name,
                                             external_platform=platform)
                    return Response(json.dumps(setting_dict), 200, content_type='application/json')
            except RemoteError as e:
                return Response(json.dumps({"Error": f"{e}"}), 400, content_type='application/json')

        elif request_method == 'PUT' and (not no_config_name):
            if config_type in ['application/json', 'text/csv', 'text/plain']:
                self._insert_config(config_type, data, vip_identity, config_name, platform)
                return Response(None, 204, content_type='application/json')
            else:
                return Response(
                    json.dumps({"Error": "The configuration type can only be 'JSON', 'CSV' and 'RAW.'"}), 400,
                    content_type='application/json')

        elif request_method == 'POST' and no_config_name:
            if config_type in ['application/json', 'text/csv', 'text/plain']:
                setting_list = self._rpc('config.store', 'manage_list_configs', vip_identity,
                                         external_platform=platform)
                if config_name in setting_list:
                    e = {'Error': f'Configuration: "{config_name}" already exists for agent: "{vip_identity}"'}
                    return Response(json.dumps(e), 409, content_type='application/json')
                self._insert_config(config_type, data, vip_identity, config_name, platform)
                response = Response(None, 201, content_type='application/json')
                response.location = f'/platforms/{platform}/agents/{vip_identity}/configs/{config_name}'
                return response
            else:
                return Response(
                    json.dumps({"Error": "The configuration type can only be 'JSON', 'CSV' and 'RAW.'"}), 400,
                    content_type='application/json')

        elif request_method == 'DELETE':
            if no_config_name:
                try:
                    self._rpc('config.store', 'manage_delete_store', vip_identity, external_platform=platform)
                    return Response(None, 204, content_type='application/json')
                except RemoteError as e:
                    return Response(json.dumps({"Error": f"{e}"}), 400, content_type='application/json')
            else:
                try:
                    self._rpc('config.store', 'manage_delete_config', vip_identity, config_name,
                              external_platform=platform)
                    return Response(None, 204, content_type='application/json')
                except RemoteError as e:
                    return Response(json.dumps({"Error": f"{e}"}), 400, content_type='application/json')

    @endpoint
    def handle_platforms_agents_enabled(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/enabled/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])
        priority = query_params.get('priority', '50')
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/enabled/?$', path_info).groups()

        if request_method == 'GET':
            try:
                list_of_agents = self._rpc('control', 'list_agents', external_platform=platform)
                result = next(item['priority'] for item in list_of_agents if item['identity'] == vip_identity)
                result = int(result) if result else result
                status = True if result is not None else False
                ret_val = {'status': status, 'priority': result}
                return Response(json.dumps(ret_val), 200, content_type='application/json')
            except StopIteration:
                return Response(json.dumps({'error': f'Agent "{vip_identity}" not found.'}),
                                400, content_type='application/json')
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'For agent {vip_identity}: {e}'}),
                                400, content_type='application/json')

        elif request_method == 'PUT':
            if not priority.isdigit() or not 0 <= int(priority) < 100:
                error = {'error': f'Priority must be an integer from 0 - 99. Received: {priority}.'}
                return Response(json.dumps(error), 400, content_type='application/json')
            try:
                uuid = self._rpc('control', 'identity_exists', vip_identity, external_platform=platform)
                self._rpc('control', 'prioritize_agent', uuid, priority, external_platform=platform)
                return Response(status=204)
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'For agent {vip_identity}: {e}'}),
                                400, content_type='application/json')

        elif request_method == 'DELETE':
            try:
                uuid = self._rpc('control', 'identity_exists', vip_identity, external_platform=platform)
                self._rpc('control', 'prioritize_agent', uuid, None, external_platform=platform)
                return Response(status=204)
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'For agent {vip_identity}: {e}'}),
                                400, content_type='application/json')

    @endpoint
    def handle_platforms_agents_rpc(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/rpc/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/rpc/?$', path_info).groups()
        if request_method == 'GET':
            method_dict = self._rpc(vip_identity, 'inspect', external_platform=platform)
            response = self._route_options(path_info, method_dict.get('methods'))
            return Response(json.dumps(response), 200, content_type='application/json')

    @endpoint
    def handle_platforms_agents_rpc_method(self, env: dict, data: Union[dict, List]) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/rpc/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity, method_name = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/rpc/([^/]+)/?$',
                                                       path_info).groups()
        if request_method == 'GET':
            try:
                method_dict = self._rpc(vip_identity, method_name + '.inspect', external_platform=platform)
            except MethodNotFound as e:
                return Response(json.dumps({f'error': f'for agent {vip_identity}: {e}'}),
                                400, content_type='application/json')
            return Response(json.dumps(method_dict), 200, content_type='application/json')

        elif request_method == 'POST':
            try:
                if type(data) is dict:
                    if 'args' in data.keys() and type(data['args']) is list:
                        args = data.pop('args')
                        result = self._rpc(vip_identity, method_name, *args, **data, external_platform=platform)
                    else:
                        result = self._rpc(vip_identity, method_name, **data, external_platform=platform)
                elif type(data) is list:
                    result = self._rpc(vip_identity, method_name, *data, external_platform=platform)
                else:
                    raise ValueError(f'Malformed message body: {data}')
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'for agent {vip_identity}: {e}'}),
                                400, content_type='application/json')
            return Response(json.dumps(result), 200, content_type='application/json')

    @endpoint
    def handle_platforms_agents_status(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/status/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/status/?$', path_info).groups()

        if request_method == 'GET':
            try:
                status_dict = self._get_status(platform)
                our_agent = status_dict[vip_identity]
                return Response(json.dumps(our_agent), 200,
                                content_type='application/json')
            except KeyError:
                return Response(json.dumps({'error': f'Agent "{vip_identity}" not found.'}),
                                400, content_type='application/json')
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'For agent  {e}'}),
                                400, content_type='application/json')

    @endpoint
    def handle_platforms_agents_tag(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/tag/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/tag/?$', path_info).groups()
        list_of_agents = self._rpc('control', 'list_agents', external_platform=platform)
        if request_method == 'GET':
            try:
                result = next(item['tag'] for item in list_of_agents if item['identity'] == vip_identity)
                return Response(json.dumps({'tag': f"{result}"}), 200, content_type='application/json')
            except StopIteration:
                return Response(json.dumps({'error': f"Agent '{vip_identity}' not found."}),
                                400, content_type='application/json')
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f"For agent '{vip_identity}': {e}"}),
                                400, content_type='application/json')

        elif request_method == 'PUT':
            tag = data.get('tag')
            uuid = self._rpc('control', 'identity_exists', vip_identity, external_platform=platform)
            if not uuid:
                return Response(json.dumps({'error': f"Agent '{vip_identity}' not found."}),
                                400, content_type='application/json')
            self._rpc('control', 'tag_agent', uuid, tag, external_platform=platform)
            return Response(status=204)

        elif request_method == 'DELETE':
            uuid = self._rpc('control', 'identity_exists', vip_identity, external_platform=platform)
            if not uuid:
                return Response(json.dumps({'error': f"Agent '{vip_identity}' not found."}),
                                400, content_type='application/json')
            self._rpc('control', 'tag_agent', uuid, None, external_platform=platform)
            return Response(status=204)

    @endpoint
    def handle_platforms_devices(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/devices/ and /vui/platforms/:platform/devices/:topic/
        :param env:
        :param data:
        :return:
        """
        def _get_allowed_write_selection(points, topic, regex, tag):
            # Query parameters:
            write_all = self._to_bool(query_params.get('write-all', False))
            confirm_values = self._to_bool(query_params.get('confirm-values', False))
            # Map of selected topics to routes:
            selection = {p.topic: f'/vui/platforms/{platform}/{p.identifier}' for p in points}
            unwritables = [p.topic for p in points if not self._to_bool(p.data['Writable'])]

            if (regex or tag or '/-' in topic or len(points) > 1) and not write_all:
                # Disallow potential use of multiple writes without explicit write-all flag:
                error_message = {
                    'error': f"Use of wildcard expressions, regex, or tags may set multiple points. "
                             f"Query must include 'write-all=true'.",
                    'requested_topic': topic,
                    'regex': regex,
                    'tag': tag,
                    'selected_points': selection
                }
                raise ValueError(json.dumps(error_message))
            elif len(unwritables) == len(points):
                raise ValueError(json.dumps({'error': 'No selected points are writable.',
                                             'unwritable_points': unwritables}))
            else:
                return confirm_values, selection, unwritables

        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])

        tag = query_params.get('tag')
        tag = tag if tag and tag.lower() != 'null' and tag.lower() != 'none' else None
        regex = query_params.get('regex')
        regex = regex if regex and regex.lower() != 'null' and regex.lower() != 'none' else None

        no_topic = re.match('^/vui/platforms/([^/]+)/devices/?$', path_info)
        if no_topic:
            platform, topic = no_topic.groups()[0], ''
        else:
            platform, topic = re.match('^/vui/platforms/([^/]+)/devices/(.*)/?$', path_info).groups()
            topic = topic[:-1] if topic[-1] == '/' else topic

        # Resolve tags if the tag query parameter is set:
        if tag:
            try:
                tag_list = self._rpc('platform.tagging', 'get_topics_by_tags', tag, external_platform=platform)
            except Timeout as e:
                return Response(json.dumps({'error': f'Tagging Service timed out: {e}'}),
                                504, content_type='application/json')
        else:
            tag_list = None
        # Prune device tree and get nodes matching topic:
        try:
            # TODO: Should we be storing this tree to use for faster requests later? How to keep it updated?
            device_tree = DeviceTree.from_store(platform, self._rpc).prune(topic, regex, tag_list)
            topic_nodes = device_tree.get_matches(f'devices/{topic}' if topic else 'devices')
            if not topic_nodes:
                return Response(json.dumps({f'error': f'Device topic {topic} not found on platform: {platform}.'}),
                                400, content_type='application/json')
            points = device_tree.points()
        except Timeout as e:
            return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        if request_method == 'GET':
            # Query parameters:
            read_all = self._to_bool(query_params.get('read-all', False))
            return_routes = self._to_bool(query_params.get('routes', True))
            return_writability = self._to_bool(query_params.get('writability', True))
            return_values = self._to_bool(query_params.get('values', True))
            return_config = self._to_bool(query_params.get('config', False))

            try:
                if read_all or all([n.is_point() for n in topic_nodes]):
                    # Either leaf values are explicitly requested, or all nodes are already points -- Return points:
                    ret_dict = defaultdict(dict)
                    if return_values:
                        ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                               [d.topic for d in points], external_platform=platform)
                        for k, v in ret_values[0].items():
                            ret_dict[k]['value'] = v
                        for k, e in ret_values[1].items():
                            ret_dict[k]['value_error'] = e
                    for point in points:
                        if return_routes:
                            ret_dict[point.topic]['route'] = f'/vui/platforms/{platform}/{point.identifier}'
                        if return_writability:
                            ret_dict[point.topic]['writable'] = self._to_bool(point.data.get('Writable'))
                        if return_config:
                            ret_dict[point.topic]['config'] = point.data
                    return Response(json.dumps(ret_dict), 200, content_type='application/json')
                else:
                    # All topics are not complete to points and read_all=False -- return route to next segments:
                    ret_dict = {
                        'route_options': device_tree.get_children_dict([n.identifier for n in topic_nodes],
                                                                       replace_topic=topic,
                                                                       prefix=f'/vui/platforms/{platform}')
                    }
                    return Response(json.dumps(ret_dict), 200, content_type='application/json')

            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        elif request_method == 'PUT':
            try:
                confirm_values, selected_routes, unwritables = _get_allowed_write_selection(points, topic, regex, tag)
            except ValueError as e:
                return Response(str(e), 405, content_type='application/json')

            # Set selected points:
            try:
                set_value = data.get('value')
                topics_values = [(d.topic, set_value) for d in points if d.topic not in unwritables]
                ret_errors = self._rpc('platform.actuator', 'set_multiple_points',
                                       requester_id=self._agent.core.identity, topics_values=topics_values,
                                       external_platform=platform)
                ret_dict = defaultdict(dict)
                for k in selected_routes.keys():
                    ret_dict[k]['route'] = selected_routes[k]
                    ret_dict[k]['set_error'] = ret_errors.get(k)
                    ret_dict[k]['writable'] = True if k not in unwritables else False
                if confirm_values:
                    ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                           [d.topic for d in points], external_platform=platform)
                    for k in selected_routes.keys():
                        ret_dict[k]['value'] = ret_values[0].get(k)
                        ret_dict[k]['value_check_error'] = ret_values[1].get(k)

                return Response(json.dumps(ret_dict), 200, content_type='application/json')

            except (LockError, OverrideError) as e:
                return Response(json.dumps({'error': e}), 409, content_type='application/json')
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        elif request_method == 'DELETE':
            try:
                confirm_values, selected_routes, unwritables = _get_allowed_write_selection(points, topic, regex, tag)
            except ValueError as e:
                return Response(str(e), status=405, content_type='application/json')

            # Reset selected points:
            try:
                for t_node in topic_nodes:
                    if t_node.is_device():
                        self._rpc('platform.actuator', 'revert_device', requester_id=self._agent.core.identity,
                                  topic=t_node.topic, external_platform=platform)
                    elif t_node.is_point() and t_node.topic not in unwritables:
                        self._rpc('platform.actuator', 'revert_point', requester_id=self._agent.core.identity,
                                  topic=t_node.topic, external_platform=platform)

                ret_dict = defaultdict(dict)
                for k in selected_routes.keys():
                    ret_dict[k]['route'] = selected_routes[k]
                    ret_dict[k]['writable'] = True if k not in unwritables else False

                if confirm_values:
                    ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                           [d.topic for d in points], external_platform=platform)
                    for k in selected_routes.keys():
                        ret_dict[k]['value'] = ret_values[0].get(k)
                        ret_dict[k]['value_check_error'] = ret_values[1].get(k)
                return Response(json.dumps(ret_dict), 200, content_type='application/json')

            except (LockError, OverrideError) as e:
                return Response(json.dumps({'error': e}), 409, content_type='application/json')
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status=501, content_type='text/plain')

    def handle_platforms_pubsub(self, env: dict, start_response, data: dict):
        from volttron.platform.web import get_bearer  # TODO: Is this necessary, with bearer imported in decorator?
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])
        _log.debug('VUI.handle_platforms_pubsub -- env is: ')
        _log.debug({k: str(v) for k, v in env.items()})
        _log.debug(f'HTTP_AUTHORIZATION is: {env["HTTP_AUTHORIZATION"]}')
        access_token = get_bearer(env)

        no_topic = re.match('^/vui/platforms/([^/]+)/pubsub/?$', path_info)
        if no_topic:
            platform, topic = no_topic.groups()[0], ''
        else:
            platform, topic = re.match('^/vui/platforms/([^/]+)/pubsub/(.*)/?$', path_info).groups()
            topic = topic[:-1] if topic[-1] == '/' else topic

        # GET -- For ../pubsub and /pubsub/:topic, Get routes to open web sockets for this user.
        if request_method == 'GET':
            if not topic:
                ret_dict = self.pubsub_manager.get_socket_routes(access_token, topic)
                response = Response(json.dumps(ret_dict), 200, content_type='application/json')
                return response
            else:
                ws = self.pubsub_manager.open_subscription_socket(access_token, topic)
                env['ws4py.app'] = self.pubsub_manager
                _log.debug('ENV is:')
                _log.debug(env)
                return [ws(env, start_response)]

        elif request_method == 'PUT':
            # PUT -- for ../pubsub/:topic: One-time publish to a topic.
            message = data.get('message')
            headers = data.get('headers')
            subscriber_count = self.pubsub_manager.publish(topic, headers, message)
            return Response(json.dumps(subscriber_count), 200, content_type='application/json')

        # elif request_method == 'DELETE':
        #     # DELETE -- For ../pubsub and /pubsub/:topic, Close open web sockets and subscriptions for this user.
        #     self.pubsub_manager.close_socket(access_token, topic)
        #     return Response(status=204)

    @endpoint
    def handle_platforms_historians(self, env: dict, data: dict) -> Response:
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform = re.match('^/vui/platforms/([^/]+)/historians/?$', path_info).groups()[0]

        if request_method == 'GET':
            agents = self._get_agents(platform)
            response = json.dumps(self._route_options(path_info, [agent for agent in agents if 'historian' in agent]))
            return Response(response, 200, content_type='application/json')

    @endpoint
    def handle_platforms_historians_historian(self, env: dict, data: dict) -> Response:
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/historians/([^/]+)/?$', path_info).groups()

        if request_method == 'GET':
            route_options = {'route_options': {'topics': f'/vui/platforms/{platform}/historians/{vip_identity}/topics'}}

            return Response(json.dumps(route_options), 200, content_type='application/json')

    @endpoint
    def handle_platforms_historians_historian_topics(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/historians/topics and /vui/platforms/:platform/historians/topics/:topic/
        :param env:
        :param data:
        :return:
        """

        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        query_params = url_decode(env['QUERY_STRING'])

        # Query parameters used directly in this method.
        tag = query_params.get('tag')
        tag = tag if tag and tag.lower() != 'null' and tag.lower() != 'none' else None
        regex = query_params.get('regex')
        regex = regex if regex and regex.lower() != 'null' and regex.lower() != 'none' else None

        # Query parameters passed directly to RPC.
        start = query_params.get('start')
        end = query_params.get('end')
        skip = int(query_params.get('skip') if query_params.get('skip') else 0)
        count = query_params.get('count')
        order = query_params.get('order') if query_params.get('order') else 'FIRST_TO_LAST'
        # TODO: agg_type & agg_period not implemented, need to check response format of Aggregate Historians
        agg_type = None
        agg_period = None

        no_topic = re.match('^/vui/platforms/([^/]+)/historians/([^/]+)/topics/?$', path_info)
        if no_topic:
            platform, historian, topic = no_topic.groups()[0], no_topic.groups()[1], ''
        else:
            platform, historian, topic = re.match('^/vui/platforms/([^/]+)/historians/([^/]+)/topics/(.*)/?$',
                                                  path_info).groups()
            topic = topic[:-1] if topic[-1] == '/' else topic

        # Resolve tags if the tag query parameter is set:
        if tag:
            try:
                tag_list = self._rpc('platform.tagging', 'get_topics_by_tags', tag,
                                     external_platform=platform).get(timeout=5)
            except Timeout as e:
                return Response(json.dumps({'error': f'Tagging Service timed out: {e}'}),
                                504, content_type='application/json')
        else:
            tag_list = None
        try:
            historian_topics = self._rpc(historian, 'get_topic_list', external_platform=platform)
            historian_tree = TopicTree(historian_topics, 'historians').prune(topic, regex, tag_list)
            topic_nodes = historian_tree.get_matches(f'historians/{topic}' if topic else 'historians')

            if not topic_nodes:
                return Response(json.dumps({f'error': f'Historian topic {topic} not found on platform: {platform}.'}),
                                400, content_type='application/json')
            points = historian_tree.leaves()
        except Timeout as e:
            return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        if request_method == 'GET':
            read_all = self._to_bool(query_params.get('read-all', False))
            return_routes = self._to_bool(query_params.get('routes', True))
            return_values = self._to_bool(query_params.get('values', True))

            try:
                if read_all or all([n.is_leaf() for n in topic_nodes]):
                    # Either leaf values are explicitly requested, or all nodes are already points -- Return points:
                    ret_dict = defaultdict(dict)

                    if return_values:
                        ret_values = self._rpc(historian, 'query',
                                               [p.topic for p in points], start, end, agg_type, agg_period, skip, count,
                                               order, external_platform=platform)
                        # to match single and multiple topics query results into the same structure
                        ret_values['values'] = ret_values['values'] if isinstance(ret_values['values'], dict) else {
                            points[0].topic: ret_values['values']}
                        for k, v in ret_values['values'].items():
                            ret_dict[k]['value'] = v
                            if ret_values['metadata']:
                                ret_dict[k]['metadata'] = ret_values['metadata']
                    for point in points:
                        if return_routes:
                            ret_dict[point.topic][
                                'route'] = f'/vui/platforms/{platform}/historians/{historian}/{point.identifier}'

                    return Response(json.dumps(ret_dict), 200, content_type='application/json')

                else:
                    # All topics are not complete to points and read_all=False -- return route to next segments:
                    ret_dict = {
                        'route_options': historian_tree.get_children_dict([n.identifier for n in topic_nodes],
                                                                          replace_topic=f'{historian}/topics/{topic}',
                                                                          prefix=f'/vui/platforms/{platform}')}
                    return Response(json.dumps(ret_dict), 200, content_type='application/json')

            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')

        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    @endpoint
    def handle_platforms_status(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/status/
        :param env:
        :param data:
        :return:
        """
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform = re.match('^/vui/platforms/([^/]+)/status/?$', path_info).groups()[0]

        if request_method == 'GET':
            try:
                status_dict = self._get_status(platform)
                return Response(json.dumps(status_dict), 200,
                                content_type='application/json')
            except MethodNotFound or ValueError as e:
                return Response(json.dumps({f'error': f'For agent  {e}'}),
                                400, content_type='application/json')
        if request_method == 'DELETE':
            self._rpc('control', 'clear_status', True, external_platform=platform)
            return Response(status=204)

    def _find_active_sub_routes(self, segments: list, path_info: str = None, enclose=True) -> dict or list:
        """
        Returns active routes with constant segments at the end of the route.
                If no path_info is provided, return only a list of the keys.
        """
        route_obj = self.active_routes
        for segment in segments:
            if route_obj and route_obj.get(segment) and route_obj.get(segment).get('endpoint-active'):
                route_obj = route_obj.get(segment)
            else:
                route_obj = {}
        keys = [k for k in route_obj.keys() if k != 'endpoint-active' and route_obj[k]['endpoint-active']]
        if not path_info:
            return keys
        else:
            return self._route_options(path_info, keys) if enclose else self._route_options(path_info, keys, False)

    def _get_platforms(self):
        platforms = []
        try:
            with open(join(self._agent.core.volttron_home, 'external_platform_discovery.json')) as f:
                platforms = [platform for platform in json.load(f).keys()]
        except FileNotFoundError:
            _log.info('Did not find VOLTTRON_HOME/external_platform_discovery.json. Only local platform available.')
        except Exception as e:
            _log.warning(f'Error opening external_platform_discovery.json: {e}')
        finally:
            if self.local_instance_name not in platforms:
                platforms.insert(0, self.local_instance_name)
        return platforms

    def _get_agents(self, platform: str, agent_state: str = "running", include_hidden=False) -> List[str]:
        agent_list = self._rpc('control', 'list_agents', external_platform=platform)
        peerlist = self._rpc('control', 'peerlist', external_platform=platform)
        for agent in agent_list:
            agent['running'] = True if agent['identity'] in peerlist else False
        if include_hidden:
            for p in peerlist:
                if p not in [a['identity'] for a in agent_list]:
                    agent_list.append({'identity': p, 'running': True})
        if agent_state == 'running':
            return [a['identity'] for a in agent_list if a['running']]
        elif agent_state == 'installed':
            return [a['identity'] for a in agent_list]
        elif agent_state == 'packaged':
            return [os.path.splitext(a)[0] for a in os.listdir(f'{self._agent.core.volttron_home}/packaged')]

    def _get_status(self, platform: str):
        list_of_agents = self._rpc('control', 'list_agents', external_platform=platform)
        running_agents = self._rpc('control', 'status_agents', external_platform=platform)
        running_agents = {a[0]: {'pid': a[2][0], 'exit_code': a[2][1]} for a in running_agents}
        ret_dict = {}
        for la in list_of_agents:
            ra = running_agents.get(la['uuid'])
            agent_identity = la.pop('identity')
            la['running'] = True if ra and ra['exit_code'] is None else False
            la['enabled'] = True if la['priority'] else False
            la['pid'] = ra['pid'] if ra else None
            la['exit_code'] = ra['exit_code'] if ra else None
            ret_dict[agent_identity] = la
        return ret_dict

    def _insert_config(self, config_type, data, vip_identity, config_name, platform):
        config_type = re.search(r'([^\/]+$)', config_type).group() if config_type in ['application/json',
                                                                                      'text/csv'] else 'raw'
        if config_type == 'json':
            data = json.dumps(data)
        self._rpc('config.store', 'manage_store', vip_identity, config_name, data, config_type,
                  external_platform=platform)
        return None

    def _rpc(self, vip_identity, method, *args, external_platform=None, **kwargs):
        external_platform = {'external_platform': external_platform}\
            if external_platform != self.local_instance_name else {}
        result = self._agent.vip.rpc.call(vip_identity, method, *args, **external_platform, **kwargs).get(timeout=5)
        return result

    @staticmethod
    def _route_options(path_info, option_segments, enclosing_dict=True):
        route_options = {segment: normpath('/'.join([path_info, segment])) for segment in option_segments}
        return route_options if not enclosing_dict else {'route_options': route_options}

    @staticmethod
    def _to_bool(values):
        values = values if type(values) is list else [values]
        bools = []
        for v in values:
            bools.append(True if str(v).lower() in ['true', 't', '1'] else False)
        if len(bools) == 1:
            return bools[0]
        elif len(bools) == 0:
            return None
        else:
            return bools
