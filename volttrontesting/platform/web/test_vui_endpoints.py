import mock
import pytest
from unittest.mock import MagicMock

import re
import json
from werkzeug import Response

from volttron.platform.vip.agent import Agent
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.vui_endpoints import VUIEndpoints
from volttrontesting.utils.utils import AgentMock
from volttrontesting.utils.web_utils import get_test_web_env
from volttron.platform.vip.agent.results import AsyncResult

import logging  # TODO: Shouldn't need logger once this is complete.
_log = logging.getLogger()


class QueryHelper:
    """
    Query helper allows us to mock out the Query subsystem and return default
    values for calls to it.
    """

    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result('my_instance_name')
        return result


@pytest.fixture()
def mock_platform_web_service() -> PlatformWebService:
    PlatformWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)
    with mock.patch(target='volttron.platform.web.vui_endpoints.Query', new=QueryHelper):
        platform_web = PlatformWebService(serverkey=MagicMock(),
                                         identity=MagicMock(),
                                         address=MagicMock(),
                                         bind_web_address=MagicMock())
        # Internally the register uses this value to determine the caller's identity
        # to allow the platform web service to map calls back to the proper agent
        platform_web.vip.rpc.context.vip_message.peer.return_value = "foo"
        platform_web.core.volttron_home = 'foo_home'
        platform_web.core.instance_name = 'my_instance_name'

        yield platform_web


def gen_response_codes(valid_codes: list, exclude: list = None):
    exclude = exclude if exclude else []
    http_methods = ('GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH')
    valid = [(f'{code}', '200') for code in http_methods if code in valid_codes]
    invalid = [(f'{code}', '501') for code in http_methods if code not in valid_codes and code not in exclude]
    return valid + invalid


def check_response_codes(response, status):
    assert isinstance(response, Response)
    assert status in response.status


def check_route_options_return(response, keys: list = None, leading_path: str = None):
    body = json.loads(response.response[0])
    assert isinstance(body, dict)
    assert isinstance(body['route_options'], dict)
    if keys:
        assert len(keys) == len(body['route_options'].keys())
        assert all([key in body['route_options'].keys() for key in keys])
    if keys and leading_path:
        assert all([re.match(f'{leading_path}/[^/]+/?$', value) for value in body['route_options'].values()])
    return body['route_options']


def test_get_routes(mock_platform_web_service):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    routes = vui_endpoints.get_routes()
    assert isinstance(routes, list)
    assert all([isinstance(route, tuple) for route in routes])
    assert all([isinstance(route[0], re.Pattern) for route in routes])
    assert all([route[1] == 'callable' for route in routes])
    assert all([hasattr(vui_endpoints, route[2].__name__) and callable(getattr(vui_endpoints, route[2].__name__))
                for route in routes])


@pytest.mark.parametrize('platforms',
    [
        ['my_instance_name', 'foo', 'bar', 'baz'],
        ['foo', 'bar', 'baz'],
        list(),
        FileNotFoundError,
        Exception
    ]
)
def test_get_platforms(mock_platform_web_service, platforms):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    if type(platforms) is list:
        external_platforms_discovery_json = {p: {} for p in platforms}
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(external_platforms_discovery_json))):
            this_instance = mock_platform_web_service.core.instance_name
            if this_instance not in platforms:
                platforms.insert(0, this_instance)
            retval = vui_endpoints._get_platforms()
            assert retval == platforms
    else:
        with mock.patch('builtins.open', mock.mock_open()) as mocked_open:
            mocked_open.side_effect = platforms
            retval = vui_endpoints._get_platforms()
            assert retval == [vui_endpoints._agent.core.instance_name]


def test_find_active_roots(mock_platform_web_service):
    pass  # TODO: test_find_active_roots


def test_to_bool(mock_platform_web_service):
    pass  # TODO: test_to_bool


def test_route_options(mock_platform_web_service):
    pass  # TODO: test_route_options


