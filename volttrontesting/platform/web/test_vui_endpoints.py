import mock
import pytest
from unittest.mock import MagicMock

import re
import json
import pickle
from werkzeug import Response

mock.patch('volttron.platform.web.vui_endpoints.endpoint', lambda x: x).start()

from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.results import AsyncResult
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.vui_endpoints import VUIEndpoints
from volttrontesting.utils.utils import AgentMock
from volttrontesting.utils.web_utils import get_test_web_env

import logging  # TODO: Shouldn't need logger once this is complete.
_log = logging.getLogger()

ACTIVE_ROUTES = {
    'vui': {'endpoint-active': True,
            'platforms': {'endpoint-active': True,
                          'agents': {'endpoint-active': True,
                                     'configs': {'endpoint-active': True},
                                     'enabled': {'endpoint-active': True},
                                     'front-ends': {'endpoint-active': False},
                                     'health': {'endpoint-active': False},
                                     'pubsub': {'endpoint-active': False},
                                     'rpc': {'endpoint-active': True},
                                     'running': {'endpoint-active': True},
                                     'status': {'endpoint-active': True},
                                     'tag': {'endpoint-active': True}
                                     },
                          'devices': {'endpoint-active': True},
                          'status': {'endpoint-active': False}
                          },
            'historians': {'endpoint-active': False}
            }
}

