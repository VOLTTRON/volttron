# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
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

import datetime
from volttron.platform.vip.agent import BasicAgent, Core
from volttron.platform.agent import utils
from zmq.utils import jsonapi
import logging
import sys
import random
import gevent
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.topics import (DRIVER_TOPIC_BASE, 
                                                DRIVER_TOPIC_ALL, 
                                                DEVICES_VALUE,
                                                DEVICES_PATH)

from volttron.platform.vip.agent.errors import VIPError, Again
from driver_locks import publish_lock

utils.setup_logging()
_log = logging.getLogger(__name__)


class DriverAgent(BasicAgent): 
    def __init__(self, parent, config_name, **kwargs):             
        super(DriverAgent, self).__init__(**kwargs)
        self.heart_beat_value = 0
        self.device_name = ''
        #Use the parent's vip connection
        self.parent = parent
        self.vip = parent.vip
        self.config_name = config_name
        
    def get_config(self, config_name):
        #Until config store is setup just grab a file.
        return open(config_name, 'rb').read()
            
        
    def get_interface(self, driver_type, config_dict, config_string):
        """Returns an instance of the interface"""
        module_name = "interfaces." + driver_type
        module = __import__(module_name,globals(),locals(),[], -1)
        sub_module = getattr(module, driver_type)
        klass = getattr(sub_module, "Interface")
        interface = klass(vip=self.vip, core=self.core)
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
        
        config_str = self.get_config(self.config_name)
        self.config = config = jsonapi.loads(utils.strip_comments(config_str))  
        driver_config = config["driver_config"] 
        driver_type = config["driver_type"] 
        registry_config = self.get_config(config["registry_config"]) 
        
        self.heart_beat_point = config.get("heart_beat_point") 
        
        self.publish_depth_first_all = config.get("publish_depth_first_all", True) 
        self.publish_breadth_first_all = config.get("publish_breadth_first_all", True) 
        self.publish_depth_first = config.get("publish_depth_first", True) 
        self.publish_breadth_first = config.get("publish_breadth_first", True) 
                           
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
                                     'tz': config['timezone']}
            
        self.base_topic = DEVICES_VALUE(campus=config.get('campus', ''), 
                                        building=config.get('building', ''), 
                                        unit=config.get('unit', ''),
                                        path=config.get('path', ''),
                                        point=None)
        
        self.device_name = DEVICES_PATH(base='',
                                   node='',
                                   campus=config.get('campus', ''), 
                                   building=config.get('building', ''), 
                                   unit=config.get('unit', ''),
                                   path=config.get('path', ''),
                                   point='')
        
        self.parent.device_startup_callback(self.device_name, self)
            
        
    def periodic_read(self):
        _log.debug("scraping device: " + self.device_name)
        
        self.parent.scrape_starting(self.device_name)
        
        try:
            results = self.interface.scrape_all()
        except Exception as ex:
            _log.error('Failed to scrape ' + self.device_name + ': ' + str(ex))
            return
        
        # XXX: Does a warning need to be printed?
        if not results:
            return
        
        utcnow = utils.get_aware_utc_now()
        utcnow_string = utils.format_timestamp(utcnow)
        
        headers = {
            headers_mod.DATE: utcnow_string,
            headers_mod.TIMESTAMP: utcnow_string,
        }
        
            

        if self.publish_depth_first or self.publish_breadth_first:
            for point, value in results.iteritems():
                depth_first_topic, breadth_first_topic = self.get_paths_for_point(point)
                message = [value, self.meta_data[point]]
                   
                if self.publish_depth_first:  
                    self._publish_wrapper(depth_first_topic, 
                                          headers=headers, 
                                          message=message)
                
                if self.publish_breadth_first:
                    self._publish_wrapper(breadth_first_topic, 
                                          headers=headers, 
                                          message=message)
         
        message = [results, self.meta_data] 
        if self.publish_depth_first_all:
            self._publish_wrapper(self.all_path_depth, 
                                  headers=headers, 
                                  message=message)
        
        if self.publish_breadth_first_all: 
            self._publish_wrapper(self.all_path_breadth, 
                                  headers=headers, 
                                  message=message)

        self.parent.scrape_ending(self.device_name)
        
        
    def _publish_wrapper(self, topic, headers, message):
        while True:
            try:
                with publish_lock():
                    _log.debug("publishing: " + topic)
                    self.vip.pubsub.publish('pubsub', 
                                        topic, 
                                        headers=headers, 
                                        message=message).get(timeout=10.0)
                                        
                    _log.debug("finish publishing: " + topic)
            except gevent.Timeout:
                _log.warn("Did not receive confirmation of publish to "+topic)
                break                           
            except Again:
                _log.warn("publish delayed: " + topic + " pubsub is busy")
                gevent.sleep(random.random())
            except VIPError as ex:
                _log.warn("driver failed to publish " + topic + ": " + str(ex))
                break
            else:
                break
            
    
    def heart_beat(self):
        if self.heart_beat_point is None:
            return
        
        self.heart_beat_value = int(not bool(self.heart_beat_value))
        
        _log.debug("sending heartbeat: " + self.device_name + ' ' + str(self.heart_beat_value))
        
        self.set_point(self.heart_beat_point, self.heart_beat_value)

    def get_paths_for_point(self, point):
        depth_first = self.base_topic(point=point)
         
        parts = depth_first.split('/')
        breadth_first_parts = parts[1:]
        breadth_first_parts.reverse()
        breadth_first_parts = [DRIVER_TOPIC_BASE] + breadth_first_parts
        breadth_first = '/'.join(breadth_first_parts)
         
        return depth_first, breadth_first 
    
    def get_point(self, point_name, **kwargs):
        return self.interface.get_point(point_name, **kwargs)
    
    def set_point(self, point_name, value, **kwargs):
        return self.interface.set_point(point_name, value, **kwargs)

    def set_multiple_points(self, point_names_values, **kwargs):
        return self.interface.set_multiple_points(self.device_name,
                                                  point_names_values,
                                                  **kwargs)
    
    def revert_point(self, point_name, **kwargs):
        self.interface.revert_point(point_name, **kwargs)
    
    def revert_all(self, **kwargs):
        self.interface.revert_all(**kwargs)
        
