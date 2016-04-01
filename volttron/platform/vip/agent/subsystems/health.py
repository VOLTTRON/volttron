# Copyright (c) 2015, Battelle Memorial Institute
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


import logging
import weakref

from volttron.platform.messaging.health import *
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)

from .base import SubsystemBase

__docformat__ = 'reStructuredText'
__version__ = '1.0'

"""
The health subsystem allows an agent to store it's health in a non-intrusive
way.
"""
_log = logging.getLogger(__name__)


class Health(SubsystemBase):
    def __init__(self, owner, core, rpc, heartbeat):
        self._owner = owner
        self._core = weakref.ref(core)
        self._heartbeat = weakref.ref(heartbeat)
        self._rpc = weakref.ref(rpc)
        self._status = None
        self._update_status(STATUS_GOOD)

        def onsetup(sender, **kwargs):
            rpc.export(self.set_status, 'health.set_status')
            rpc.export(self.get_status, 'health.get_status')

        def onstart(sender, **kwargs):
            heartbeat.start()

        core.onsetup.connect(onsetup, self)
        core.onstart.connect(onstart, self)

    def _update_status(self, status, context=None):
        if status not in ACCEPTABLE_STATUS:
            status = STATUS_BAD
            context = str(context) + ' Invalid status detected'

        self._status = {
            CURRENT_STATUS: status,
            CONTEXT: context,
            LAST_UPDATED: format_timestamp(get_aware_utc_now())
        }

    def set_status(self, status, context=None):
        """RPC method

        Updates the agents status to the new value with the specified context.

        :param: status: str: GODD, BAD
        :param: context: str: A serializable that denotes the context of
        status.
        """
        do_heartbeat_now = self._status['current_status'] != status

        self._update_status(status, context)

        if do_heartbeat_now:
            # TODO: Check that the heartbeat publishes immediately
            _log.debug("exercise heartbeat!")
            self._heartbeat().stop()
            self._heartbeat().start()

    def get_status(self):
        """"RPC method

        Returns the last updated status from the object with the context.

        The minimum output from the status would be:

            {
                "status": "GOOD",
                "context": None,
                "utc_last_update": "2016-03-31T15:40:32.685138+0000"
            }

        """
        return self._status.copy()
