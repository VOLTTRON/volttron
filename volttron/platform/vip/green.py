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

'''VIP - VOLTTRON™ Interconnect Protocol implementation

See https://volttron.readthedocs.io/en/develop/core_services/messagebus/VIP/VIP-Overview.html
for protocol specification.

This module is for use within gevent. It provides some locking around
send operations to protect the VIP state. It should be safe to use a
single socket in multiple greenlets without any kind of locking.
'''




from contextlib import contextmanager as _contextmanager

from gevent import sleep as _sleep
from gevent.local import local as _local
from gevent.lock import RLock as _RLock

from zmq.green import NOBLOCK, POLLOUT
from zmq import green as _green

from .router import BaseRouter as _BaseRouter
from .socket import _Socket


class Socket(_Socket, _green.Socket):
    _context_class = _green.Context
    _local_class = _local

    def __init__(self, *args, **kwargs):
        super(Socket, self).__init__(*args, **kwargs)
        object.__setattr__(self, '_Socket__send_lock', _RLock())

    @_contextmanager
    def _sending(self, flags):
        flags |= getattr(self._Socket__local, 'flags', 0)
        lock = self._Socket__send_lock
        while not lock.acquire(not flags & NOBLOCK):
            if not self.poll(0, POLLOUT):
                raise _green.Again()
            _sleep(0)
        try:
            yield flags
        finally:
            lock.release()


class BaseRouter(_BaseRouter):
    _context_class = _green.Context
    _socket_class = _green.Socket
