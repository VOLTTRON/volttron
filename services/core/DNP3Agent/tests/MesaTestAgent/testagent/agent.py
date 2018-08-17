# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, 8minutenergy / Kisensum.
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
# Neither 8minutenergy nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by 8minutenergy or Kisensum.
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

TEST_GET_POINT_NAME1 = 'DCHD.ModEna'
TEST_GET_POINT_NAME2 = 'DCHD.VArAct.out'
TEST_GET_SELECTOR_BLOCK_POINT_NAME = 'Curve Edit Selector'
TEST_SET_POINT_NAME = 'DCHD.WTgt.1'
TEST_SET_SUPPORT_POINT_NAME = 'DCHA.Beh'
# Test has been disabled: these points are not part of the current production data definitions.
# TEST_DEVICE_ARRAY = {
#     "Inverter power readings": [
#         {
#             "Inverter active power output - Present Active Power output level": 302,
#             "Inverter reactive output - Present reactive power output level": 100
#         }
#     ]
# }
TEST_INPUT_CURVE = {
    "FMAR.in.PairArray.CsvPts": [
        {"FMAR.in.PairArray.CsvPts.xVal": 30, "FMAR.in.PairArray.CsvPts.yVal": 130},
        {"FMAR.in.PairArray.CsvPts.xVal": 31, "FMAR.in.PairArray.CsvPts.yVal": 131},
        {"FMAR.in.PairArray.CsvPts.xVal": 32, "FMAR.in.PairArray.CsvPts.yVal": 132}
    ]
}


def mesa_test_agent(config_path, **kwargs):
    """
        Parse the TestAgent configuration file and return an instance of
        the agent that has been created using that configuration.

        See initialize_config() method documentation for a description of each configurable parameter.

        This agent can be installed from a command-line shell as follows:
            export VOLTTRON_ROOT=<your volttron install directory>
            export MESA_TEST=$VOLTTRON_ROOT/services/core/MesaAgent/tests/TestAgent
            cd $VOLTTRON_ROOT
            python scripts/install-agent.py -s $$MESA_TEST -i mesatest -c $MESA_TEST/testagent.config -t mesatest -f

    :param config_path: (str) Path to a configuration file.
    :returns: TestAgent instance
    """
    try:
        config = utils.load_config(config_path)
    except (StandardError, err):
        _log.error("Error loading MesaTestAgent configuration: {}".format(err))
        config = {}
    mesaagent_id = config.get('mesaagent_id', 'mesaagent')
    point_topic = config.get('point_topic', 'mesa/point')
    function_topic = config.get('function_topic', 'mesa/function')
    outstation_status_topic = config.get('outstation_status_topic', 'mesa/outstation_status')
    point_config = config.get('point_config', None)
    return MesaTestAgent(mesaagent_id, point_topic, function_topic, outstation_status_topic, point_config, **kwargs)


