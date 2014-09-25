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
    
from smap import driver, actuate, core
#from smap.drivers.file import _Actuator, BinaryActuator, ContinuousActuator, DiscreteActuator
from smap.util import periodicSequentialCall

import zmq
import datetime

from volttron.platform.agent.base import PublishMixin

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.topics import DRIVER_TOPIC_BASE

import abc
import os

from twisted.internet.defer import maybeDeferred

#Addresses agents use to setup the pub/sub
default_publish_address = 'ipc://$VOLTTRON_HOME/run/no-publisher'
if 'AGENT_PUB_ADDR' in os.environ:
    default_publish_address = os.environ['AGENT_PUB_ADDR'] 
# 'ipc://$VOLTTRON_HOME/run/publish'

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
    def __init__(self, **kwargs):
        super(BaseInterface, self).__init__(**kwargs)
        
        self.point_map = {}
        
        self.build_register_map()
        
    def build_register_map(self):
        self.registers = {('byte',True):[],
                          ('byte',False):[],
                          ('bit',True):[],
                          ('bit',False):[]}
        
    def get_register_by_name(self, name):
        return self.point_map[name]
    
    def get_register_names(self):
        return self.point_map.keys()
        
    def get_registers_by_type(self, reg_type, read_only):
        return self.registers[reg_type,read_only]
        
    def insert_register(self, register):
        register_point = register.point_name
        self.point_map[register_point] = register
        
        register_type = register.get_register_type()
        self.registers[register_type].append(register)        
        
    #Mostly for testing by hand and initializing actuators.
    @abc.abstractmethod
    def get_point_sync(self, point_name):
        pass
    
    #Mostly for testing by hand.
    @abc.abstractmethod
    def set_point_sync(self, point_name, value):
        pass
    
    #Getting data in a async manner
    @abc.abstractmethod
    def get_point_async(self, point_name):    
        pass
    
    #setting data in a async manner
    @abc.abstractmethod
    def set_point_async(self, point_name, value): 
        pass
    
    @abc.abstractmethod        
    def scrape_all(self):
        """Should return either a dictionary of point names:values
        Alternatively it can return a deferred that will produce the same thing."""
        pass

class InterfaceBitActuator(actuate.BinaryActuator):
    """
    Actuator that uses the Modbus interface to touch points 
    """
    def setup(self, opts):
        super(InterfaceBitActuator, self).setup(opts)
        self.point_name = opts['point_name']
        self.interface = opts['interface']
        

    def get_state(self, request):
        return self.interface.get_point_async(self.point_name)
        
    # @authenticated(['__has_ssl__'])
    def set_state(self, request, state):
        return self.interface.set_point_async(self.point_name, state)
        
class InterfaceIntActuator(actuate.IntegerActuator):
    """
    Actuator that uses the Modbus interface to touch points 
    """
    def setup(self, opts):
        super(InterfaceIntActuator, self).setup(opts)
        self.point_name = opts['point_name']
        self.interface = opts['interface']
        

    def get_state(self, request):
        return self.interface.get_point_async(self.point_name)
        
    # @authenticated(['__has_ssl__'])
    def set_state(self, request, state):
        return self.interface.set_point_async(self.point_name, state)
        
class InterfaceFloatActuator(actuate.IntegerActuator):
    """
    Actuator that uses the Modbus interface to touch points 
    """
    ACTUATE_MODEL = 'continuous'
    def valid_state(self, state):
        try:
            float(state)
            return True
        except:
            return False

    def parse_state(self, state):
        return float(state)
    
    def setup(self, opts):
        super(InterfaceFloatActuator, self).setup(opts)
        self.point_name = opts['point_name']
        self.interface = opts['interface']
        
    def get_state(self, request):
        return self.interface.get_point_async(self.point_name)
        
    # @authenticated(['__has_ssl__'])
    def set_state(self, request, state):
        return self.interface.set_point_async(self.point_name, state)
        
