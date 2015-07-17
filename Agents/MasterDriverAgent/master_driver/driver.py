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
import datetime
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
from zmq.utils import jsonapi
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.topics import (DRIVER_TOPIC_BASE, 
                                                DRIVER_TOPIC_ALL, 
                                                DEVICES_VALUE,
                                                CONFIG_ADD,
                                                CONFIG_REMOVE,
                                                CONFIG_UPDATE)

class DriverAgent(Agent): 
    def __init__(self, parent, **kwargs):             
        super(DriverAgent, self).__init__(**kwargs)
        self.parent = parent
        
    def get_config(self, config_name):
        #Until config store is setup just grab a file.
        return open(config_name, 'rb').read()
            
        
    def get_interface(self, driver_type, config_dict, config_string):
        """Returns an instance of the interface"""
        module_name = "interfaces." + driver_type
        module = __import__(module_name,globals(),locals(),[], -1)
        sub_module = getattr(module, driver_type)
        klass = getattr(sub_module, "Interface")
        interface = klass(vip=self.vip)
        interface.configure(config_dict, config_string)
        return interface
        
    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        self.registry_config_name = None
        self.setup_device()
        
        interval = self.config.get("interval", 60)
        self.core.periodic(interval, self.periodic_read, wait=None)
            
        self.all_path_depth, self.all_path_breadth = self.get_paths_for_point(DRIVER_TOPIC_ALL)


    def setup_device(self):
        #First call to setup_device won't have anything to unsubscribe to.
#         try:
#             self.vip.pubsub.unsubscribe('pubsub', None, None)
#         except KeyError:
#             pass
        
        config = self.get_config(self.core.identity)
        self.config = jsonapi.loads(utils.strip_comments(config))  
        driver_config = self.config["driver_config"] 
        driver_type = self.config["driver_type"] 
        registry_config = self.get_config(self.config["registry_config"]) 
                           
        self.interface = self.get_interface(driver_type, driver_config, registry_config)
        self.meta_data = {}
        
        for point in self.interface.get_register_names():
            register = self.interface.get_register_by_name(point)
            if register.register_type == 'bit':
                ts_type = 'boolean'
            else:
                if register.python_type is int:
                    ts_type = 'integer'
                elif register.python_type is float:
                    ts_type = 'float'
                elif register.python_type is str:
                    ts_type = 'string'
            
            self.meta_data[point] = {'units': register.get_units(),
                                     'type': ts_type,
                                     'tz': self.config['timezone']}
            
        self.base_topic = DEVICES_VALUE(campus=self.config.get('campus', ''), 
                                        building=self.config.get('building', ''), 
                                        unit=self.config.get('unit', ''),
                                        path=self.config.get('path', ''),
                                        point=None)
        
        self.parent.device_startup_callback(self.base_topic, self)
            
        
    def periodic_read(self):
        print "scraping target"
        results = self.interface.scrape_all()
        
        # XXX: Does a warning need to be printed?
        if results is None:
            return

        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
            headers_mod.DATE: now,
        }
            

        for point, value in results.iteritems():
            topics = self.get_paths_for_point(point)
            for topic in topics:
                message = [jsonapi.dumps(value), jsonapi.dumps(self.meta_data[point])] 
                self.vip.pubsub.publish('pubsub', topic, 
                                        headers=headers, 
                                        message=message)
         
        message = [jsonapi.dumps(results), jsonapi.dumps(self.meta_data)] 
        self.vip.pubsub.publish('pubsub', 
                                self.all_path_depth, 
                                headers=headers, 
                                message=message)
         
        self.vip.pubsub.publish('pubsub', 
                                self.all_path_breadth, 
                                headers=headers, 
                                message=message)

    def get_paths_for_point(self, point):
        depth_first = self.base_topic(point=point)
         
        parts = depth_first.split('/')
        breadth_first_parts = parts[1:]
        breadth_first_parts.reverse()
        breadth_first_parts = [DRIVER_TOPIC_BASE] + breadth_first_parts
        breadth_first = '/'.join(breadth_first_parts)
         
        return depth_first, breadth_first 
    
    @RPC.export
    def get_point(self, point_name):
        return self.interface.get_point(point_name)
    
    @RPC.export
    def set_point(self, point_name, value):
        return self.interface.set_point(point_name, value)
