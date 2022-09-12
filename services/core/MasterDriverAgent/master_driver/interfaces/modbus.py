# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import struct
import logging

from gevent import monkey
monkey.patch_socket()

from pymodbus.client.sync import ModbusTcpClient as SyncModbusClient  
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse
from pymodbus.constants import Defaults

from contextlib import contextmanager, closing

from master_driver.driver_locks import socket_lock
from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert, DriverInterfaceError
from volttron.platform.agent import utils

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


class ModbusInterfaceException(ModbusException):
    pass


class ModbusRegisterBase(BaseRegister):
    def __init__(self, address, register_type, read_only, pointName, units, description='', slave_id=0):
        super(ModbusRegisterBase, self).__init__(register_type, read_only, pointName, units, description=description)
        self.address = address
        self.slave_id = slave_id


class ModbusBitRegister(ModbusRegisterBase):
    def __init__(self, address, type_string, pointName, units, read_only, mixed_endian=False, description='',
                 slave_id=0):
        super(ModbusBitRegister, self).__init__(address, "bit", read_only, pointName, units, description=description,
                                                slave_id=slave_id)
        
        self.python_type = bool
    
    def parse_value(self, starting_address, bit_stream):
        # find the bytes we care about
        index = (self.address - starting_address)        
        return bit_stream[index]
    
    def get_register_count(self):
        return 1
    
    def get_state(self, client):
        response_bits = client.read_discrete_inputs(self.address, unit=self.slave_id) if self.read_only else \
            client.read_coils(self.address, unit=self.slave_id)
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
    def __init__(self, address, type_string, pointName, units, read_only, mixed_endian=False, description='',
                 slave_id=0):
        super(ModbusByteRegister, self).__init__(address, "byte", read_only, pointName, units, description=description,
                                                 slave_id=slave_id)
        
        try:
            self.parse_struct = struct.Struct(type_string)
        except struct.error:
            raise ValueError("Invalid Modbus Register '" + type_string + "' for point " + pointName)
        
        struct_types = [type(x) for x in self.parse_struct.unpack(b'\x00'*self.parse_struct.size)]
        
        if len(struct_types) != 1:
            raise ValueError("Invalid length Modbus Register '" + type_string + "' for point " + pointName)
        
        self.python_type = struct_types[0]

        self.mixed_endian = mixed_endian
        
    def get_register_count(self):        
        return self.parse_struct.size // MODBUS_REGISTER_SIZE
    
    def parse_value(self, starting_address, byte_stream):
        # find the bytes we care about
        index = (self.address - starting_address) * 2
        width = self.parse_struct.size
        
        target_bytes = byte_stream[index:index+width]
        if len(target_bytes) < width:
            raise ValueError('Not enough data to parse')

        if self.mixed_endian:
            register_values = []
            for i in range(0, len(target_bytes), PYMODBUS_REGISTER_STRUCT.size):
                register_values.extend(PYMODBUS_REGISTER_STRUCT.unpack_from(target_bytes, i))
            register_values.reverse()

            target_bytes = ""
            target_bytes = bytes.join(b'', [PYMODBUS_REGISTER_STRUCT.pack(value) for value in register_values])
            # for value in register_values:
            #     target_bytes += PYMODBUS_REGISTER_STRUCT.pack(value).decode('utf-8')
        
        return self.parse_struct.unpack(target_bytes)[0]

    def get_state(self, client):
        if self.read_only:
            response = client.read_input_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
        else:
            response = client.read_holding_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
            
        if response is None:
            raise ModbusInterfaceException("pymodbus returned None")

        if self.mixed_endian:
            response.registers.reverse()
            
        response_bytes = response.encode()
        # skip the result count
        return self.parse_struct.unpack(response_bytes[1:])[0]

    def set_state(self, client, value):
        if not self.read_only:
            value_bytes = self.parse_struct.pack(value)
            register_values = []
            for i in range(0, len(value_bytes), PYMODBUS_REGISTER_STRUCT.size):
                register_values.extend(PYMODBUS_REGISTER_STRUCT.unpack_from(value_bytes, i))
            if self.mixed_endian:
                register_values.reverse()
            client.write_registers(self.address, register_values, unit=self.slave_id)
            return self.get_state(client)
        return None
    
        
