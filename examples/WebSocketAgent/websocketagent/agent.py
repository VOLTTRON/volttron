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
