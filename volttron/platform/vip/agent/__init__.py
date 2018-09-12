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

from __future__ import absolute_import

import os
import logging as _log

from volttron.platform.vip.agent.subsystems.web import WebSubSystem

from .core import *
from .errors import *
from .decorators import *
from .subsystems import *
from .... import platform
from .... platform.agent.utils import is_valid_identity


class Agent(object):
    class Subsystems(object):
        def __init__(self, owner, core, heartbeat_autostart,
                     heartbeat_period, enable_store, enable_web,
                     enable_channel, enable_fncs):
            self.peerlist = PeerList(core)
            self.ping = Ping(core)
            self.rpc = RPC(core, owner)
            self.hello = Hello(core)
            self.pubsub = PubSub(core, self.rpc, self.peerlist, owner)
            if enable_channel:
                self.channel = Channel(core)
            self.health = Health(owner, core, self.rpc)
            self.heartbeat = Heartbeat(owner, core, self.rpc, self.pubsub,
                                       heartbeat_autostart, heartbeat_period)
            if enable_store:
                self.config = ConfigStore(owner, core, self.rpc)
            if enable_web:
                self.web = WebSubSystem(owner, core, self.rpc)
            self.auth = Auth(owner, core, self.rpc)
            if enable_fncs:
                self.fncs = FNCS(owner, core, self.pubsub)

    def __init__(self, identity=None, address=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 heartbeat_autostart=False, heartbeat_period=60,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, enable_store=True,
                 enable_web=False, enable_channel=False,
                 reconnect_interval=None, version='0.1', enable_fncs=False):

        self._version = version

        if identity is not None and not is_valid_identity(identity):
            _log.warn('Deprecation warning')
            _log.warn(
                'All characters in {identity} are not in the valid set.'.format(
                    identity=identity))

        self.core = Core(self, identity=identity, address=address,
                         context=context, publickey=publickey,
                         secretkey=secretkey, serverkey=serverkey,
                         volttron_home=volttron_home, agent_uuid=agent_uuid,
                         reconnect_interval=reconnect_interval,
                         version=version, enable_fncs=enable_fncs)

        self.vip = Agent.Subsystems(self, self.core, heartbeat_autostart,
                                    heartbeat_period, enable_store, enable_web,
                                    enable_channel, enable_fncs)
        self.core.setup()
        self.vip.rpc.export(self.core.version, 'agent.version')


class BasicAgent(object):
    def __init__(self, **kwargs):
        kwargs.pop('identity', None)
        super(BasicAgent, self).__init__(**kwargs)
        self.core = BasicCore(self)
