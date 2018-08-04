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

import cmd
import logging
import sys

from pydnp3 import opendnp3

from dnp3.points import PointDefinitions, DIRECT_OPERATE
from mesa_master import MesaMaster
from function_test import FunctionTest

LOG_LEVELS = opendnp3.levels.NORMAL
SERVER_IP = "127.0.0.1"
CLIENT_IP = "0.0.0.0"
PORT_NUMBER = 20000
POINT_DEFINITIONS_PATH = 'tests/data/mesa_points.config'
FUNCTION_DEFINITIONS_PATH = 'tests/data/mesa_functions.yaml'

CURVE_JSON = {
    "name": "function_test_curve",
    "function_id": "curve",
    "function_name": "curve_function",
    "Curve Edit Selector": 3,
    "Curve Mode Type": 40,
    "Curve Time Window": 5000,
    "Curve Ramp Time": 24,
    "Curve Revert Time": 51,
    "Curve Maximum Number of Points": 671,
    "Independent (X-Value) Units for Curve": 51,
    "Dependent (Y-Value) Units for Curve": 625,
    "Curve Time Constant": 612,
    "Curve Decreasing Max Ramp Rate": 331,
    "Curve Increasing Ramp Rate": 451,
    "CurveStart-X": [
        {"Curve-X": 111, "Curve-Y": 2},
        {"Curve-X": 3, "Curve-Y": 4},
        {"Curve-X": 5, "Curve-Y": 6},
        {"Curve-X": 7, "Curve-Y": 8},
        {"Curve-X": 9, "Curve-Y": 10}
    ],
    "Curve Number of Points": 5
}

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
_log.addHandler(stdout_stream)
_log.setLevel(logging.DEBUG)


class MesaMasterCmd(cmd.Cmd):
    """
        Run MesaMaster from the command line in support of certain types of ad-hoc outstation testing.
    """

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = 'master> '   # Used by the Cmd framework, displayed when issuing a command-line prompt.
        self._application = None

    @property
    def application(self):
        if self._application is None:
            self._application = MesaMaster(local_ip=SERVER_IP, port=PORT_NUMBER)
            self._application.connect()
        return self._application

    def startup(self):
        """Display the command-line interface's menu and issue a prompt."""
        self.do_menu('')
        self.cmdloop('Please enter a command.')
        exit()

    def do_menu(self, line):
        """Display a menu of command-line options. Command syntax is: menu"""
        print('\tfunction\tSend all data/commands for the MESA-ESS function.')
        print('\tquit')

    def do_function(self, line):
        """Send a function test after validating the function test (as JSON)."""
        point_defs = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)
        ftest = FunctionTest(FUNCTION_DEFINITIONS_PATH, CURVE_JSON)
        ftest.is_valid()
        for func_step_def in ftest.get_function_def().steps:
            try:
                point_value = ftest.points[func_step_def.name]
            except KeyError:
                continue
            pdef = point_defs.point_named(func_step_def.name)
            if not pdef:
                raise ValueError("Point definition not found: {}".format(pdef.name))

            if type(point_value) == list:
                self.application.send_array(point_value, pdef)
            else:
                try:
                    send_func = self.application.SEND_FUNCTIONS[func_step_def.fcodes[0]
                    if func_step_def.fcodes
                    else DIRECT_OPERATE]
                except (KeyError, IndexError):
                    raise ValueError("Unrecognized sent command function")

                self.application.send_command(send_func, pdef, point_value)

    def do_quit(self, line):
        """Quit the command line interface. Command syntax is: quit"""
        self.application.shutdown()
        exit()


def main():
    cmd_interface = MesaMasterCmd()
    _log.debug('Initialization complete. In command loop.')
    cmd_interface.startup()
    _log.debug('Exiting.')


if __name__ == '__main__':
    main()