class MesaTestAgent(Agent):
    """
        This is a sample test agent that demonstrates and tests MesaAgent.
        It exercises MesaAgent's exposed RPC calls and consumes VOLTTRON messages published by MesaAgent.
    """

    def __init__(self, mesaagent_id, point_topic, function_topic, outstation_status_topic, point_config, **kwargs):
        super(MesaTestAgent, self).__init__(**kwargs)
        self.mesaagent_id = None
        self.point_topic = None
        self.function_topic = None
        self.outstation_status_topic = None
        self.point_config = None
        self.default_config = {'mesaagent_id': mesaagent_id,
                               'point_topic': point_topic,
                               'function_topic': function_topic,
                               'outstation_status_topic': outstation_status_topic,
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
        self.mesaagent_id = config['mesaagent_id']
        self.point_topic = config['point_topic']
        self.function_topic = config['function_topic']
        self.outstation_status_topic = config['outstation_status_topic']
        self.point_config = config['point_config']
        _log.debug('MesaTestAgent configuration parameters:')
        _log.debug('\tmesaagent_id={}'.format(self.mesaagent_id))
        _log.debug('\tpoint_topic={}'.format(self.point_topic))
        _log.debug('\tfunction_topic={}'.format(self.function_topic))
        _log.debug('\toutstation_status_topic={}'.format(self.outstation_status_topic))
        _log.debug('\tpoint_config={}'.format(self.point_config))

    @Core.receiver('onstart')
    def onstart_method(self, sender):
        """The test agent has started. Perform initialization and spawn the main process loop."""
        _log.debug('Starting MesaTestAgent')
        if self.point_config:
            # This test agent can configure the points itself, or (by default) it can rely on the DNP3 driver to do it.
            _log.debug('Sending DNP3 point map: {}'.format(self.point_config))
            self.send_rpc('config_points', self.point_config)
        # Subscribe to the MesaAgent's point, function, and outstation_status publications.
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.point_topic, callback=self.receive_point_value)
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.function_topic, callback=self.receive_function)
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.outstation_status_topic, callback=self.receive_status)
        self.core.periodic(RPC_INTERVAL_SECS, self.issue_rpcs)

    @staticmethod
    def receive_point_value(peer, sender, bus, topic, headers, point_value):
        """(Subscription callback) Receive a point value."""
        _log.debug('MesaTestAgent received point_value={}'.format(point_value))

    def receive_function(self, peer, sender, bus, topic, headers, point_value):
        """(Subscription callback) Receive a function."""
        _log.debug('MesaTestAgent received function={}'.format(point_value))
        if 'expected_response' in point_value:
            # The function step expects a response. Send one.
            self.set_point(point_value['expected_response'], 1)

    @staticmethod
    def receive_status(peer, sender, bus, topic, headers, point_value):
        """(Subscription callback) Receive outstation status."""
        _log.debug('MesaTestAgent received outstation status={}'.format(point_value))

    def issue_rpcs(self):
        """Periodically issue RPCs to the DNP3 agent."""
        self.get_point(TEST_GET_POINT_NAME1)
        self.get_point(TEST_GET_POINT_NAME2)
        self.get_selector_block(TEST_GET_SELECTOR_BLOCK_POINT_NAME, 3)
        self.set_point(TEST_SET_POINT_NAME, 10)
        self.set_point(TEST_SET_SUPPORT_POINT_NAME, True)
        # self.set_points(TEST_DEVICE_ARRAY)
        self.set_points(TEST_INPUT_CURVE)

    def get_point(self, point_name):
        """Get a single metric from the MesaAgent via an RPC call."""
        point_value = self.send_rpc('get_point', point_name)
        _log.debug('MesaTestAgent get_point received {}={}'.format(point_name, point_value))

    def get_selector_block(self, point_name, edit_selector):
        """Get a selector block from the MesaAgent via an RPC call."""
        selector_block = self.send_rpc('get_selector_block', point_name, edit_selector)
        _log.debug('MesaTestAgent get_selector_block {} selector {} received {}'.format(point_name,
                                                                                        edit_selector,
                                                                                        selector_block))

    def set_point(self, point_name, value):
        """Send a single point value to the MesaAgent via an RPC call."""
        _log.debug('MesaTestAgent set_point sent {}={}'.format(point_name, value))
        self.send_rpc('set_point', point_name, value)

    def set_points(self, json_payload):
        """Send a single point value to the MesaAgent via an RPC call."""
        _log.debug('MesaTestAgent sending points: {}'.format(json_payload))
        self.send_rpc('set_points', json_payload)

    def send_rpc(self, rpc_name, *args, **kwargs):
        """Send an RPC request to the MesaAgent, and return its response (if any)."""
        response = self.vip.rpc.call(self.mesaagent_id, rpc_name, *args, **kwargs)
        return response.get(30)


def main():
    """Start the agent."""
    utils.vip_main(mesa_test_agent, identity='mesa_test_agent', version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
