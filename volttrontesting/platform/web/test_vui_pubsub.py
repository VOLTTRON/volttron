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

"""Lifecycle of VUI subscription websockets: bookkeeping by login session and release of the bus subscription."""

import json
import time
from unittest.mock import MagicMock

import pytest

from volttron.platform.web.token_revocation import SESSION_CLAIM
from volttron.platform.web.vui_pubsub import POLICY_VIOLATION, VUIPubsubManager, VUIWebSocket


class FakeSocket(VUIWebSocket):
    """A VUIWebSocket without a transport. ws4py's ``terminated`` property reads the two flags."""

    def __init__(self):
        self.client_terminated = self.server_terminated = False
        self.environ = {}
        self.closed_with = None
        self.sent = []

    def close(self, code=1000, reason=''):
        self.closed_with = (code, reason)
        self.client_terminated = self.server_terminated = True

    def send(self, payload, binary=False):
        self.sent.append(payload)


def claims_for(sid, groups=('vui',), **extra):
    return {SESSION_CLAIM: sid, 'grant_type': 'access_token', 'groups': list(groups), **extra}


@pytest.fixture
def manager():
    agent = MagicMock()
    agent.get_user_claims = MagicMock(return_value=claims_for('s1'))
    return VUIPubsubManager(agent)


def _open(manager, sid='s1', topic='devices/a', token=None, **extra):
    sock = FakeSocket()
    manager.client_opened(sock, topic, token or f'token-{sid}', claims_for(sid, **extra))
    return sock


class TestOpenAndClose:
    def test_opened_socket_is_subscribed_and_filed_under_its_session(self, manager):
        sock = _open(manager, 's1', 'devices/a')
        manager._agent.vip.pubsub.subscribe.assert_called_once_with('pubsub', 'devices/a', sock.on_topic)
        assert sock.vui_topic == 'devices/a' and sock.vui_sid == 's1' and sock.vui_token == 'token-s1'
        assert manager._sockets == {'s1': {sock}}

    def test_client_closed_unsubscribes_and_forgets_the_socket(self, manager):
        sock = _open(manager)
        assert manager.client_closed(sock) is True
        manager._agent.vip.pubsub.unsubscribe.assert_called_once_with('pubsub', 'devices/a', sock.on_topic)
        assert manager._sockets == {}

    def test_client_closed_is_idempotent_and_ignores_unknown_sockets(self, manager):
        sock = _open(manager)
        manager.client_closed(sock)
        assert manager.client_closed(sock) is False
        assert manager.client_closed(FakeSocket()) is False
        assert manager._agent.vip.pubsub.unsubscribe.call_count == 1

    def test_closing_one_socket_leaves_another_on_the_same_topic_subscribed(self, manager):
        first, second = _open(manager, 's1', 'devices/a'), _open(manager, 's2', 'devices/a')
        manager.client_closed(first)
        unsubscribed = [c.args[2] for c in manager._agent.vip.pubsub.unsubscribe.call_args_list]
        assert unsubscribed == [first.on_topic]
        assert manager._sockets == {'s2': {second}}

    def test_ws4py_closed_callback_reaches_the_manager(self, manager):
        sock = _open(manager)
        sock.environ = {'ws4py.app': manager}
        sock.closed(1000, 'client left')
        manager._agent.vip.pubsub.unsubscribe.assert_called_once()
        assert manager._sockets == {}

    def test_closed_callback_without_an_app_is_harmless(self):
        FakeSocket().closed(1000)

    def test_close_socket_releases_then_closes_with_policy_code(self, manager):
        sock = _open(manager)
        assert manager.close_socket(sock, 'Because') is True
        assert sock.closed_with == (POLICY_VIOLATION, 'Because')
        manager._agent.vip.pubsub.unsubscribe.assert_called_once()
        # Already terminated: bookkeeping is clean and nothing more is closed.
        assert manager.close_socket(sock, 'Again') is False

    def test_close_failure_is_logged_not_raised(self, manager):
        sock = _open(manager)
        sock.close = MagicMock(side_effect=RuntimeError('socket gone'))
        assert manager.close_socket(sock, 'Because') is False
        assert manager._sockets == {}

    def test_unsubscribe_failure_is_logged_not_raised(self, manager):
        sock = _open(manager)
        manager._agent.vip.pubsub.unsubscribe.side_effect = RuntimeError('bus gone')
        assert manager.client_closed(sock) is True
        assert manager._sockets == {}


