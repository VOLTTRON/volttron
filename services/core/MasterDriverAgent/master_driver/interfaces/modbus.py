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

from gevent import monkey
monkey.patch_socket()

from pymodbus.client.sync import ModbusTcpClient as SyncModbusClient  
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse
from pymodbus.constants import Defaults
from volttron.platform.agent import utils

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert, DriverInterfaceError

import struct
import logging
from csv import DictReader
from StringIO import StringIO
import os.path

from contextlib import contextmanager, closing
from master_driver.driver_locks import socket_lock

@contextmanager
def modbus_client(address, port):
    with socket_lock():
        with closing(SyncModbusClient(address, port)) as client:
            yield client

modbus_logger = logging.getLogger("pymodbus")
modbus_logger.setLevel(logging.WARNING)

utils.setup_logging()
_log = logging.getLogger(__name__)

MODBUS_REGISTER_SIZE = 2
MODBUS_READ_MAX = 100
PYMODBUS_REGISTER_STRUCT = struct.Struct('>H')

path = os.path.dirname(os.path.abspath(__file__))
configFile = os.path.join(path, "example.csv")


class ModbusInterfaceException(ModbusException):
    pass

class ModbusRegisterBase(BaseRegister):
    def __init__(self, address, register_type, read_only, pointName, units, description = '', slave_id=0):
        super(ModbusRegisterBase, self).__init__(register_type, read_only, pointName, units, description = '')
        self.address = address
        self.slave_id = slave_id

class ModbusBitRegister(ModbusRegisterBase):
    def __init__(self, address, type_string, pointName, units, read_only, description = '', slave_id=0):
        super(ModbusBitRegister, self).__init__(address, "bit", read_only, pointName, units, 
                                                description = description, slave_id=slave_id)        
        
        self.python_type = bool
    
    def parse_value(self, starting_address, bit_stream):
        #find the bytes we care about
        index = (self.address - starting_address)        
        return bit_stream[index]
    
    def get_register_count(self):
        return 1
    
    def get_state(self, client):
        response_bits = client.read_discrete_inputs(self.address, unit=self.slave_id) if self.read_only else client.read_coils(self.address, unit=self.slave_id)
        if response_bits is None:
            raise ModbusInterfaceException("pymodbus returned None")
        return response_bits.bits[0]
    
    def set_state(self, client, value):
        if not self.read_only:   
            response = client.write_coil(self.address, value, unit=self.slave_id)
            if response is None:
                raise ModbusInterfaceException("pymodbus returned None")
            if isinstance(response, ExceptionResponse):
                raise ModbusInterfaceException(str(response))
            return response.value
        return None

class ModbusByteRegister(ModbusRegisterBase):
    def __init__(self, address, type_string, pointName, units, read_only, description = '', slave_id=0):
        super(ModbusByteRegister, self).__init__(address, "byte", read_only, 
                                                 pointName, units, description = description, slave_id=slave_id)
        
        try:
            self.parse_struct = struct.Struct(type_string)
        except struct.error:
            raise ValueError("Invalid Modbus Register '" + type_string + "' for point " + pointName)
        
        struct_types = [type(x) for x in self.parse_struct.unpack('\x00'*self.parse_struct.size)]
        
        if len(struct_types) != 1:
            raise ValueError("Invalid length Modbus Register '" + type_string + "' for point " + pointName)
        
        self.python_type = struct_types[0]
        
    def get_register_count(self):        
        return self.parse_struct.size // MODBUS_REGISTER_SIZE
    
    def parse_value(self, starting_address, byte_stream):
        #find the bytes we care about
        index = (self.address - starting_address) * 2
        width = self.parse_struct.size
        
        target_bytes = byte_stream[index:index+width]
        if len(target_bytes) < width:
            raise ValueError('Not enough data to parse')
        
        return self.parse_struct.unpack(target_bytes)[0]
    
   
    def get_state(self, client):
        if self.read_only:
            response = client.read_input_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
        else:
            response = client.read_holding_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
            
        if response is None:
            raise ModbusInterfaceException("pymodbus returned None")
        response_bytes = response.encode()
        #skip the result count
        return self.parse_struct.unpack(response_bytes[1:])[0]
    
    
    def set_state(self, client, value):
        if not self.read_only:   
            value_bytes = self.parse_struct.pack(value)
            register_values = PYMODBUS_REGISTER_STRUCT.unpack_from(value_bytes)
            client.write_registers(self.address, register_values, unit=self.slave_id)
            return self.get_state(client)
        return None
    
        
