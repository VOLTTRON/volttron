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
# This material was prepared as an account of work sponsored by an agency of the United States Government. Neither the
# United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any
# jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product, process, or service by trade name,
# trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions
# of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency
# thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY under
# Contract DE-AC05-76RL01830
# }}}

from datetime import datetime
import os
import sys

import json
import gevent
import logging
from gevent.core import callback
from gevent import Timeout

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils

# Log warnings and errors to make the node red log less chatty
utils.setup_logging(level=logging.WARNING)
_log = logging.getLogger(__name__)

# These are the options that can be set from the settings module.
from settings import agent_kwargs

''' takes two arguments.  Firist is topic to publish under.  Second is message. '''
if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        agent = Agent(identity='NodeRedPublisher', **agent_kwargs)
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        event = gevent.event.Event()
        task = gevent.spawn(agent.core.run, event)
        with gevent.Timeout(10):
            event.wait()

        try:
            result = agent.vip.pubsub.publish('pubsub', sys.argv[1], headers, sys.argv[2])
            result.get(timeout=10)
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
