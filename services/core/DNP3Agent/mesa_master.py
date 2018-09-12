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

import os
import time

from pydnp3 import opendnp3

from dnp3.points import DIRECT_OPERATE, SELECT, OPERATE
from dnp3.points import POINT_TYPE_ANALOG_OUTPUT, POINT_TYPE_BINARY_OUTPUT
from dnp3.points import PointDefinitions
from dnp3_master import DNP3Master
from function_test import FunctionTest

POINT_DEF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tests', 'data', 'mesa_points.config'))

OUTPUT_TYPES = {
    float: opendnp3.AnalogOutputFloat32,
    int: opendnp3.AnalogOutputInt32,
    bool: opendnp3.ControlRelayOutputBlock
}

POINT_TYPE_TO_PYTHON_TYPE = {
    POINT_TYPE_BINARY_OUTPUT: {bool},
    POINT_TYPE_ANALOG_OUTPUT: {int, float},
}


class MesaMasterException(Exception):
    pass


class MesaMaster(DNP3Master):

    def __init__(self, **kwargs):
        DNP3Master.__init__(self, **kwargs)

        self.SEND_FUNCTIONS = {
            DIRECT_OPERATE: self.send_direct_operate_command,
            SELECT: self.send_select_and_operate_command,
            OPERATE: self.send_select_and_operate_command,
        }

    def send_command(self, send_func, pdef, point_value, index=None):
        """
            Send a command to outstation. Check for valid value to send.

        :param send_func: send_direct_operate_command or send_select_and_operate_command
        :param pdef: point definition
        :param point_value: value of the point that will be sent to outstation
        :param index: index of the point from point definition
        """
        value_type = type(point_value)

        if pdef.point_type == POINT_TYPE_BINARY_OUTPUT:
            point_value = opendnp3.ControlCode.LATCH_ON if point_value else opendnp3.ControlCode.LATCH_OFF

        try:
            send_func(OUTPUT_TYPES[value_type](point_value), index or pdef.index)
            time.sleep(0.2)
        except KeyError:
            raise MesaMasterException("Unrecognized output type: {}".format(value_type))

    def send_array(self, json_array, pdef):
        """
            Send point array to outstation.

        :param json_array: json array of points and values that will be sent to outstation
        :param pdef: point definition
        """
        for offset, value in enumerate(
                record[field['name']]
                for record in json_array for field in pdef.array_points):

            self.send_command(self.send_direct_operate_command, pdef, value, index=pdef.index+offset)

    def send_function_test(self, point_def_path='', func_def_path='', func_test_path='', func_test_json=None):
        """
            Send a function test after validating the function test (as JSON).

        :param point_def_path: path to point definition config
        :param func_def_path: path to function definition config
        :param func_test_path: path to function test json
        :param func_test_json: function test json
        """
        ftest = FunctionTest(func_test_path, func_test_json, point_def_path=point_def_path, func_def_path=func_def_path)

        ftest.is_valid()

        pdefs = PointDefinitions(point_definitions_path=point_def_path or POINT_DEF_PATH)

        func_def = ftest.get_function_def()
        for func_step_def in func_def.steps:
            try:
                point_value = ftest.points[func_step_def.name]
            except KeyError:
                continue

            pdef = pdefs.point_named(func_step_def.name)  # No need to test for valid point name, as that was done above
            if not pdef:
                raise MesaMasterException("Point definition not found: {}".format(func_step_def.name))

            if type(point_value) == list:
                self.send_array(point_value, pdef)
            else:
                try:
                    send_func = self.SEND_FUNCTIONS[func_step_def.fcodes[0] if func_step_def.fcodes else DIRECT_OPERATE]
                except (KeyError, IndexError):
                    raise MesaMasterException("Unrecognized sent command function")

                self.send_command(send_func, pdef, point_value)


def main():
    mesa_master = MesaMaster()
    mesa_master.connect()
    # Ad-hoc tests can be inserted here if desired.
    mesa_master.shutdown()


if __name__ == '__main__':
    main()
