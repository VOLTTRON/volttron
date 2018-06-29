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

import gevent
import json
import os
import pytest
import yaml

from dnp3.points import PointDefinitions
from mesa_master_test import MesaMasterTest
from volttron.platform import get_services_core
from volttron.platform.agent.utils import strip_comments

MESA_AGENT_ID = 'mesaagent'
FUNCTION_TOPIC = 'mesa/function'
TEST_SET_POINT_NAME = 'DLFL.WinTms'

# This module gets point and function definitions from the checked-in production versions.
POINT_DEFINITIONS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../dnp3', 'mesa_points.config'))
FUNCTION_DEFINITIONS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../dnp3/mesa', 'mesa_functions.yaml'))

pdefs = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)

input_group_map = {
    1: "Binary",
    2: "Binary",
    30: "Analog",
    31: "Analog",
    32: "Analog",
    33: "Analog",
    34: "Analog"
}

MESA_AGENT_CONFIG = {
    "points": "config://mesa_points.config",
    "functions": "config://mesa_functions.config",
    "outstation_config": {
        "database_sizes": 700,
        "log_levels": ["NORMAL"]
    },
    "local_ip": "0.0.0.0",
    "port": 20000
}

messages = {}


def onmessage(peer, sender, bus, topic, headers, message):
    """Callback: As mesaagent publishes mesa/function messages, store them in a multi-level global dictionary."""
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
    """Add PointDefinitions and FunctionDefinitions to the mesaagent's config store."""
    with open(POINT_DEFINITIONS_PATH, 'r') as f:
        points_json = json.loads(strip_comments(f.read()))
    test_agent.vip.rpc.call('config.store', 'manage_store', MESA_AGENT_ID,
                            'mesa_points.config', points_json, config_type='raw')
    with open(FUNCTION_DEFINITIONS_PATH, 'r') as f:
        functions_json = yaml.load(f.read())
    test_agent.vip.rpc.call('config.store', 'manage_store', MESA_AGENT_ID,
                            'mesa_functions.config', functions_json, config_type='raw')


@pytest.fixture(scope="module")
def mesa_data_agent(request, volttron_instance):
    """Build the test agent for rpc call."""

    gevent.sleep(1)        # Give a prior volttron instance extra time to shut down

    test_agent = volttron_instance.build_agent()

    add_definitions_to_config_store(test_agent)

    print('Installing Mesa Agent')
    os.environ['AGENT_MODULE'] = 'dnp3.mesa.agent'
    agent_id = volttron_instance.install_agent(agent_dir=get_services_core("DNP3Agent"),
                                               config_file=MESA_AGENT_CONFIG,
                                               vip_identity=MESA_AGENT_ID,
                                               start=True)

    # Subscribe to MESA functions
    test_agent.vip.pubsub.subscribe(peer='pubsub',
                                    prefix=FUNCTION_TOPIC,
                                    callback=onmessage)

    def stop():
        """Stop test agent."""
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_id)
            volttron_instance.remove_agent(agent_id)
            test_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


@pytest.fixture(scope="module")
def run_data_master(request):
    """Run Mesa master application."""
    master = MesaMasterTest(local_ip=MESA_AGENT_CONFIG['local_ip'],
                            port=MESA_AGENT_CONFIG['port'])
    master.connect()

    def stop():
        master.shutdown()

    request.addfinalizer(stop)

    return master


@pytest.fixture(scope="function")
def reset(mesa_data_agent):
    """Reset agent and global variable messages before running every test."""
    global messages
    messages = {}
    mesa_data_agent.vip.rpc.call(MESA_AGENT_ID, 'reset')