DEV_TREE = b'\x80\x04\x952\x11\x00\x00\x00\x00\x00\x00\x8c volttron.platform.web.topic_tree\x94\x8c\nDeviceTree\x94\x93\x94)\x81\x94}\x94(\x8c\x0b_identifier\x94\x8c$43dd9fcc-0066-11ec-afd5-f834419e14e3\x94\x8c\nnode_class\x94h\x00\x8c\nDeviceNode\x94\x93\x94\x8c\x06_nodes\x94}\x94(\x8c\x07devices\x94h\t)\x81\x94}\x94(h\x05h\x0c\x8c\x04_tag\x94h\x0c\x8c\x08expanded\x94\x88\x8c\x0c_predecessor\x94}\x94h\x06Ns\x8c\x0b_successors\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04list\x94\x93\x94\x85\x94R\x94h\x06]\x94\x8c\x0edevices/Campus\x94as\x8c\x04data\x94N\x8c\x10_initial_tree_id\x94h\x06\x8c\x0csegment_type\x94\x8c\nTOPIC_ROOT\x94\x8c\x05topic\x94\x8c\x00\x94ubh\x1dh\t)\x81\x94}\x94(h\x05h\x1dh\x0f\x8c\x06Campus\x94h\x10\x88h\x11}\x94h\x06h\x0csh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94(\x8c\x18devices/Campus/Building1\x94\x8c\x18devices/Campus/Building2\x94\x8c\x18devices/Campus/Building3\x94esh\x1eNh\x1fh\x06h \x8c\rTOPIC_SEGMENT\x94h"\x8c\x06Campus\x94ubh+h\t)\x81\x94}\x94(h\x05h+h\x0f\x8c\tBuilding1\x94h\x10\x88h\x11}\x94h\x06h\x1dsh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94\x8c\x1edevices/Campus/Building1/Fake1\x94ash\x1eNh\x1fh\x06h h.h"\x8c\x10Campus/Building1\x94ubh7h\t)\x81\x94}\x94(h\x05h7h\x0f\x8c\x05Fake1\x94h\x10\x88h\x11}\x94h\x06h+sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94(\x8c3devices/Campus/Building1/Fake1/SampleWritableFloat1\x94\x8c*devices/Campus/Building1/Fake1/SampleBool1\x94esh\x1e}\x94(\x8c\rdriver_config\x94}\x94\x8c\x08interval\x94K<\x8c\x08timezone\x94\x8c\nUS/Pacific\x94\x8c\x0bdriver_type\x94\x8c\nfakedriver\x94\x8c\x19publish_breadth_first_all\x94\x89\x8c\x13publish_depth_first\x94\x89\x8c\x15publish_breadth_first\x94\x89\x8c\x06campus\x94\x8c\x06campus\x94\x8c\x08building\x94\x8c\x08building\x94\x8c\x04unit\x94\x8c\x0bfake_device\x94uh\x1fh\x06h \x8c\x06DEVICE\x94h"\x8c\x16Campus/Building1/Fake1\x94ubh@h\t)\x81\x94}\x94(h\x05h@h\x0f\x8c\x14SampleWritableFloat1\x94h\x10\x88h\x11}\x94h\x06h7sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(\x8c\nPoint Name\x94\x8c\x14SampleWritableFloat1\x94\x8c\x05Units\x94\x8c\x03PPM\x94\x8c\rUnits Details\x94\x8c\x111000.00 (default)\x94\x8c\x08Writable\x94\x8c\x04TRUE\x94\x8c\x0eStarting Value\x94\x8c\x0210\x94\x8c\x04Type\x94\x8c\x05float\x94\x8c\x05Notes\x94\x8c-Setpoint to enable demand control ventilation\x94uh\x1fh\x06h \x8c\x05POINT\x94h"\x8c+Campus/Building1/Fake1/SampleWritableFloat1\x94ubhAh\t)\x81\x94}\x94(h\x05hAh\x0f\x8c\x0bSampleBool1\x94h\x10\x88h\x11}\x94h\x06\x8c\x1edevices/Campus/Building1/Fake1\x94sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(h]\x8c\x0bSampleBool1\x94h_\x8c\x08On / Off\x94ha\x8c\x06on/off\x94hc\x8c\x05FALSE\x94he\x8c\x04TRUE\x94hg\x8c\x07boolean\x94hi\x8c$Status indidcator of cooling stage 1\x94uh\x1fh\x06h hkh"\x8c"Campus/Building1/Fake1/SampleBool1\x94ubh,h\t)\x81\x94}\x94(h\x05h,h\x0f\x8c\tBuilding2\x94h\x10\x88h\x11}\x94h\x06\x8c\x0edevices/Campus\x94sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94\x8c\x1edevices/Campus/Building2/Fake1\x94ash\x1eNh\x1fh\x06h h.h"\x8c\x10Campus/Building2\x94ubh\x86h\t)\x81\x94}\x94(h\x05h\x86h\x0f\x8c\x05Fake1\x94h\x10\x88h\x11}\x94h\x06h,sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94(\x8c3devices/Campus/Building2/Fake1/SampleWritableFloat1\x94\x8c*devices/Campus/Building2/Fake1/SampleBool1\x94esh\x1e}\x94(\x8c\rdriver_config\x94}\x94\x8c\x08interval\x94K<\x8c\x08timezone\x94\x8c\nUS/Pacific\x94\x8c\x0bdriver_type\x94\x8c\nfakedriver\x94\x8c\x19publish_breadth_first_all\x94\x89\x8c\x13publish_depth_first\x94\x89\x8c\x15publish_breadth_first\x94\x89\x8c\x06campus\x94\x8c\x06campus\x94\x8c\x08building\x94\x8c\x08building\x94\x8c\x04unit\x94\x8c\x0bfake_device\x94uh\x1fh\x06h hSh"\x8c\x16Campus/Building2/Fake1\x94ubh\x8fh\t)\x81\x94}\x94(h\x05h\x8fh\x0f\x8c\x14SampleWritableFloat1\x94h\x10\x88h\x11}\x94h\x06h\x86sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(\x8c\nPoint Name\x94\x8c\x14SampleWritableFloat1\x94\x8c\x05Units\x94\x8c\x03PPM\x94\x8c\rUnits Details\x94\x8c\x111000.00 (default)\x94\x8c\x08Writable\x94\x8c\x04TRUE\x94\x8c\x0eStarting Value\x94\x8c\x0210\x94\x8c\x04Type\x94\x8c\x05float\x94\x8c\x05Notes\x94\x8c-Setpoint to enable demand control ventilation\x94uh\x1fh\x06h hkh"\x8c+Campus/Building2/Fake1/SampleWritableFloat1\x94ubh\x90h\t)\x81\x94}\x94(h\x05h\x90h\x0f\x8c\x0bSampleBool1\x94h\x10\x88h\x11}\x94h\x06\x8c\x1edevices/Campus/Building2/Fake1\x94sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(h\xab\x8c\x0bSampleBool1\x94h\xad\x8c\x08On / Off\x94h\xaf\x8c\x06on/off\x94h\xb1\x8c\x05FALSE\x94h\xb3\x8c\x04TRUE\x94h\xb5\x8c\x07boolean\x94h\xb7\x8c$Status indidcator of cooling stage 1\x94uh\x1fh\x06h hkh"\x8c"Campus/Building2/Fake1/SampleBool1\x94ubh-h\t)\x81\x94}\x94(h\x05h-h\x0f\x8c\tBuilding3\x94h\x10\x88h\x11}\x94h\x06\x8c\x0edevices/Campus\x94sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94\x8c\x1edevices/Campus/Building3/Fake1\x94ash\x1eNh\x1fh\x06h h.h"\x8c\x10Campus/Building3\x94ubh\xd3h\t)\x81\x94}\x94(h\x05h\xd3h\x0f\x8c\x05Fake1\x94h\x10\x88h\x11}\x94h\x06h-sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94(\x8c3devices/Campus/Building3/Fake1/SampleWritableFloat1\x94\x8c*devices/Campus/Building3/Fake1/SampleBool1\x94esh\x1e}\x94(\x8c\rdriver_config\x94}\x94\x8c\x08interval\x94K<\x8c\x08timezone\x94\x8c\nUS/Pacific\x94\x8c\x0bdriver_type\x94\x8c\nfakedriver\x94\x8c\x19publish_breadth_first_all\x94\x89\x8c\x13publish_depth_first\x94\x89\x8c\x15publish_breadth_first\x94\x89\x8c\x06campus\x94\x8c\x06campus\x94\x8c\x08building\x94\x8c\x08building\x94\x8c\x04unit\x94\x8c\x0bfake_device\x94uh\x1fh\x06h hSh"\x8c\x16Campus/Building3/Fake1\x94ubh\xdch\t)\x81\x94}\x94(h\x05h\xdch\x0f\x8c\x14SampleWritableFloat1\x94h\x10\x88h\x11}\x94h\x06h\xd3sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(\x8c\nPoint Name\x94\x8c\x14SampleWritableFloat1\x94\x8c\x05Units\x94\x8c\x03PPM\x94\x8c\rUnits Details\x94\x8c\x111000.00 (default)\x94\x8c\x08Writable\x94\x8c\x04TRUE\x94\x8c\x0eStarting Value\x94\x8c\x0210\x94\x8c\x04Type\x94\x8c\x05float\x94\x8c\x05Notes\x94\x8c-Setpoint to enable demand control ventilation\x94uh\x1fh\x06h hkh"\x8c+Campus/Building3/Fake1/SampleWritableFloat1\x94ubh\xddh\t)\x81\x94}\x94(h\x05h\xddh\x0f\x8c\x0bSampleBool1\x94h\x10\x88h\x11}\x94h\x06\x8c\x1edevices/Campus/Building3/Fake1\x94sh\x13h\x16h\x19\x85\x94R\x94h\x06]\x94sh\x1e}\x94(h\xf8\x8c\x0bSampleBool1\x94h\xfa\x8c\x08On / Off\x94h\xfc\x8c\x06on/off\x94h\xfe\x8c\x05FALSE\x94j\x00\x01\x00\x00\x8c\x04TRUE\x94j\x02\x01\x00\x00\x8c\x07boolean\x94j\x04\x01\x00\x00\x8c$Status indidcator of cooling stage 1\x94uh\x1fh\x06h hkh"\x8c"Campus/Building3/Fake1/SampleBool1\x94ubu\x8c\x04root\x94h\x0c\x8c\x07_reader\x94X\x9c\x01\x00\x00devices\n\xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 Campus\n    \xe2\x94\x9c\xe2\x94\x80\xe2\x94\x80 Building1\n    \xe2\x94\x82   \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 Fake1\n    \xe2\x94\x82       \xe2\x94\x9c\xe2\x94\x80\xe2\x94\x80 SampleBool1\n    \xe2\x94\x82       \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 SampleWritableFloat1\n    \xe2\x94\x9c\xe2\x94\x80\xe2\x94\x80 Building2\n    \xe2\x94\x82   \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 Fake1\n    \xe2\x94\x82       \xe2\x94\x9c\xe2\x94\x80\xe2\x94\x80 SampleBool1\n    \xe2\x94\x82       \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 SampleWritableFloat1\n    \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 Building3\n        \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 Fake1\n            \xe2\x94\x9c\xe2\x94\x80\xe2\x94\x80 SampleBool1\n            \xe2\x94\x94\xe2\x94\x80\xe2\x94\x80 SampleWritableFloat1\n\x94ub.'


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
        platform_web.get_user_claims = lambda x: {'groups': ['vui']}

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


