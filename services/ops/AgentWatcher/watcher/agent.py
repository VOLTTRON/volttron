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