class TestMesaData:
    """Regression tests for MesaAgent production data definitions (points and functions)."""

    @staticmethod
    def get_point(agent, point_name):
        """Ask DNP3Agent for a point value for a DNP3 resource."""
        return agent.vip.rpc.call(MESA_AGENT_ID, 'get_point', point_name).get(timeout=10)

    @staticmethod
    def get_point_definitions(agent, point_names):
        """Ask DNP3Agent for a list of point definitions."""
        return agent.vip.rpc.call(MESA_AGENT_ID, 'get_point_definitions', point_names).get(timeout=10)

    @staticmethod
    def get_point_by_index(agent, group, index):
        """Ask DNP3Agent for a point value for a DNP3 resource."""
        return agent.vip.rpc.call(MESA_AGENT_ID, 'get_point_by_index', group, index).get(timeout=10)

    @staticmethod
    def set_point(agent, point_name, value):
        """Use DNP3Agent to set a point value for a DNP3 resource."""
        response = agent.vip.rpc.call(MESA_AGENT_ID, 'set_point', point_name, value).get(timeout=10)
        gevent.sleep(1)     # Give the Master time to receive an echoed point value back from the Outstation.
        return response

    @staticmethod
    def set_points(agent, point_dict):
        """Use DNP3Agent to set point values for a DNP3 resource."""
        return agent.vip.rpc.call(MESA_AGENT_ID, 'set_points', point_dict).get(timeout=10)

    @staticmethod
    def get_selector_block(agent, point_name, edit_selector):
        """Get a selector block from the MesaAgent via an RPC call."""
        return agent.vip.rpc.call(MESA_AGENT_ID, 'get_selector_block', point_name, edit_selector).get(timeout=10)

    @staticmethod
    def convert_json_file_to_dict(json_file):
        """Convert a json file to a dictionary."""
        send_json = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', json_file))
        return json.load(open(send_json))

    @staticmethod
    def send_points(master, send_json, send_in_step_order=True):
        """Master loads points from json and send them to mesa agent.
        Return empty dictionary if function sent successfully, the dictionary with key and error otherwise."""
        exceptions = {}
        try:
            if send_in_step_order:
                master.send_function_test(func_test_json=send_json,
                                          point_def_path=POINT_DEFINITIONS_PATH,
                                          func_def_path=FUNCTION_DEFINITIONS_PATH)
            else:
                master.send_json(pdefs, FUNCTION_DEFINITIONS_PATH, send_json=send_json)
        except Exception as err:
            print("{}: {}".format(type(err).__name__, str(err)))
            exceptions['key'] = type(err).__name__
            exceptions['error'] = str(err)
        return exceptions

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

    def send_function_and_confirm(self, master, agent, function):
        """Send point values for a function and test that they were received correctly."""

        # 'function' can be the name of a file containing json or it can be a dictionary
        function_to_send = self.convert_json_file_to_dict(function) if type(function) == str else function
        exceptions = self.send_points(master, function_to_send)
        assert exceptions == {}

        for point_name in function_to_send.keys():
            if point_name not in ["name", "function_id", "function_name"]:
                pdef = pdefs.point_named(point_name)
                if pdef is None:
                    raise ValueError('Missing point definition: {}'.format(point_name))
                elif pdef.is_array_head_point:
                    for offset, value in enumerate(
                        record[field['name']]
                            for record in function_to_send[point_name] for field in pdef.array_points
                    ):
                        get_point = self.get_point_by_index(agent, pdef.group, pdef.index+offset)
                        assert get_point == value, "Expected {} = {}, got {}".format(point_name, value, get_point)
                else:
                    # Ask the agent whether it has a point definition for the point name.
                    point_def = self.get_point_definitions(agent, [point_name]).get(point_name, None)
                    assert point_def is not None, "Agent has no point definition for {}".format(point_name)

                    # Confirm that the agent's current value for the point matches the value that was sent.
                    agent_value = self.get_point(agent, point_name)
                    sent_value = function_to_send[point_name]
                    assert agent_value == sent_value, "Expected {} = {}, got {}".format(point_name,
                                                                                        sent_value,
                                                                                        agent_value)

        # Confirm that the agent published function values that match the ones which were sent.
        # When comparing the function that was sent, ignore its special keys (which wouldn't have been received).
        func_compared = {k: v for k, v in function_to_send.items() if k not in ["name", "function_id", "function_name"]}
        dict_compare(func_compared, messages.get(FUNCTION_TOPIC, {}).get('message', {}).get('points', {}))
        assert exceptions == {}

    # **********
    # ********** OUTPUT TESTS (send data from Master to Agent to ControlAgent) ************
    # **********

    def test_point_definition(self, mesa_data_agent, reset):
        """Confirm whether the agent has a point def for a given name."""
        point_name = 'DOPM.WinTms'
        point_def = self.get_point_definitions(mesa_data_agent, [point_name]).get(point_name, None)
        assert point_def is not None, "Agent has no point definition for {}".format(point_name)

    def test_simple_function(self, run_data_master, mesa_data_agent, reset):
        """Send charge_discharge function values -- a simple function (no arrays or selector blocks)."""
        charge_discharge_function = {
            "name": "function_test_name",
            "function_id": "charge_discharge",
            "function_name": "charge_discharge",
            "DCHD.WinTms": 10,
            "DCHD.RmpTms": 12,
            "DCHD.RvrtTms": 13,
            "DCHD.WTgt": 14,
            "DCHD.RmpUpRte": 15,
            "DCHD.RmpDnRte": 16,
            "DCHD.ChaRmpUpRte": 17,
            "DCHD.ChaRmpDnRte.out": 18,
            "DCHD.ModPrty.out": 19,
            "DCHD.VArAct.out": 20,
            "DCHD.ModEna": 1
        }
        self.set_point(mesa_data_agent, 'DCHA.Beh', True)         # Set the function support point to True
        self.send_function_and_confirm(run_data_master, mesa_data_agent, charge_discharge_function)

    # **********
    # ********** INPUT TESTS (send data from ControlAgent to Agent to Master) ************
    # **********

    def test_set_point(self, run_data_master, mesa_data_agent, reset):
        """Test set an input point and confirm getting the same value for that point."""
        self.set_point(mesa_data_agent, TEST_SET_POINT_NAME, 45)
        received_val = self.get_value_from_master(run_data_master, TEST_SET_POINT_NAME)
        assert received_val == 45, "Expected {} = {}, got {}".format(TEST_SET_POINT_NAME, 45, received_val)