def check_links_return(response, keys: list = None, leading_path: str = None):
    body = json.loads(response.response[0])
    assert isinstance(body, dict)
    assert isinstance(body['links'], dict)
    if keys:
        assert len(keys) == len(body['links'].keys())
        assert all([key in body['links'].keys() for key in keys])
    if keys and leading_path:
        assert all([re.match(f'{leading_path}/[^/]+/?$', value) for value in body['links'].values()])
    return body['links']


def test_get_routes(mock_platform_web_service):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    routes = vui_endpoints.get_routes()
    assert isinstance(routes, list)
    assert all([isinstance(route, tuple) for route in routes])
    assert all([isinstance(route[0], re.Pattern) for route in routes])
    assert all([route[1] == 'callable' for route in routes])
    assert all([hasattr(vui_endpoints, route[2].__name__) and callable(getattr(vui_endpoints, route[2].__name__))
                for route in routes])


@pytest.mark.parametrize('platforms', [
    ['my_instance_name', 'foo', 'bar', 'baz'],
    ['foo', 'bar', 'baz'],
    list(),
    FileNotFoundError,
    Exception
])
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


@pytest.mark.parametrize('segments, expected_keys, expected_links',
                         [
                             (['vui'], ['platforms'], {'platforms': '/foo/bar/platforms'}),
                             (['vui', 'platforms'], ['agents', 'devices'],
                              {'agents': '/foo/bar/agents', 'devices': '/foo/bar/devices'}),
                             (['vui', 'platforms', 'agents'], ['configs', 'enabled', 'rpc', 'running', 'status', 'tag'],
                              {'rpc': '/foo/bar/rpc', 'configs': '/foo/bar/configs', 'enabled': '/foo/bar/enabled',
                              'running': '/foo/bar/running', 'status': '/foo/bar/status', 'tag': '/foo/bar/tag'}),
                             (['vui', 'platforms', 'agents', 'configs'], [], {}),
                             (['vui', 'platforms', 'agents', 'rpc'], [], {}),
                             (['vui', 'platforms', 'devices'], [], {}),
                             (['vui', 'platforms', 'status'], [], {}),
                             (['vui', 'historians'], [], {}),
                         ])
def test_find_active_sub_routes(mock_platform_web_service, segments, expected_keys, expected_links):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints.active_routes = ACTIVE_ROUTES
    assert vui_endpoints._find_active_sub_routes(segments) == expected_keys
    assert vui_endpoints._find_active_sub_routes(segments, '/foo/bar', False) == expected_links
    assert vui_endpoints._find_active_sub_routes(segments, '/foo/bar') == {'links': expected_links}


@pytest.mark.parametrize('values, expected',
                         [
                             ([], None),
                             ('true', True),
                             ('false', False),
                             (['True', 'true', 'T', 't', '1', 'F', 'f', 1, '2', ''],
                              [True, True, True, True, True, False, False, True, False, False])
                         ])
def test_to_bool(mock_platform_web_service, values, expected):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    assert vui_endpoints._to_bool(values) == expected


@pytest.mark.parametrize('option_segments, expected_links',
                         [
                             ([], {}),
                             (['foo', 'bar', 'baz'],
                              {'foo': '/foo/bar/foo', 'bar': '/foo/bar/bar', 'baz': '/foo/bar/baz'})
                         ])
def test_links(mock_platform_web_service, option_segments, expected_links):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    assert vui_endpoints._links('/foo/bar', option_segments, False) == expected_links
    assert vui_endpoints._links('/foo/bar', option_segments) == {'links': expected_links}


def test_rpc(mock_platform_web_service):
    def rpc_caller(peer, method, *args, **kwargs):
        class MockAsyncResponse:
            @staticmethod
            def get(timeout=5):
                return True
        if kwargs.get('external_platform') and kwargs['external_platform'] == 'my_instance_name':
            raise Exception('Passed this instance as external platform.')
        return MockAsyncResponse

    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._agent.vip.rpc.call = rpc_caller
    assert vui_endpoints._rpc('a_vip_id', 'some_method', external_platform='my_instance_name') is True
    assert vui_endpoints._rpc('a_vip_id', 'some_method', external_platform='other_platform') is True


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_vui_root(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui', method=method, HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_vui_root(env, {})
    check_response_codes(response, status)
    if '200' in response.status:
        check_links_return(response)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms', method=method, HTTP_AUTHORIZATION='BEARER foo')
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
                         ])
def test_handle_platforms_response(mock_platform_web_service, platforms):
    path = '/vui/platforms'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    if type(platforms) is list:
        external_platforms_discovery_json = {p: {} for p in platforms}
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(external_platforms_discovery_json))):
            this_instance = mock_platform_web_service.core.instance_name
            if this_instance not in platforms:
                platforms.insert(0, this_instance)
            response = vui_endpoints.handle_platforms(env, {})
            links = check_links_return(response, platforms, path)
    else:
        with mock.patch('builtins.open', mock.mock_open()) as mocked_open:
            mocked_open.side_effect = platforms
            response = vui_endpoints.handle_platforms(env, {})
            links = check_links_return(response, [vui_endpoints.local_instance_name], path)
    assert '200' in response.status
    assert list(links.keys())[0] == vui_endpoints.local_instance_name


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_platform_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name', method=method, HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_platform(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize("platform", ['my_instance_name', 'other_instance_name', 'not_a_platform'])
def test_handle_platforms_platform_response(mock_platform_web_service, platform):
    path = f'/vui/platforms/{platform}'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps({'other_instance_name': {}}))):
        response = vui_endpoints.handle_platforms_platform(env, {})
        if platform in ['my_instance_name', 'other_instance_name']:
            check_links_return(response, leading_path=path)
        else:
            assert '400' in response.status


