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

'''VIP - VOLTTRON(TM) Interconnect Protocol implementation

See https://volttron.readthedocs.io/en/develop/core_services/messagebus/VIP/VIP-Overview.html
for protocol specification.

This module is for use within gevent. It provides some locking around
send operations to protect the VIP state. It should be safe to use a
single socket in multiple greenlets without any kind of locking.
'''




import logging
from contextlib import contextmanager as _contextmanager
from time import monotonic as _monotonic
from traceback import format_stack as _format_stack

from gevent import getcurrent as _getcurrent
from gevent import sleep as _sleep
from gevent import Timeout as _Timeout
from gevent.local import local as _local
from gevent.lock import RLock as _RLock

from zmq.green import NOBLOCK, POLLOUT
from zmq import green as _green

from .router import BaseRouter as _BaseRouter
from .socket import SendLockTimeout, _Socket

_log = logging.getLogger(__name__)

# Longest a greenlet will wait for another greenlet on the same socket to
# finish framing a message. The lock serializes framing only; the network
# wait happens inside the critical section, so a wait this long means the
# holder is wedged, not that a peer is slow. Module global so a test can
# monkeypatch it without touching the socket's setsockopt-backed attributes.
SEND_LOCK_TIMEOUT = 60.0

# Longest a NOBLOCK send will spin waiting for the lock before reporting
# Again. A NOBLOCK caller asked not to block.
NOBLOCK_LOCK_SPIN = 0.05


class Socket(_Socket, _green.Socket):
    _context_class = _green.Context
    _local_class = _local

    def __init__(self, *args, **kwargs):
        super(Socket, self).__init__(*args, **kwargs)
        # zmq.Socket maps unknown attribute assignment onto setsockopt, so
        # every per-instance attribute here must go through
        # object.__setattr__, both here and on every later write.
        object.__setattr__(self, '_Socket__send_lock', _RLock())
        object.__setattr__(self, '_Socket__send_owner', None)

    @_contextmanager
    def _sending(self, flags):
        flags |= getattr(self._Socket__local, 'flags', 0)
        lock = self._Socket__send_lock
        if flags & NOBLOCK:
            deadline = _monotonic() + NOBLOCK_LOCK_SPIN
            while not lock.acquire(False):
                if not self.poll(0, POLLOUT) or _monotonic() >= deadline:
                    raise _green.Again()
                _sleep(0)
        elif not lock.acquire(True, SEND_LOCK_TIMEOUT):
            self._log_send_lock_timeout()
            raise SendLockTimeout(
                'send lock held for more than %.1fs; see the local log for'
                ' the holder' % SEND_LOCK_TIMEOUT)
        # The acquire stays outside the try: a failed or timed-out acquire
        # must never reach the release below.
        previous = self._Socket__send_owner
        object.__setattr__(self, '_Socket__send_owner', _getcurrent())
        try:
            yield flags
        finally:
            object.__setattr__(self, '_Socket__send_owner', previous)
            lock.release()

    def _log_send_lock_timeout(self):
        """Log the send-lock holder and its stack, to the local log only.

        This never reaches the raised exception's message or args: a
        SendLockTimeout from an RPC handler is serialized by jsonrpc.py
        (str(exc) and exc.args both go into the returned error) and
        returned across the RPC boundary to a remote caller. The holder's
        stack carries absolute filesystem paths and source text, and a
        handler's spawn arguments can carry RPC credentials (gevent's own
        Greenlet.__repr__ renders each argument, truncated to 50 chars,
        which is exactly how a reviewed defect put a password fragment
        into a returned RPC error). None of that belongs on the wire, so
        it is logged locally instead, and the exception carries no more
        than the bare fact of the timeout.

        A failure while building this report must not replace
        SendLockTimeout with some other exception type, so it is degraded
        rather than allowed to propagate. Exception and gevent.Timeout are
        caught, matching every other guard in this change: a realistic
        failure in this method (an AttributeError, a gevent.Timeout from
        something unexpectedly yielding) is degraded, while GreenletExit
        and other BaseException signals that legitimately end the process
        or greenlet still propagate, same as everywhere else.
        """
        try:
            _log.error(self._describe_send_lock_holder())
        except (Exception, _Timeout):
            _log.error('send lock held for more than %.1fs; holder'
                       ' description unavailable', SEND_LOCK_TIMEOUT)

    def _describe_send_lock_holder(self):
        """Build the holder description text for the local log.

        The holder is identified by type, name and id only, never by
        repr(): see _log_send_lock_timeout for why. If the holder cannot
        be identified (self._Socket__send_owner is read after the acquire
        has already failed, so the real holder may already have released
        by then), say so explicitly rather than rendering a wrong or
        misleadingly bare "None". The stack text (traceback.format_stack:
        file, line and source only, never frame locals) is safe to log
        locally but is exactly the disclosure surface that keeps it out of
        the exception itself.
        """
        holder = self._Socket__send_owner
        if holder is None:
            return ('send lock held for more than %.1fs; the holder could'
                     ' not be identified (it may have released the lock'
                     ' between the timeout and this report)'
                     % SEND_LOCK_TIMEOUT)
        holder_id = '%s(name=%r, id=0x%x)' % (
            type(holder).__name__, getattr(holder, 'name', None), id(holder))
        lines = ['send lock held for more than %.1fs by %s'
                 % (SEND_LOCK_TIMEOUT, holder_id)]
        frame = getattr(holder, 'gr_frame', None)
        if frame is not None:
            lines.extend(_format_stack(frame))
        return ''.join(lines)


class BaseRouter(_BaseRouter):
    _context_class = _green.Context
    _socket_class = _green.Socket
