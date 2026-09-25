"""Unit tests for the RPC reply-send guard (#3280 review).

RPC._handle_subsystem is @spawn'ed and never joined. Its reply send used
to sit in a try whose only handler was `except ZMQError`, and
SendLockTimeout is deliberately not a ZMQError, so the exception killed
the unjoined greenlet with a stderr traceback only: no log record, and
the caller's AsyncResult was never filled.
"""
import weakref

import pytest

from volttron.platform.vip.agent.subsystems.rpc import RPC
from volttron.platform.vip.socket import Message, SendLockTimeout


class _FakeDispatcher:
    """Any truthy dispatch result exercises the reply-send branch below."""

    def dispatch(self, msg, message):
        return 'a-response'


class _FakeConnection:
    def __init__(self, raises=None):
        self._raises = raises
        self.sent = []

    def send_vip_object(self, message, copy=True, track=False):
        if self._raises is not None:
            raise self._raises
        self.sent.append(message)

    def send_vip(self, peer, subsystem, args=None, msg_id=b'', user=b'',
                via=None, flags=0, copy=True, track=False):
        if self._raises is not None:
            raise self._raises
        self.sent.append((peer, subsystem, args))


class _FakeCore:
    """core is held by weakref.ref in RPC; the test keeps this alive."""

    def __init__(self, connection):
        self.connection = connection
        self.identity = 'testagent'
        self.messagebus = 'zmq'


def _make_rpc(connection):
    rpc = RPC.__new__(RPC)
    fake_core = _FakeCore(connection)
    rpc.core = weakref.ref(fake_core)
    rpc._dispatcher = _FakeDispatcher()
    rpc._isconnected = True
    rpc._message_bus = 'zmq'
    rpc.peer_list = {}
    return rpc, fake_core


def test_reply_send_failure_is_logged_and_does_not_kill_the_greenlet(caplog):
    connection = _FakeConnection(raises=SendLockTimeout('simulated'))
    rpc, fake_core = _make_rpc(connection)
    message = Message(peer='caller', subsystem='RPC', id='call-1', args=['x'])

    with caplog.at_level('ERROR'):
        g = rpc._handle_subsystem(message)    # @spawn: runs in its own greenlet
        g.join(5)

    assert g.ready(), 'the spawned greenlet never finished'
    assert g.exception is None, (
        'the guard should have caught the send failure inside the greenlet,'
        ' not let it kill the unjoined greenlet')
    error_records = [r for r in caplog.records if r.levelname == 'ERROR']
    assert any(r.exc_info is not None for r in error_records), (
        'no ERROR log record carried the send failure traceback')
    assert not connection.sent, 'a failed send must not be recorded as sent'


def test_reply_send_succeeds_normally():
    # Control: proves the guard does not interfere with an ordinary,
    # successful reply.
    connection = _FakeConnection()
    rpc, fake_core = _make_rpc(connection)
    message = Message(peer='caller', subsystem='RPC', id='call-2', args=['x'])

    g = rpc._handle_subsystem(message)
    g.join(5)

    assert g.ready()
    assert g.exception is None
    assert connection.sent and connection.sent[0].id == 'call-2'


def test_reply_send_zmqerror_enotsock_still_handled_as_before():
    # Control: the pre-existing ZMQError/ENOTSOCK path is unchanged by the
    # new guard (it is caught first, by the earlier except clause).
    from zmq import ZMQError
    from zmq.green import ENOTSOCK

    connection = _FakeConnection(raises=ZMQError(ENOTSOCK))
    rpc, fake_core = _make_rpc(connection)
    message = Message(peer='caller', subsystem='RPC', id='call-3', args=['x'])

    g = rpc._handle_subsystem(message)
    g.join(5)

    assert g.ready()
    assert g.exception is None


def _make_external_rpc_message():
    # args items that are strings go through jsonapi.loads(); a plain dict
    # skips that and is passed straight to dispatch().
    rpc_msg = {
        'args': [{'x': 1}],
        'from_platform': 'platform-a',
        'from_peer': 'peer-a',
        'to_platform': 'platform-b',
        'to_peer': 'peer-b',
    }
    return Message(peer='caller', subsystem='external_rpc', id='ext-1',
                   args=['operation', rpc_msg])


def test_external_rpc_reply_send_failure_is_logged_and_does_not_kill_the_greenlet(
        caplog):
    # The same unguarded-send shape as _handle_subsystem, found in the
    # sibling external-RPC handler while sweeping for every site that can
    # now raise SendLockTimeout and is not guarded.
    connection = _FakeConnection(raises=SendLockTimeout('simulated'))
    rpc, fake_core = _make_rpc(connection)
    message = _make_external_rpc_message()

    with caplog.at_level('ERROR'):
        g = rpc._handle_external_rpc_subsystem(message)
        g.join(5)

    assert g.ready(), 'the spawned greenlet never finished'
    assert g.exception is None, (
        'the guard should have caught the send failure inside the greenlet')
    error_records = [r for r in caplog.records if r.levelname == 'ERROR']
    assert any(r.exc_info is not None for r in error_records), (
        'no ERROR log record carried the send failure traceback')
    assert not connection.sent, 'a failed send must not be recorded as sent'


def test_external_rpc_reply_send_succeeds_normally():
    connection = _FakeConnection()
    rpc, fake_core = _make_rpc(connection)
    message = _make_external_rpc_message()

    g = rpc._handle_external_rpc_subsystem(message)
    g.join(5)

    assert g.ready()
    assert g.exception is None
    assert connection.sent and connection.sent[0][1] == 'external_rpc'
