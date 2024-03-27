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

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD
from volttron.platform.scheduling import periodic

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '0.1'


class AgentWatcher(Agent):
    def __init__(self, config_path, **kwargs):
        super(AgentWatcher, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.watchlist = config["watchlist"]
        self.check_period = config.get("check-period", 10)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.core.schedule(periodic(self.check_period), self.watch_agents)

    def watch_agents(self):
        peerlist = self.vip.peerlist().get()

        missing_agents = []
        for vip_id in self.watchlist:
            if vip_id not in peerlist:
                missing_agents.append(vip_id)

        if missing_agents:
            alert_key = "AgentWatcher"
            context = "Agent(s) expected but but not running {}".format(missing_agents)
            _log.warning(context)
            status = Status.build(STATUS_BAD, context=context)
            self.vip.health.send_alert(alert_key, status)


def main():
    utils.vip_main(AgentWatcher, version=__version__)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
