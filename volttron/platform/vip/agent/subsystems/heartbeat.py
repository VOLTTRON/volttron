# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830


import os
import weakref
from datetime import datetime

from .base import SubsystemBase
from volttron.platform.messaging.headers import DATE
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
        topic = 'heartbeat/' + self.owner.__class__.__name__
        try:
            if os.environ['AGENT_UUID']:
                topic += '/' + os.environ['AGENT_UUID']
        except KeyError:
            pass

        headers = {DATE: format_timestamp(get_aware_utc_now())}
        message = self.owner.vip.health.get_status()

        self.pubsub().publish('pubsub', topic, headers, message)
