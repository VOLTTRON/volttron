# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
# }}}

from __future__ import absolute_import

import os
import logging as _log

from .core import *
from .errors import *
from .decorators import *
from .subsystems import *
from .... import platform
from .... platform.agent.utils import is_valid_identity


class Agent(object):
    class Subsystems(object):
        def __init__(self, owner, core, heartbeat_autostart,
                     heartbeat_period, enable_store):
            self.peerlist = PeerList(core)
            self.ping = Ping(core)
            self.rpc = RPC(core, owner)
            self.hello = Hello(core)
            self.pubsub = PubSub(core, self.rpc, self.peerlist, owner)
            self.channel = Channel(core)
            self.health = Health(owner, core, self.rpc)
            self.heartbeat = Heartbeat(owner, core, self.rpc, self.pubsub,
                                       heartbeat_autostart, heartbeat_period)
            if enable_store:
                self.config = ConfigStore(owner, core, self.rpc)

    def __init__(self, identity=None, address=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 heartbeat_autostart=False, heartbeat_period=60,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, enable_store=True, developer_mode=False):

        if identity is not None and not is_valid_identity(identity):
            _log.warn('Deprecation warining')
            _log.warn(
                'All characters in {identity} are not in the valid set.'.format(
                    idenity=identity))

        self.core = Core(self, identity=identity, address=address,
                         context=context, publickey=publickey,
                         secretkey=secretkey, serverkey=serverkey,
                         volttron_home=volttron_home, agent_uuid=agent_uuid,
                         developer_mode=developer_mode)
        self.vip = Agent.Subsystems(self, self.core, heartbeat_autostart,
                                    heartbeat_period, enable_store)
        self.core.setup()


class BasicAgent(object):
    def __init__(self, **kwargs):
        kwargs.pop('identity', None)
        super(BasicAgent, self).__init__(**kwargs)
        self.core = BasicCore(self)
