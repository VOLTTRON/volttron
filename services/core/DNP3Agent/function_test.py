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

import json
import os

from dnp3.mesa.functions import FunctionDefinitions
from dnp3.points import PointDefinitions
from dnp3.points import POINT_TYPE_ANALOG_OUTPUT, POINT_TYPE_BINARY_OUTPUT, POINT_TYPES_BY_GROUP


POINT_DEF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tests', 'data', 'mesa_points.config'))
FUNCTION_DEF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tests', 'data', 'mesa_functions.yaml'))

POINT_TYPE_TO_PYTHON_TYPE = {
    POINT_TYPE_BINARY_OUTPUT: {bool},
    POINT_TYPE_ANALOG_OUTPUT: {int, float},
}


class FunctionTestException(Exception):
    pass


class FunctionTest(object):

    def __init__(self, func_test_path='', func_test_json=None, func_def_path='', point_def_path=''):
        self.func_def_path = func_def_path or FUNCTION_DEF_PATH
        self.point_definitions = PointDefinitions(point_definitions_path=point_def_path or POINT_DEF_PATH)
        self.ftest = func_test_json or json.load(open(func_test_path))
        self.function_id = self.ftest.get('function_id', self.ftest.get('id', None))
        self.function_name = self.ftest.get('function_name', self.ftest.get('name', None))
        self.name = self.ftest.get('name', None)
        self.points = {k: v for k, v in self.ftest.items() if k not in ["name", "function_id", "function_name", "id"]}

    def get_function_def(self):
        """
            Gets the function definition for the function test. Returns None if no definition is found.
        """
        fdefs = FunctionDefinitions(point_definitions=self.point_definitions,
                                    function_definitions_path=self.func_def_path)
        return fdefs.function_for_id(self.function_id)

    @staticmethod
    def get_mandatory_steps(func_def):
        """
            Returns list of mandatory steps for the given function definition.

        :param func_def: function definition
        """
        return [step.name for step in func_def.steps if step.optional == 'M']

    def has_mandatory_steps(self, fdef=None):
        """
            Returns True if the instance has all required steps, and raises an exception if not.

        :param fdef: function definition
        """
        fdef = fdef or self.get_function_def()
        if not fdef:
            raise FunctionTestException("Function definition not found: {}".format(self.function_id))

        if not all(step in self.ftest.keys() for step in self.get_mandatory_steps(fdef)):
            raise FunctionTestException("Function Test missing mandatory steps")

        return True

    def points_resolve(self, func_def):
        """
            Returns true if all the points in the instance resolve to point names in the function definition,
            and raises an exception if not.

        :param func_def: function definition of the given instance
        """
        # It would have been more informative to identify the mismatched step/point name,
        # but that would break a pytest assertion that matches on this specific exception description.
        if not all(step_name in [step.point_def.name for step in func_def.steps] for step_name in self.points.keys()):
            raise FunctionTestException("Not all points resolve")
        return True

    def correct_point_types(self):
        """
            Check valid point value.
        """
        for point_name, point_value in self.points.items():
            point_def = self.point_definitions.point_named(point_name)
            point_values = sum([list(v.values()) for v in point_value], []) if point_def.is_array else [point_value]
            for value in point_values:
                if type(value) not in POINT_TYPE_TO_PYTHON_TYPE[POINT_TYPES_BY_GROUP[point_def.group]]:
                    # It would have been more informative to display the value and/or type in the error message,
                    # but that would break a pytest assertion that matches on this specific exception description.
                    raise FunctionTestException("Invalid point value: {}".format(point_name))
        return True

    def is_valid(self):
        """
            Returns True if the function test passes two validation steps:
                1. it has all the mandatory steps
                2. its point names resolve to point names in the function definition
                3. its point value is valid
            If the function test is invalid, an exception is raised.
        """
        f_def = self.get_function_def()

        try:
            self.has_mandatory_steps(f_def)
            self.points_resolve(f_def)
            self.correct_point_types()
            return True
        except Exception as err:
            raise FunctionTestException("Validation Error: {}".format(str(err)))


def main():
    function_test = FunctionTest(func_test_path=os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                                             'tests', 'data', 'curve.json')))
    function_test.is_valid()


if __name__ == '__main__':
    main()