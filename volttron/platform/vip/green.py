# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

'''VIP - VOLTTRON™ Interconnect Protocol implementation

See https://github.com/VOLTTRON/volttron/wiki/VIP for protocol
specification.

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

from . import *
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
