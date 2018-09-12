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

import gevent
import json
import os
import pytest

from volttron.platform import get_services_core
from volttron.platform.agent.utils import strip_comments

from dnp3.points import PointDefinitions
from mesa_master_test import MesaMasterTest

from pydnp3 import asiodnp3, asiopal, opendnp3, openpal

FILTERS = opendnp3.levels.NORMAL | opendnp3.levels.ALL_COMMS
HOST = "127.0.0.1"
LOCAL = "0.0.0.0"
PORT = 20000

DNP3_AGENT_ID = 'dnp3agent'
POINT_TOPIC = "dnp3/point"
TEST_GET_POINT_NAME = 'DCHD.VArAct (out)'
TEST_SET_POINT_NAME = 'DCHD.WinTms (in)'

input_group_map = {
    1: "Binary",
    2: "Binary",
    30: "Analog",
    31: "Analog",
    32: "Analog",
    33: "Analog",
    34: "Analog"
}

DNP3_AGENT_CONFIG = {
    "points": "config://mesa_points.config",
    "point_topic": POINT_TOPIC,
    "outstation_config": {
        "log_levels": ["NORMAL", "ALL_APP_COMMS"]
    },
    "local_ip": "0.0.0.0",
    "port": 20000
}

# Get point definitions from the files in the test directory.
POINT_DEFINITIONS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'mesa_points.config'))

pdefs = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)

AGENT_CONFIG = {
    "points": "config://mesa_points.config",
    "outstation_config": {
        "database_sizes": 700,
        "log_levels": ["NORMAL"]
    },
    "local_ip": "0.0.0.0",
    "port": 20000
}

messages = {}


def onmessage(peer, sender, bus, topic, headers, message):
    """Callback: As DNP3Agent publishes mesa/point messages, store them in a multi-level global dictionary."""
    global messages
    messages[topic] = {'headers': headers, 'message': message}


def dict_compare(source_dict, target_dict):
    """Assert that the value for each key in source_dict matches the corresponding value in target_dict.

       Ignores keys in target_dict that are not in source_dict.
    """
    for name, source_val in source_dict.iteritems():
        target_val = target_dict.get(name, None)
        assert source_val == target_val, "Source value of {}={}, target value={}".format(name, source_val, target_val)


def add_definitions_to_config_store(test_agent):
    """Add PointDefinitions to the mesaagent's config store."""
    with open(POINT_DEFINITIONS_PATH, 'r') as f:
        points_json = json.loads(strip_comments(f.read()))
    test_agent.vip.rpc.call('config.store', 'manage_store', DNP3_AGENT_ID,
                            'mesa_points.config', points_json, config_type='raw')


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
    """Build the test agent for rpc call."""

    test_agent = volttron_instance.build_agent()

    add_definitions_to_config_store(test_agent)

    print('Installing DNP3Agent')
    os.environ['AGENT_MODULE'] = 'dnp3.agent'
    agent_id = volttron_instance.install_agent(agent_dir=get_services_core("DNP3Agent"),
                                               config_file=AGENT_CONFIG,
                                               vip_identity=DNP3_AGENT_ID,
                                               start=True)

    # Subscribe to DNP3 point publication
    test_agent.vip.pubsub.subscribe(peer='pubsub', prefix=POINT_TOPIC, callback=onmessage)

    def stop():
        """Stop test agent."""
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_id)
            volttron_instance.remove_agent(agent_id)
            test_agent.core.stop()

    gevent.sleep(2)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


@pytest.fixture(scope="module")
def run_master(request):
    """Run Mesa master application."""
    master = MesaMasterTest(local_ip=AGENT_CONFIG['local_ip'], port=AGENT_CONFIG['port'])
    master.connect()

    def stop():
        master.shutdown()

    request.addfinalizer(stop)

    return master


@pytest.fixture(scope="function")
def reset(agent):
    """Reset agent and global variable messages before running every test."""
    global messages
    messages = {}
    agent.vip.rpc.call(DNP3_AGENT_ID, 'reset')


