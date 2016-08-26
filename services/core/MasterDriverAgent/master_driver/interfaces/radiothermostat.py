'''
Copyright (c) 2016, Alliance for Sustainable Energy, LLC
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided
that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions
and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or
promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''

"""

Volttron-3.0 Driver framewrok Interface for radio thermostat relay agent

The way schedules are reported and set will probably change in a future version of VOLTTRON.

Schedule points for this interface:
heat_pgm_week,cool_pgm_week,heat_pgm_mon,heat_pgm_tue,heat_pgm_wed,heat_pgm_thu,heat_pgm_fri,
heat_pgm_sat,heat_pgm_sun,cool_pgm_mon,cool_pgm_tue,cool_pgm_wed,cool_pgm_thu,
cool_pgm_fri,cool_pgm_sat,cool_pgm_sun,

"""
import json
import logging
import sys
import time
import ast
import csv
from master_driver.interfaces import BaseInterface, BaseRegister, DriverInterfaceError
from csv import DictReader
from StringIO import StringIO
from datetime import datetime
from . import  thermostat_api


class Register(BaseRegister):
    '''Inherits from  Volttron Register Class'''
    def __init__(self, read_only, pointName, device_point_name, units, default_value):
        '''Initialize register with read_only,pointName, device_point_name, units and default_value '''
        super(Register, self).__init__("byte", read_only, pointName, units, default_value)
        self.default_value = default_value
        self.device_point_name = device_point_name


class Interface(BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        # Heat program name
        self.program_heat = {
            'heat_pgm_mon',
            'heat_pgm_tue',
            'heat_pgm_wed',
            'heat_pgm_thu',
            'heat_pgm_fri',
            'heat_pgm_sat',
            'heat_pgm_sun',
        }
        # cool program names
        self.program_cool = {
            'cool_pgm_mon',
            'cool_pgm_tue',
            'cool_pgm_wed',
            'cool_pgm_thu',
            'cool_pgm_fri',
            'cool_pgm_sat',
            'cool_pgm_sun'
        }

        self.point_name_map = {
                'tstat_mode' : "tmode",
                'tstat_temp_sensor' : "temp",
                'tstat_heat_sp' : 't_heat',
                'tstat_cool_sp' : "t_cool",
                'tstat_fan_mode' : 'fmode',
                'tstat_hvac_state' : 'tstate'
        }
        # point name present in a default query to the thermostat
        self.query_point_name = {
                'tstat_mode',
                'tstat_temp_sensor',
                'tstat_heat_sp',
                'tstat_cool_sp',
                'tstat_fan_mode',
                'tstat_hvac_state',
                'override',
                'hold'
        }
        # list of program modes/names
        self.program_name = {
            'heat_pgm_week',
            'heat_pgm_mon',
            'heat_pgm_tue',
            'heat_pgm_wed',
            'heat_pgm_thu',
            'heat_pgm_fri',
            'heat_pgm_sat',
            'heat_pgm_sun',
            'cool_pgm_week',
            'cool_pgm_mon',
            'cool_pgm_tue',
            'cool_pgm_wed',
            'cool_pgm_thu',
            'cool_pgm_fri',
            'cool_pgm_sat',
            'cool_pgm_sun'
        }


    def configure(self, config_dict, registry_config_str):
        '''Configure the Inteface'''
        print config_dict
        self.parse_config(registry_config_str)
        self.target_address = config_dict["device_address"]
        self.ping_target(self.target_address)
        url = config_dict["device_url"]
        self.thermostat = thermostat_api.ThermostatInterface(url)


    def get_point(self, point_name):
        '''Returns the value of a point on the device'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.device_point_name,register.default_value]}
        # result = self.vip.rpc.call('radiothermostat', 'get_point',
        #                                self.target_address,point_map).get()
        result = self._get_point(self.target_address,point_map)
        return result


    def set_point(self, point_name, value):
        '''Sets the value of a point o  the devcie'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.device_point_name,register.default_value]}
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)
        # result = self.vip.rpc.call('radiothermostat', 'set_point',
        #                                self.target_address,point_map,value).get()
        result = self._set_point(self.target_address,point_map,value)
        return result


    def revert_point(self,point_name):
        '''sets the value of a point to its default value'''
        if point_name == 'heat_pgm_week':
            for program in self.program_heat:
                register = self.get_register_by_name(program)
                value = register.default_value
                self.set_point(program,value)
        elif point_name == 'cool_pgm_week':
            for program in self.program_cool:
                register = self.get_register_by_name(program)
                value = register.default_value
                self.set_point(program,value)
        else:
            register = self.get_register_by_name(point_name)
            value = register.default_value
            self.set_point(point_name,value)




    def _set_point(self, device, point_map, value):
        '''
            Set value of a point_name on a device
        '''
        result = {}
        for point_names, properties in point_map.iteritems():
            point_name = properties[0]

            if point_name in self.program_name:
                pgm,day = point_name.rsplit('_',1)
                if pgm == 'heat_pgm':
                    if(day == 'week'):
                        result = self.thermostat.set_heat_pgm(value)
                    else:
                        result = self.thermostat.set_heat_pgm(value, day)
                elif pgm == 'cool_pgm':
                    if(day == 'week'):
                        result = self.thermostat.set_cool_pgm(value)
                    else:
                        result = self.thermostat.set_cool_pgm(value, day)
            elif point_name == "tstat_mode":
                result = self.thermostat.mode(int(value))
            elif point_name == "tstat_fan_mode":
                result = self.thermostat.fmode(int(value))
            elif point_name == "tstat_cool_sp":
                result = self.thermostat.t_cool(value)
            elif point_name == "tstat_heat_sp":
                result = self.thermostat.t_heat(value)
            elif point_name == 'energy_led':
                result = self.thermostat.energy_led(value)
            else:
                print("No such writable point found"+point_names)
        print str(point_names) + "::" + str(result)
        return (result)



    def _get_point(self, device, point_map):
        '''
            Get value of a point_name on a device
        '''
        result = {}
        query = {}
        point_map_obj = {}
        for point_names, properties in point_map.iteritems():
            point_name =  properties[0]
    
            query = json.loads(self.thermostat.tstat())
            if point_name in self.query_point_name:
                try:
                    db = query[self.point_name_map[point_name]]
                    result.update({point_names : str(db) })
                except:
                    result.update({point_names : str("NA") })
            else:
                pgm,day = point_name.rsplit('_',1)
                if pgm == 'heat_pgm':
                    if day == 'week':
                        query = self.thermostat.get_heat_pgm()
                        result.update({point_names : str(query)})
                    else:
                        query = self.thermostat.get_heat_pgm(day)
                        result.update({point_names : str(query)})
                elif pgm == 'cool_pgm':
                    if day == 'week':
                        query = self.thermostat.get_cool_pgm()
                        result.update({point_names : str(query)})
                    else:
                        query = self.thermostat.get_cool_pgm(day)
                        result.update({point_names : str(query)})
        return (result)


    def revert_all(self):
        '''Sets all points on the device to their default values'''
        write_registers = self.get_registers_by_type("byte", False)
        for register in write_registers:
            self.revert_point(register.point_name)

    def scrape_all(self):
        '''Scrapes the device for current status of all points'''
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            point_map[register.point_name] = [register.device_point_name,register.default_value]
        # result = self.vip.rpc.call('radiothermostat', 'get_point',
        #                                self.target_address,point_map).get()
        result = self._get_point(self.target_address,point_map)
        return result

    def ping_target(self, address):
        '''Ping target function not implemented for this interface'''
        print("ping_target not implemented in radiothermostat interface")

    def parse_config(self, config_string):
        '''Parses the file with point_names and properties, and creates registers'''
        if config_string is None:
            return
        f = StringIO(config_string)
        configDict = DictReader(f)

        for regDef in configDict:

            read_only = regDef['Writable'] == 'FALSE'
            point_name = regDef['Volttron Point Name']
            device_point_name = regDef['Point Name']
            units = regDef['Units']
            default_value = regDef['Default']
            register = Register(
                                read_only,
                                point_name,
                                device_point_name,
                                units,
                                default_value)
            self.insert_register(register)
