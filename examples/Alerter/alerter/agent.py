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

import datetime
import sys
import logging

from volttron.platform.messaging.health import STATUS_BAD, STATUS_GOOD, Status
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.messaging.utils import normtopic


from dateutil.parser import parse


utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = "0.1"


class AlerterAgent(Agent):
    """
    The `AlerterAgent` is a simple agent that allows control via rpc to
    send an alert and update it's heartbeat.
    """

    def __init__(self, config_path, **kwargs):
        """ Configures the `AlertMonitorAgent`

        Validates that the outfile parameter in the config file is specified
        and sets up the agent.

        @param config_path: path to the configuration file for this agent.
        @param kwargs:
        @return:
        """

        # pop off the identity arge because we are goint to explicitly
        # set it to our identity.  If we didn't do this it would cause
        # an error.  The default identity is the uuid of the agent.
        kwargs.pop('identity')
        super(AlerterAgent, self).__init__(**kwargs)

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        self.vip.heartbeat.start_with_period(15)

    @RPC.export
    def status_bad(self, context):
        self.vip.health.set_status(STATUS_BAD, context)

    @RPC.export
    def status_good(self):
        self.vip.health.set_status(STATUS_GOOD)

    @RPC.export
    def send_alert1(self, key, message):
        status = Status.build(STATUS_BAD, message)
        self.vip.health.send_alert(key, status)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(AlerterAgent, identity='alerter')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
