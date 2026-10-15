import pytest

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from volttron.platform.jsonrpc import METHOD_NOT_FOUND, UNAUTHORIZED
from vc_agent_factory import make_agent

U = 'vcp-abc'

ADMIN_USER = {'user': 'admin', 'groups': ['admin'], 'ip': '10.0.0.1', 'channel': 'ch'}
READER = {'user': 'reader', 'groups': ['reader'], 'ip': '10.0.0.1', 'channel': 'ch'}

ANY_USER_METHODS = [
    'list_platforms', 'list_performance', 'register_management_endpoint',
    'get_setting', 'get_setting_keys',
    'historian.query', 'historian.get_topic_list',
    'list_agents', 'status_agents', 'get_devices',
    'platforms.uuid.{}.list_agents'.format(U),
    'platforms.uuid.{}.status_agents'.format(U),
    'platforms.uuid.{}.get_devices'.format(U),
    'platforms.uuid.{}.agent_status'.format(U),
]
ADMIN_METHODS = [
    'set_setting', 'enable_setup_mode', 'disable_setup_mode',
    'store_agent_config', 'get_agent_config', 'delete_agent_config',
    'list_agent_configs', 'start_bacnet_scan', 'publish_bacnet_props',
    'platforms.uuid.{}.store_agent_config'.format(U),
    'platforms.uuid.{}.get_agent_config'.format(U),
    'platforms.uuid.{}.delete_agent_config'.format(U),
    'platforms.uuid.{}.list_agent_configs'.format(U),
    'platforms.uuid.{}.start_bacnet_scan'.format(U),
    'platforms.uuid.{}.publish_bacnet_props'.format(U),
    'platforms.uuid.{}.start_agent'.format(U),
    'platforms.uuid.{}.stop_agent'.format(U),
    'platforms.uuid.{}.restart_agent'.format(U),
    'platforms.uuid.{}.remove_agent'.format(U),
    'platforms.uuid.{}.install'.format(U),
]
REFUSED_FOR_ALL = [
    'platforms.uuid.{}.historian.delete_all'.format(U),
    'x.y.store_agent_config',
    'x.y.list_agents',
    'platforms.uuid.{}.config_store.set_config'.format(U),
    'platforms.uuid.{}.agents.uuid.A.inspect'.format(U),
    'platforms.uuid.{}.list_agents.x'.format(U),
    'platforms.uuid.{}'.format(U),
    'platforms.uuid',
    'platforms.uuid..list_agents',
    'platforms.uid.{}.list_agents'.format(U),
    'platform.uuid.{}.list_agents'.format(U),
    'historian.query.x',
    'historian.delete_all',
    'historian',
    'list_agents.x',
    'register_instance',
    'unregister_platform',
    'start_agent',
    'install',
    'remove_agent',
    'agent_status',
    'LIST_PLATFORMS',
    ' list_platforms',
    '',
    5,
    None,
]


def probe(agent, session_user, method, params=None):
    """Returns 'unauthorized', 'unknown' or 'reached' for one request."""
    agent.vip.reset_mock()
    agent._platforms.reset_mock()
    try:
        result = agent._route_request(session_user, '1', method, params)
    except Exception:
        # Past the table check and into a handler that this mock cannot finish.
        return 'reached'
    if isinstance(result, dict) and 'error' in result:
        code = result['error']['code']
        if code == UNAUTHORIZED:
            return 'unauthorized'
        if code == METHOD_NOT_FOUND:
            return 'unknown'
    return 'reached'


@pytest.fixture
def agent(monkeypatch):
    agent = make_agent(monkeypatch)
    agent._platforms.is_registered.return_value = True
    return agent


@pytest.mark.parametrize('method', ANY_USER_METHODS)
def test_read_methods_are_open_to_any_logged_in_user(agent, method):
    assert probe(agent, READER, method, {'platform_uuid': U}) == 'reached'
    assert probe(agent, ADMIN_USER, method, {'platform_uuid': U}) == 'reached'


@pytest.mark.parametrize('method', ADMIN_METHODS)
def test_admin_methods_refuse_a_non_admin_before_anything_runs(agent, method):
    assert probe(agent, READER, method, {'platform_uuid': U}) == 'unauthorized'
    assert agent.vip.mock_calls == []
    assert agent._platforms.mock_calls == []
    assert probe(agent, ADMIN_USER, method, {'platform_uuid': U}) == 'reached'


@pytest.mark.parametrize('method', REFUSED_FOR_ALL)
@pytest.mark.parametrize('session_user', [READER, ADMIN_USER],
                         ids=['reader', 'admin'])
def test_names_outside_the_table_are_refused_for_everyone(agent, session_user, method):
    assert probe(agent, session_user, method, {'platform_uuid': U}) == 'unknown'
    assert agent.vip.mock_calls == []
    assert agent._platforms.mock_calls == []


