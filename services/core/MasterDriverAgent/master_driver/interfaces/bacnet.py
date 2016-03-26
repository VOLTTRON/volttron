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

from master_driver.interfaces import BaseInterface, BaseRegister
from csv import DictReader
from StringIO import StringIO
import logging

from master_driver.driver_exceptions import DriverConfigError

#Logging is completely configured by now.
_log = logging.getLogger(__name__)

class Register(BaseRegister):
    def __init__(self, instance_number, object_type, property_name, read_only, pointName, units, 
                 description = '',
                 priority = None,
                 list_index = None):
        super(Register, self).__init__("byte", read_only, pointName, units, description = '')
        self.instance_number = int(instance_number)
        self.object_type = object_type
        self.property = property_name
        self.priority = priority
        self.index = list_index

        
class Interface(BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        
    def configure(self, config_dict, registry_config_str):
        self.min_priority = config_dict.get("min_priority", 8)
        self.parse_config(registry_config_str)         
        self.target_address = config_dict["device_address"]
        self.proxy_address = config_dict.get("proxy_address", "platform.bacnet_proxy")
        self.max_per_request = config_dict.get("max_per_request")        
        self.ping_target(self.target_address)
                                         
    def ping_target(self, address):    
        #Some devices (mostly RemoteStation addresses behind routers) will not be reachable without 
        # first establishing the route to the device. Sending a directed WhoIsRequest is will
        # settle that for us when the response comes back. 
        return self.vip.rpc.call(self.proxy_address, 'ping_device', self.target_address).get(timeout=10.0)
        
    def get_point(self, point_name, get_priority_array=False): 
        register = self.get_register_by_name(point_name)   
        my_property = "priorityArray" if get_priority_array else register.property
        point_map = {point_name:[register.object_type, 
                                 register.instance_number, 
                                 my_property]}
        result = self.vip.rpc.call(self.proxy_address, 'read_properties', 
                                       self.target_address, point_map).get(timeout=10.0)
        return result[point_name]
    
    def set_point(self, point_name, value, priority=None):    
        #TODO: support writing from an array.
        register = self.get_register_by_name(point_name)  
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)
        
        if priority is not None and priority < self.min_priority:
            raise  IOError("Trying to write with a priority lower than the minimum of "+str(self.min_priority))
        
        #We've already validated the register priority against the min priority.
        args = [self.target_address, value,
                register.object_type, 
                register.instance_number, 
                register.property,
                priority if priority is not None else register.priority]
        result = self.vip.rpc.call(self.proxy_address, 'write_property', *args).get(timeout=10.0)
        return result
        
    def scrape_all(self):
        #TODO: support reading from an array.
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False) 
        for register in read_registers + write_registers:             
            point_map[register.point_name] = [register.object_type, 
                                              register.instance_number, 
                                              register.property]
        
        result = self.vip.rpc.call(self.proxy_address, 'read_properties', 
                                       self.target_address, point_map,
                                       self.max_per_request).get(timeout=10.0)
        return result
    
    def revert_all(self, priority=None):
        """Revert entrire device to it's default state"""
        #TODO: Add multipoint write support
        write_registers = self.get_registers_by_type("byte", False) 
        for register in write_registers:             
            self.revert_point(register.point_name, priority=priority)
    
    def revert_point(self, point_name, priority=None):
        """Revert point to it's default state"""
        self.set_point(point_name, None, priority=priority)
        
    
    def parse_config(self, config_string):
        if config_string is None:
            return
        
        f = StringIO(config_string)
        
        configDict = DictReader(f)
        
        for regDef in configDict:
            #Skip lines that have no address yet.
#             if not regDef['Point Name']:
#                 continue
            
            io_type = regDef['BACnet Object Type']
            read_only = regDef['Writable'].lower() != 'true'
            point_name = regDef['Volttron Point Name']        
            index = int(regDef['Index'])   
                
            list_index = regDef.get('Array Index', '')
            list_index = list_index.strip()
            if not list_index:
                list_index = None
            else:
                list_index = int(list_index) 
                
            priority = regDef.get('Write Priority', '')
            priority = priority.strip()
            if not priority:
                priority = None
            else:
                priority = int(priority) 
                
                if priority < self.min_priority:
                    message = "{point} configured with a priority {priority} which is lower than than minimum {min}."
                    raise DriverConfigError(message.format(point=point_name,
                                                           priority=priority,
                                                           min=self.min_priority))
                
            description = regDef.get('Notes', '')                 
            units = regDef['Units']       
            property_name = regDef['Property']       
                        
            register = Register(index, 
                                io_type, 
                                property_name, 
                                read_only, 
                                point_name,
                                units, 
                                description = description,
                                priority = priority,
                                list_index = list_index)
                
            self.insert_register(register)
