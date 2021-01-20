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
try:
    import dnp3
except ImportError:
    pytest.skip("pydnp3 not found!", allow_module_level=True)

from volttron.platform import jsonapi
from collections import OrderedDict

from dnp3 import DIRECT_OPERATE
from dnp3_master import SOEHandler
from mesa_master import MesaMaster
from dnp3.mesa.functions import FunctionDefinitions
from function_test import DATA_TYPE_TO_PYTHON_TYPE


class MesaMasterTestException(Exception):
    pass


class MesaMasterTest(MesaMaster):

    def __init__(self, **kwargs):
        MesaMaster.__init__(self, soe_handler=SOEHandler(), **kwargs)

    def shutdown(self):
        """
            Override MesaMaster shutdown
        """
        self.master.Disable()
        del self.master
        del self.channel

    def send_single_point(self, pdefs, point_name, point_value):
        """
            Send a single non-function point to the outstation. Check for validation.

            Used by DNP3Agent (not MesaAgent).

        :param pdefs: point definitions
        :param point_name: name of the point that will be sent
        :param point_value: value of the point that will be sent
        """
        pdef = pdefs.point_named(point_name)
        if not pdef:
            raise MesaMasterTestException("Point definition not found: {}".format(point_name))
        if not pdef.data_type:
            raise MesaMasterTestException("Unrecognized data type: {}".format(pdef.data_type))
        if pdef.data_type in DATA_TYPE_TO_PYTHON_TYPE and \
                type(point_value) not in DATA_TYPE_TO_PYTHON_TYPE[pdef.data_type]:
            raise MesaMasterTestException("Invalid point value: {}".format(pdef.name))
        self.send_command(self.send_direct_operate_command, pdef, point_value)

    def send_json(self, pdefs, func_def_path, send_json_path='', send_json=None):
        """
            Send a json in order for testing purpose.

        :param pdefs: point definitions
        :param func_def_path: path to function definition
        :param send_json_path: path to json that will be sent to the outstation
        :param send_json: json that will be sent to the outstation
        :return:
        """
        if send_json_path:
            send_json = jsonapi.load(open(send_json_path), object_pairs_hook=OrderedDict)

        try:
            function_id = send_json['function_id']
        except KeyError:
            raise MesaMasterTestException('Missing function_id')

        fdefs = FunctionDefinitions(pdefs, function_definitions_path=func_def_path)
        
        try:
            fdef = fdefs[function_id]
        except KeyError:
            raise MesaMasterTestException('Invalid function_id {}'.format(function_id))

        step = 1
        for name, value in send_json.items():
            if name not in ['name', 'function_id', 'function_name']:
                pdef = pdefs.point_named(name)
                step_def = fdef[pdef]
                if step != step_def.step_number:
                    raise MesaMasterTestException("Step not in order: {}".format(step))
                if type(value) == list:
                    self.send_array(value, pdef)
                else:
                    send_func = self.SEND_FUNCTIONS.get(step_def.fcodes[0] if step_def.fcodes else DIRECT_OPERATE, None)
                    self.send_command(send_func, pdef, value)
                step += 1


def main():
    mesa_platform_test = MesaMasterTest()
    mesa_platform_test.connect()
    # Ad-hoc tests can be inserted here if desired.
    mesa_platform_test.shutdown()


if __name__ == '__main__':
    main()