def _mock_agents_rpc(peer, meth, *args, external_platform=None, **kwargs):
    list_of_agents = [{'name': 'rn1', 'uuid': '1', 'tag': 'r1', 'identity': 'run1', 'priority': None},
                      {'name': 'rn2', 'uuid': '2', 'tag': 'r2', 'identity': 'run2', 'priority': 50},
                      {'name': 'stp1', 'uuid': '3', 'tag': 'st1', 'identity': 'stopped1', 'priority': None},
                      {'name': 'stp2', 'uuid': '4', 'tag': 'st2', 'identity': 'stopped2', 'priority': 35}]
    config_definition_list = [{'identity': 'run1', 'configs': {'config1': {'setting1': 1, 'setting2': 2},
                                                               'config2': {'setting1': 3, 'setting2': 4}}},
                              {'identity': 'run2', 'configs': {'config1': {'setting1': 5, 'setting2': 6},
                                                               'config2': {'setting1': 7, 'setting2': 8}}}]
    if peer == 'config.store' and meth == 'manage_get':
        config_list = [a['configs'].get(args[1]) for a in config_definition_list if a['identity'] == args[0]]
        if not config_list or config_list == [None]:
            raise RemoteError(f'''builtins.KeyError('No configuration file \"{args[1]}\" for VIP IDENTIY {args[0]}')''',
                              exc_info={"exc_type": '', "exc_args": []})
        return config_list[0] if config_list else []
    elif peer == 'config.store' and meth == 'manage_list_configs':
        config_list = [a['configs'].keys() for a in config_definition_list if a['identity'] == args[0]]
        return config_list[0] if config_list else []
    elif peer == 'config.store' and meth == 'manage_list_stores':
        return [a['identity'] for a in config_definition_list]
    elif peer == 'control' and meth == 'list_agents':
        return list_of_agents
    elif peer == 'control' and meth == 'identity_exists':
        uuid = [a['uuid'] for a in list_of_agents if a['identity'] == args[0]]
        return uuid[0] if uuid else None
    elif peer == 'control' and meth == 'status_agents':
        return [['1', '', [10, None]], ['2', '', [11, None]], ['4', '', [12, 0]]]
    elif peer == 'control' and meth == 'peerlist':
        return ['run1', 'run2', 'hid1', 'hid2']
    elif peer == 'control' and meth == 'inspect':
        return {'methods': ['list_agents', 'peerlist', 'status_agents']}
    elif peer == 'control' and meth == 'status_agents.inspect':
        return {'params': {}}
    elif peer == 'agents_rpc' and meth == 'kw_only':
        return [kwargs['foo'], kwargs['bar']]
    elif peer == 'agents_rpc' and meth == 'args_and_kw':
        return [*args, kwargs['foo'], kwargs['bar']]
    elif peer == 'agents_rpc' and meth == 'args_only':
        return [*args]


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
    env = get_test_web_env('/vui/platforms/my_instance_name/agents', method=method, HTTP_AUTHORIZATION='BEARER foo')
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
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    env['QUERY_STRING'] = f'agent-state={agent_state}&include-hidden={str(include_hidden).lower()}'
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps({'other_instance_name': {}}))):
        response = vui_endpoints.handle_platforms_agents(env, {})
        if platform in ['my_instance_name', 'other_instance_name']:
            check_links_return(response, keys=expected, leading_path=path)
        else:
            assert '400' in response.status


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_agents_agent_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/agent_vip', method=method,
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_agents_agent(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', ['configs', 'enabled', 'rpc', 'running', 'status', 'tag']),
    ('stopped1', ['configs', 'enabled', 'running', 'status', 'tag']),
    ('not.installed.agent', ['configs'])
    ])
def test_handle_platforms_agents_agent_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints.active_routes = ACTIVE_ROUTES
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_agent(env, {})
    check_links_return(response, keys=expected, leading_path=path)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], ['POST', 'DELETE']))
def test_handle_platforms_agents_configs_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/configs', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], ['PUT', 'DELETE']))
def test_handle_platforms_agents_configs_config_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/configs/config1', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize("vip_identity, expected", [
    ('-', ["run1", "run2"]),
    ('run1', {"links": {"config1": "/vui/platforms/my_instance_name/agents/run1/configs/config1",
                                "config2": "/vui/platforms/my_instance_name/agents/run1/configs/config2"}}),
    ('does_not_exist',  {"links": {}})  #needs to be changed as code is changed
])
def test_handle_platforms_agents_configs_get_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/configs'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize("vip_identity, config_name, expected", [
    ('run1', 'config1', {'setting1': 1, 'setting2': 2}),
    ('run2', 'config2', {'setting1': 7, 'setting2': 8}),
    ('does_not_exist', 'config1',
     {"Error": "builtins.KeyError('No configuration file \"config1\" for VIP IDENTIY does_not_exist')"}),
    ('run1', 'does_not_exist',
     {"Error": "builtins.KeyError('No configuration file \"does_not_exist\" for VIP IDENTIY run1')"})
   ])
def test_handle_platforms_agents_configs_config_get_response(mock_platform_web_service, vip_identity, config_name,
                                                             expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/configs/{config_name}'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize('vip_identity, config_name, data_given, data_passed, config_type, status', [
    ('run1', 'config', {"setting1": 30, "setting2": 0}, '{"setting1": 30, "setting2": 0}', 'application/json',
     '204'),
    ('run1', 'config', '"setting1", 30, "setting2", 0', '"setting1", 30, "setting2", 0', 'text/csv',
     '204'),
    ('run1', 'config', '"setting1" 30 "setting2" 0', '"setting1" 30 "setting2" 0', 'text/plain',
     '204'),
    ('run1', 'config', "something else", "something else", 'invalid_type', '400')
])
def test_handle_platforms_agents_configs_config_put_response(mock_platform_web_service, vip_identity, config_name,
                                                             data_given, data_passed, config_type,
                                                             status):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/configs/{config_name}'
    env = get_test_web_env(path, method='PUT', CONTENT_TYPE=config_type, HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_configs(env, data_given)
    check_response_codes(response, status)
    config_type = re.search(r'([^\/]+$)', config_type).group() if config_type in ['application/json',
                                                                                  'text/csv'] else 'raw'
    if status == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('config.store', 'manage_store', vip_identity, config_name,
                                                       data_passed, config_type, external_platform='my_instance_name')])
    elif status == '400':
        assert json.loads(response.response[0]) == \
               {"Error": "The configuration type can only be 'JSON', 'CSV' and 'RAW.'"}



