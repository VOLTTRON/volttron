"""Unit tests for the bounded VIP send lock (#3280).

Socket._sending in volttron.platform.vip.green acquired the per-socket send
lock with no deadline. A greenlet wedged inside the network send therefore
blocked every other greenlet on that socket forever, with no error and no
diagnostic. These tests park a deliberate holder on the real lock (through
the real _sending context manager) and drive the real send_vip path against
it; none of them starts a platform.
"""
import time

import gevent
import gevent.event
import pytest
import zmq
import zmq.green
from zmq.error import Again, ZMQError

from volttron.platform.vip import green
from volttron.platform.vip.socket import Address, SendLockTimeout, nonblocking


def test_send_lock_timeout_is_not_a_zmqerror():
    # Criterion 1: PeerList and Ping catch ZMQError and act only on
    # ENOTSOCK, so a ZMQError subclass here would be swallowed into an
    # AsyncResult that is never filled.
    assert not issubclass(SendLockTimeout, ZMQError)


def _hold_lock_and_wait(sock, ready_event, hold_for=30):
    """Park a greenlet holding sock's send lock, via the real _sending path.

    Used by every contention test below: the greenlet enters the same
    critical section a real send would, so the lock, the owner-tracking
    attribute, and the parked stack are all the production ones.
    """
    with sock._sending(0):
        ready_event.set()
        gevent.sleep(hold_for)


def test_uncontended_send_completes_and_peer_receives_in_order():
    # Control for T1: proves a working send_vip round trip before any test
    # asserts one fails under contention.
    ctx = zmq.green.Context()
    peer = green.Socket(ctx, zmq.ROUTER)
    peer.bind(Address('inproc://t2-uncontended', domain='test'))
    sock = green.Socket(ctx, zmq.DEALER)
    sock.connect('inproc://t2-uncontended')

    sock.send_vip('', 'echo', args=['hello', 'world'], msg_id='t2')

    msg = peer.recv_vip_object()
    assert msg.subsystem == 'echo'
    assert msg.id == 't2'
    assert msg.args == ['hello', 'world']


def test_contended_send_raises_send_lock_timeout(monkeypatch):
    # Criterion 1. RED against the unfixed code in about 5 seconds: the
    # unbounded acquire blocks, this test's own gevent.Timeout(5) fires
    # instead of SendLockTimeout, and pytest.raises re-raises it as a fast,
    # specific failure rather than a 300-second suite hang.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.5)
    ctx = zmq.green.Context()
    sock = green.Socket(ctx, zmq.DEALER)
    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, sock, ready)
    try:
        assert ready.wait(2), 'the holder greenlet never took the lock'
        t0 = time.monotonic()
        with pytest.raises(SendLockTimeout):
            with gevent.Timeout(5):
                sock.send_vip('', 'peerlist', args=['list'], msg_id='x')
        elapsed = time.monotonic() - t0
        # the lower bound proves the deadline was honored, not skipped; the
        # upper bound proves some other path did not return early.
        assert 0.4 < elapsed < 3
    finally:
        g.kill()


def test_reentrant_acquire_by_owner_neither_blocks_nor_times_out():
    # Criterion 3 of #3280. send_vip re-enters _sending twice per call,
    # through send_multipart for the header frames and again for the args
    # frame; a reentrant acquire by the owning greenlet must succeed
    # immediately.
    ctx = zmq.green.Context()
    peer = green.Socket(ctx, zmq.ROUTER)
    peer.bind(Address('inproc://t3-reentrant', domain='test'))
    sock = green.Socket(ctx, zmq.DEALER)
    sock.connect('inproc://t3-reentrant')

    sock.send_vip('', 'echo', args=['hi'], msg_id='reentrant')
    peer.recv_vip_object()

    lock = sock._Socket__send_lock
    assert lock.acquire(True, 0.1)
    assert lock.acquire(True, 0.1)
    lock.release()
    lock.release()


