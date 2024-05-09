# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

__docformat__ = 'reStructuredText'

"""The cdriver is an example implementation of an interface that
allows the platform driver to transparently call C code.
This file is an `interface` and will only be usable in the
platform_driver/interfaces directory. The shared object will
need to be somewhere it can be found by this file.
"""

from io import StringIO
from csv import DictReader
from ctypes import CDLL, cdll

from platform_driver.interfaces import BasicRevert, BaseInterface, BaseRegister


def so_lookup_function(shared_object, function_name):
    """Attempt to find a symbol in the loaded shared object
    or raise an IOerror.

    :param shared_object:
    :type shared_object: shared object
    :param function_name:
    :type function_name: string
    :returns: function or raises an exception
    """
    try:
        function = getattr(shared_object, function_name)
    except AttributeError:
        raise IOError("No such function in shared object: {}".format(function_name))

    return function

class CRegister(BaseRegister):
    def __init__(self, read_only, pointName, units, description=''):
        super(CRegister, self).__init__("byte", read_only, pointName, units, description = '')


class Interface(BasicRevert, BaseInterface):
    """Simple interface that calls c code.
    Function names are constructed based on register
    point names for brevity. Few if any APIs will
    support this.
    """
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, registry_config_str):
        so_filename = config_dict['shared_object']
        cdll.LoadLibrary(so_filename)
        self.shared_object = CDLL(so_filename)
        self.parse_config(registry_config_str)

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        so_get_point = so_lookup_function(self.shared_object,
                                          "get_" + register.point_name)
        return so_get_point()

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)

        so_set_point = so_lookup_function(self.shared_object,
                                          "set_" + register.point_name)
        so_set_point(value)

    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            result[register.point_name] = self.get_point(register.point_name)

        return result

    def parse_config(self, configDict):
        if configDict is None:
            return

        for regDef in configDict:
            #Skip lines that have no address yet.
            if not regDef['Point Name']:
                continue

            read_only = regDef['Writable'].lower() != 'true'
            point_name = regDef['Volttron Point Name']
            description = regDef['Notes']
            units = regDef['Units']
            register = CRegister(read_only, point_name, units, description=description)

            self.insert_register(register)