class BaseSmapVolttron(driver.SmapDriver, PublishMixin):     
    __metaclass__ = abc.ABCMeta
    
    def setup(self, opts):
        self.interval = float(opts.get('interval',60))
        self.set_metadata('/', {'Instrument/SamplingPeriod' : str(self.interval)})
          
        self.add_collection('/actuators')
        
        publish_address = opts.get('publish_address', default_publish_address)
        
        PublishMixin._setup(self, publish_address)
        
        self.interface = self.get_interface(opts)
         
        self.all_path_depth, self.all_path_breadth = self.get_paths_for_point('/all')
        
        for point in self.interface.get_register_names():
            register = self.interface.get_register_by_name(point)
            if register.register_type == 'bit':
                data_type = 'long'
            else:
                if register.python_type is int:
                    data_type = 'long'
                elif register.python_type is float:
                    data_type = 'double'
                else:
                    raise ValueError('sMAP currently only supports int and float based data types.')
            self.add_timeseries('/'+point, register.units, data_type=data_type, description=register.description)
             
        for register in self.interface.get_registers_by_type('bit',False):
            point = register.point_name
            
            actuator_point = '/actuators/'+point
            
            print 'Setting up actuator point:', actuator_point
            
            a = self.add_actuator(actuator_point, register.units, InterfaceBitActuator, 
                              setup={'point_name':point, 'interface': self.interface}) #, read_limit=1.0, write_limit=1.0)
            
            value = self.interface.get_point_sync(point)
            if value is None:
                print("ERROR: Failed to read " + actuator_point + " interface returned None")
            else:
                self.add(actuator_point, value)
            
            
        for register in self.interface.get_registers_by_type('byte',False):
            point = register.point_name
            actuator_point = '/actuators/'+point
            
            print 'Setting up actuator point:', actuator_point
            
            if register.python_type is int:
                act_class, data_type = (InterfaceIntActuator, 'long')
            elif register.python_type is float:
                act_class, data_type = (InterfaceFloatActuator, 'double')
            else:
                raise ValueError('sMAP currently only supports int and float based data types.')
                        
            a = self.add_actuator(actuator_point, register.units, act_class, 
                              setup={'point_name':point, 'interface': self.interface},
                              data_type=data_type) #, read_limit=1.0, write_limit=1.0)
            
        
            value = self.interface.get_point_sync(point)
            if value is not None:
                self.add(actuator_point, value)
            else:
                print("ERROR: Failed to read " + actuator_point + " interface returned None")
        
    @abc.abstractmethod
    def get_interface(self, opts):
        pass
    
    def start(self):
        # Call read every minute seconds
        periodicSequentialCall(self.read).start(self.interval)
        
    def read_callback(self, results):
        # XXX: Does a warning need to be printed?
        if results is None:
            return

        now = str(datetime.datetime.utcnow())
        
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
            headers_mod.DATE: now,
        }
         
        for point, value in results.iteritems():
            if isinstance(value, bool):
                value = int(value)
            self.add('/'+point, value)
            
        try:    
            for point, value in results.iteritems():
                if isinstance(value, bool):
                    value = int(value)
                depth, breadth = self.get_paths_for_point('/'+point)
                self.publish_json(depth, headers, value, flags=zmq.NOBLOCK)
                self.publish_json(breadth, headers, value, flags=zmq.NOBLOCK)
                
            self.publish_json(self.all_path_depth, headers, results, flags=zmq.NOBLOCK)
            self.publish_json(self.all_path_breadth, headers, results, flags=zmq.NOBLOCK)
        except zmq.error.Again:
            print ("Warning: platform not running, topics not published. (Data to smap historian is unaffected by this warning)")

    
    def read_errback(self, failure):
        print "Data scrape failed:", str(failure)
        return failure
 
    def read(self):
        d = maybeDeferred(self.interface.scrape_all)
        d.addCallbacks(self.read_callback, self.read_errback)
        
        
    def get_paths_for_point(self, point):
        depth_first = DRIVER_TOPIC_BASE + self._SmapDriver__join_id(point)
         
        parts = depth_first.split('/')
        breadth_first_parts = parts[1:]
        breadth_first_parts.reverse()
        breadth_first_parts = [DRIVER_TOPIC_BASE] + breadth_first_parts
        breadth_first = '/'.join(breadth_first_parts)
         
        return depth_first, breadth_first
