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

import logging
import weakref

from .base import SubsystemBase

from volttron.platform.agent.known_identities import AUTH
from volttron.platform.jsonrpc import RemoteError

"""
The auth subsystem allows an agent to quickly query authorization state
(e.g., which capabilities each user has been granted).
"""

__docformat__ = 'reStructuredText'
__version__ = '1.0'

_log = logging.getLogger(__name__)


class Auth(SubsystemBase):
    def __init__(self, owner, core, rpc):
        self._owner = owner
        self._core = weakref.ref(core)
        self._rpc = weakref.ref(rpc)
        self._user_to_capabilities = {}
        self._dirty = True

        def onsetup(sender, **kwargs):
            rpc.export(self._update_capabilities, 'auth.update')

        core.onsetup.connect(onsetup, self)

    def _fetch_capabilities(self):
        while self._dirty:
            self._dirty = False
            try:
                self._user_to_capabilities = self._rpc().call(AUTH,
                    'get_user_to_capabilities').get(timeout=10)
            except RemoteError:
                self._dirty = True

    def get_capabilities(self, user_id):
        """Gets capabilities for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of capabilities
        :rtype: list
        """
        self._fetch_capabilities()
        return self._user_to_capabilities.get(user_id, [])

    def _update_capabilities(self, user_to_capabilities):
        identity = bytes(self._rpc().context.vip_message.peer)
        if identity == AUTH:
            self._user_to_capabilities = user_to_capabilities
            self._dirty = True
