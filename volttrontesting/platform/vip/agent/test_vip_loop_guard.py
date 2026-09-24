"""Unit tests for the vip_loop handler guard (#3279).

Before this fix, an exception raised by a subsystem handler propagated out of
ZMQCore's vip_loop, ending that greenlet. Core.run then raised
RuntimeError('VIP loop ended prematurely') and the agent became
unrecoverable. These tests drive the real vip_loop code through Core.run and
Core.stop, with the socket and ZMQ connection faked so no network I/O or
authentication setup is needed.
"""
import gevent
import gevent.event
import pytest
from zmq.green import ENOTSOCK, ZMQError

from volttron.platform.vip.agent.core import ZMQCore
from volttron.platform.vip.socket import Message


class _WatchdogExpired(BaseException):
    """A test-only deadline signal, deliberately not an Exception.

    TimeoutError (an Exception subclass, MRO TimeoutError -> OSError ->
    Exception -> BaseException) would be swallowed by an internal
    `except Exception:` guard running in the same greenlet, silently
    turning a hung call into a passing test. This class stays outside
    Exception so it always reaches the test.
    """


class _Owner:
    """A minimal agent-like owner for Core.setup(); no annotated members."""


class _FakeSocket:
    """Stands in for the DEALER socket vip_loop reads from.

    recv_vip_object yields the queued messages in order, then blocks
    (simulating an idle, still-connected socket) unless told to raise.
    """

    def __init__(self, messages, then_raise=None):
        self._messages = list(messages)
        self._then_raise = then_raise
        self._idle = gevent.event.Event()
        self.sent = []

    def recv_vip_object(self, copy=False):
        if self._messages:
            return self._messages.pop(0)
        if self._then_raise is not None:
            raise self._then_raise
        self._idle.wait()    # simulate a socket with nothing more to read
        raise AssertionError('unreachable: idle event is never set')

    def send_vip_object(self, message, copy=False):
        self.sent.append(message)

    def monitor(self, *args, **kwargs):
        pass


class _FakeConnection:
    """Stands in for ZMQConnection so vip_loop runs with no real ZMQ I/O."""

    def __init__(self, socket, *args, **kwargs):
        self.socket = socket

    def open_connection(self, socket_type):
        pass

    def set_properties(self, flags):
        pass

    def connect(self, callback=None):
        pass

    def send_vip_object(self, message, flags=0, copy=True, track=False):
        pass

    def disconnect(self):
        pass

    def close_connection(self, linger=5):
        pass


def _make_core(monkeypatch, fake_socket):
    """A ZMQCore wired to fake_socket via a faked ZMQConnection.

    address is neither 'inproc:', 'tcp:' nor 'ipc:' prefixed, so loop()
    skips both the hello handshake and the monitor greenlet: vip_loop is
    the only thing driving the fake socket.
    """
    monkeypatch.setattr(
        'volttron.platform.vip.agent.core.ZMQConnection',
        lambda *a, **kw: _FakeConnection(fake_socket, *a, **kw))
    return ZMQCore(_Owner(),
                   address='fake://unittest',
                   identity='testagent',
                   enable_auth=False,
                   messagebus='zmq')


def test_handler_exception_is_logged_and_next_message_still_delivered(
        monkeypatch, caplog):
    # Criteria 1 and 2 of #3279.
    delivered = gevent.event.Event()
    received = []

    def raising_handler(message):
        raise ValueError('boom from subsystem handler')

    def normal_handler(message):
        received.append(message)
        delivered.set()

    fake_socket = _FakeSocket([
        Message(peer='router', subsystem='raising', id='m1', args=[]),
        Message(peer='router', subsystem='normal', id='m2', args=[]),
    ])
    core = _make_core(monkeypatch, fake_socket)
    core.register('raising', raising_handler)
    core.register('normal', normal_handler)

    run_greenlet = gevent.spawn(core.run)
    try:
        with caplog.at_level('ERROR'):
            assert delivered.wait(5), (
                'the message after the raising handler was never delivered:'
                ' the loop greenlet died')

        assert len(received) == 1
        assert received[0].id == 'm2'

        # criterion 1: the handler exception was logged with its traceback,
        # not swallowed silently.
        error_records = [r for r in caplog.records if r.levelname == 'ERROR']
        assert any(r.exc_info is not None for r in error_records), (
            'no ERROR log record carried the handler exception traceback')
        assert any('boom from subsystem handler' in r.getMessage()
                   or (r.exc_info and 'boom from subsystem handler'
                       in str(r.exc_info[1]))
                   for r in error_records)
    finally:
        with gevent.Timeout(5, _WatchdogExpired('core.stop() hung')):
            core.stop(timeout=5)
        run_greenlet.join(5)
        run_greenlet.kill()