@pytest.mark.parametrize('vip_identity, config_name, data_given, data_passed, config_type, status', [
    ('run1', 'config', {'setting1': 30, 'setting2': 0}, {'setting1': 30, 'setting2': 0}, 'application/json',
     '201'),
    ('run1', 'config', "'setting1', 30, 'setting2', 0", "'setting1', 30, 'setting2', 0", 'text/csv',
     '201'),
    ('run1', 'config', "'setting1'  30 'setting2' 0", "'setting1' 30 'setting2' 0", 'text/plain',
     '201'),
    ('run1', 'config', "something else", "something else", 'invalid_type', '400'),
    ('run1', 'config1', {'setting1': 30, 'setting2': 0}, {'setting1': 30, 'setting2': 0}, 'application/json', '409')
])
def test_handle_platforms_agents_configs_post_response(mock_platform_web_service, vip_identity, config_name,
                                                             data_given, data_passed, config_type,
                                                             status):
    query_string = f'config-name={config_name}' if config_name else ''
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/configs'
    env = get_test_web_env(path, method='POST', query_string=query_string, CONTENT_TYPE=config_type,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_configs(env, data_given)
    check_response_codes(response, status)
    if status == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('config.store', 'manage_store', vip_identity, config_name,
                                                       data_passed, config_type, external_platform='my_instance_name')])
    elif status == '400':
        assert json.loads(response.response[0]) == \
               {"Error": "The configuration type can only be 'JSON', 'CSV' and 'RAW.'"}
    elif status == '409':
        assert json.loads(response.response[0]) == \
               {'Error': f'Configuration: "{config_name}" already exists for agent: "{vip_identity}"'}


@pytest.mark.parametrize('vip_identity_given, vip_identity_passed, status', [
    ('run1', 'run1', '204')
])
def test_handle_platforms_agents_configs_delete_response(mock_platform_web_service, vip_identity_given,
                                                         vip_identity_passed, status):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity_given}/configs'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    check_response_codes(response, status)
    if status == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('config.store', 'manage_delete_store', vip_identity_passed,
                                                       external_platform='my_instance_name')])


@pytest.mark.parametrize('vip_identity, config_name_given, config_name_passed, status', [
    ('run1', 'config1', 'config1', '204')
])
def test_handle_platforms_agents_configs_config_delete_response(mock_platform_web_service, vip_identity,
                                                                config_name_given, config_name_passed, status):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/configs/{config_name_given}'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_configs(env, {})
    check_response_codes(response, status)
    if status == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('config.store', 'manage_delete_config', vip_identity,
                                                       config_name_passed, external_platform='my_instance_name')])


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], ['PUT', 'DELETE']))
def test_handle_platforms_agents_enabled_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/enabled', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_enabled(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', {'status': False, 'priority': None}),
    ('run2', {'status': True, 'priority': 50}),
    ('stopped2', {'status': True, 'priority': 35}),
    ('not_exist', {'error': 'Agent "not_exist" not found.'})])
def test_handle_platforms_agents_enabled_get_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/enabled'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_enabled(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize('priority_given, priority_passed, expected', [
    ('30', '30', '204'),
    (None, '50', '204'),
    ('-1', None, '400'),
    ('100', None, '400'),
    ('foo', None, '400')
])
def test_handle_platforms_agents_enabled_put_response(mock_platform_web_service, priority_given, priority_passed,
                                                      expected):
    query_string = f'priority={priority_given}' if priority_given else ''
    path = f'/vui/platforms/my_instance_name/agents/run1/enabled'
    env = get_test_web_env(path, method='PUT', query_string=query_string, HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_enabled(env, {})
    check_response_codes(response, expected)
    if expected == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', 'run1',
                                                       external_platform='my_instance_name'),
                                             mock.call('control', 'prioritize_agent', '1', priority_passed,
                                                       external_platform='my_instance_name')])


def test_handle_platforms_agents_enabled_delete_response(mock_platform_web_service):
    path = f'/vui/platforms/my_instance_name/agents/run1/enabled'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_enabled(env, {})
    check_response_codes(response, '204')
    vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', 'run1',
                                                   external_platform='my_instance_name'),
                                         mock.call('control', 'prioritize_agent', '1', None,
                                                   external_platform='my_instance_name')])


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_agents_rpc_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/agent_vip/rpc', method=method,
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_agents_rpc(env, {})
    check_response_codes(response, status)


def test_handle_platforms_agents_rpc_response(mock_platform_web_service):
    path = f'/vui/platforms/my_instance_name/agents/control/rpc'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_rpc(env, {})
    check_links_return(response, ['list_agents', 'peerlist', 'status_agents'], leading_path=path)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET', 'POST']))
def test_handle_platforms_agents_rpc_method_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/control/rpc/status_agents', method=method,
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_rpc_method(env, {})
    check_response_codes(response, status)


def test_handle_platforms_rpc_method_get_response(mock_platform_web_service):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/control/rpc/status_agents', method='GET',
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_rpc_method(env, {})
    body = json.loads(response.response[0])
    assert isinstance(body, dict)
    assert isinstance(body['params'], dict)


def test_handle_platforms_rpc_method_post_response(mock_platform_web_service):
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/agents_rpc/rpc/kw_only', method='POST',
                           HTTP_AUTHORIZATION='BEARER foo')
    response = vui_endpoints.handle_platforms_agents_rpc_method(env, {'foo': 1, 'bar': 2})
    body = json.loads(response.response[0])
    assert body == [1, 2]
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/agents_rpc/rpc/args_and_kw', method='POST',
                           HTTP_AUTHORIZATION='BEARER foo')
    response = vui_endpoints.handle_platforms_agents_rpc_method(env, {'args': [1, 2], 'foo': 3, 'bar': 4})
    body = json.loads(response.response[0])
    assert body == [1, 2, 3, 4]
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/agents_rpc/rpc/args_only', method='POST',
                           HTTP_AUTHORIZATION='BEARER foo')
    response = vui_endpoints.handle_platforms_agents_rpc_method(env, [1, 2])
    body = json.loads(response.response[0])
    assert body == [1, 2]


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], ['PUT', 'DELETE']))
def test_handle_platforms_agents_running_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/running', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_running(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', {'running': True}),
    ('stopped1', {'running': False}),
    ('not_exist', {'error': 'Agent "not_exist" not found.'})])