class TestSessionRevocation:
    def test_close_session_sockets_closes_and_unsubscribes_every_socket_of_the_session(self, manager):
        a, b = _open(manager, 's1', 'devices/a'), _open(manager, 's1', 'devices/b')
        other = _open(manager, 's2', 'devices/a')
        assert manager.close_session_sockets('s1') == 2
        assert a.closed_with == (POLICY_VIOLATION, 'Session revoked') and b.terminated
        assert not other.terminated
        assert manager._agent.vip.pubsub.unsubscribe.call_count == 2
        assert manager._sockets == {'s2': {other}}
        assert manager.close_session_sockets('s1') == 0 and manager.close_session_sockets('nope') == 0


class TestRoutesAndVerification:
    def test_socket_routes_list_the_sessions_open_topics(self, manager):
        _open(manager, 's1', 'devices/a')
        gone = _open(manager, 's1', 'devices/b')
        gone.client_terminated = gone.server_terminated = True
        _open(manager, 's2', 'devices/c')
        assert set(manager.get_socket_routes('token-s1')) == {'devices/a'}

    def test_socket_routes_of_an_unverifiable_token_are_empty(self, manager):
        _open(manager, 's1', 'devices/a')
        manager._agent.get_user_claims = MagicMock(side_effect=ValueError('bad token'))
        assert manager.get_socket_routes('token-s1') == {}

    @pytest.mark.parametrize('claims', [None, {}, {'groups': ['admin']}, {'groups': 'vui'}, {'groups': None}])
    def test_verify_token_requires_the_vui_group(self, manager, claims):
        manager._agent.get_user_claims = MagicMock(return_value=claims)
        assert manager.verify_token('tok') is None

    def test_verify_token_never_raises(self, manager):
        manager._agent.get_user_claims = MagicMock(side_effect=RuntimeError('boom'))
        assert manager.verify_token('tok') is None
        assert manager.verify_token(None) is None

    def test_open_subscription_socket_returns_a_wsgi_application(self, manager):
        app = manager.open_subscription_socket('tok', 'devices/a')
        assert app.handler_cls is VUIWebSocket
        assert manager._sockets == {}    # nothing is recorded before the socket verifies its token


class TestOnTopic:
    def test_message_is_forwarded_as_json(self, manager):
        sock = _open(manager)
        sock.on_topic('peer', 'sender', 'pubsub', 'devices/a', {}, {'point': 1})
        assert sock.sent == ['{"point": 1}']

    def test_terminated_socket_receives_nothing(self, manager):
        sock = _open(manager)
        sock.client_terminated = sock.server_terminated = True
        sock.on_topic('peer', 'sender', 'pubsub', 'devices/a', {}, 1)
        assert sock.sent == []


# ---------------------------------------------------------------- token lifetime and renewal

def _message(payload):
    m = MagicMock()
    m.data = payload if isinstance(payload, bytes) else payload.encode('utf-8')
    return m


class TestTokenLifetime:
    def test_claims_are_recorded_on_the_socket(self, manager):
        sock = _open(manager, 's1', 'devices/a', sub='alice', exp=1_700_000_000)
        assert (sock.vui_sub, sock.vui_exp) == ('alice', 1_700_000_000.0)
        plain = _open(manager, 's2', 'devices/a', exp=True)   # bool is not a time; no sub claim
        assert (plain.vui_sub, plain.vui_exp) == (None, None)

    def test_on_topic_closes_an_expired_socket_instead_of_sending(self, manager):
        sock = _open(manager, exp=time.time() - 1)
        sock.environ = {'ws4py.app': manager}
        sock.on_topic('peer', 'sender', 'pubsub', 'devices/a', {}, 1)
        assert sock.sent == [] and sock.closed_with == (POLICY_VIOLATION, 'Token expired')
        manager._agent.vip.pubsub.unsubscribe.assert_called_once()

    def test_on_topic_sends_while_the_token_is_valid(self, manager):
        sock = _open(manager, exp=time.time() + 60)
        sock.on_topic('peer', 'sender', 'pubsub', 'devices/a', {}, 1)
        assert sock.sent == ['1']

    def test_sweep_closes_expired_and_unverifiable_sockets_and_keeps_the_rest(self, manager):
        expired = _open(manager, 's1', 'devices/a', exp=time.time() - 1)
        revoked = _open(manager, 's2', 'devices/b', token='revoked', exp=time.time() + 60)
        fine = _open(manager, 's3', 'devices/c', token='fine', exp=time.time() + 60)
        gone = _open(manager, 's4', 'devices/d')
        gone.client_terminated = gone.server_terminated = True
        manager._agent.get_user_claims = lambda token: {} if token == 'revoked' else claims_for('s3')
        assert manager.revalidate_sockets() == 2
        assert expired.closed_with == (POLICY_VIOLATION, 'Token expired')
        assert revoked.closed_with == (POLICY_VIOLATION, 'Not Authorized')
        assert fine.closed_with is None
        assert manager._sockets == {'s3': {fine}}     # the terminated socket was dropped from the books
        assert manager._agent.vip.pubsub.unsubscribe.call_count == 3

    def test_sweep_is_scheduled_once_when_the_first_socket_opens(self, manager):
        manager._agent.core.schedule.assert_not_called()
        _open(manager, 's1', 'devices/a')
        _open(manager, 's1', 'devices/b')
        manager._agent.core.schedule.assert_called_once()
        assert manager._agent.core.schedule.call_args.args[1] == manager.revalidate_sockets

    def test_manager_without_a_core_does_not_schedule(self):
        agent = MagicMock(spec=['vip', 'get_user_claims'])
        VUIPubsubManager(agent).client_opened(FakeSocket(), 'devices/a', 'tok', claims_for('s1'))

    def test_scheduling_failure_is_logged_not_raised(self, manager):
        manager._agent.core.schedule.side_effect = RuntimeError('no hub')
        _open(manager)


