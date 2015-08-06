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

import abc

class DriverInterfaceError(Exception):
    pass

class BaseRegister(object):
    def __init__(self, register_type, read_only, pointName, units, description = ''):
        self.read_only = read_only
        self.register_type = register_type
        self.point_name = pointName
        self.units = units
        self.description = description
        self.python_type = int
        
    def get_register_python_type(self):
        return self.python_type
    
    def get_register_type(self):
        '''Get (type, read_only) tuple'''
        return self.register_type, self.read_only
    
    def get_units(self):
        return self.units
    
    def get_description(self):
        return self.description
    
class BaseInterface(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, vip=None, **kwargs):
        super(BaseInterface, self).__init__(**kwargs)
        self.vip = vip
        
        self.point_map = {}
        
        self.build_register_map()
        
    def build_register_map(self):
        self.registers = {('byte',True):[],
                          ('byte',False):[],
                          ('bit',True):[],
                          ('bit',False):[]}
     
    @abc.abstractmethod   
    def configure(self, config_dict, registry_config_str):
        pass
        
    def get_register_by_name(self, name):
        try:
            return self.point_map[name]
        except KeyError:
            raise DriverInterfaceError("Point not configured on device: "+name)
    
    def get_register_names(self):
        return self.point_map.keys()
        
    def get_registers_by_type(self, reg_type, read_only):
        return self.registers[reg_type,read_only]
        
    def insert_register(self, register):
        register_point = register.point_name
        self.point_map[register_point] = register
        
        register_type = register.get_register_type()
        self.registers[register_type].append(register)        
        
    @abc.abstractmethod
    def get_point(self, point_name):    
        pass
    
    @abc.abstractmethod
    def set_point(self, point_name, value): 
        pass
    
    @abc.abstractmethod        
    def scrape_all(self):
        """Return a dictionary of point names:values for device"""
        pass