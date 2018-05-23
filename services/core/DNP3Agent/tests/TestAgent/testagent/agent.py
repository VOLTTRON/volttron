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

from __future__ import print_function

import logging
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.0'

RPC_INTERVAL_SECS = 10

TEST_GET_POINT_NAME = 'DCHD.VArAct'
TEST_SET_POINT_NAME = 'DCHD.WTgt-In'


def dnp3_test_agent(config_path, **kwargs):
    """
        Parse the TestAgent configuration file and return an instance of
        the agent that has been created using that configuration.

        See initialize_config() method documentation for a description of each configurable parameter.

        This agent can be installed from a command-line shell as follows:
            export VOLTTRON_ROOT=<your volttron install directory>
            export DNP3_TEST=$VOLTTRON_ROOT/services/core/DNP3Agent/tests/TestAgent
            cd $VOLTTRON_ROOT
            python scripts/install-agent.py -s $DNP3_TEST -i dnp3test -c $DNP3_TEST/testagent.config -t dnp3test -f

    :param config_path: (str) Path to a configuration file.
    :returns: TestAgent instance
    """
    try:
        config = utils.load_config(config_path)
    except StandardError, err:
        _log.error("Error loading DNP3TestAgent configuration: {}".format(err))
        config = {}
    dnp3agent_id = config.get('dnp3agent_id', 'dnp3agent')
    point_topic = config.get('point_topic', 'dnp3/point')
    point_config = config.get('point_config', None)
    return DNP3TestAgent(dnp3agent_id, point_topic, point_config, **kwargs)


class DNP3TestAgent(Agent):
    """
        This is a sample test agent that demonstrates and tests DNP3Agent.
        It exercises DNP3Agent's exposed RPC calls and consumes VOLTTRON messages published by DNP3Agent.
    """

    def __init__(self, dnp3agent_id, point_topic, point_config, **kwargs):
        super(DNP3TestAgent, self).__init__(**kwargs)
        self.dnp3agent_id = None
        self.point_topic = None
        self.point_config = None
        self.default_config = {'dnp3agent_id': dnp3agent_id,
                               'point_topic': point_topic,
                               'point_config': point_config}
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        self.initialize_config(self.default_config)

    def _configure(self, config_name, action, contents):
        """The agent's config may have changed. Re-initialize it."""
        config = self.default_config.copy()
        config.update(contents)
        self.initialize_config(config)

    def initialize_config(self, config):
        self.dnp3agent_id = config['dnp3agent_id']
        self.point_topic = config['point_topic']
        self.point_config = config['point_config']
        _log.debug('DNP3TestAgent configuration parameters:')
        _log.debug('\tdnp3agent_id={}'.format(self.dnp3agent_id))
        _log.debug('\tpoint_topic={}'.format(self.point_topic))
        _log.debug('\tpoint_config={}'.format(self.point_config))

    @Core.receiver('onstart')
    def onstart_method(self, sender):
        """The test agent has started. Perform initialization and spawn the main process loop."""
        _log.debug('Starting DNP3TestAgent')
        if self.point_config:
            # This test agent can configure the points itself, or (by default) it can rely on the DNP3 driver to do it.
            _log.debug('Sending DNP3 point map: {}'.format(self.point_config))
            self.send_rpc('config_points', self.point_config)
        # Subscribe to the DNP3Agent's point value publication.
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.point_topic, callback=self.receive_point_value)
        self.core.periodic(RPC_INTERVAL_SECS, self.issue_rpcs)

    @staticmethod
    def receive_point_value(peer, sender, bus, topic, headers, point_value):
        """(Subscription callback) Receive a point value."""
        _log.debug('Received DNP3 point value={}'.format(point_value))

    def issue_rpcs(self):
        """Periodically issue RPCs to the DNP3 agent."""
        self.get_point(TEST_GET_POINT_NAME)
        self.get_points()
        self.set_point(TEST_SET_POINT_NAME, 10)

    def get_point(self, point_name):
        """Get a single metric from the DNP3 agent via an RPC call."""
        _log.debug('Getting a DNP3 {} value'.format(point_name))
        point_value = self.send_rpc('get_point', point_name)
        _log.debug('DNP3 {} value returned by DNP3Agent: {}'.format(point_name, point_value))

    def get_points(self):
        """Get all current point values from the DNP3 agent via an RPC call."""
        _log.debug('Getting all DNP3 point values')
        point_values = self.send_rpc('get_points')
        _log.debug('DNP3 point values returned by DNP3Agent: {}'.format(point_values))

    def set_point(self, point_name, value):
        """Send a single point value to the DNP3 agent via an RPC call."""
        _log.debug('Sending a DNP3 {} value: {}'.format(point_name, value))
        self.send_rpc('set_point', point_name, value)

    def send_rpc(self, rpc_name, *args, **kwargs):
        """Send an RPC request to the DNP3Agent, and return its response (if any)."""
        response = self.vip.rpc.call(self.dnp3agent_id, rpc_name, *args, **kwargs)
        return response.get(30)


def main():
    """Start the agent."""
    utils.vip_main(dnp3_test_agent, identity='dnp3testagent', version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