class TestRenewal:
    def test_token_of_the_same_session_extends_the_socket(self, manager):
        sock = _open(manager, 's1', 'devices/a', exp=time.time() + 10)
        manager._agent.get_user_claims = MagicMock(return_value=claims_for('s1', exp=time.time() + 900))
        assert manager.renew_socket(sock, 'new-token') is True
        assert sock.vui_token == 'new-token' and sock.vui_exp > time.time() + 800
        assert manager._sockets == {'s1': {sock}}

    def test_token_of_a_new_login_by_the_same_user_moves_the_socket(self, manager):
        sock = _open(manager, 's1', 'devices/a', sub='alice')
        manager._agent.get_user_claims = MagicMock(return_value=claims_for('s2', sub='alice'))
        assert manager.renew_socket(sock, 'new-token') is True
        assert sock.vui_sid == 's2' and manager._sockets == {'s2': {sock}}
        # Revoking the old session no longer touches it; revoking the new one does.
        assert manager.close_session_sockets('s1') == 0 and not sock.terminated
        assert manager.close_session_sockets('s2') == 1 and sock.terminated

    @pytest.mark.parametrize('claims', [claims_for('s2', sub='bob'), claims_for('s2'), {}, None,
                                        claims_for('s2', groups=['admin'], sub='alice')])
    def test_tokens_of_another_user_or_without_vui_are_refused(self, manager, claims):
        sock = _open(manager, 's1', 'devices/a', sub='alice', exp=time.time() + 10)
        manager._agent.get_user_claims = MagicMock(return_value=claims)
        assert manager.renew_socket(sock, 'new-token') is False
        assert sock.vui_sid == 's1' and sock.vui_token == 'token-s1' and not sock.terminated

    def test_a_socket_opened_without_a_user_claim_accepts_only_its_own_session(self, manager):
        sock = _open(manager, 's1', 'devices/a')
        manager._agent.get_user_claims = MagicMock(return_value=claims_for('s2', sub='alice'))
        assert manager.renew_socket(sock, 'new-token') is False

    def test_a_closed_socket_cannot_be_renewed(self, manager):
        sock = _open(manager)
        manager.client_closed(sock)
        assert manager.renew_socket(sock, 'token-s1') is False

    def test_received_renewal_frame_is_answered(self, manager):
        sock = _open(manager, 's1', 'devices/a', exp=time.time() + 10)
        sock.environ = {'ws4py.app': manager}
        manager._agent.get_user_claims = MagicMock(return_value=claims_for('s1', exp=1_900_000_000))
        sock.received_message(_message(json.dumps({'access_token': 'new-token'})))
        assert json.loads(sock.sent[-1]) == {'renewed': True, 'expires': 1_900_000_000}
        assert sock.vui_token == 'new-token'

    def test_received_refused_token_is_answered_and_socket_stays_open(self, manager):
        sock = _open(manager, 's1', 'devices/a')
        sock.environ = {'ws4py.app': manager}
        manager._agent.get_user_claims = MagicMock(return_value={})
        sock.received_message(_message(json.dumps({'access_token': 'nope'})))
        assert json.loads(sock.sent[-1]) == {'error': 'Not Authorized'}
        assert not sock.terminated and sock.vui_token == 'token-s1'

    @pytest.mark.parametrize('payload', [b'hello', b'{"other": 1}', b'["access_token"]', b'{"access_token": 5}',
                                         b'\xff\xfe'])
    def test_other_messages_get_the_help_text(self, manager, payload):
        sock = _open(manager)
        sock.environ = {'ws4py.app': manager}
        sock.received_message(_message(payload))
        assert json.loads(sock.sent[-1]) == {'error': VUIWebSocket.RENEWAL_HELP}
        manager._agent.get_user_claims.assert_not_called()
