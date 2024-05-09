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

"""VIP - VOLTTRON™ Interconnect Protocol implementation

See https://volttron.readthedocs.io/en/develop/core_services/messagebus/VIP/VIP-Overview.html
for protocol specification.

This module is useful for using VIP outside of gevent. Please understand
that ZeroMQ sockets are not thread-safe and care must be used when using
across threads (or avoided all together). There is no locking around the
state as there is with the gevent version in the green sub-module.
"""

# Monkeypatch for gevent
from volttron.utils import monkey_patch
monkey_patch()

from threading import local as _local

import zmq as _zmq

from .socket import *
from .socket import _Socket

class Socket(_Socket, _zmq.Socket):
    _context_class = _zmq.Context
    _local_class = _local


class BaseConnection:
    """
    Base connection class for message bus connection.
    """
    def __init__(self, url, identity, instance_name):
        self._url = url
        self._identity = identity
        self._instance_name = instance_name
        self._vip_handler = None