def test_core_stop_returns_after_handler_exception(monkeypatch):
    # Criterion 3 of #3279: core.stop() must not hang once a handler has
    # raised. The vip_loop greenlet stays parked (idle) after the raising
    # message, exactly as it would in production while waiting for more
    # traffic; stop() must still return promptly.
    def raising_handler(message):
        raise ValueError('boom')

    fake_socket = _FakeSocket([
        Message(peer='router', subsystem='raising', id='m1', args=[]),
    ])
    core = _make_core(monkeypatch, fake_socket)
    core.register('raising', raising_handler)

    run_greenlet = gevent.spawn(core.run)
    try:
        gevent.sleep(0.2)    # let vip_loop process the raising message

        with gevent.Timeout(5, _WatchdogExpired('core.stop() hung')):
            core.stop(timeout=5)
    finally:
        run_greenlet.join(5)
        run_greenlet.kill()


def test_greenletexit_from_handler_still_ends_the_loop(monkeypatch):
    # Criterion 4 of #3279: an exception that legitimately ends the loop
    # (here, GreenletExit escaping a handler) must still end it. Only
    # Exception is swallowed by the guard; BaseException is not.
    def killing_handler(message):
        raise gevent.GreenletExit('legitimately ending the loop')

    fake_socket = _FakeSocket([
        Message(peer='router', subsystem='killing', id='m1', args=[]),
    ])
    core = _make_core(monkeypatch, fake_socket)
    core.register('killing', killing_handler)

    run_greenlet = gevent.spawn(core.run)
    run_greenlet.join(5)
    assert run_greenlet.ready(), 'core.run() never returned'
    with pytest.raises(RuntimeError, match='VIP loop ended prematurely'):
        run_greenlet.get()


def test_socket_closed_error_still_ends_the_loop(monkeypatch):
    # Criterion 4 of #3279, the other half: a closed-socket ZMQError
    # (ENOTSOCK) is unrelated to the handler guard and must still end the
    # loop exactly as before this change.
    fake_socket = _FakeSocket([], then_raise=ZMQError(ENOTSOCK))
    core = _make_core(monkeypatch, fake_socket)

    run_greenlet = gevent.spawn(core.run)
    run_greenlet.join(5)
    assert run_greenlet.ready(), 'core.run() never returned'
    with pytest.raises(RuntimeError, match='VIP loop ended prematurely'):
        run_greenlet.get()


def test_gevent_timeout_from_handler_does_not_kill_the_loop(monkeypatch):
    # gevent.Timeout subclasses BaseException directly (it does not
    # subclass Exception), so a bare `except Exception` does not catch it.
    # An AsyncResult.get(timeout=...) inside a handler raises exactly this
    # on expiry, and that is an operational timeout, not a signal that
    # should end the loop.
    delivered = gevent.event.Event()
    received = []

    def timing_out_handler(message):
        # gevent.Timeout's first positional arg is seconds, not a message;
        # an AsyncResult.get(timeout=N) that expires raises a bare Timeout
        # the same way (no seconds, no explicit exception argument).
        raise gevent.Timeout()

    def normal_handler(message):
        received.append(message)
        delivered.set()

    fake_socket = _FakeSocket([
        Message(peer='router', subsystem='timing_out', id='m1', args=[]),
        Message(peer='router', subsystem='normal', id='m2', args=[]),
    ])
    core = _make_core(monkeypatch, fake_socket)
    core.register('timing_out', timing_out_handler)
    core.register('normal', normal_handler)

    run_greenlet = gevent.spawn(core.run)
    try:
        assert delivered.wait(5), (
            'the message after the gevent.Timeout handler was never'
            ' delivered: the loop greenlet died')
        assert len(received) == 1
        assert received[0].id == 'm2'
    finally:
        with gevent.Timeout(5, _WatchdogExpired('core.stop() hung')):
            core.stop(timeout=5)
        run_greenlet.join(5)
        run_greenlet.kill()


def test_unknown_subsystem_reply_is_sent_correctly(monkeypatch):
    # The KeyError branch was moved unchanged out of vip_loop's inline
    # body; this pins that the move preserved its behavior, using
    # _FakeSocket.sent (previously unread by any test).
    fake_socket = _FakeSocket([
        Message(peer='router', subsystem='nosuchsubsystem', id='m1',
                args=[]),
    ])
    core = _make_core(monkeypatch, fake_socket)

    run_greenlet = gevent.spawn(core.run)
    try:
        deadline = gevent.Timeout(5, TimeoutError('reply was never sent'))
        with deadline:
            while not fake_socket.sent:
                gevent.sleep(0.05)
        reply = fake_socket.sent[0]
        assert reply.subsystem == 'error'
        assert reply.peer == 'router'
        assert reply.args[-1] == 'nosuchsubsystem'
    finally:
        with gevent.Timeout(5, _WatchdogExpired('core.stop() hung')):
            core.stop(timeout=5)
        run_greenlet.join(5)
        run_greenlet.kill()
