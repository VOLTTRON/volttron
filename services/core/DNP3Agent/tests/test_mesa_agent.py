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
TEST_SET_POINT_NAME = "DCHD.WinTms (in)"

# Get point and function definitions from the files in the test directory.
POINT_DEFINITIONS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'mesa_points.config'))
FUNCTION_DEFINITIONS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'mesa_functions.yaml'))

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
def agent(request, volttron_instance):
    """Build the test agent for rpc call."""

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
                                    prefix='mesa/function',
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
def run_master(request):
    """Run Mesa master application."""
    master = MesaMasterTest(local_ip=MESA_AGENT_CONFIG['local_ip'],
                            port=MESA_AGENT_CONFIG['port'])
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
    agent.vip.rpc.call(MESA_AGENT_ID, 'reset')


class TestMesaAgent:
    """Regression tests for the Mesa Agent."""

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
                master.send_function_test(func_test_json=send_json)
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

    def send_function_and_confirm(self, master, agent, json_file):
        """Test get points to confirm if points is set correctly by master."""
        send_function = self.convert_json_file_to_dict(json_file)
        exceptions = self.send_points(master, send_function)

        for point_name in send_function.keys():
            if point_name not in ["name", "function_id", "function_name"]:

                pdef = pdefs.point_named(point_name)

                if pdef.is_array_head_point:
                    for offset, value in enumerate(
                        record[field['name']]
                            for record in send_function[point_name] for field in pdef.array_points
                    ):
                        get_point = self.get_point_by_index(agent, pdef.group, pdef.index+offset)
                        assert get_point == value, "Expected {} = {}, got {}".format(point_name, value, get_point)
                else:
                    get_point = self.get_point(agent, point_name)
                    # Ask the agent whether it has a point definition for that point name.
                    point_defs = self.get_point_definitions(agent, [point_name])
                    point_def = point_defs.get(point_name, None)
                    assert point_def is not None, "Agent has no point definition for {}".format(point_name)
                    # Confirm that the agent's point value matches the value in the json.
                    json_val = send_function[point_name]
                    assert get_point == json_val, "Expected {} = {}, got {}".format(point_name,
                                                                                    json_val,
                                                                                    get_point)
        dict_compare(messages['mesa/function']['message']['points'], send_function)
        assert exceptions == {}

    # **********
    # ********** OUTPUT TESTS (send data from Master to Agent to ControlAgent) ************
    # **********

    def test_simple_function(self, run_master, agent, reset):
        """Test a simple function (not array or selector block)."""

        # Set the function support point to True
        self.set_point(agent, 'Supports Charge/Discharge Mode', True)

        self.send_function_and_confirm(run_master, agent, 'charge_discharge.json')

    def test_array(self, run_master, agent, reset):
        """Test array function."""
        self.send_function_and_confirm(run_master, agent, 'curve.json')
        self.send_function_and_confirm(run_master, agent, 'inverter.json')

    def test_selector_blocks(self, run_master, agent, reset):
        """Test selector block functions."""
        assert self.get_selector_block(agent, 'Curve Edit Selector', 2) == {}
        assert self.get_selector_block(agent, 'Curve Edit Selector', 5) == {}

        send_function_1 = self.convert_json_file_to_dict('selector_block_1.json')
        exceptions_1 = self.send_points(run_master, send_function_1)
        assert exceptions_1 == {}

        send_function_2 = self.convert_json_file_to_dict('selector_block_2.json')
        exceptions_2 = self.send_points(run_master, send_function_2)
        assert exceptions_2 == {}

        get_selector_block_1 = self.get_selector_block(agent, 'Curve Edit Selector', 2)
        get_selector_block_2 = self.get_selector_block(agent, 'Curve Edit Selector', 5)
        dict_compare(get_selector_block_1, send_function_1)
        dict_compare(get_selector_block_2, send_function_2)
        assert get_selector_block_1 != get_selector_block_2

    def test_invalid_function(self, run_master, agent, reset):
        """Test send an invalid function, confirm getting exception error."""
        send_function = {
            "name": "function_test_name",
            "function_id": "Invalid Function",
            "function_name": "Testing Invalid Function",
            "point_1": 1,
            "point_2": 2
        }

        exceptions = self.send_points(run_master, send_function)
        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Function definition not found: Invalid Function'
        }

    def test_invalid_point_value(self, run_master, agent, reset):
        """Test send a function with an invalid data type for a point, confirm getting exception error."""
        # Set the function support point to True
        self.set_point(agent, "Supports Charge/Discharge Mode", True)

        send_function = self.convert_json_file_to_dict('charge_discharge.json')

        # Change the analog value to binary
        send_function['DCHD.WinTms (out)'] = True

        exceptions = self.send_points(run_master, send_function)
        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Invalid point value: DCHD.WinTms (out)'
        }

        # Change back to the valid point value
        send_function['DCHD.WinTms (out)'] = 10

        # Change the binary value to analog
        send_function['DCHD.ModEna'] = 1

        exceptions = self.send_points(run_master, send_function)
        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Invalid point value: DCHD.ModEna'
        }

    def test_invalid_array_value(self, run_master, agent, reset):
        """Test send a function with an invalid data type for a point, confirm getting exception error."""
        send_function = self.convert_json_file_to_dict('curve.json')

        # Change the analog array value to binary
        send_function['CurveStart-X'] = [
            {"Curve-X": 100,
             "Curve-Y": 200},
            {"Curve-X": 300,
             "Curve-Y": 400},
            {"Curve-X": True,
             "Curve-Y": 500}
        ]

        exceptions = self.send_points(run_master, send_function)
        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Invalid point value: CurveStart-X'
        }

    def test_missing_mandatory_step(self, run_master, agent, reset):
        """Test send a function missing its mandatory step, confirm getting exception error."""

        # Set the function support point to True
        self.set_point(agent, "Supports Charge/Discharge Mode", True)

        send_function = self.convert_json_file_to_dict('charge_discharge.json')

        # Remove mandatory step
        del send_function['DCHD.RmpTms (out)']

        exceptions = self.send_points(run_master, send_function)

        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Function Test missing mandatory steps'
        }

    def test_missing_point_definition(self, run_master, agent, reset):
        """Test send a function with a point not defined in point definitions, confirm getting exception error."""

        # Set the function support point to True
        self.set_point(agent, "Supports Charge/Discharge Mode", True)

        send_function = self.convert_json_file_to_dict('charge_discharge.json')

        # Add a point for testing
        send_function['test point'] = 5

        exceptions = self.send_points(run_master, send_function)

        assert exceptions == {
            'key': 'FunctionTestException',
            'error': 'Validation Error: Not all points resolve'
        }

    def test_missing_support_point(self, run_master, agent, reset):
        """Test send a function missing its support point, confirm getting exception error."""

        # Set the function support point to True
        self.set_point(agent, "Supports Charge/Discharge Mode", False)

        send_function = self.convert_json_file_to_dict('charge_discharge.json')
        exceptions = self.send_points(run_master, send_function)

        for point_name in send_function.keys():
            if point_name not in ["name", "function_id", "function_name"]:
                received_val = self.get_point(agent, point_name)
                err_msg = "Expected no {} value due to unsupported function, but received {}"
                assert received_val is None, err_msg.format(point_name, received_val)

        assert messages == {}
        assert exceptions == {}

    def test_wrong_step_order(self, run_master, agent, reset):
        """Test send a function in wrong step order, confirm getting exception error."""

        # Set the function support point to True
        self.set_point(agent, "Supports Charge/Discharge Mode", True)

        charge_discharge_dict = {
            "name": "function_test_name",
            "function_id": "LN DCHD",
            "function_name": "charge_discharge_mode",
            "DCHD.RmpTms (out)": 12,
            "DCHD.WinTms (out)": 10,  # In wrong order: suppose to be step 1 instead of step 2
            "DCHD.RevtTms (out)": 13,
            "DCHD.WTgt (out)": 14,
            "DCHD.RmpUpRte (out)": 15,
            "DCHD.RmpDnRte (out)": 16,
            "DCHD.ChaRmpUpRte (out)": 17,
            "DCHD.ChaRmpDnRte (out)": 18,
            "DCHD.ModPrty (out)": 19,
            "DCHD.VArAct (out)": 20,
            "DCHD.ModEna": True
        }

        exceptions = self.send_points(run_master, charge_discharge_dict, send_in_step_order=False)

        assert exceptions == {
            'key': 'MesaMasterTestException',
            'error': 'Step not in order: 1'
        }

    # **********
    # ********** INPUT TESTS (send data from ControlAgent to Agent to Master) ************
    # **********

    def test_set_point(self, run_master, agent, reset):
        """Test set an input point and confirm getting the same value for that point."""
        self.set_point(agent, TEST_SET_POINT_NAME, 45)
        received_val = self.get_value_from_master(run_master, TEST_SET_POINT_NAME)
        assert received_val == 45, "Expected {} = {}, got {}".format(TEST_SET_POINT_NAME, 45, received_val)

    def test_set_invalid_point(self, agent, reset):
        """Test set an invalid input point and confirm getting exception error."""
        try:
            self.set_point(agent, "Invalid Point", 45)
            assert False, "Input point with invalid name failed to cause an exception"
        except Exception as err:
            assert str(err) == "dnp3.points.DNP3Exception('No point named Invalid Point')"

    def test_set_invalid_point_value(self, agent, reset):
        """Test set an invalid input point and confirm getting exception error."""
        try:
            self.set_point(agent, "DCHD.WinTms (in)", True)
            assert False, "Input point with invalid value failed to cause an exception"
        except Exception as err:
            assert str(err) == "dnp3.points.DNP3Exception(\"Received <type 'bool'> value for PointDefinition " \
                               "DCHD.WinTms (in) (30.1, index=91, type=Analog Input).\")"

    def test_set_points(self, run_master, agent, reset):
        """Test set a set of points and confirm getting the correct values for all point that are set."""

        set_points_dict = {
            "DCHD.WinTms (in)": 1,
            "DCHD.RmpTms (in)": 2,
            "DCHD.RevtTms (in)": 3,
            "DCHD.WTgt (in)": 4,
            "DCHD.RmpUpRte (in)": 5,
            "DCHD.RmpDnRte (in)": 6,
            "DCHD.ChaRmpUpRte (in)": 7,
            "DCHD.ChaRmpDnRte (in)": 8,
            "DCHD.ModPrty (in)": 9,
            "DCHD.VArAct (in)": 10,
            "DCHD.ModEna (in)": True
        }

        self.set_points(agent, set_points_dict)

        for point_name in set_points_dict.keys():
            assert self.get_value_from_master(run_master, point_name) == set_points_dict[point_name]

    def test_set_points_array(self, run_master, agent, reset):
        """Test set a set of points of an array and confirm getting the correct values for all point that are set."""

        self.set_points(agent, {
            "CurveStart-X (in)": [
                {"Curve-X": 1,
                 "Curve-Y": 2},
                {"Curve-X": 3,
                 "Curve-Y": 4},
                {"Curve-X": 5,
                 "Curve-Y": 6}
            ]
        })

        pdef = pdefs.point_named("CurveStart-X (in)")
        group = input_group_map[pdef.group]

        assert run_master.soe_handler.result[group][500] == 1.0
        assert run_master.soe_handler.result[group][501] == 2.0
        assert run_master.soe_handler.result[group][502] == 3.0
        assert run_master.soe_handler.result[group][503] == 4.0
        assert run_master.soe_handler.result[group][504] == 5.0
        assert run_master.soe_handler.result[group][505] == 6.0

    def test_wrong_database_size(self, run_master, agent, reset):
        """Test set point for an index out of database size range, confirm receiving None for that point."""

        try:
            # This Input Test Point index is 800, but database size is only 700
            self.set_point(agent, "Input Test Point", 45)
            assert False, "Wrong database size failed to cause an exception"
        except Exception as err:
            assert str(err) == "dnp3.points.DNP3Exception('Attempt to set a value for index 800 " \
                               "which exceeds database size 700')"
