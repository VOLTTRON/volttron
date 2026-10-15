import errno
import logging
from unittest import mock

import gevent
import pytest

from services.core.VolttronCentral.volttroncentral import agent as vc_agent
from services.core.VolttronCentral.volttroncentral.sessions import IDLE_TIMEOUT
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent import Unreachable
from vc_agent_factory import IP, login, make_agent

SECRET = 'historian-password-7731'
ADMIN = {'user': 'admin', 'groups': ['admin'], 'ip': IP, 'channel': 'c'}


@pytest.fixture
def agent(monkeypatch):
    agent = make_agent(monkeypatch)
    agent._platforms.is_registered.return_value = True
    return agent


def _open_management_socket(agent, channel):
    path = '/vc/ws/{}/management'.format(channel)
    assert agent.open_authenticate_ws_endpoint(IP, path) is True
    assert path in agent._websocket_endpoints
    return path


def _sent_paths(agent):
    agent.vip.web.send.reset_mock()
    agent.send_management_message('PING')
    return [call.args[0] for call in agent.vip.web.send.call_args_list]


def test_relogin_stops_tracking_and_sending_to_the_old_socket(agent):
    _, old_channel = login(agent)
    old_path = _open_management_socket(agent, old_channel)
    assert _sent_paths(agent) == [old_path]

    _, new_channel = login(agent)

    assert old_path not in agent._websocket_endpoints
    assert _sent_paths(agent) == []
    new_path = _open_management_socket(agent, new_channel)
    assert _sent_paths(agent) == [new_path]


def test_expiry_stops_tracking_and_sending_to_the_socket(agent):
    _, channel = login(agent)
    path = _open_management_socket(agent, channel)
    created = next(iter(
        agent._authenticated_sessions._session_tokens.values()))['created']
    agent._authenticated_sessions._clock = lambda: created + IDLE_TIMEOUT + 1

    agent._authenticated_sessions.expire()

    assert path not in agent._websocket_endpoints
    assert _sent_paths(agent) == []


def test_ending_one_session_keeps_the_sockets_of_another(agent):
    _, first = login(agent, user='admin')
    _, second = login(agent, user='reader', groups=['reader'])
    _open_management_socket(agent, first)
    kept = _open_management_socket(agent, second)

    login(agent, user='admin')

    assert agent._websocket_endpoints == {kept}


@pytest.mark.parametrize('failure', [
    RemoteError('no such route'), Unreachable(errno.EHOSTUNREACH, 'gone', 'web', 'web'),
    gevent.Timeout(5)], ids=['remote-error', 'unreachable', 'timeout'])
def test_a_failed_route_removal_is_logged_and_does_not_stop_cleanup(
        agent, caplog, failure):
    _, channel = login(agent)
    path = '/vc/ws/{}/management'.format(channel)
    agent._handle_management_endpoint({'channel': channel}, {})
    agent.vip.web.unregister_websocket.side_effect = failure

    with caplog.at_level(logging.ERROR):
        login(agent)

    assert [r.getMessage() for r in caplog.records
            if r.levelname == 'ERROR' and path in r.getMessage()]


def _sweep_harness(agent):
    """Make the scan's schedule call observable; returns the scheduled list."""
    scheduled = []
    agent.core = mock.Mock()
    agent.core.schedule.side_effect = (
        lambda when, fn: scheduled.append(fn) or mock.Mock())
    agent._platform_scan_event = None
    agent._platform_scan_running = False
    agent._platforms.get_platform_vip_identities.return_value = set()
    return scheduled


def test_a_failed_sweep_is_logged_and_the_next_sweep_still_expires(
        agent, caplog):
    _, channel = login(agent)
    session = next(iter(agent._authenticated_sessions._session_tokens.values()))
    scheduled = _sweep_harness(agent)
    agent.vip.peerlist.return_value.get.side_effect = gevent.Timeout(5)

    with caplog.at_level(logging.ERROR):
        agent._scan_platform_connect_disconnect()

    assert len(scheduled) == 1
    assert [r for r in caplog.records if r.levelname == 'ERROR']
    assert session['id'] in agent._authenticated_sessions._session_tokens

    agent.vip.peerlist.return_value.get.side_effect = None
    agent.vip.peerlist.return_value.get.return_value = []
    agent._authenticated_sessions._clock = (
        lambda: session['created'] + IDLE_TIMEOUT + 1)
    scheduled[0]()

    assert agent._authenticated_sessions._session_tokens == {}
    assert len(scheduled) == 2


def test_a_failing_expiry_does_not_stop_the_platform_scan(agent):
    scheduled = _sweep_harness(agent)
    agent.vip.peerlist.return_value.get.return_value = ['vcp-one']
    agent._authenticated_sessions.expire = mock.Mock(
        side_effect=RuntimeError('boom'))

    agent._scan_platform_connect_disconnect()

    agent._platforms.add_platform.assert_called_once_with('vcp-one')
    assert len(scheduled) == 1


def test_a_failing_expiry_is_logged(agent, caplog):
    _sweep_harness(agent)
    agent.vip.peerlist.return_value.get.return_value = []
    agent._authenticated_sessions.expire = mock.Mock(
        side_effect=RuntimeError('boom'))

    with caplog.at_level(logging.ERROR):
        agent._scan_platform_connect_disconnect()

    errors = [r for r in caplog.records if r.levelname == 'ERROR']
    assert [r.getMessage() for r in errors] == ['Expiring sessions failed']
    assert errors[0].exc_info[0] is RuntimeError


def test_a_slow_platform_connect_does_not_start_a_second_scan(agent):
    scheduled = _sweep_harness(agent)
    agent.vip.peerlist.return_value.get.return_value = ['vcp-one']
    agent._authenticated_sessions.expire = mock.Mock()
    connects = []

    def slow_connect(identity):
        connects.append(identity)
        if len(connects) == 1:
            # The next sweep fires while this connect is still blocked.
            scheduled[0]()

    agent._platforms.add_platform.side_effect = slow_connect

    agent._scan_platform_connect_disconnect()

    assert connects == ['vcp-one']
    assert agent._authenticated_sessions.expire.call_count == 2
    assert len(scheduled) == 2


def test_a_failed_scan_does_not_block_the_next_scan(agent):
    scheduled = _sweep_harness(agent)
    agent.vip.peerlist.return_value.get.side_effect = RuntimeError('boom')
    agent._scan_platform_connect_disconnect()

    agent.vip.peerlist.return_value.get.side_effect = None
    agent.vip.peerlist.return_value.get.return_value = ['vcp-one']
    scheduled[0]()

    agent._platforms.add_platform.assert_called_once_with('vcp-one')


def test_platform_handler_responses_are_not_logged(agent, caplog):
    platform = agent._platforms.get_platform.return_value
    platform.get_agent_config.return_value = {'password': SECRET}

    with caplog.at_level(logging.DEBUG):
        result = agent._route_request(
            ADMIN, '1', 'get_agent_config',
            {'platform_uuid': 'u1', 'identity': 'x', 'config_name': 'c'})

    assert result == {'password': SECRET}
    assert caplog.records
    for record in caplog.records:
        assert SECRET not in record.getMessage()
        assert SECRET not in str(record.args)
