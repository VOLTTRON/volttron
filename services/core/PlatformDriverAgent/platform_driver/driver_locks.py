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

from collections import defaultdict
import logging
from gevent.lock import BoundedSemaphore, DummySemaphore
from contextlib import contextmanager

from volttron.platform.agent import utils
utils.setup_logging()
_log = logging.getLogger(__name__)

_socket_lock = None

def configure_socket_lock(max_connections=0):
    global _socket_lock
    if _socket_lock is not None:
        raise RuntimeError("socket_lock already configured!")
    if max_connections < 1:
        _socket_lock = DummySemaphore()
    else:
        _socket_lock = BoundedSemaphore(max_connections)

@contextmanager
def socket_lock():
    global _socket_lock
    if _socket_lock is None:
        raise RuntimeError("socket_lock not configured!")
    _socket_lock.acquire()
    try:
        yield
    finally:
        _socket_lock.release()

_publish_lock = None

def configure_publish_lock(max_connections=0):
    global _publish_lock
    if _publish_lock is not None:
        raise RuntimeError("socket_lock already configured!")
    if max_connections < 1:
        _publish_lock = DummySemaphore()
    else:
        _publish_lock = BoundedSemaphore(max_connections)

@contextmanager
def publish_lock():
    global _publish_lock
    if _publish_lock is None:
        raise RuntimeError("socket_lock not configured!")
    _publish_lock.acquire()
    try:
        yield
    finally:
        _publish_lock.release()

_client_socket_locks  = defaultdict(lambda: None)
lock_counter = 0

def configure_client_socket_lock(address, port, max_connections=0):
    _log.debug("Configuring client socket lock for {}:{}".format(address, port))
    global _client_socket_locks
    if _client_socket_locks[(address, port)] is not None:
        if isinstance(_client_socket_locks[(address, port)], DummySemaphore) or isinstance(_client_socket_locks[(address, port)], BoundedSemaphore):
            _log.debug(f"Client socket lock already configured for {address}:{port}")
            return
        else:
            raise RuntimeError("client socket lock already configured!")
    if max_connections < 1:
        _client_socket_locks[(address, port)] = DummySemaphore()
    else:
        _client_socket_locks[(address, port)] = BoundedSemaphore(max_connections)

@contextmanager
def client_socket_locks(address, port):
    global _client_socket_locks
    lock = _client_socket_locks[(address, port)]
    _log.debug(f"ADDRESS: {address}")
    _log.debug(f"PORT: {port}")
    _log.debug(f"Acquiring client socket lock ({type(lock)}) for {address}:{port} at {id(lock)}")
    if lock is None:
        _log.debug(f"socket_lock not configured {address}:{port}")
        _log.debug(f"lock is None: lock: {lock}, type: {type(lock)}, id ${id(lock)}")
        raise RuntimeError("socket_lock not configured!")
    lock.acquire()
    global lock_counter
    lock_counter +=1
    _log.debug(f"lock_counter: {lock_counter}")

    try:
        yield
    finally:
        _log.debug(f"Releasing client socket lock ({type(lock)}) for {address}:{port} at {id(lock)}")
        lock.release()
        lock_counter -=1
        _log.debug(f"lock_counter after release: {lock_counter}")