def test_handle_platforms_agents_running_get_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/running'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_running(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize('vip_identity, uuid, restart, status_code', [
    ('run1', '1', False, '400'),
    ('run1', '1', True, '204'),
    ('run1', '1', 'foo', '400'),
    ('stopped2', '4', False, '204'),
    ('stopped1', '3', True, '204'),
    ('not_exist', '', True, '400')
])
def test_handle_platforms_agents_running_put_response(mock_platform_web_service, vip_identity, uuid,
                                                      restart, status_code):
    query_string = f'restart={restart}'
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/running'
    env = get_test_web_env(path, method='PUT', query_string=query_string, HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_running(env, {})
    check_response_codes(response, status_code)
    if status_code == '204':
        if restart:
            vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', vip_identity,
                                                           external_platform='my_instance_name'),
                                                 mock.call('control', 'restart_agent', uuid,
                                                           external_platform='my_instance_name')])
        else:
            vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', vip_identity,
                                                           external_platform='my_instance_name'),
                                                mock.call('control', 'peerlist', external_platform='my_instance_name'),
                                                mock.call('control', 'start_agent', uuid,
                                                          external_platform='my_instance_name')])


@pytest.mark.parametrize('vip_identity, uuid, status_code', [
    ('run1', '1', '204'),
    ('stopped1', '3', '204'),
    ('not_exist', '', '400')
])
def test_handle_platforms_agents_running_delete_response(mock_platform_web_service, vip_identity, uuid, status_code):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/running'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_running(env, {})
    check_response_codes(response, status_code)
    if status_code == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', vip_identity,
                                                       external_platform='my_instance_name'),
                                             mock.call('control', 'stop_agent', uuid,
                                                       external_platform='my_instance_name')])


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], []))
def test_handle_platforms_agents_status_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/status', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_status(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', {'name': 'rn1', 'uuid': '1', 'tag': 'r1', 'priority': None, 'running': True,
              'enabled': False, 'pid': 10, 'exit_code': None}),
    ('run2', {'name': 'rn2', 'uuid': '2', 'tag': 'r2', 'priority': 50, 'running': True,
              'enabled': True, 'pid': 11, 'exit_code': None}),
    ('stopped1', {'name': 'stp1', 'uuid': '3', 'tag': 'st1', 'priority': None, 'running': False,
                  'enabled': False, 'pid': None, 'exit_code': None}),
    ('stopped2', {'name': 'stp2', 'uuid': '4', 'tag': 'st2', 'priority': 35, 'running': False,
                  'enabled': True, 'pid': 12, 'exit_code': 0}),
    ('not_exist', {'error': 'Agent "not_exist" not found.'})])
def test_handle_platforms_agents_status_get_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/status'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_status(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], [ 'PUT', 'DELETE']))
def test_handle_platforms_agents_tag_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/agents/run1/tag', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_tag(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', {'tag': 'r1'}),
    ('run2', {'tag': 'r2'}),
    ('stopped1', {'tag': 'st1'}),
    ('stopped2', {'tag': 'st2'}),
    ('not_exist', {'error': "Agent 'not_exist' not found."})])
def test_handle_platforms_agents_tag_get_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/tag'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_agents_tag(env, {})
    assert json.loads(response.response[0]) == expected


@pytest.mark.parametrize('vip_identity, uuid, tag, expected', [
    ('run1', '1', 'foo', '204'),
    ('not_exists', None, 'foo', '400')
])
def test_handle_platforms_agents_tag_put_response(mock_platform_web_service, vip_identity, uuid, tag, expected):
    data = {"tag": tag}
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/tag'
    env = get_test_web_env(path, method='PUT', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_tag(env, data)
    check_response_codes(response, expected)
    if expected == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', vip_identity,
                                                       external_platform='my_instance_name'),
                                             mock.call('control', 'tag_agent', uuid, tag,
                                                       external_platform='my_instance_name')])
    elif expected == '400':
        assert json.loads(response.response[0]) == {'error': "Agent 'not_exists' not found."}


@pytest.mark.parametrize('vip_identity, expected', [
    ('run1', '204'),
    ('not_exists', '400')
])
def test_handle_platforms_agents_tag_delete_response(mock_platform_web_service, vip_identity, expected):
    path = f'/vui/platforms/my_instance_name/agents/{vip_identity}/tag'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_agents_tag(env, {})
    check_response_codes(response, expected)
    if expected == '204':
        vui_endpoints._rpc.assert_has_calls([mock.call('control', 'identity_exists', vip_identity,
                                                       external_platform='my_instance_name'),
                                             mock.call('control', 'tag_agent', '1', None,
                                                       external_platform='my_instance_name')])
    elif expected == '400':
        assert json.loads(response.response[0]) == {'error': "Agent 'not_exists' not found."}


def _mock_devices_rpc(peer, meth, *args, external_platform=None, **kwargs):
    if peer == 'platform.actuator' and meth == 'get_multiple_points':
        ret_val = [{}, {}]
        for topic in args[0]:
            ret_val[0][topic] = 10.0
        return ret_val
    elif peer == 'platform.actuator' and meth == 'set_multiple_points':
        return {}
    elif peer == 'platform.actuator' and meth == 'revert_device':
        return None
    elif peer == 'platform.actuator' and meth == 'revert_point':
        return None
    elif peer == 'platform.tagging' and meth == 'get_topics_by_tag':
        return []


