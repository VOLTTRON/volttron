# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent import Core
from volttron.platform.vip.agent.subsystems.web import WebSubSystem

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.0.1'


class WebSocketAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(WebSocketAgent, self).__init__(**kwargs)
        self._websubsystem = None

    @Core.receiver("onstart")
    def _starting(self, sender, **kwargs):
        self._websubsystem = WebSubSystem(self.vip.rpc)
        # self._websubsystem.register_path('/foo', )
        self._websubsystem.register_websocket('/ws', self._opened, self._closed,
                                              self._received)

    @Core.receiver("onstop")
    def _stopping(self, sender, **kwargs):
        pass

    def _opened(self):
        _log.info('Client connected')

    def _closed(self):
        _log.info('Client disconnected')

    def _received(self, message):
        _log.info('Message Received: {}'.format(message))
        _log.info('Sending message to {} {}'.format('/ws', message))
        self._websubsystem.send('/ws', message)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""

    try:
        utils.vip_main(WebSocketAgent, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