class TestDNP3Agent:
    """Regression tests for (non-MESA) DNP3Agent."""

    @staticmethod
    def get_point(agent, point_name):
        """Ask DNP3Agent for a point value for a DNP3 resource."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'get_point', point_name).get(timeout=10)

    @staticmethod
    def get_point_definitions(agent, point_names):
        """Ask DNP3Agent for a list of point definitions."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'get_point_definitions', point_names).get(timeout=10)

    @staticmethod
    def get_point_by_index(agent, group, index):
        """Ask DNP3Agent for a point value for a DNP3 resource."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'get_point_by_index', group, index).get(timeout=10)

    @staticmethod
    def set_point(agent, point_name, value):
        """Use DNP3Agent to set a point value for a DNP3 resource."""
        response = agent.vip.rpc.call(DNP3_AGENT_ID, 'set_point', point_name, value).get(timeout=10)
        gevent.sleep(1)     # Give the Master time to receive an echoed point value back from the Outstation.
        return response

    @staticmethod
    def set_points(agent, point_dict):
        """Use DNP3Agent to set point values for a DNP3 resource."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'set_points', point_dict).get(timeout=10)

    @staticmethod
    def send_single_point(master, point_name, point_value):
        """
            Send a point name and value from the Master to DNP3Agent.

            Return a dictionary with an exception key and error, empty if successful.
        """
        try:
            master.send_single_point(pdefs, point_name, point_value)
            return {}
        except Exception as err:
            exception = {'key': type(err).__name__, 'error': str(err)}
            print("Exception sending point from master: {}".format(exception))
            return exception

    @staticmethod
    def get_value_from_master(master, point_name):
        """Get value of the point from master after being set by test agent."""
        try:
            pdef = pdefs.point_named(point_name)
            group = input_group_map[pdef.group]
            index = pdef.index
            return master.soe_handler.result[group][index]
        except KeyError:
            return None

    def get_point_definition(self, agent, point_name):
        """Confirm that the agent has a point definition named point_name. Return the definition."""
        point_defs = self.get_point_definitions(agent, [point_name])
        point_def = point_defs.get(point_name, None)
        assert point_def is not None, "Agent has no point definition for {}".format(TEST_GET_POINT_NAME)
        return point_def

    @staticmethod
    def subscribed_points():
        """Return point values published by DNP3Agent using the dnp3/point topic."""
        return messages[POINT_TOPIC].get('message', {})

    # **********
    # ********** OUTPUT TESTS (send data from Master to Agent to ControlAgent) ************
    # **********

    def test_get_point_definition(self, run_master, agent, reset):
        """Ask the agent whether it has a point definition for a point name."""
        self.get_point_definition(agent, TEST_GET_POINT_NAME)

    def test_send_point(self, run_master, agent, reset):
        """Send a point from the master and get its value from DNP3Agent."""
        self.get_point_definition(agent, TEST_GET_POINT_NAME)
        exceptions = self.send_single_point(run_master, TEST_GET_POINT_NAME, 45)
        assert exceptions == {}
        received_point = self.get_point(agent, TEST_GET_POINT_NAME)
        assert exceptions == {}
        # Confirm that the agent's received point value matches the value that was sent.
        assert received_point == 45, "Expected {} = {}, got {}".format(TEST_GET_POINT_NAME, 45, received_point)
        dict_compare({TEST_GET_POINT_NAME: 45}, self.subscribed_points())

    # **********
    # ********** INPUT TESTS (send data from ControlAgent to Agent to Master) ************
    # **********

    def test_set_point(self, run_master, agent, reset):
        """Test set an input point and confirm getting the same value for that point."""
        self.set_point(agent, TEST_SET_POINT_NAME, 45)
        received_val = self.get_value_from_master(run_master, TEST_SET_POINT_NAME)
        assert received_val == 45, "Expected {} = {}, got {}".format(TEST_SET_POINT_NAME, 45, received_val)
