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

import pytest

from dnp3.points import ArrayHeadPointDefinition, PointDefinitions, PointValue
from dnp3.mesa.agent import MesaAgent
from dnp3.mesa.functions import FunctionDefinitions

from test_mesa_agent import POINT_DEFINITIONS_PATH, FUNCTION_DEFINITIONS_PATH


def test_point_definition_load():
    point_defs = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)
    import pprint
    pprint.pprint(point_defs._points)
    pprint.pprint(point_defs._point_name_dict)
    print("_point_variations_dict")
    pprint.pprint(point_defs._point_variation_dict)


def test_point_definition():

    test_dict = {
        "name": "CurveStart-X",
        "type": "array",                # Start of the curve's X/Y array
        "array_times_repeated": 100,
        "group": 40,
        "variation": 1,
        "index": 207,
        "description": "Starting index for a curve of up to 99 X/Y points",
        "array_points": [
            {
                "name": "Curve-X"
            },
            {
                "name": "Curve-Y"
            }
        ]
    }
    test_def = ArrayHeadPointDefinition(test_dict)
    print(test_def)


def send_points(mesa_agent, some_points):

    for name, value, index in some_points:
        pdef = mesa_agent.point_definitions.get_point_named(name,index)
        point_value = PointValue('Operate',
                                 None,
                                 value,
                                 pdef,
                                 pdef.index,
                                 None)  # What is op_type used for?

        print(point_value)
        mesa_agent._process_point_value(point_value)


def test_mesa_agent():
    mesa_agent = MesaAgent(point_topic='points_foobar', local_ip='127.0.0.1', port=8999, outstation_config={},
                           function_topic='functions_foobar', outstation_status_topic='',
                           local_point_definitions_path=POINT_DEFINITIONS_PATH,
                           local_function_definitions_path=FUNCTION_DEFINITIONS_PATH)

    mesa_agent._configure('', '', {})
    point_definitions = mesa_agent.point_definitions
    supported_pdef = point_definitions.get_point_named("Supports Charge/Discharge Mode")
    mesa_agent.update_input_point(supported_pdef, True)

    test_points = (
        # ("DCHD.WinTms (out)", 1.0),
        # ("DCHD.RmpTms (out)", 2.0),
        # ("DCHD.RevtTms (out)", 3.0),
        ("CurveStart-X", 1.0, None),
        ("CurveStart-X", 2.0, 208),

    )
    send_points(mesa_agent, test_points)


def test_mesa_agent_2():
    mesa_agent = MesaAgent(point_topic='points_foobar', local_ip='127.0.0.1', port=8999, outstation_config={},
                           function_topic='functions_foobar', outstation_status_topic='',
                           local_point_definitions_path=POINT_DEFINITIONS_PATH,
                           local_function_definitions_path=FUNCTION_DEFINITIONS_PATH)

    mesa_agent._configure('', '', {})
    point_definitions = mesa_agent.point_definitions
    supported_pdef = point_definitions.get_point_named("Supports Charge/Discharge Mode")
    mesa_agent.update_input_point(supported_pdef, True)

    test_points = (
        ("DCHD.WinTms (out)", 1.0, None),
        #("DCHD.RmpTms (out)", 2.0, None),
        ("DCHD.RevtTms (out)", 3.0, None),

    )
    send_points(mesa_agent, test_points)


def test_function_definitions():
    point_definitions = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)
    fdefs = FunctionDefinitions(point_definitions, function_definitions_path=FUNCTION_DEFINITIONS_PATH)

    fd = fdefs.function_for_id("curve")
    print(fd)

    pdef = point_definitions.get_point_named("DCHD.WinTms (out)")
    print(pdef)
    print(fdefs.step_definition_for_point(pdef))


def test_selector_block():
    """
        Test send a Curve function / selector block (including an array of points) to MesaAgent.
        Get MesaAgent's selector block and confirm that it has the correct contents.
        Do this for a variety of Edit Selectors and array contents.
    """

    def process_block_points(agt, block_points, edit_selector):
        """Send each point value in block_points to the MesaAgent."""
        # print('Processing {}'.format(block_points))
        for name, value, index in block_points:
            point_definitions = agt.point_definitions
            pdef = point_definitions.get_point_named(name, index)
            point_value = PointValue('Operate', None, value, pdef, pdef.index, None)
            agt._process_point_value(point_value)
        returned_block = mesa_agent.get_selector_block('Curve Edit Selector', edit_selector)
        # print('get_selector_block returned {}'.format(returned_block))
        return returned_block

    mesa_agent = MesaAgent(point_topic='points_foobar', local_ip='127.0.0.1', port=8999, outstation_config={},
                           function_topic='functions_foobar', outstation_status_topic='',
                           local_point_definitions_path=POINT_DEFINITIONS_PATH,
                           local_function_definitions_path=FUNCTION_DEFINITIONS_PATH)
    mesa_agent._configure('', '', {})

    block_1_points = [('Curve Edit Selector', 1, None),           # index 191 - Function and SelectorBlock start
                      ('CurveStart-X', 1.0, None),                # Point #1-X: index 207 - Array start
                      ('CurveStart-X', 2.0, 208),                 # Point #1-Y
                      ('Curve Number of Points', 1, None)]        # index 196 - Curve function end
    block_2_points = [('Curve Edit Selector', 2, None),           # index 191 - Function and SelectorBlock start
                      ('CurveStart-X', 1.0, None),                # Point #1-X: index 207 - Array start
                      ('CurveStart-X', 2.0, 208),                 # Point #1-Y
                      ('CurveStart-X', 3.0, 209),                 # Point #2-X
                      ('CurveStart-X', 4.0, 210),                 # Point #2-Y
                      ('Curve Number of Points', 2, None)]        # index 196 - Curve function end
    block_2a_points = [('Curve Edit Selector', 2, None),          # index 191 - Function and SelectorBlock start
                       ('CurveStart-X', 1.0, None),               # Point #1-X: index 207 - Array start
                       ('CurveStart-X', 2.0, 208),                # Point #1-Y
                       ('CurveStart-X', 5.0, 211),                # Point #3-X
                       ('CurveStart-X', 6.0, 212),                # Point #3-Y
                       ('Curve Number of Points', 3, None)]       # index 196 - Curve function end

    # Send block #1. Confirm that its array has a point with Y=2.0.
    block = process_block_points(mesa_agent, block_1_points, 1)
    assert block['CurveStart-X'][0]['Curve-Y'] == 2.0

    # Send block #2. Confirm that its array has a point #2 with Y=4.0.
    block = process_block_points(mesa_agent, block_2_points, 2)
    assert block['CurveStart-X'][1]['Curve-Y'] == 4.0

    # Send an updated block #2 with no point #2 and a new point #3.
    block = process_block_points(mesa_agent, block_2a_points, 2)
    # Confirm that its array still has a point #2 with Y=4.0, even though it wasn't just sent.
    assert block['CurveStart-X'][1]['Curve-Y'] == 4.0
    # Confirm that its array now has a point #3 with Y=6.0.
    assert block['CurveStart-X'][2]['Curve-Y'] == 6.0

    # Re-send block #1. Confirm that selector block initialization reset the point cache: the array has no second point.
    block = process_block_points(mesa_agent, block_1_points, 1)
    assert len(block['CurveStart-X']) == 1


if __name__ == "__main__":
    # test_mesa_agent()
    # test_mesa_agent_2()
    # test_function_definitions()
    # test_point_definition()
    test_point_definition_load()
    # test_selector_block()
