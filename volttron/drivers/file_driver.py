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

import os
import abc
from base import BaseSmapVolttron, BaseInterface, BaseRegister
from csv import DictReader
import struct

path = os.path.dirname(os.path.abspath(__file__))
default_config = os.path.join(path, "example.csv")
default_directory = os.path.dirname(os.path.abspath(__file__))

class FileRegister(BaseRegister):
    __metaclass__ = abc.ABCMeta
    def __init__(self, type_string, read_only, pointName, units, description = '', directory='.'):
        self.file_path = os.path.join(directory, pointName)
        
        #We only use struct to sort out the type of the register.
        self.bit_register = type_string.lower() == 'bool'
        register_type = 'bit' if self.bit_register else 'byte'
        
        super(FileRegister, self).__init__(register_type, read_only, pointName, units, description = '')
        
        if self.bit_register:
            self.python_type = int
        else:
            try:
                self.parse_struct = struct.Struct(type_string)
            except struct.error:
                raise ValueError("Invalid Register '" + type_string + "' for point " + pointName)
            
            struct_types = [type(x) for x in self.parse_struct.unpack('\x00'*self.parse_struct.size)]
            
            if len(struct_types) != 1:
                raise ValueError("Invalid length Register '" + type_string + "' for point " + pointName)
            
            self.python_type = struct_types[0]
    
    def parse_value(self, value_string):
        return self.python_type(value_string)
    
    def get_value(self):
        try:
            with open(self.file_path) as f:
                return self.parse_value(f.read())
        except (ValueError, IOError):
            #Build up default files.
            value = self.parse_value('0')
            print "Creating default file for point: ", self.point_name
            with open(self.file_path, 'w') as f:
                f.write(str(value))
            return value
    
    def set_value(self, value):
        self.value = value
        with open(self.file_path, 'w') as f:
            f.write(str(value))
        return value
    
class FileInterface(BaseInterface): 
    def __init__(self, directory=default_directory, config_file=default_config, **kwargs):
        super(FileInterface, self).__init__(**kwargs)
        self.parse_config(directory, config_file)
    
    def parse_config(self, directory, config_file):
        if config_file is None:
            return
        
        with open(config_file, 'rb') as f:
            configDict = DictReader(f)
            
            for regDef in configDict:
                #Skip lines that have no address yet.
                if not regDef['Point Name']:
                    continue
                
                io_type = regDef['Modbus Register']
                read_only = regDef['Writable'].lower() != 'true'
                point_path = regDef['PNNL Point Name']        
                description = regDef['Notes']                 
                units = regDef['Units']         
                register = FileRegister(io_type, read_only, point_path, units, description = description, directory=directory)
                    
                self.insert_register(register)
                
    #Getting data in a async manner
    def get_point_async(self, point_name):    
        return self.get_point_sync(point_name)
    
    #setting data in a async manner
    def set_point_async(self, point_name, value): 
        return self.set_point_sync(point_name, value)
    
    #Getting data in a sync manner
    def get_point_sync(self, point_name):    
        register = self.point_map[point_name]
        return register.get_value()
    
    #setting data in a sync manner
    def set_point_sync(self, point_name, value): 
        register = self.point_map[point_name]
        return register.set_value(value)
    
    def scrape_all(self):
        result_dict={}
        try:            
            for point in self.point_map:
                result_dict[point]=self.get_point_sync(point)
        except (IOError):
            print ("ERROR: Failed to scrape device at " + 
                   self.ip_address + ":" + str(self.port) + " " + 
                   "ID: " + str(self.slave_id))
            return None
        
        return result_dict

class File(BaseSmapVolttron):
    """
    Fake device backed by a file for each register. 
    Designed to use the modbus configuration file for setup.
    """     
    def setup(self, opts):
        super(File, self).setup(opts)
        self.set_metadata('/', {'Instrument/Manufacturer' : 'Pacific Northwest National Labratory',
                                'Extra/Driver' : 'volttron.drivers.file_driver.File'})
        
    def get_interface(self, opts):
        directory = opts.get('directory', default_directory)
        config_file = opts.get('register_config', default_config)
        
        return FileInterface(directory=directory, config_file=config_file)