def test_lock_timeout_leaves_send_state_and_wire_untouched(monkeypatch):
    # Criterion 4 of #3280. A DEALER's idle _send_state is 0, which is
    # also the value every reset path writes, so comparing 0 to 0 cannot
    # fail and a state-resetting mutant would stay green. On a
    # ROUTER, 0 is never the idle/reset value (-1 is, per _Socket.__init__
    # and reset_send), so advancing to 0 for real, with a direct
    # SNDMORE send, gives a value a corrupting mutant cannot fake.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    router = green.Socket(ctx, zmq.ROUTER)
    router.bind(Address('inproc://t4-state', domain='test'))
    dealer_peer = green.Socket(ctx, zmq.DEALER)
    dealer_peer.identity = b'peer-identity'
    dealer_peer.connect('inproc://t4-state')

    assert router._send_state == -1, 'ROUTER idle state should be -1'
    router.send(b'peer-identity', flags=zmq.SNDMORE)
    state_before = router._send_state
    assert state_before == 0, 'the direct send above should be mid-message'

    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, router, ready)
    try:
        assert ready.wait(2)
        with pytest.raises(SendLockTimeout):
            with gevent.Timeout(5):
                router.send_vip('peer-identity', 'echo', args=['x'],
                                msg_id='timeout', via=b'peer-identity')
        assert router._send_state == state_before, (
            'a lock timeout must not touch the in-progress send state')
        assert dealer_peer.poll(50) == 0, (
            'peer received a frame from a timed-out send')
    finally:
        g.kill()    # releases the lock via _sending's finally

    # The lock itself is usable again once the real holder is gone: proof
    # the timeout path did not leak it (pinned more directly by
    # test_timed_out_acquirer_does_not_hold_or_release_the_lock below).
    assert router._Socket__send_lock.acquire(True, 1)
    router._Socket__send_lock.release()


def test_timed_out_acquirer_does_not_hold_or_release_the_lock(monkeypatch):
    # Proves the timeout path did not half-acquire and did not release
    # someone else's lock: the lock stays held by the real holder until it
    # is killed, then becomes acquirable again.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    sock = green.Socket(ctx, zmq.DEALER)
    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, sock, ready)
    try:
        assert ready.wait(2)
        with pytest.raises(SendLockTimeout):
            with gevent.Timeout(5):
                sock.send_vip('', 'peerlist', args=['list'], msg_id='x')

        assert not sock._Socket__send_lock.acquire(False), (
            'the lock was free after a timeout: the timed-out acquirer or'
            ' the real holder released it wrongly')
    finally:
        g.kill()

    assert sock._Socket__send_lock.acquire(True, 1)
    sock._Socket__send_lock.release()


def test_report_generation_failure_still_raises_send_lock_timeout(
        monkeypatch):
    # A failure while building the holder report (for example a __repr__
    # that raises) must not replace SendLockTimeout with some other
    # exception type, which every downstream ZMQError or SendLockTimeout
    # handler would then miss entirely.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    sock = green.Socket(ctx, zmq.DEALER)

    def _raises_instead_of_describing():
        raise RuntimeError('boom from report generation')

    monkeypatch.setattr(
        sock, '_describe_send_lock_holder', _raises_instead_of_describing)

    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, sock, ready)
    try:
        assert ready.wait(2)
        with pytest.raises(SendLockTimeout):
            with gevent.Timeout(5):
                sock.send_vip('', 'peerlist', args=['list'], msg_id='x')
    finally:
        g.kill()


def test_report_generation_gevent_timeout_still_raises_send_lock_timeout(
        monkeypatch):
    # gevent.Timeout subclasses BaseException directly, not Exception, so
    # an `except Exception` here would let it escape and replace
    # SendLockTimeout, same reasoning as everywhere else this change
    # widened a guard to (Exception, gevent.Timeout).
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    sock = green.Socket(ctx, zmq.DEALER)

    def _raises_instead_of_describing():
        raise gevent.Timeout(0, 'simulated unexpected yield mid-report')

    monkeypatch.setattr(
        sock, '_describe_send_lock_holder', _raises_instead_of_describing)

    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, sock, ready)
    try:
        assert ready.wait(2)
        with pytest.raises(SendLockTimeout):
            with gevent.Timeout(5):
                sock.send_vip('', 'peerlist', args=['list'], msg_id='x')
    finally:
        g.kill()