@pytest.mark.parametrize("method, status", gen_response_codes(['GET', 'PUT', 'DELETE']))
def test_handle_platforms_devices_status_code(mock_platform_web_service, method, status):
    with mock.patch('volttron.platform.web.vui_endpoints.DeviceTree.from_store', return_value=pickle.loads(DEV_TREE)):
        env = get_test_web_env('/vui/platforms/my_instance_name/devices/Campus/Building1/Fake1/SampleWritableFloat1',
                               method=method, HTTP_AUTHORIZATION='BEARER foo')
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        vui_endpoints._rpc = _mock_devices_rpc
        response = vui_endpoints.handle_platforms_devices(env, {'value': 1})
        check_response_codes(response, status)


DEVICE_TOPIC_LIST = ['Campus/Building1/Fake1/SampleWritableFloat1', 'Campus/Building1/Fake1/SampleBool1',
                     'Campus/Building2/Fake1/SampleWritableFloat1', 'Campus/Building2/Fake1/SampleBool1',
                     'Campus/Building3/Fake1/SampleWritableFloat1', 'Campus/Building3/Fake1/SampleBool1']


# TODO: Test with tag query parameters.
@pytest.mark.parametrize('topic, is_point, read_all, return_routes, return_writability, return_values, return_config', [
    ('', False, False, True, True, True, False),
    ('', False, True, True, True, True, False),
    ('Campus/Building1/Fake1', False, False, True, True, True, False),
    ('Campus/Building1/Fake1', False, True, True, True, True, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, False, True, True, True, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, True, False, False, False, True)
])
def test_handle_platforms_devices_get_response(mock_platform_web_service, topic, is_point, read_all, return_routes,
                                               return_writability, return_values, return_config):
    query_string = f'read-all={read_all}&routes={return_routes}&writability={return_writability}' \
                   f'&values={return_values}&config={return_config}'
    with mock.patch('volttron.platform.web.vui_endpoints.DeviceTree.from_store', return_value=pickle.loads(DEV_TREE)):
        env = get_test_web_env(f'/vui/platforms/my_instance_name/devices/{topic}', query_string=query_string,
                               method='GET', HTTP_AUTHORIZATION='BEARER foo')
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        vui_endpoints._rpc = _mock_devices_rpc
        response = vui_endpoints.handle_platforms_devices(env, {})
        if not read_all and not is_point:
            seg_number = 0 if topic == '' else len(topic.split('/'))
            _log.debug(f'SEG_NUMBER is: {seg_number}')
            keys = [list_topic.split('/')[seg_number] for list_topic in DEVICE_TOPIC_LIST]
            check_links_return(response, list(set(keys)))
        else:
            body = json.loads(response.response[0])
            assert isinstance(body, dict)
            for k, v in body.items():
                keys = list(v.keys())
                assert isinstance(v, dict)
                assert 'route' in keys if return_routes else 'route' not in keys
                if return_writability:
                    assert 'writable' in keys
                    assert isinstance(v['writable'], bool)
                else:
                    assert 'writable' not in keys
                assert 'value' in keys if return_values else 'value' not in keys
                assert 'config' in keys if return_config else 'config' not in keys


@pytest.mark.parametrize('topic, is_point, write_all, confirm_values', [
    ('', False, False, False),
    ('', False, True, False),
    ('Campus/Building1/Fake1/', False, False, False),
    ('Campus/Building1/Fake1/', False, True, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, False, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, True, True)
])
def test_handle_platforms_devices_put_response(mock_platform_web_service, topic, is_point, write_all, confirm_values):
    query_string = f'write-all={write_all}&confirm-values={confirm_values}'
    with mock.patch('volttron.platform.web.vui_endpoints.DeviceTree.from_store', return_value=pickle.loads(DEV_TREE)):
        env = get_test_web_env(f'/vui/platforms/my_instance_name/devices/{topic}', query_string=query_string,
                               method='PUT', HTTP_AUTHORIZATION='BEARER foo')
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        vui_endpoints._rpc = _mock_devices_rpc
        response = vui_endpoints.handle_platforms_devices(env, {})
        body = json.loads(response.response[0])
        _log.debug('BODY IS:')
        _log.debug(body)
        assert isinstance(body, dict)
        if not is_point and not write_all:
            assert body['error'] == "Use of wildcard expressions, regex, or tags may set multiple points." \
                                    " Query must include 'write-all=true'."
        else:
            for k, v in body.items():
                keys = list(v.keys())
                assert 'route' in keys
                assert 'set_error' in keys
                assert 'writable' in keys
                assert isinstance(v['writable'], bool)
                if confirm_values:
                    assert 'value' in keys
                    assert "value_check_error" in keys
                else:
                    assert 'value' not in keys
                    assert "value_check_error" not in keys


@pytest.mark.parametrize('topic, is_point, write_all, confirm_values', [
    ('', False, False, False),
    ('', False, True, False),
    ('Campus/Building1/Fake1/', False, False, False),
    ('Campus/Building1/Fake1/', False, True, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, False, False),
    ('Campus/Building1/Fake1/SampleWritableFloat1', True, True, True)
])
def test_handle_platforms_devices_delete_response(mock_platform_web_service, topic, is_point, write_all,
                                                  confirm_values):
    query_string = f'write-all={write_all}&confirm-values={confirm_values}'
    with mock.patch('volttron.platform.web.vui_endpoints.DeviceTree.from_store', return_value=pickle.loads(DEV_TREE)):
        env = get_test_web_env(f'/vui/platforms/my_instance_name/devices/{topic}', query_string=query_string,
                               method='DELETE', HTTP_AUTHORIZATION='BEARER foo')
        vui_endpoints = VUIEndpoints(mock_platform_web_service)
        vui_endpoints._rpc = _mock_devices_rpc
        response = vui_endpoints.handle_platforms_devices(env, {})
        body = json.loads(response.response[0])
        _log.debug('BODY IS:')
        _log.debug(body)
        assert isinstance(body, dict)
        if not is_point and not write_all:
            assert body['error'] == "Use of wildcard expressions, regex, or tags may set multiple points." \
                                    " Query must include 'write-all=true'."
        else:
            for k, v in body.items():
                keys = list(v.keys())
                assert 'route' in keys
                assert 'writable' in keys
                assert isinstance(v['writable'], bool)
                if confirm_values:
                    assert 'value' in keys
                    assert "value_check_error" in keys
                else:
                    assert 'value' not in keys
                    assert "value_check_error" not in keys


