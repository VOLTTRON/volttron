'''
Copyright (c) 2013, Battelle Memorial Institute
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


try:
    import simplejson as json
except ImportError:
    import json
    
from smap import driver, actuate
#from smap.drivers.file import _Actuator, BinaryActuator, ContinuousActuator, DiscreteActuator
from smap.util import periodicSequentialCall

from pymodbus.client.sync import ModbusTcpClient as SyncModbusClient  
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse
from twisted.internet import reactor, protocol
from twisted.python import log
from pymodbus.constants import Defaults
from pymodbus.client.async import ModbusClientProtocol

from base import BaseSmapVolttron, BaseRegister, BaseInterface

import struct
from csv import DictReader
import os.path
import zmq
import datetime

from volttron.platform.agent.base import PublishMixin

from volttron.platform.messaging import headers as headers_mod

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
    
    def get_state_callback(self, response_bits):
        if response_bits is None:
            raise ModbusInterfaceException("pymodbus returned None")
        return response_bits.bits[0]
    
    def get_state_async(self, client):
        d = client.read_discrete_inputs(self.address, unit=self.slave_id) if self.read_only else client.read_coils(self.address, unit=self.slave_id)
        d.addCallback(self.get_state_callback)
        return d    
    
    def get_state_sync(self, client):
        response_bits = client.read_discrete_inputs(self.address, unit=self.slave_id) if self.read_only else client.read_coils(self.address, unit=self.slave_id)
        return self.get_state_callback(response_bits)
    
    def set_state_callback(self, response):
        if response is None:
            raise ModbusInterfaceException("pymodbus returned None")
        if isinstance(response, ExceptionResponse):
            raise ModbusInterfaceException(str(response))
        return response.value
    
    def set_state_sync(self, client, value):
        if not self.read_only:   
            r = client.write_coil(self.address, value, unit=self.slave_id)
            return self.set_state_callback(r)
        return None
    
    def set_state_async(self, client, value):
        if not self.read_only:   
            r = client.write_coil(self.address, value, unit=self.slave_id)
            r.addCallback(self.set_state_callback)
            return r
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
    
    def get_state_callback(self, response):
        if response is None:
            raise ModbusInterfaceException("pymodbus returned None")
        response_bytes = response.encode()
        #skip the result count
        return self.parse_struct.unpack(response_bytes[1:])[0]
    
    def get_state_async(self, client):
        if self.read_only:
            d = client.read_input_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
        else:
            d = client.read_holding_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
        d.addCallback(self.get_state_callback)
        return d  
    
    def get_state_sync(self, client):
        if self.read_only:
            response = client.read_input_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
        else:
            response = client.read_holding_registers(self.address, count=self.get_register_count(), unit=self.slave_id)
            
        return self.get_state_callback(response)
    
    def set_state_sync(self, client, value):
        if not self.read_only:   
            value_bytes = self.parse_struct.pack(value)
            register_values = PYMODBUS_REGISTER_STRUCT.unpack_from(value_bytes)
            client.write_registers(self.address, register_values, unit=self.slave_id)
            return self.get_state_sync(client)
        return None
    
    def set_state_callback(self, value, client):
        return self.get_state_async(client)
    
    def set_state_async(self, client, value):
        if not self.read_only:   
            value_bytes = self.parse_struct.pack(value)
            register_values = PYMODBUS_REGISTER_STRUCT.unpack_from(value_bytes)
            r = client.write_registers(self.address, register_values, unit=self.slave_id)
            r.addCallback(self.set_state_callback, client)
            return r
        return None
        
class ModbusInterface(BaseInterface):
    def __init__(self, ip_address, port=Defaults.Port, slave_id=0, config_file=configFile, **kwargs):
        super(ModbusInterface, self).__init__(**kwargs)
        
        self.slave_id=slave_id
        self.ip_address = ip_address
        self.port = port
        self.build_ranges_map()
        self.parse_config(config_file)
        
    def build_ranges_map(self):
        self.register_ranges = {('byte',True):[None,None],
                                ('byte',False):[None,None],
                                ('bit',True):[None,None],
                                ('bit',False):[None,None]}
        
    def insert_register(self, register):
        super(ModbusInterface, self).insert_register(register)
        
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
        
    #Mostly for testing by hand and initializing actuators.
    def get_point_sync(self, point_name):    
        register = self.point_map[point_name]
        client = SyncModbusClient(self.ip_address, port=self.port)
        try:
            result = register.get_state_sync(client)
        except (ConnectionException, ModbusIOException, ModbusInterfaceException):
            result = None
        finally:
            client.close()
        return result
    
    #Mostly for testing by hand.
    def set_point_sync(self, point_name, value):    
        register = self.point_map[point_name]
        client = SyncModbusClient(self.ip_address, port=self.port)
        result = None
        try:
            result = register.set_state_sync(client, value)
        except (ConnectionException, ModbusIOException, ModbusInterfaceException):
            result = None
        finally:
            client.close()
        return result
    
    def close_async_connection_later(self, client):
        reactor.callLater(5, client.transport.loseConnection)
        return client
    
    #Getting data in a async manner
    def get_point_async(self, point_name):    
        register = self.point_map[point_name]
        d = protocol.ClientCreator(reactor, ModbusClientProtocol).connectTCP(self.ip_address, self.port)
        d.addCallback(self.close_async_connection_later)
        d.addCallback(register.get_state_async)
        return d
    
    #setting data in a async manner
    def set_point_async(self, point_name, value):    
        register = self.point_map[point_name]
        d = protocol.ClientCreator(reactor, ModbusClientProtocol).connectTCP(self.ip_address, self.port)
        d.addCallback(register.set_state_async, value)
        return d
    
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
        
    def scrape_all(self):
        result_dict={}
        try:
            client = SyncModbusClient(self.ip_address, port=self.port)
            
            result_dict.update(self.scrape_byte_registers(client, True))
            result_dict.update(self.scrape_byte_registers(client, False))
            
            result_dict.update(self.scrape_bit_registers(client, True))
            result_dict.update(self.scrape_bit_registers(client, False))
        except (ConnectionException, ModbusIOException, ModbusInterfaceException) as e:
            print ("ERROR: Failed to scrape device at " + 
                   self.ip_address + ":" + str(self.port) + " " + 
                   "ID: " + str(self.slave_id) + str(e))
            return None
        finally:
            client.close()
        
        return result_dict
    
    def parse_config(self, config_file):
        if config_file is None:
            return
        
        with open(config_file, 'rb') as f:
            configDict = DictReader(f)
            
            for regDef in configDict:
                #Skip lines that have no address yet.
                if not regDef['Point Name']:
                    continue
                
                io_type = regDef['Modbus Register']
                bit_register = io_type.lower() == 'bool'
                read_only = regDef['Writable'].lower() != 'true'
                point_path = regDef['PNNL Point Name']        
                address = int(regDef['Point Address'])        
                description = regDef['Notes']                 
                units = regDef['Units']         
                            
                klass = ModbusBitRegister if bit_register else ModbusByteRegister
                register = klass(address, io_type, point_path, units, read_only, description = description, slave_id=self.slave_id)
                    
                self.insert_register(register)

    
class Modbus(BaseSmapVolttron):
    def setup(self, opts):
        super(Modbus, self).setup(opts)
        self.set_metadata('/', {'Extra/Driver' : 'volttron.drivers.modbus.Modbus'})
             
    def get_interface(self, opts):
        ip_address = opts['ip_address']
        slave_id = int(opts.get('slave_id',0))
        port = int(opts.get('port',502))
        catalyst_config = opts.get('register_config', configFile)
        
        return ModbusInterface(ip_address, slave_id=slave_id, port=port, config_file=catalyst_config)

if __name__ == "__main__":
    from pprint import pprint
    iface = ModbusInterface('130.20.3.14')
    r = iface.get_point_sync('ReturnAirCO2')
    print 'ReturnAirCO2', r
    r = iface.get_point_sync('ServiceSwitch')
    print 'ServiceSwitch', r
    r = iface.get_point_sync('ReturnAirCO2Stpt')
    print 'ReturnAirCO2Stpt', r
    r = iface.get_point_sync('DamperSignal')
    print 'DamperSignal', r
    r = iface.get_point_sync('CoolSupplyFanSpeed1')
    print 'CoolSupplyFanSpeed1', r
    r = iface.get_point_sync('ESMMode')
    print 'ESMMode', r
    r = iface.get_point_sync('CoolCall1')
    print 'Occupied', r
    print
    print 'Writing to ESMMode:', True
    r = iface.set_point_sync('ESMMode', True)
    print 'New ESMMode:', r
    print
    print 'Writing to CoolSupplyFanSpeed1:', 65.0
    r = iface.set_point_sync('CoolSupplyFanSpeed1', 65.0)
    print 'New CoolSupplyFanSpeed1', r
    
    r = iface.scrape_all()
    pprint(r)
    
    print 'Getting via async interface'
    print 'ESMMode',
    def printvalue(value):
        print value
    
    d = iface.get_point_async('ESMMode')
    d.addCallback(printvalue)
    reactor.run()

