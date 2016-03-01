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

import abc
import logging

_log = logging.getLogger(__name__)

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
    def get_point(self, point_name, **kwargs):    
        pass
    
    @abc.abstractmethod
    def set_point(self, point_name, value, **kwargs): 
        pass
    
    @abc.abstractmethod        
    def scrape_all(self):
        """Return a dictionary of point names:values for device"""
        pass
    
    @abc.abstractmethod        
    def revert_all(self, **kwargs):
        """Revert entrire device to it's default state"""
        pass
    
    @abc.abstractmethod        
    def revert_point(self, point_name, **kwargs):
        """Revert point to it's default state"""
        pass
    

#Used to track how to revert values on a device.
#Choose not to integrate this into BaseRegister as some
# interfaces (BACnet) have no use for it and it would clutter
# up the interface needlessly. 
class RevertTracker(object):
    def __init__(self):
        self.defaults = {}
        self.clean_values = {}
        self.dirty_points = set()
    
    def update_clean_values(self, points):
        clean_values = {}
        for k, v in points.iteritems():
            if k not in self.dirty_points and k not in self.defaults:
                clean_values[k] = v
        self.clean_values.update(clean_values)
        
    def set_default(self, point, value):
        self.defaults[point] = value
        
    def get_revert_value(self, point):
        """Gets the value to revert the point to."""
        if point in self.defaults:
            return self.defaults[point]
        if point not in self.clean_values:
            raise DriverInterfaceError("Nothing to revert to for {}".format(point))
        
        return self.clean_values[point]
        
    def clear_dirty_point(self, point):   
        self.dirty_points.discard(point)
        
    def mark_dirty_point(self, point):
        if point not in self.defaults:
            self.dirty_points.add(point)
        
    def get_all_revert_values(self):
        results = {}
        for point in self.dirty_points.union(self.defaults):
            try:
                results[point] = self.get_revert_value(point)
            except DriverInterfaceError:
                results[point] = DriverInterfaceError()
            
        return results
    
class BasicRevert(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, **kwargs):
        super(BasicRevert, self).__init__(**kwargs)
        self._tracker = RevertTracker()
        
    def _update_clean_values(self, points):
        self._tracker.update_clean_values(points)
    
    def set_default(self, point, value):    
        self._tracker.set_default(point, value)
        
    
    def set_point(self, point_name, value):
        result = self._set_point(point_name, value)        
        self._tracker.mark_dirty_point(point_name)
        return result
    
    def scrape_all(self):
        result = self._scrape_all()   
        self._update_clean_values(result)

        return result
    
    @abc.abstractmethod    
    def _set_point(self, point_name, value):
        pass
    
    @abc.abstractmethod    
    def _scrape_all(self):
        pass    
    
         
    def revert_all(self, **kwargs):
        """Revert entrire device to it's default state"""
        points = self._tracker.get_all_revert_values()
        for point_name, value in points.iteritems():
            if not isinstance(value, DriverInterfaceError):
                try:
                    self._set_point(point_name, value)
                    self._tracker.clear_dirty_point(point_name)
                except Exception as e:
                    _log.warning("Error while reverting point {}: {}".format(point_name, str(e)))
                
          
    def revert_point(self, point_name, **kwargs):
        """Revert point to it's default state"""
        try:
            value = self._tracker.get_revert_value(point_name)
        except DriverInterfaceError:
            return
        
        _log.debug("Reverting {} to {}".format(point_name, value))
        
        self._set_point(point_name, value)   
        self._tracker.clear_dirty_point(point_name) 
        
        
        