def test_rpc(mock_platform_web_service):
    pass  # TODO: test_rpc


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_vui_root(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui', method=method)
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_vui_root(env, {})
    check_response_codes(response, status)
    if '200' in response.status:
        check_route_options_return(response)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms', method=method)
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('platforms',
    [
        ['my_instance_name', 'foo', 'bar', 'baz'],
        ['foo', 'bar', 'baz'],
        list(),
        FileNotFoundError,
        Exception
    ]
)
def test_handle_platforms_response(mock_platform_web_service, platforms):
    path = '/vui/platforms'
    env = get_test_web_env(path, method='GET')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    if type(platforms) is list:
        external_platforms_discovery_json = {p: {} for p in platforms}
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(external_platforms_discovery_json))):
            this_instance = mock_platform_web_service.core.instance_name
            if this_instance not in platforms:
                platforms.insert(0, this_instance)
            response = vui_endpoints.handle_platforms(env, {})
            route_options = check_route_options_return(response, platforms, path)
    else:
        with mock.patch('builtins.open', mock.mock_open()) as mocked_open:
            mocked_open.side_effect = platforms
            response = vui_endpoints.handle_platforms(env, {})
            route_options = check_route_options_return(response, [vui_endpoints.local_instance_name], path)
    assert '200' in response.status
    assert list(route_options.keys())[0] == vui_endpoints.local_instance_name


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_platform_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name', method=method)
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_platform(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize("platform", ['my_instance_name', 'other_instance_name', 'not_a_platform'])
def test_handle_platforms_platform_response(mock_platform_web_service, platform):
    path = f'/vui/platforms/{platform}'
    env = get_test_web_env(path, method='GET')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps({'other_instance_name': {}}))):
        response = vui_endpoints.handle_platforms_platform(env, {})
        if platform in ['my_instance_name', 'other_instance_name']:
            check_route_options_return(response, leading_path=path)
        else:
            assert '400' in response.status


def _mock_agents_rpc(peer, meth, on_platform=None):
    if meth == 'list_agents':
        return [{'uuid': '1', 'identity': 'run1'}, {'uuid': '2', 'identity': 'run2'},
                {'uuid': '3', 'identity': 'stopped1'}, {'uuid': '4', 'identity': 'stopped2'}]
    elif meth == 'status_agents':
        return [['1', '', ['', '']], ['2', '', ['', '']]]
    elif meth == 'peerlist':
        return ['run1', 'run2', 'hid1', 'hid2']


@pytest.mark.parametrize(
    'agent_state, include_hidden, expected', [
        ('running', False, ['run1', 'run2']),
        ('running', True, ['run1', 'run2', 'hid1', 'hid2']),
        ('installed', False, ['run1', 'run2', 'stopped1', 'stopped2']),
        ('installed', True, ['run1', 'run2', 'stopped1', 'stopped2', 'hid1', 'hid2']),
        ('packaged', False, ['packaged1', 'packaged2']),
        ('packaged', True, ['packaged1', 'packaged2'])
    ]
)
def test_get_agents(mock_platform_web_service, agent_state, include_hidden, expected):
    with mock.patch('os.listdir') as mocked_dir:
        mocked_dir.return_value = ['packaged1.whl', 'packaged2.whl']
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        vui_endpoints._rpc = _mock_agents_rpc
        result = vui_endpoints._get_agents('my_instance_name', agent_state, include_hidden)
    assert isinstance(result, list)
    assert result == expected


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_agents_status_code(mock_platform_web_service, method, status):
        env = get_test_web_env('/vui/platforms/my_instance_name/agents', method=method)
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        response = vui_endpoints.handle_platforms_agents(env, {})
        check_response_codes(response, status)


@pytest.mark.parametrize(
    'agent_state, include_hidden, expected', [
        ('running', False, ['run1', 'run2']),
        ('running', True, ['run1', 'run2', 'hid1', 'hid2']),
        ('installed', False, ['run1', 'run2', 'stopped1', 'stopped2']),
        ('installed', True, ['run1', 'run2', 'stopped1', 'stopped2', 'hid1', 'hid2'])
    ]
)
@pytest.mark.parametrize("platform", ['my_instance_name', 'other_instance_name', 'not_a_platform'])
def test_handle_platforms_agents_response(mock_platform_web_service, platform, agent_state, include_hidden, expected):
    path = f'/vui/platforms/{platform}/agents'
    env = get_test_web_env(path, method='GET')
    env['agent-state'] = agent_state
    env['include-hidden'] = include_hidden
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps({'other_instance_name': {}}))):
        response = vui_endpoints.handle_platforms_agents(env, {})
        if platform in ['my_instance_name', 'other_instance_name']:
            check_route_options_return(response, keys=expected, leading_path=path)
        else:
            assert '400' in response.status

