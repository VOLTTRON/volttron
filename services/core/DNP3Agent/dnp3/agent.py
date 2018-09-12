# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / Kisensum.
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
# United States Department of Energy, nor SLAC, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

import logging
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Core

from base_dnp3_agent import BaseDNP3Agent
from points import DNP3Exception

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.1'


class DNP3Agent(BaseDNP3Agent):
    """
        DNP3Agent is a VOLTTRON agent that handles DNP3 outstation communications.

        DNP3Agent models a DNP3 outstation, communicating with a DNP3 master.

        For further information about this agent and DNP3 communications, please see the VOLTTRON
        DNP3 specification, located in VOLTTRON readthedocs
        under http://volttron.readthedocs.io/en/develop/specifications/dnp3_agent.html.

        This agent can be installed from a command-line shell as follows:
            $ export VOLTTRON_ROOT=<your volttron install directory>
            $ cd $VOLTTRON_ROOT
            $ source services/core/DNP3Agent/install_dnp3_agent.sh
    """

    def __init__(self, **kwargs):
        """Initialize the DNP3 agent."""
        super(DNP3Agent, self).__init__(**kwargs)
        self.vip.config.set_default('config', self.default_config)
        self.vip.config.subscribe(self._configure, actions=['NEW', 'UPDATE'], pattern='config')

    def _process_point_value(self, point_value):
        """DNP3Agent publishes each point value to the message bus as the value is received from the master."""
        point_val = super(DNP3Agent, self)._process_point_value(point_value)
        if point_val:
            self.publish_point_value(point_value)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """Start the DNP3Outstation instance, kicking off communication with the DNP3 Master."""
        super(DNP3Agent, self).onstart(sender, **kwargs)


def dnp3_agent(config_path, **kwargs):
    """
        Parse the DNP3 Agent configuration. Return an agent instance created from that config.

    :param config_path: (str) Path to a configuration file.
    :returns: (DNP3Agent) The DNP3 agent
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}
    return DNP3Agent(points=config.get('points', None),
                     point_topic=config.get('point_topic', 'dnp3/point'),
                     local_ip=config.get('local_ip', '0.0.0.0'),
                     port=config.get('port', 20000),
                     outstation_config=config.get('outstation_config', {}),
                     **kwargs)


def main():
    """Main method called to start the agent."""
    utils.vip_main(dnp3_agent, identity='dnp3agent', version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
