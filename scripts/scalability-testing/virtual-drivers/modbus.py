#!python

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

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
args = parser.parse_args()

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

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
        count = end - start + 1
        
        #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
        # section 4.4 about this nonsense.
        start += 1 
        print "bit", True, start, count
        di = ModbusSequentialDataBlock(start, [0]*count)
        
        start, end = self.register_ranges[('bit',False)]
        count = end - start + 1
        
        #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
        # section 4.4 about this nonsense.
        start += 1 
        print "bit", False, start, count
        co = ModbusSequentialDataBlock(start, [0]*count)
        
        start, end = self.register_ranges[('byte',True)]
        count = end - start + 1
        
        #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
        # section 4.4 about this nonsense.
        start += 1 
        print "byte", True, start, count
        ir = ModbusSequentialDataBlock(start, [0]*count)
        
        start, end = self.register_ranges[('byte',False)]
        count = end - start + 1
        
        #See http://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
        # section 4.4 about this nonsense.
        start += 1 
        print "byte", False, start, count
        hr = ModbusSequentialDataBlock(start, [0]*count)
        
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