def test_handle_platforms_pubsub(mock_platform_web_service):
    pass
# TODO: handle_platforms_pubsub


HISTORIAN_TOPIC_LIST = ['Campus/Building1/Fake1/SampleBool1', 'Campus/Building1/Fake1/EKG',
                        'Campus/Building1/Fake1/SampleWritableFloat1', 'Campus/Building1/Fake1/EKG_Sin',
                        'Campus/Building1/Fake1/EKG_Cos']


def _mock_historians_rpc(peer, meth, *args, external_platform=None, **kwargs):
    if meth == 'get_topic_list':
        return HISTORIAN_TOPIC_LIST
    elif meth == 'query':
        if len(args[0]) > 1:
            retval = {'values': {}, 'metadata': {}}
            for topic in args[0]:
                retval['values'][topic] = [['2021-06-17T22:15:00.551451+00:00', True],
                                   ['2021-06-17T22:16:00.550595+00:00', True],
                                   ['2021-06-17T22:17:00.551621+00:00', True],
                                   ['2021-06-17T22:18:00.551112+00:00', True],
                                   ['2021-06-17T22:19:00.551337+00:00', True]]
        else:
            retval = {'values': [['2021-06-17T22:15:00.551451+00:00', True]],
                      'metadata': {'units': 'On / Off', 'type': 'integer', 'tz': 'US/Pacific'}}
        return retval


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_historians_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/historians', method=method, HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_historians(env, {})
    check_response_codes(response, status)


def test_handle_platforms_historians_response(mock_platform_web_service):
    path = f'/vui/platforms/my_instance_name/historians'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._get_agents = lambda x: ['platform.other', 'foo.historian', 'random.agent', 'platform.historian']
    response = vui_endpoints.handle_platforms_historians(env, {})
    check_links_return(response, ['platform.historian', 'foo.historian'], leading_path=path)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_historians_historian_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/historians/my_instance_name', method=method,
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_historians_historian(env, {})
    check_response_codes(response, status)


def test_handle_platforms_historians_historian_response(mock_platform_web_service):
    path = f'/vui/platforms/my_instance_name/historians/platform.historian'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_historians_historian(env, {})
    check_links_return(response, ['topics'], leading_path=path)


@pytest.mark.parametrize("method, status", gen_response_codes(['GET']))
def test_handle_platforms_historians_historian_topics_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/historians/my_instance_name/topics', method=method,
                           HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    response = vui_endpoints.handle_platforms_historians_historian_topics(env, {})
    check_response_codes(response, status)


# Test tag query parameters.
@pytest.mark.parametrize('topic, is_full_topic, read_all, return_routes, return_values', [
    ('', False, False, True, True),
    ('', False, True, True, True),
    ('Campus/Building1/Fake1', False, False, True, True),
    ('Campus/Building1/Fake1', False, True, True, True),
    ('Campus/Building1/Fake1/SampleBool1', True, False, True, True),
    ('Campus/Building1/Fake1/SampleBool1', True, False, False, False)
])
def test_handle_platforms_historians_historian_topics_get_response(mock_platform_web_service, topic, is_full_topic,
                                                                   read_all, return_routes, return_values):
    query_string = f'read-all={read_all}&routes={return_routes}&values={return_values}'
    env = get_test_web_env(f'/vui/platforms/my_instance_name/historians/platform.historian/topics/{topic}',
                           query_string=query_string, method='GET', HTTP_AUTHORIZATION='BEARER foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_historians_rpc
    response = vui_endpoints.handle_platforms_historians_historian_topics(env, {})
    if not read_all and not is_full_topic:
        seg_number = 0 if topic == '' else len(topic.split('/'))
        keys = [list_topic.split('/')[seg_number] for list_topic in HISTORIAN_TOPIC_LIST]
        _log.debug(f'KEYS IS: {keys}')
        check_links_return(response, list(set(keys)))
    else:
        body = json.loads(response.response[0])
        assert isinstance(body, dict)
        _log.debug('BODY IS:')
        _log.debug(body)
        for k, v in body.items():
            keys = v.keys()
            assert 'route' in keys if return_routes else 'route' not in keys
            assert 'value' in keys if return_values else 'value' not in keys


@pytest.mark.parametrize("method, status", gen_response_codes(['GET'], ['DELETE']))
def test_handle_platforms_status_status_code(mock_platform_web_service, method, status):
    env = get_test_web_env('/vui/platforms/my_instance_name/status', method=method,
                           HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_status(env, {})
    check_response_codes(response, status)


@pytest.mark.parametrize('expected', [{
    'run1': {'name': 'rn1', 'uuid': '1', 'tag': 'r1', 'priority': None, 'running': True,
             'enabled': False, 'pid': 10, 'exit_code': None},
    'run2': {'name': 'rn2', 'uuid': '2', 'tag': 'r2', 'priority': 50, 'running': True,
             'enabled': True, 'pid': 11, 'exit_code': None},
    'stopped1': {'name': 'stp1', 'uuid': '3', 'tag': 'st1', 'priority': None,  'running': False,
                 'enabled': False, 'pid': None, 'exit_code': None},
    'stopped2': {'name': 'stp2', 'uuid': '4', 'tag': 'st2', 'priority': 35, 'running': False,
                 'enabled': True, 'pid': 12, 'exit_code': 0}}])
def test_handle_platforms_status_get_response(mock_platform_web_service, expected):
    path = f'/vui/platforms/my_instance_name/status'
    env = get_test_web_env(path, method='GET', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = _mock_agents_rpc
    response = vui_endpoints.handle_platforms_status(env, {})
    assert json.loads(response.response[0]) == expected


def test_handle_platforms_status_delete_response(mock_platform_web_service):
    path = f'/vui/platforms/my_instance_name/status'
    env = get_test_web_env(path, method='DELETE', HTTP_AUTHORIZATION='Bearer foo')
    vui_endpoints = VUIEndpoints(mock_platform_web_service)
    vui_endpoints._rpc = MagicMock(wraps=_mock_agents_rpc)
    response = vui_endpoints.handle_platforms_status(env, {})
    check_response_codes(response, '204')
    vui_endpoints._rpc.assert_has_calls([mock.call('control', 'clear_status', True,
                                                   external_platform='my_instance_name')])
