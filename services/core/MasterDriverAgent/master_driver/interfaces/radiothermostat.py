""""

Volttron-3.0 Driver framewrok Interface for radio thermostat relay agent
April 2016
NREL

"""

import csv
from master_driver.interfaces import BaseInterface, BaseRegister, DriverInterfaceError
from csv import DictReader
from StringIO import StringIO


class Register(BaseRegister):
    '''Inherits from  Volttron Register Class'''
    def __init__(self, read_only, pointName, units, default_value):
        '''Initialize register with read_only,pointName, units and default_value '''
        super(Register, self).__init__("byte", read_only, pointName, units, default_value)
        self.default_value = default_value


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


    def configure(self, config_dict, registry_config_str):
        '''Configure the Inteface'''
        self.parse_config(registry_config_str)
        self.target_address = config_dict["device_address"]
        self.ping_target(self.target_address)


    def get_point(self, point_name):
        '''Returns the value of a point on the device'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.default_value]}
        result = self.vip.rpc.call('radiothermostat', 'get_point',
                                       self.target_address,point_map).get()
        return str(result)


    def set_point(self, point_name, value):
        '''Sets the value of a point o  the devcie'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.default_value]}
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)
        result = self.vip.rpc.call('radiothermostat', 'set_point',
                                       self.target_address,point_map,value).get()
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
            point_map[register.point_name] = [register.default_value]
        result = self.vip.rpc.call('radiothermostat', 'get_point',
                                       self.target_address,point_map).get()
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
            units = regDef['Units']
            default_value = regDef['Default']
            register = Register(
                                read_only,
                                point_name,
                                units,
                                default_value)
            self.insert_register(register)
