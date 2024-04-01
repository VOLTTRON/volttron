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

import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import CONTROL_CONNECTION
from volttron.platform.vip.agent import Agent as BaseAgent

class ControlConnection(object):
    def __init__(self, address, peer="control"):
        self.address = address
        self.peer = peer
        message_bus = utils.get_messagebus()
        allow_auth = utils.is_auth_enabled()
        self._server = BaseAgent(
            address=self.address,
            enable_store=False,
            identity=CONTROL_CONNECTION,
            message_bus=message_bus,
            enable_channel=True,
            enable_auth=allow_auth
        )
        self._greenlet = None

    @property
    def server(self):
        if self._greenlet is None:
            event = gevent.event.Event()
            self._greenlet = gevent.spawn(self._server.core.run, event)
            event.wait()
        return self._server

    def call(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(self.peer, method, *args,
                                        **kwargs).get()

    def call_no_get(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(self.peer, method, *args, **kwargs)

    def notify(self, method, *args, **kwargs):
        return self.server.vip.rpc.notify(self.peer, method, *args, **kwargs)

    def kill(self, *args, **kwargs):
        """
        Resets a running greenlet and cleans up the internal stopped agent.
        """
        if self._greenlet is not None:
            try:
                self._server.core.stop()
            finally:
                self._server = None
            try:
                self._greenlet.kill(*args, **kwargs)
            finally:
                self._greenlet = None