def test_diagnostic_stays_out_of_the_exception_and_never_leaks_a_payload(
        monkeypatch, caplog):
    # A SendLockTimeout can cross the RPC boundary. jsonrpc.py serializes
    # str(exc), exc.args, and any attribute an RPC method attaches to the
    # exception object, back to a remote caller. So the holder's stack
    # (absolute paths, source text) and anything derived from its call
    # arguments must never be in the exception's message, args, or
    # __dict__; the rich diagnostic goes to the local log only.
    #
    # The holder is spawned carrying a real payload through send_vip (not
    # a bare unread local), matching the RPC-argument path the review
    # found; gevent's own Greenlet.__repr__ embeds spawn arguments
    # (confirmed separately), so repr(holder) is never called.
    #
    # The greenlet is parked inside a monkeypatched send_multipart, which
    # is the innermost (leaf) frame on its stack while suspended. That
    # closes an earlier mutation gap (a mutation that dumped only the leaf
    # frame's locals survived, because the leaf frame used to be inside
    # gevent/zmq internals with no application-level local in it); here
    # the leaf frame is application code and msg_parts is the marker.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    peer = green.Socket(ctx, zmq.ROUTER)
    peer.bind(Address('inproc://t6-payload', domain='test'))
    sock = green.Socket(ctx, zmq.DEALER)
    sock.connect('inproc://t6-payload')

    ready = gevent.event.Event()
    marker = 'RPC-PAYLOAD-MARKER-SECRET'
    real_send_multipart = sock.send_multipart

    def parking_send_multipart(msg_parts, *a, **kw):
        ready.set()
        gevent.sleep(30)
        return real_send_multipart(msg_parts, *a, **kw)

    sock.send_multipart = parking_send_multipart
    g = gevent.spawn(sock.send_vip, '', 'echo', args=[marker],
                     msg_id='hold-marker')
    try:
        assert ready.wait(2)
        with caplog.at_level('ERROR'):
            with pytest.raises(SendLockTimeout) as excinfo:
                with gevent.Timeout(5):
                    sock.send_vip('', 'peerlist', args=['list'], msg_id='x')

        exc_text = str(excinfo.value)
        assert marker not in exc_text
        assert repr(g) not in exc_text
        assert 'test_green_socket.py' not in exc_text, (
            'the stack must not be in the exception: it crosses the RPC'
            ' boundary (jsonrpc.py returns str(exc) and exc.args to a'
            ' remote caller)')
        # The message is not the only place a payload could hide: a
        # mutant that attached the holder to the exception object without
        # touching its message (e.g. exc.exc_info = {...}) must also be
        # caught, because rpc.py's own exception path sets exc_info and
        # jsonrpc.py ships it to the remote caller unchanged.
        assert marker not in repr(excinfo.value.args)
        assert excinfo.value.__dict__ == {}

        log_text = '\n'.join(r.getMessage() for r in caplog.records)
        assert marker not in log_text
        assert repr(g) not in log_text
        assert 'test_green_socket.py' in log_text, (
            'the stack should still be available locally, in the log')
    finally:
        g.kill()


def test_diagnostic_says_so_when_the_holder_is_unknown(monkeypatch):
    # self._Socket__send_owner is read after the acquire has already
    # failed, so the real holder may have released by then. Naming a
    # wrong or bare "None" holder is worse than saying plainly that it
    # could not be identified.
    monkeypatch.setattr(green, 'SEND_LOCK_TIMEOUT', 0.3)
    ctx = zmq.green.Context()
    sock = green.Socket(ctx, zmq.DEALER)

    assert sock._Socket__send_owner is None    # never held yet
    assert 'could not be identified' in sock._describe_send_lock_holder()


def test_noblock_send_fails_fast_when_held_and_succeeds_when_free(monkeypatch):
    # A NOBLOCK send must not spin forever either: the pre-fix retry loop
    # kept spinning with no deadline as long as the socket stayed
    # writable, which defeats a caller who explicitly asked not to block.
    monkeypatch.setattr(green, 'NOBLOCK_LOCK_SPIN', 0.05)
    ctx = zmq.green.Context()
    peer = green.Socket(ctx, zmq.ROUTER)
    peer.bind(Address('inproc://t7-noblock', domain='test'))
    sock = green.Socket(ctx, zmq.DEALER)
    sock.connect('inproc://t7-noblock')

    ready = gevent.event.Event()
    g = gevent.spawn(_hold_lock_and_wait, sock, ready)
    try:
        assert ready.wait(2)
        t0 = time.monotonic()
        with pytest.raises(Again):
            with nonblocking(sock):
                sock.send_vip('', 'peerlist', args=['list'], msg_id='x')
        assert time.monotonic() - t0 < 0.5
    finally:
        g.kill()

    # control: without a holder, the same call succeeds and is delivered.
    with nonblocking(sock):
        sock.send_vip('', 'peerlist', args=['list'], msg_id='y')
    msg = peer.recv_vip_object()
    assert msg.id == 'y'


def test_gevent_lock_rlock_acquire_takes_blocking_and_timeout():
    # Confirm the installed gevent's RLock.acquire signature before relying
    # on a positional timeout argument. Established by calling it both ways
    # and by inspecting the bound method's signature; both must agree with
    # SEND_LOCK_TIMEOUT's usage in green.py, `lock.acquire(True,
    # SEND_LOCK_TIMEOUT)`.
    import inspect

    from gevent.lock import RLock

    sig = inspect.signature(RLock.acquire)
    assert list(sig.parameters) == ['self', 'blocking', 'timeout']

    lock = RLock()
    assert lock.acquire(True, 1.0) is True    # positional form used in green.py
    lock.release()
    assert lock.acquire(blocking=True, timeout=1.0) is True    # keyword form
    lock.release()