def test_the_historian_probe_names_never_reach_the_platform(agent):
    for method in ('platforms.uuid.{}.historian.delete_all'.format(U),
                   'x.y.store_agent_config',
                   'platforms.uuid.{}.config_store.set_config'.format(U)):
        assert probe(agent, ADMIN_USER, method, {}) == 'unknown'
        platform = agent._platforms.get_platform.return_value
        assert platform.route_to_agent_method.mock_calls == []
        assert platform.call.mock_calls == []


def test_historian_query_passes_its_params_to_the_platform_historian(agent):
    agent.vip.peerlist.return_value.get.return_value = [
        vc_agent.PLATFORM_HISTORIAN]

    agent._route_request(READER, '1', 'historian.query', {'topic': 't', 'count': 2})

    agent.vip.rpc.call.assert_called_once_with(
        vc_agent.PLATFORM_HISTORIAN, 'query', topic='t', count=2)


def test_historian_topic_list_calls_get_topic_list(agent):
    agent.vip.peerlist.return_value.get.return_value = [
        vc_agent.PLATFORM_HISTORIAN]

    agent._route_request(READER, '1', 'historian.get_topic_list', None)

    agent.vip.rpc.call.assert_called_once_with(
        vc_agent.PLATFORM_HISTORIAN, 'get_topic_list')


def test_four_segment_admin_method_goes_to_the_named_platform(agent):
    platform = agent._platforms.get_platform.return_value
    platform.route_to_agent_method.return_value = {'result': 'ok'}

    result = agent._route_request(
        ADMIN_USER, '7', 'platforms.uuid.{}.start_agent'.format(U), {'uuid': 'a-1'})

    agent._platforms.get_platform.assert_called_once_with(U)
    platform.route_to_agent_method.assert_called_once_with(
        '7', 'start_agent', {'uuid': 'a-1'})
    assert result == {'result': 'ok'}


def test_bare_platform_method_takes_the_platform_from_the_params(agent):
    platform = agent._platforms.get_platform.return_value
    platform.get_agent_list.return_value = ['an agent']

    result = agent._route_request(
        READER, '9', 'list_agents', {'platform_uuid': U})

    agent._platforms.get_platform.assert_called_once_with(U)
    platform.get_agent_list.assert_called_once_with(READER, {'message_id': '9'})
    assert result == ['an agent']


def test_platform_in_the_name_wins_over_the_one_in_the_params(agent):
    agent._route_request(READER, '9', 'platforms.uuid.{}.list_agents'.format(U),
                         {'platform_uuid': 'vcp-other'})

    agent._platforms.get_platform.assert_called_once_with(U)


def test_a_platform_method_without_any_platform_is_invalid_params(agent):
    result = agent._route_request(READER, '9', 'list_agents', None)

    assert result['error']['code'] == vc_agent.INVALID_PARAMS
    assert agent._platforms.get_platform.mock_calls == []


def test_unknown_platform_is_reported_and_not_called(agent):
    agent._platforms.is_registered.return_value = False

    result = agent._route_request(
        READER, '9', 'platforms.uuid.{}.list_agents'.format(U), None)

    assert result['error']['code'] == vc_agent.UNAVAILABLE_PLATFORM
    assert agent._platforms.get_platform.mock_calls == []


def test_table_groups_are_exactly_the_documented_ones():
    groups = {}
    for table in (vc_agent.VC_METHODS, vc_agent.HISTORIAN_METHODS,
                  vc_agent.PLATFORM_METHODS, vc_agent.PLATFORM_ONLY_METHODS):
        groups.update(table)

    assert {n for n, g in groups.items() if g == vc_agent.ANY_USER} == {
        'list_platforms', 'list_performance', 'register_management_endpoint',
        'get_setting', 'get_setting_keys', 'historian.query',
        'historian.get_topic_list', 'list_agents', 'status_agents',
        'get_devices', 'agent_status'}
    assert {n for n, g in groups.items() if g == vc_agent.ADMIN} == {
        'set_setting', 'enable_setup_mode', 'disable_setup_mode',
        'store_agent_config', 'get_agent_config', 'delete_agent_config',
        'list_agent_configs', 'start_bacnet_scan', 'publish_bacnet_props',
        'start_agent', 'stop_agent', 'restart_agent', 'remove_agent',
        'install'}


def test_a_refused_request_broadcasts_nothing_to_the_management_sockets(agent):
    agent._websocket_endpoints = {'/vc/ws/ch/management'}

    assert probe(agent, READER, 'set_setting', {}) == 'unauthorized'
    assert probe(agent, READER, 'no.such.method') == 'unknown'
    assert agent.vip.web.send.mock_calls == []

    agent.vip.reset_mock()
    probe(agent, READER, 'list_platforms')
    assert agent.vip.web.send.call_count == 1


@pytest.mark.parametrize('method', [
    'get_setting', 'list_platforms', 'platforms.uuid.{}.list_agents'.format(U)])
def test_a_handler_given_params_that_are_not_an_object_gets_invalid_params(agent, method):
    result = agent._route_request(READER, '1', method, ['not', 'an', 'object'])

    assert result['error']['code'] == vc_agent.INVALID_PARAMS