class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.build_ranges_map()
        
    def configure(self, config_dict, registry_config_str):
        self.slave_id = config_dict.get("slave_id", 0)
        self.ip_address = config_dict["device_address"]
        self.port = config_dict.get("port", Defaults.Port)
        self.parse_config(registry_config_str) 
        
    def build_ranges_map(self):
        self.register_ranges = {('byte', True): [],
                                ('byte', False): [],
                                ('bit', True): [],
                                ('bit', False): []}
        
    def insert_register(self, register):
        super(Interface, self).insert_register(register)

        # MODBUS requires extra bookkeeping.
        register_type = register.get_register_type()
        register_range = self.register_ranges[register_type]
        register_count = register.get_register_count()

        # Store the range of registers for each point.
        start, end = register.address, register.address + register_count - 1
        register_range.append([start, end, [register]])

    def merge_register_ranges(self):
        """
        Merges any adjacent registers for more efficient scraping. May only be called after all registers have been
        inserted."""
        for key, register_ranges in self.register_ranges.items():
            if not register_ranges:
                continue
            register_ranges.sort()
            result = []
            current = register_ranges[0]
            for register_range in register_ranges[1:]:
                if register_range[0] > current[1] + 1:
                    result.append(current)
                    current = register_range
                    continue

                current[1] = register_range[1]
                current[2].extend(register_range[2])

            result.append(current)

            self.register_ranges[key] = result

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
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)

        with modbus_client(self.ip_address, self.port) as client:
            try:
                result = register.set_state(client, value)
            except (ConnectionException, ModbusIOException, ModbusInterfaceException) as ex:
                raise IOError("Error encountered trying to write to point {}: {}".format(point_name, ex))
        return result
    
    def scrape_byte_registers(self, client, read_only):
        result_dict = {}
        register_ranges = self.register_ranges[('byte', read_only)]

        read_func = client.read_input_registers if read_only else client.read_holding_registers

        for register_range in register_ranges:
            start, end, registers = register_range
            result = b''

            for group in range(start, end + 1, MODBUS_READ_MAX):
                count = min(end - group + 1, MODBUS_READ_MAX)
                response = read_func(group, count, unit=self.slave_id)
                if response is None:
                    raise ModbusInterfaceException("pymodbus returned None")
                if isinstance(response, ModbusException):
                    raise response
                response_bytes = response.encode()
                # Trim off length byte.
                result += response_bytes[1:]

            for register in registers:
                point = register.point_name
                value = register.parse_value(start, result)
                result_dict[point] = value

        return result_dict
    
    def scrape_bit_registers(self, client, read_only):
        result_dict = {}
        register_ranges = self.register_ranges[('bit', read_only)]

        for register_range in register_ranges:
            start, end, registers = register_range
            if not registers:
                return result_dict

            result = []

            for group in range(start, end + 1, MODBUS_READ_MAX):
                count = min(end - group + 1, MODBUS_READ_MAX)
                response = client.read_discrete_inputs(group, count, unit=self.slave_id) if read_only else \
                    client.read_coils(group, count, unit=self.slave_id)
                if response is None:
                    raise ModbusInterfaceException("pymodbus returned None")
                if isinstance(response, ModbusException):
                    raise response
                result += response.bits

            for register in registers:
                point = register.point_name
                value = register.parse_value(start, result)
                result_dict[point] = value
            
        return result_dict
        
    def _scrape_all(self):
        result_dict = {}
        with modbus_client(self.ip_address, self.port) as client:
            try:
                
                result_dict.update(self.scrape_byte_registers(client, True))
                result_dict.update(self.scrape_byte_registers(client, False))
                
                result_dict.update(self.scrape_bit_registers(client, True))
                result_dict.update(self.scrape_bit_registers(client, False))
            except (ConnectionException, ModbusIOException, ModbusInterfaceException) as e:
                raise DriverInterfaceError("Failed to scrape device at " + self.ip_address + ":" + str(self.port) +
                                           " ID: " + str(self.slave_id) + str(e))
                
        return result_dict
    
    def parse_config(self, configDict):
        if configDict is None:
            return
        
        for regDef in configDict:
            # Skip lines that have no address yet.
            if not regDef['Volttron Point Name']:
                continue
            
            io_type = regDef['Modbus Register']
            bit_register = io_type.lower() == 'bool'
            read_only = regDef['Writable'].lower() != 'true'
            point_path = regDef['Volttron Point Name']        
            address = int(regDef['Point Address'])        
            description = regDef.get('Notes', '')
            units = regDef['Units']   
            
            default_value = regDef.get("Default Value", '').strip()

            mixed_endian = regDef.get('Mixed Endian', '').strip().lower() == 'true'
                
            klass = ModbusBitRegister if bit_register else ModbusByteRegister
            register = klass(address, io_type, point_path, units, read_only, mixed_endian=mixed_endian,
                             description=description, slave_id=self.slave_id)
            
            self.insert_register(register)
            
            if not read_only:
                if default_value:
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
                            _log.warning("Unable to set default value for {}, bad default value in configuration. "
                                         "Using default revert method.".format(point_path))
                            
                else:
                    _log.info("No default value supplied for point {}. Using default revert method.".format(point_path))

        # Merge adjacent ranges for efficiency.
        self.merge_register_ranges()
