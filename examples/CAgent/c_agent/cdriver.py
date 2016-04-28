'''
Copyright (c) 2015, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.
'''

'''
This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''

__docformat__ = 'reStructuredText'

'''The cdriver is an example implementation of an interface that
allows the master driver to transparently call C code.
This file is an `interface` and will only be usable in the
master_driver/interfaces directory. The shared object will
need to be somewhere it can be found by this file.
'''

from StringIO import StringIO
from csv import DictReader

from master_driver.interfaces import BaseInterface, BaseRegister

################################################################################
from ctypes import *

so_filename = "libfoo.so"
cdll.LoadLibrary(so_filename)
shared_object = CDLL(so_filename)

water_temperature = shared_object.get_water_temperature
water_temperature.restype = c_float

def so_lookup_function(function_name):
    '''Attempt to find a symbol in the loaded shared object
    or raise an IOerror.

    :param function_name:
    :type function_name: string
    :returns: function or raises an exception
    '''
    try:
        function = getattr(shared_object, function_name)
    except AttributeError:
        raise IOError("No such function in shared object: {}".format(function_name))

    return function

################################################################################


class CRegister(BaseRegister):
    def __init__(self,read_only, pointName, units, description = ''):
        super(CRegister, self).__init__("byte", read_only, pointName, units, description = '')


class Interface(BaseInterface):
    '''Simple interface that calls c code.
    Function names are constructed based on register
    point names for brevity. Few if any APIs will
    support this.
    '''
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, registry_config_str):
        self.parse_config(registry_config_str)

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        so_get_point = so_lookup_function("get_" + register.point_name)

        return so_get_point()

    def set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)

        so_set_point = so_lookup_function("set_" + register.point_name)
        so_set_point(value)

        return None

    def scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            result[register.point_name] = self.get_point(register.point_name)

        return result

    def parse_config(self, config_string):
        if config_string is None:
            return

        f = StringIO(config_string)

        configDict = DictReader(f)

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
