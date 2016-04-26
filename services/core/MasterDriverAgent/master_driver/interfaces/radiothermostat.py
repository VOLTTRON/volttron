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
        self.parse_config(registry_config_str)
        self.target_address = config_dict["device_address"]
        self.ping_target(self.target_address)
        url = config_dict["device_url"]
        self.thermostat = thermostat_api.ThermostatInterface(url)


    def get_point(self, point_name):
        '''Returns the value of a point on the device'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.default_value]}
        # result = self.vip.rpc.call('radiothermostat', 'get_point',
        #                                self.target_address,point_map).get()
        result = self._get_point(self.target_address,point_map)
        return str(result)


    def set_point(self, point_name, value):
        '''Sets the value of a point o  the devcie'''
        register = self.get_register_by_name(point_name)
        point_map = {}
        point_map = {point_name:[register.default_value]}
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
        for point_name, properties in point_map.iteritems():

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
            elif point_name == "tstat_cool_sp":
                result = self.thermostat.t_cool(value)
            elif point_name == "tstat_heat_sp":
                result = self.thermostat.t_heat(value)
            elif point_name == 'energy_led':
                result = self.thermostat.energy_led(value)
            else:
                _log.debug("No such writable point found")
        return (str(result))



    def _get_point(self, device, point_map):
        '''
            Get value of a point_name on a device
        '''
        result = {}
        query = {}
        point_map_obj = {}
        for point_name, properties in point_map.iteritems():
            query = json.loads(self.thermostat.tstat())
            if point_name in self.query_point_name:
                try:
                    db = query[self.point_name_map[point_name]]
                    result.update({point_name : str(db) })
                except:
                    result.update({point_name : str("NA") })
            else:
                pgm,day = point_name.rsplit('_',1)
                if pgm == 'heat_pgm':
                    if day == 'week':
                        query = self.thermostat.get_heat_pgm()
                        result.update({point_name : str(query)})
                    else:
                        query = self.thermostat.get_heat_pgm(day)
                        result.update({point_name : str(query)})
                elif pgm == 'cool_pgm':
                    if day == 'week':
                        query = self.thermostat.get_cool_pgm()
                        result.update({point_name : str(query)})
                    else:
                        query = self.thermostat.get_cool_pgm(day)
                        result.update({point_name : str(query)})
        return str(result)


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
            units = regDef['Units']
            default_value = regDef['Default']
            register = Register(
                                read_only,
                                point_name,
                                units,
                                default_value)
            self.insert_register(register)
