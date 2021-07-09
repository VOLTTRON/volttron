import re
import json
from os import environ
from os.path import normpath, join
from gevent.timeout import Timeout
from collections import defaultdict

from volttron.platform.agent.known_identities import CONFIGURATION_STORE
from werkzeug import Response
from werkzeug.urls import url_decode
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.jsonrpc import MethodNotFound
from services.core.PlatformDriverAgent.platform_driver.agent import OverrideError
# TODO: How to get this without modifiying the actuator.py import of ScheduleManager from scheduler?
from services.core.ActuatorAgent.actuator.agent import LockError

from volttron.platform.web.topic_tree import DeviceTree, TopicTree


import logging
_log = logging.getLogger(__name__)


class VUIEndpoints(object):
    def __init__(self, agent=None):
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
                            'endpoint-active': False,
                        },
                        'enabled': {
                            'endpoint-active': False,
                        },
                        'front-ends': {
                            'endpoint-active': False,
                        },
                        'health': {
                            'endpoint-active': False,
                        },
                        'pubsub': {
                            'endpoint-active': True,
                        },
                        'rpc': {
                            'endpoint-active': True,
                        },
                        'running': {
                            'endpoint-active': False,
                        },
                        'status': {
                            'endpoint-active': False,
                        },
                        'tag': {
                            'endpoint-active': False,
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
                        'endpoint-active': False,
                    },
                    'statistics': {
                        'endpoint-active': False,
                    }
                },
                'devices': {
                    'endpoint-active': True,
                },
                'historians': {
                    'endpoint-active': True,
                }
            }
        }

    def get_routes(self):
        """
        Returns a list of tuples with the routes for the administration endpoints
        available in it.

        :return:
        """
        # TODO: Break this up into appends to allow configuration of which endpoints are available.
        _log.debug('In VUIEndpoints.get_routes()')
        return [
            (re.compile('^/vui/?$'), 'callable', self.handle_vui_root),
            (re.compile('^/vui/platforms/?$'), 'callable', self.handle_platforms),
            (re.compile('^/vui/platforms/[^/]+/?$'), 'callable', self.handle_platforms_platform),
            (re.compile('^/vui/platforms/[^/]+/agents/?$'), 'callable', self.handle_platforms_agents),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/?$'), 'callable', self.handle_platforms_agents_agent),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/rpc/?$'), 'callable', self.handle_platforms_agents_rpc),
            (re.compile('^/vui/platforms/[^/]+/agents/[^/]+/rpc/[^/]+/?$'), 'callable', self.handle_platforms_agents_rpc_method),
            (re.compile('^/vui/platforms/[^/]+/devices/?$'), 'callable', self.handle_platforms_devices),
            (re.compile('^/vui/platforms/[^/]+/devices/.*/?$'), 'callable', self.handle_platforms_devices),
            (re.compile('^/vui/platforms/[^/]+/historians/?$'), 'callable', self.handle_platforms_historians),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/?$'), 'callable', self.handle_platforms_historians_historian),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/topics/?$'), 'callable', self.handle_platforms_historians_historian_topics),
            (re.compile('^/vui/platforms/[^/]+/historians/[^/]+/topics/.*/?$'), 'callable', self.handle_platforms_historians_historian_topics),
            # (re.compile('^/vui/platforms/[^/]+/pubsub(/.*/)?$'), 'callable', self.handle_platforms_pubsub),
            # (re.compile('^/vui/platforms/[^/]+/pubsub(/.*/)?$'), 'callable', self.handle_platforms_pubsub_topic),
            # (re.compile('^/vui/devices/?$'), 'callable', self.handle_vui_devices),
            # (re.compile('^/vui/devices/.+/?$'), 'callable', self.handle_vui_devices_topic),
            # (re.compile('^/vui/devices/hierarchy/?$'), 'callable', self.handle_vui_devices_hierarchy),
            # (re.compile('^/vui/devices/hierarchy/.+/?$'), 'callable', self.handle_vui_devices_hierarchy_topic),
            # (re.compile('^/vui/historians/?$'), 'callable', self.handle_vui_historians),
            # (re.compile('^/vui/history/?$), 'callable', self.handle_vui_history)
        ]

    def handle_vui_root(self, env: dict, data: dict) -> Response:
        _log.debug('VUI: In handle_vui_root')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            path_info = env.get('PATH_INFO')
            response = json.dumps(self._find_active_sub_routes(['vui'], path_info=path_info))
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms(self, env: dict, data: dict) -> Response:
        _log.debug('VUI: In handle_platforms')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            platforms = []
            try:
                with open(join(environ['VOLTTRON_HOME'], 'external_platform_discovery.json')) as f:
                    platforms = [platform for platform in json.load(f).keys()]
            except FileNotFoundError:
                _log.info('Did not find VOLTTRON_HOME/external_platform_discovery.json. Only local platform available.')
            except Exception as e:
                _log.warning(f'Error opening external_platform_discovery.json: {e}')
            finally:
                if self.local_instance_name not in platforms:
                    platforms.insert(0, self.local_instance_name)
            response = json.dumps({p: normpath(path_info + '/' + p) for p in platforms})
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_platform(self, env: dict, data: dict) -> Response:
        _log.debug('VUI: In handle_platforms_platform')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        if request_method == 'GET':
            response = json.dumps(self._find_active_sub_routes(['vui', 'platforms'], path_info=path_info))
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_agents(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/
        :param env:
        :param data:
        :return:
        """
        # TODO: The API specification calls for a "packaged" query parameter that will return packaged agents which
        #  could be installed. We can get that from os.listdir(VOLTTRON_HOME/packaged), but skipping for now since
        #  there is no POST to the endpoint right now anyway.
        _log.debug('VUI: In handle_platforms_agents')
        _log.debug(env)
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform = re.match('^/vui/platforms/([^/]+)/agents/?$', path_info).groups()[0]
        if request_method == 'GET':
            agents = self._get_agents(platform)
            # TODO: How to catch invalid platform. The routing service seems to catch the exception and just log an
            #  error without raising it. Can we get a list of external platforms from somewhere? Again, the routing
            #  service seems to have that, but it isn't exposed as an RPC call anywhere that I can find....
            # return Response(json.dumps({'error': f'Platform: {platform} did not respond to request for agents.'}),
            #                400, content_type='application/json')
            response = json.dumps({agent: normpath(path_info + '/' + agent) for agent in agents.keys()})
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_agents_agent(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/
        :param env:
        :param data:
        :return:
        """
        _log.debug('VUI: In handle_platforms_agents_agent')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/?$', path_info).groups()
        # TODO: Check whether this agent is actually running.
        # TODO: Check whether certain types of actions are actually available for this agent (or require next endpoint for this)?
        if request_method == 'GET':
            response = json.dumps(self._find_active_sub_routes(['vui', 'platforms', 'agents'], path_info=path_info))
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_agents_rpc(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/rpc/
        :param env:
        :param data:
        :return:
        """
        _log.debug('VUI: In handle_platforms_agents_rpc')
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/rpc/?$', path_info).groups()
        if request_method == 'GET':
            try:
                method_dict = self._rpc(vip_identity, 'inspect', on_platform=platform)
            # TODO: Move this exception handling up to a wrapper.
            except TimeoutError as e:
                return Response(json.dumps({'error': f'Request Timed Out: {e}'}), 504, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({'error' f'Unexpected Error: {e}'}), 500, content_type='application/json')

            response = {method: normpath(path_info + '/' + method) for method in (method_dict.get('methods'))}
            return Response(json.dumps(response), 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_agents_rpc_method(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/agents/:vip_identity/rpc/
        :param env:
        :param data:
        :return:
        """
        _log.debug("VUI: in handle_platform_agents_rpc_method")
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")
        platform, vip_identity, method_name = re.match('^/vui/platforms/([^/]+)/agents/([^/]+)/rpc/([^/]+)/?$',
                                                       path_info).groups()
        _log.debug(f'VUI: Parsed - platform: {platform}, vip_identity: {vip_identity}, method_name: {method_name}')
        if request_method == 'GET':
            try:
                _log.debug('VUI: request_method was "GET"')
                method_dict = self._rpc(vip_identity, method_name + '.inspect', on_platform=platform)
                _log.debug(f'VUI: method_dict is: {method_dict}')
            # TODO: Move this exception handling up to a wrapper.
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except MethodNotFound as e:
                return Response(json.dumps({f'error': f'for agent {vip_identity}: {e}'}),
                                400, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({'error' f'Unexpected Error: {e}'}), 500, content_type='application/json')

            return Response(json.dumps(method_dict), 200, content_type='application/json')

        elif request_method == 'POST':
            # TODO: Should this also support lists?
            data = data if type(data) is dict else {}
            try:
                _log.debug('VUI: request_method was "POST')
                _log.debug(f'VUI: data has type: {type(data)}, value: {data}')
                result = self._rpc(vip_identity, method_name, **data, on_platform=platform)
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except MethodNotFound as e:
                return Response(json.dumps({f'error': f'for agent {vip_identity}: {e}'}),
                                400, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({'error' f'Unexpected Error: {e}'}), 500, content_type='application/json')

            return Response(json.dumps(result), 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_devices(self, env: dict, data: dict) -> Response:
        """
        Endpoints for /vui/platforms/:platform/devices/ and /vui/platforms/:platform/devices/:topic/
        :param env:
        :param data:
        :return:
        """
        def _get_allowed_write_selection(points, topic, regex, tag):
            # Query parameters:
            write_all = self._to_bool(query_params.get('write-all', 'false'))
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
        regex = query_params.get('regex')

        no_topic = re.match('^/vui/platforms/([^/]+)/devices/?$', path_info)
        if no_topic:
            platform, topic = no_topic.groups()[0], ''
        else:
            platform, topic = re.match('^/vui/platforms/([^/]+)/devices/(.*)/?$', path_info).groups()
            topic = topic[:-1] if topic[-1] == '/' else topic

        # Resolve tags if the tag query parameter is set:
        if tag:
            try:
                tag_list = self._rpc('platform.tagging', 'get_topics_by_tags', tag, on_platform=platform).get(timeout=5)
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
        # TODO: Move this exception handling up to a wrapper.
        except Timeout as e:
            return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
        except Exception as e:
            return Response(json.dumps({f'error': f'Error querying device topic {topic}: {e}'}),
                            400, content_type='application/json')

        if request_method == 'GET':
            # Query parameters:
            read_all = query_params.get('read-all', False)
            return_routes = query_params.get('routes', True)
            return_writability = query_params.get('writability', True)
            return_values = query_params.get('values', True)
            return_config = query_params.get('config', False)

            try:
                if read_all or all([n.is_point() for n in topic_nodes]):
                    # Either leaf values are explicitly requested, or all nodes are already points -- Return points:
                    ret_dict = defaultdict(dict)
                    if return_values:
                        ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                              [d.topic for d in points], on_platform=platform)
                        for k, v in ret_values[0].items():
                            ret_dict[k]['value'] = v
                        for k, e in ret_values[1].items():
                            ret_dict[k]['value_error'] = e
                    for point in points:
                        if return_routes:
                            ret_dict[point.topic]['route'] = f'/vui/platforms/{platform}/{point.identifier}'
                        if return_writability:
                            ret_dict[point.topic]['writability'] = point.data.get('Writable')
                        if return_config:
                            ret_dict[point.topic]['config'] = point.data

                    return Response(json.dumps(ret_dict), 200, content_type='application/json')
                else:
                    # All topics are not complete to points and read_all=False -- return route to next segments:
                    ret_dict = device_tree.get_children_dict([n.identifier for n in topic_nodes], replace_topic=topic,
                                                             prefix=f'/vui/platforms/{platform}')
                    return Response(json.dumps(ret_dict), 200, content_type='application/json')

            # TODO: Move this exception handling up to a wrapper.
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({f'error': f'Error querying device topic {topic}: {e}'}),
                                400, content_type='application/json')

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
                                       on_platform=platform)
                ret_dict = defaultdict(dict)
                for k in selected_routes.keys():
                    ret_dict[k]['route'] = selected_routes[k]
                    ret_dict[k]['set_error'] = ret_errors.get(k)
                    ret_dict[k]['writable'] = True if k not in unwritables else False
                if confirm_values:
                    ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                           [d.topic for d in points], on_platform=platform)
                    for k in selected_routes.keys():
                        ret_dict[k]['value'] = ret_values[0].get(k)
                        ret_dict[k]['value_check_error'] = ret_values[1].get(k)

                return Response(json.dumps(ret_dict), 200, content_type='application/json')

            # TODO: Move this exception handling up to a wrapper.
            except (LockError, OverrideError) as e:
                return Response(json.dumps({'error': e}), 409, content_type='application/json')
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({f'error': f'Error querying device topic {topic}: {e}'}),
                                400, content_type='application/json')

        elif request_method == 'DELETE':
            try:
                confirm_values, selected_routes, unwritables = _get_allowed_write_selection(points, topic, regex, tag)
            except ValueError as e:
                return Response(str(e), status=405, content_type='application/json')

            # Reset selected points:
            try:
                for t_node in topic_nodes:
                    if t_node.is_device():
                        self._rpc('platform.actuator', 'revert_device',
                                  requester_id=self._agent.core.identity, topic=t_node.topic, on_platform=platform)
                    elif t_node.is_point() and t_node.topic not in unwritables:
                        self._rpc('platform.actuator', 'revert_point',
                                  requester_id=self._agent.core.identity, topic=t_node.topic, on_platform=platform)

                ret_dict = defaultdict(dict)
                for k in selected_routes.keys():
                    ret_dict[k]['route'] = selected_routes[k]
                    ret_dict[k]['writable'] = True if k not in unwritables else False

                if confirm_values:
                    ret_values = self._rpc('platform.actuator', 'get_multiple_points',
                                           [d.topic for d in points], on_platform=platform)
                    for k in selected_routes.keys():
                        ret_dict[k]['value'] = ret_values[0].get(k)
                        ret_dict[k]['value_check_error'] = ret_values[1].get(k)
                return Response(json.dumps(ret_dict), 200, content_type='application/json')

            # TODO: Move this exception handling up to a wrapper.
            except (LockError, OverrideError) as e:
                return Response(json.dumps({'error': e}), 409, content_type='application/json')
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({f'error': f'Error querying device topic {topic}: {e}'}),
                                400, content_type='application/json')

        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_historians(self, env: dict, data: dict) -> Response:
        _log.debug("VUI: in handle_platforms_historians")
        path_info = env.get('PATH_INFO')

        _log.debug(f'path_info: {path_info}')
        request_method = env.get("REQUEST_METHOD")

        platform = re.match('^/vui/platforms/([^/]+)/historians/?$', path_info).groups()[0]
        _log.debug(f'platform: {platform}')

        if request_method == 'GET':
            agents = self._get_agents(platform)
            response = json.dumps(
                {agent: normpath(path_info + '/' + agent) for agent in agents.keys() if 'historian' in agent})
            return Response(response, 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def handle_platforms_historians_historian(self, env: dict, data: dict) -> Response:

        _log.debug("VUI: in handle_platforms_historians_historian")
        path_info = env.get('PATH_INFO')
        request_method = env.get("REQUEST_METHOD")

        platform, vip_identity = re.match('^/vui/platforms/([^/]+)/historians/([^/]+)/?$', path_info).groups()

        if request_method == 'GET':
            route_options = {'route_options': {'topics': f'/vui/platforms/{platform}/historians/{vip_identity}/topics'}}

            return Response(json.dumps(route_options), 200, content_type='application/json')
        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

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

        tag = query_params.get('tag')
        regex = query_params.get('regex')

        start = query_params.get('start')
        end = query_params.get('end')

        skip = int(query_params.get('skip') if query_params.get('skip') else 0)
        count = query_params.get('count')
        order = query_params.get('order') if query_params.get('order') else 'FIRST_TO_LAST'
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
                tag_list = self._rpc('platform.tagging', 'get_topics_by_tags', tag, on_platform=platform).get(timeout=5)
            except Timeout as e:
                return Response(json.dumps({'error': f'Tagging Service timed out: {e}'}),
                                504, content_type='application/json')
        else:
            tag_list = None
        try:
            historian_topics = self._rpc(historian, 'get_topic_list', on_platform=platform)
            historian_tree = TopicTree(historian_topics, 'historians').prune(topic, regex, tag_list)
            topic_nodes = historian_tree.get_matches(f'historians/{topic}' if topic else 'historians')

            if not topic_nodes:
                return Response(json.dumps({f'error': f'Historian topic {topic} not found on platform: {platform}.'}),
                                400, content_type='application/json')
            points = historian_tree.leaves()

        # TODO: Move this exception handling up to a wrapper.
        except Timeout as e:
            return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
        except Exception as e:
            return Response(json.dumps({f'error': f'Error querying historian topic {topic}: {e}'}),
                            400, content_type='application/json')

        if request_method == 'GET':
            read_all = query_params.get('read-all', False)
            return_routes = query_params.get('routes', True)
            return_values = query_params.get('values', True)

            try:
                if read_all or all([n.is_leaf() for n in topic_nodes]):
                    # Either leaf values are explicitly requested, or all nodes are already points -- Return points:
                    ret_dict = defaultdict(dict)

                    if return_values:
                        ret_values = self._rpc('platform.historian', 'query',
                                               [d.topic for d in points], start, end, agg_type, agg_period, skip, count,
                                               order, on_platform=platform)

                        # TODO: check return type for ret_values and based on that code
                        # to match single and multiple topics query results into the same structure
                        ret_values['values'] = ret_values['values'] if isinstance(ret_values['values'], dict) else {
                            points[0].topic: ret_values['values']}

                        for k, v in ret_values['values'].items():
                            ret_dict[k]['value'] = v
                        for k, m in ret_values['metadata'].items():
                            ret_dict[k]['metadata'] = m
                    for point in points:
                        if return_routes:
                            ret_dict[point.topic][
                                'route'] = f'/vui/platforms/{platform}/historians/{historian}/{point.identifier}'

                    return Response(json.dumps(ret_dict), 200, content_type='application/json')

                else:
                    # All topics are not complete to points and read_all=False -- return route to next segments:
                    ret_dict = historian_tree.get_children_dict([n.identifier for n in topic_nodes],
                                                                replace_topic=topic,
                                                                prefix=f'/vui/platforms/{platform}')
                    return Response(json.dumps(ret_dict), 200, content_type='application/json')


            # TODO: Move this exception handling up to a wrapper.
            except Timeout as e:
                return Response(json.dumps({'error': f'RPC Timed Out: {e}'}), 504, content_type='application/json')
            except Exception as e:
                return Response(json.dumps({f'error': f'Error querying historian topic {topic}: {e}'}),
                                400, content_type='application/json')

        else:
            return Response(f'Endpoint {request_method} {path_info} is not implemented.',
                            status='501 Not Implemented', content_type='text/plain')

    def _find_active_sub_routes(self, segments: list, path_info: str = None) -> dict or list:
        """
        Returns active routes with constant segments at the end of the route.
                If no path_info is provided, return only a list of the keys.
        """
        route_obj = self.active_routes
        for segment in segments:
            if route_obj and route_obj.get(segment) and route_obj.get(segment).get('endpoint-active'):
                route_obj = route_obj.get(segment)
            else:
                return {}
        keys = [k for k in route_obj.keys() if k != 'endpoint-active' and route_obj[k]['endpoint-active']]
        if not path_info:
            return keys
        else:
            return {k: normpath(path_info + '/' + k) for k in keys}

    # TODO: Add running parameter.
    def _get_agents(self, platform, running=True):
        _log.debug(f'VUI._get_agents: local_instance_name is: {self.local_instance_name}')
        try:
            agent_list = self._rpc('control', 'list_agents', on_platform=platform)
            peerlist = self._rpc('control', 'peerlist', on_platform=platform)
        except TimeoutError:
            agent_list = []
            peerlist = []
        except Exception as e:
            agent_list = []
            peerlist = []
            _log.debug(f'VUI._get_agents - UNEXPECTED EXCEPTION: {e}')
        agent_dict = {}
        _log.debug('VUI._get_agents: agent_list: {}'.format(agent_list))
        _log.debug('VUI._get_agents: peerlist: {}'.format(peerlist))
        # TODO: Add option to include system agents (e.g., control) instead of just installed or packaged agents?
        for agent in agent_list:
            agent_id = agent.pop('identity')
            agent['running'] = True if agent_id in peerlist else False
            agent_dict[agent_id] = agent
        return agent_dict

    def _rpc(self, vip_identity, method, *args, on_platform=None, **kwargs):
        external_platform = {'external_platform': on_platform}\
            if on_platform != self.local_instance_name else {}
        result = self._agent.vip.rpc.call(vip_identity, method, *args, **external_platform, **kwargs).get(timeout=5)
        return result

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

    # def admin(self, env, data):
    #     if env.get('REQUEST_METHOD') == 'POST':
    #         decoded = dict((k, v if len(v) > 1 else v[0])
    #                        for k, v in parse_qs(data).items())
    #         username = decoded.get('username')
    #
    # def verify_and_dispatch(self, env, data):
    #     """ Verify that the user is an admin and dispatch"""
    #
    #     from volttron.platform.web import get_bearer, NotAuthorized
    #     try:
    #         claims = self._rpc_caller(PLATFORM_WEB, 'get_user_claims', get_bearer(env)).get()
    #     except NotAuthorized:
    #         _log.error("Unauthorized user attempted to connect to {}".format(env.get('PATH_INFO')))
    #         return Response('<h1>Unauthorized User</h1>', status="401 Unauthorized")
    #
    #     # Make sure we have only admins for viewing this.
    #     if 'admin' not in claims.get('groups'):
    #         return Response('<h1>Unauthorized User</h1>', status="401 Unauthorized")
    #
    #     path_info = env.get('PATH_INFO')
    #     if path_info.startswith('/admin/api/'):
    #         return self.__api_endpoint(path_info[len('/admin/api/'):], data)
    #
    #     return Response(resp)