class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.build_ranges_map()
        
    def configure(self, config_dict, registry_config_str):
        self.slave_id=config_dict.get("slave_id", 0)
        self.ip_address = config_dict["device_address"]
        self.port = config_dict.get("port", Defaults.Port)
        self.parse_config(registry_config_str) 
        
    def build_ranges_map(self):
        self.register_ranges = {('byte',True):[None,None],
                                ('byte',False):[None,None],
                                ('bit',True):[None,None],
                                ('bit',False):[None,None]}
        
    def insert_register(self, register):
        super(Interface, self).insert_register(register)
        
        register_type = register.get_register_type()
        
        register_range = self.register_ranges[register_type]    
        register_count = register.get_register_count()
        
        start, end = register.address, register.address + register_count - 1
        
        if register_range[0] is None:
            register_range[:] = start, end            
        else:
            if register_range[0] > start:
                register_range[0] = start
            if register_range[1] < end:
                register_range[1] = end        
        
    def get_point(self, point_name):    
        register = self.get_register_by_name(point_name)
        with modbus_client(self.ip_address, self.port) as client:
            try:
                result = register.get_state(client)
            except (ConnectionException, ModbusIOException, ModbusInterfaceException):
                result = None
        return result
    
    def _set_point(self, point_name, value):    
        register = self.get_register_by_name(point_name)
        with modbus_client(self.ip_address, self.port) as client:
            try:
                result = register.set_state(client, value)
            except (ConnectionException, ModbusIOException, ModbusInterfaceException):
                result = None
        return result
    
    def scrape_byte_registers(self, client, read_only):
        result_dict = {}
        start, end = self.register_ranges[('byte',read_only)]
        registers = self.registers[('byte',read_only)]
        
        if not registers:
            return result_dict
        
        result = ''
        
        for group in xrange(start, end + 1, MODBUS_READ_MAX):
            count = min(end - group + 1, MODBUS_READ_MAX)            
            response = client.read_input_registers(group, count, unit=self.slave_id) if read_only else client.read_holding_registers(group, count, unit=self.slave_id)
            if response is None:
                raise ModbusInterfaceException("pymodbus returned None")
            response_bytes = response.encode()
            result += response_bytes[1:]
            
        for register in registers:
            point = register.point_name
            value = register.parse_value(start, result)
            result_dict[point] = value
            
        return result_dict
    
    def scrape_bit_registers(self, client, read_only):
        result_dict = {}
        start, end = self.register_ranges[('bit',read_only)]
        registers = self.registers[('bit',read_only)]
        
        if not registers:
            return result_dict
        
        result = []
        
        for group in xrange(start, end + 1, MODBUS_READ_MAX):
            count = min(end - group + 1, MODBUS_READ_MAX)            
            response = client.read_discrete_inputs(group, count, unit=self.slave_id) if read_only else client.read_coils(group, count, unit=self.slave_id)
            if response is None:
                raise ModbusInterfaceException("pymodbus returned None")
            result += response.bits
            
        for register in registers:
            point = register.point_name
            value = register.parse_value(start, result)
            result_dict[point] = value
            
        return result_dict
        
    def _scrape_all(self):
        result_dict={}
        with modbus_client(self.ip_address, self.port) as client:
            try:
                
                result_dict.update(self.scrape_byte_registers(client, True))
                result_dict.update(self.scrape_byte_registers(client, False))
                
                result_dict.update(self.scrape_bit_registers(client, True))
                result_dict.update(self.scrape_bit_registers(client, False))
            except (ConnectionException, ModbusIOException, ModbusInterfaceException) as e:
                raise DriverInterfaceError ("Failed to scrape device at " + 
                           self.ip_address + ":" + str(self.port) + " " + 
                           "ID: " + str(self.slave_id) + str(e))
                
        return result_dict
    
    def parse_config(self, config_string):
        f = StringIO(config_string)
        configDict = DictReader(f)
        
        for regDef in configDict:
            #Skip lines that have no address yet.
            if not regDef['Volttron Point Name']:
                continue
            
            io_type = regDef['Modbus Register']
            bit_register = io_type.lower() == 'bool'
            read_only = regDef['Writable'].lower() != 'true'
            point_path = regDef['Volttron Point Name']        
            address = int(regDef['Point Address'])        
            description = regDef['Notes']                 
            units = regDef['Units']   
            
            default_value = regDef.get("Default Value", '').strip()
            if not default_value:
                default_value = None  
                
            klass = ModbusBitRegister if bit_register else ModbusByteRegister
            register = klass(address, io_type, point_path, units, read_only, description = description, slave_id=self.slave_id)
            
            self.insert_register(register)
            
            if not read_only:
                if default_value is not None:
                    if isinstance(register, ModbusBitRegister):
                        try:
                            value = bool(int(default_value))
                        except ValueError:
                            value = default_value.lower().startswith('t') or default_value.lower() == 'on'
                        self.set_default(point_path, value)
                    else:
                        try:
                            value = register.python_type(default_value)
                            self.set_default(point_path, value)
                        except ValueError:
                            _log.warning("Unable to set default value for {}, "
                            "bad default value in configuration. Using default revert method.".format(point_path))
                            
                else:
                    _log.info("No default value supplied for point {}. Using default revert method.".format(point_path))
                        
                
                
            
