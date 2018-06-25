# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import os
import weakref
from datetime import datetime

from .base import SubsystemBase
from volttron.platform.messaging.headers import TIMESTAMP
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)

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

    def start(self):
        """RPC method

        Starts an agent's heartbeat.
        """
        if not self.enabled:
            self.greenlet = self.core().periodic(self.period, self.publish)
            self.enabled = True

    def start_with_period(self, period):
        """RPC method

        Set period and start heartbeat.

        :param period: Time in seconds between publishes.
        """
        self.set_period(period)
        self.start()

    def stop(self):
        """RPC method

        Stop an agent's heartbeat.
        """
        if self.enabled:
            self.greenlet.kill()
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

        self.pubsub().publish('pubsub', topic, headers, message)
