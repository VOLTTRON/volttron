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

import os
import weakref
from datetime import datetime

from .base import SubsystemBase
from volttron.platform.messaging.headers import TIMESTAMP
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)
from volttron.platform.scheduling import periodic
from ..errors import Unreachable

"""The heartbeat subsystem adds an optional periodic publish to all agents.
Heartbeats can be started with agents and toggled on and off at runtime.
"""

__docformat__ = 'reStructuredText'
__version__ = '1.0'


class Heartbeat(SubsystemBase):
    def __init__(self, owner, core, rpc, pubsub, heartbeat_autostart,
                 heartbeat_period):
        self.owner = owner
        self.core = weakref.ref(core)
        self.pubsub = weakref.ref(pubsub)

        self.autostart = heartbeat_autostart
        self.period = heartbeat_period
        self.enabled = False
        self.connect_error = False

        def onsetup(sender, **kwargs):
            rpc.export(self.start, 'heartbeat.start')
            rpc.export(self.start_with_period, 'heartbeat.start_with_period')
            rpc.export(self.stop, 'heartbeat.stop')
            rpc.export(self.restart, 'heartbeat.restart')
            rpc.export(self.set_period, 'heartbeat.set_period')

        def onstart(sender, **kwargs):
            if self.autostart:
                self.start()

        core.onsetup.connect(onsetup, self)
        core.onstart.connect(onstart, self)
        core.onconnected.connect(self.reconnect)

    def start(self):
        """RPC method

        Starts an agent's heartbeat.
        """
        if not self.enabled:
            self.scheduled = self.core().schedule(periodic(self.period), self.publish)
            self.enabled = True

    def start_with_period(self, period):
        """RPC method

        Set period and start heartbeat.

        :param period: Time in seconds between publishes.
        """
        self.set_period(period)
        self.start()

    def reconnect(self, sender, **kwargs):
        if self.connect_error:
            self.restart()
            self.connect_error = False

    def stop(self):
        """RPC method

        Stop an agent's heartbeat.
        """
        if self.enabled:
            # Trap the fact that scheduled may not have been
            # set yet if the start hasn't been called.
            try:
                self.scheduled.cancel()
            except AttributeError:
                pass
            self.enabled = False

    def restart(self):
        """RPC method

        Restart the heartbeat with the current period.  The heartbeat will
        be immediately sending the heartbeat to the message bus.
        """
        self.stop()
        self.start()

    def set_period(self, period):
        """RPC method

        Set heartbeat period.

        :param period: Time in seconds between publishes.
        """
        if self.enabled:
            self.stop()
            self.period = period
            self.start()
        else:
            self.period = period

    def publish(self):
        topic = 'heartbeat/' + self.core().identity
        headers = {TIMESTAMP: format_timestamp(get_aware_utc_now())}
        message = self.owner.vip.health.get_status_value()
        try:
            self.pubsub().publish('pubsub', topic, headers, message)
        except Unreachable as exc:
            self.connect_error = True
            self.stop()
