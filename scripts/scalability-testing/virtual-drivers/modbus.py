#!python

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

#This is based on example code from the pymodbus source.

#---------------------------------------------------------------------------# 
# import the various server implementations
#---------------------------------------------------------------------------# 
from pymodbus.server.sync import StartTcpServer

from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.pdu import ModbusPDU

from csv import DictReader

#---------------------------------------------------------------------------# 
# configure the service logging
#---------------------------------------------------------------------------# 


import argparse
import struct
import logging

from utils import createDaemon

parser = argparse.ArgumentParser(description='Run a test pymodbus driver')
parser.add_argument('config', help='device registry configuration')
parser.add_argument('interface', help='interface address')
parser.add_argument('--port', default=5020, type=int, help='port for device to listen on')
parser.add_argument('--no-daemon', help='do not create a daemon process', action='store_true')
parser.add_argument('--debug-output', help='Get info about values written to and read from registers', action='store_true')
args = parser.parse_args()

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG if args.debug_output else logging.INFO)

modbus_logger = logging.getLogger("pymodbus")
modbus_logger.setLevel(logging.WARNING)

MODBUS_REGISTER_SIZE = 2

class Register(object):
    def __init__(self, address, register_type, read_only, register_struct=''):
        self.read_only = read_only
        self.register_type = register_type
        self.address = address
        
        if register_type == "byte":
            self.parse_struct = struct.Struct(register_struct)
            self.register_count = self.parse_struct.size // MODBUS_REGISTER_SIZE
        else:
            self.register_count = 1
    
    def get_register_type(self):
        '''Get (type, read_only) tuple'''
        return self.register_type, self.read_only


def log_callback(address, values):
    log.debug("Address: {} Values: {}".format(address, [hex(v) for v in values]))

class CallbackSequentialDataBlock(ModbusSequentialDataBlock):
    ''' A datablock that stores the new value in memory
    and passes the operation to a message queue for further
    processing.
    '''

    def __init__(self, callback, *args, **kwargs):
        '''
        '''
        super(CallbackSequentialDataBlock, self).__init__(*args, **kwargs)
        self.callback = callback

    def setValues(self, address, values):
        ''' Sets the requested values of the datastore

        :param address: The starting address
        :param values: The new values to be set
        '''
        super(CallbackSequentialDataBlock, self).setValues(address, values)
        self.callback(address, values)

    def getValues(self, address, count=1):
        ''' Sets the requested values of the datastore

        :param address: The starting address
        :param values: The new values to be set
        '''
        results = super(CallbackSequentialDataBlock, self).getValues(address, count)
        self.callback(address, results)
        return results


class DeviceAbstraction(object):
    def __init__(self, config_file):
        self.build_register_map()
        self.build_ranges_map()
        self.parse_config(config_file)
        
    def build_register_map(self):
        self.registers = {('byte',True):[],
                          ('byte',False):[],
                          ('bit',True):[],
                          ('bit',False):[]}
        
    def build_ranges_map(self):
        self.register_ranges = {('byte',True):[None,None],
                                ('byte',False):[None,None],
                                ('bit',True):[None,None],
                                ('bit',False):[None,None]}
        
    def insert_register(self, register):        
        register_type = register.get_register_type()
        self.registers[register_type].append(register) 
        
        register_type = register.get_register_type()
        
        register_range = self.register_ranges[register_type]    
        register_count = register.register_count
        
        start, end = register.address, register.address + register_count - 1
        
        if register_range[0] is None:
            register_range[:] = start, end            
        else:
            if register_range[0] > start:
                register_range[0] = start
            if register_range[1] < end:
                register_range[1] = end   
                
    def parse_config(self, config_file):
        with open(config_file, 'rb') as f:
            configDict = DictReader(f)
            
            for regDef in configDict:            
                io_type = regDef['Modbus Register']
                bit_register = io_type.lower() == 'bool'
                read_only = regDef['Writable'].lower() != 'true'  
                address = int(regDef['Point Address'])       
                            
                register_type = 'bit' if bit_register else 'byte'
                register = Register(address, register_type, read_only, io_type)
                    
                self.insert_register(register)
                
    
    def get_server_context(self):        
        start, end = self.register_ranges[('bit',True)]
        if start is None:
            di = None
        else:
            count = end - start + 1
        
            #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
            # section 4.4 about this nonsense.
            start += 1
            log.debug( "{} Read only: {} Address: {} Count: {}".format("bit", True, start, count))
            di = CallbackSequentialDataBlock(log_callback, start, [0]*count)

        start, end = self.register_ranges[('bit',False)]
        if start is None:
            co = None
        else:
            count = end - start + 1
        
            #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
            # section 4.4 about this nonsense.
            start += 1
            log.debug("{} Read only: {} Address: {} Count: {}".format("bit", False, start, count))
            co = CallbackSequentialDataBlock(log_callback, start, [0]*count)
        
        start, end = self.register_ranges[('byte',True)]
        if start is None:
            ir = None
        else:
            count = end - start + 1
        
            #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
            # section 4.4 about this nonsense.
            start += 1
            log.debug("{} Read only: {} Address: {} Count: {}".format("byte", True, start, count))
            ir = CallbackSequentialDataBlock(log_callback, start, [0]*count)
        
        start, end = self.register_ranges[('byte',False)]
        if start is None:
            hr = None
        else:
            count = end - start + 1
        
            #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
            # section 4.4 about this nonsense.
            start += 1
            log.debug("{} Read only: {} Address: {} Count: {}".format("byte", False, start, count))
            hr = CallbackSequentialDataBlock(log_callback, start, [0]*count)
        
        store = ModbusSlaveContext(
            di = di,
            co = co,
            hr = hr,
            ir = ir)
        context = ModbusServerContext(slaves=store, single=True)
        
        return context  


#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
# If you don't set this or any fields, they are defaulted to empty strings.
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'VOLTTRON'
identity.ProductCode = 'VT'
identity.VendorUrl   = 'http://github.com/VOLTTRON/volttron'
identity.ProductName = 'VOLTTRON Modbus Test Device'
identity.ModelName   = 'VOLTTRON Modbus Test Device'
identity.MajorMinorRevision = '1.0'

abstraction = DeviceAbstraction(args.config)

#Create the deamon as soon as we've loaded the device configuration.
if not args.no_daemon:
    createDaemon()
    
context = abstraction.get_server_context()

#---------------------------------------------------------------------------# 
# run the server you want
#---------------------------------------------------------------------------# 
StartTcpServer(context, identity=identity, address=(args.interface, args.port))
