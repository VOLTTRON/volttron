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

import logging
import sys
import gevent
import random

from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.async import AsyncCall
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.topics import (DRIVER_TOPIC_BASE, 
                                                DRIVER_TOPIC_ALL, 
                                                DEVICES_VALUE,
                                                DEVICES_PATH)

from volttron.platform.vip.agent.errors import VIPError, Again

import dateutil

import stomp
from stomp.listener import TestListener

class MyTestListener(TestListener):

    def wait_for_message(self):
        with self.message_condition:
            while not self.message_received:
                self.message_condition.wait(timeout=5)
        self.message_received = False

    def get_latest_message(self):
        if not self.message_list:
            return None
        
        message = self.message_list[-1]
        self.message_list = []
        return message

utils.setup_logging()
_log = logging.getLogger(__name__)

modbus_logger = logging.getLogger("stomp")
modbus_logger.setLevel(logging.WARNING)

import os.path

write_debug_str = "Writing: {target} {property} : {value} {result}"

def matlab_proxy_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    vip_identity = config.get("vip_identity", "platform.matlab_proxy")
    #pop off the uuid based identity
    kwargs.pop('identity', None)
    
    activemq_address= config['activemq_address']
    activemq_port= config['activemq_port']
    activemq_user = config['activemq_user']
    activemq_password = config['activemq_password']
    request_queue = config['request_queue']
    response_queue = config['response_queue']
    status_format = config['status_format']
    building_power_format = config['building_power_format']
    building_power_row_index = building_power_format["building_power_row_index"]
    building_power_device = building_power_format["building_power_device"]
    building_power_point = building_power_format["building_power_point"]
    timestamp_row = config["timestamp_row"]
    interval = config["interval"]
    defaults = config.get("defaults", {})
    
    SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
    
    class MATLABProxyAgent(Agent):
        '''This agent creates a virtual matlab device that is used by
        the matlab driver interface to communicate with matlab simulation devices.
        '''
        def __init__(self, **kwargs):
            super(MATLABProxyAgent, self).__init__(identity=vip_identity, **kwargs)
            #TODO error handling
            self.dirty_points = set()
            self.setup_device()
            
            
            
        def setup_device(self): 
            self.conn = stomp.Connection12(host_and_ports=((activemq_address, activemq_port),),auto_content_length=False)
            self.conn.set_listener('', MyTestListener())
            self.conn.start()
            self.conn.connect(activemq_user,activemq_password, wait=True)
            self.conn.subscribe(destination=response_queue, id=1, ack='auto')
            
        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):
#             self.advance_publish()
#             self.set_point('foo', 'RTU1Compressor1/ThermostateSetPointTemperature',65)
#             self.set_point('foo', 'RTU1Compressor2/ThermostateSetPointTemperature',65)
#             self.set_point('foo', 'RTU2/ThermostateSetPointTemperature',67)
#             self.set_point('foo', 'RTU3/ThermostateSetPointTemperature',68)
#             self.set_point('foo', 'RTU4/ThermostateSetPointTemperature',69)
            self.advance_publish()
            self.core.periodic(interval, self.advance_publish, wait=None)
            
        @RPC.export    
        def request_new_schedule(self, requester_id, task_id, priority, requests):
            _log.debug(requester_id + " requests new schedule " + task_id + " " + str(requests))
            data =  {}        
            results = {'result':SCHEDULE_RESPONSE_SUCCESS, 
                       'data': data, 
                       'info':""}
            return results
        
        @RPC.export 
        def request_cancel_schedule(self, requester_id, task_id):
            _log.debug(requester_id + " canceled " + task_id)
            message = {'result':SCHEDULE_RESPONSE_SUCCESS,  
                       'info': '',
                       'data':{}}
                
            return message   
            
        @RPC.export
        def set_point(self, requester_id, topic, value, **kwargs):
            """Write to a property."""
            
            target_device, property_name = topic.rsplit('/', 1)
            
            _log.debug("Attempting to write " +str(target_device)+', '+str(property_name)+" with value: "+str(value))
            
            request = 'setpoint,'+str(target_device)+','+str(property_name)+','+str(value)
            
            self.conn.send(body=request, destination=request_queue, headers = {"content-type": "text/plain"})
            self.conn.get_listener(name='').wait_for_message()
            response = self.conn.get_listener(name='').get_latest_message()
            
            _log.debug(write_debug_str.format(target=target_device,
                                              property=property_name,
                                              value=value,
                                              result=response[1]))
            
            if response[1]=='success':
                return value;
            else:
                raise RuntimeError("Failed to set value: " + response[1])
         
        @RPC.export
        def revert_point(self, requester_id, topic, **kwargs):
            target_device, property_name = topic.rsplit('/', 1)
            value = defaults.get(target_device, {}).get(property_name)
            if value is None:
                _log.warning("Unable to revert point "+topic+" to "+str(value)+"!")
                return
            _log.debug("Reverting point "+topic+" to "+str(value))
            self.set_point(requester_id, topic, value)
            
        def advance_publish(self):
            """Read system status and return the results"""
                        
            values  = {}
            matrix = []
            
            _log.debug("Advancing simulation")
            self.conn.send(body='advance', destination=request_queue, headers = {"content-type": "text/plain"})
            self.conn.get_listener(name='').wait_for_message()
            response = self.conn.get_listener(name='').get_latest_message()
            
            rows = response[1].split(';')
            
            building_power = rows[building_power_row_index]
            timestamp_value = rows[timestamp_row]
            
            for rows_string in rows[:4]:
                row = [float(x) for x in rows_string.split()]
                matrix.append(row)
            
            for column_index, device_config in enumerate(status_format):
                device_name, point_map = device_config
                device_result = {}
                for point_name, row_index in point_map.items():
                    value = matrix[row_index][column_index]
                    device_result[point_name] = value
                    
                values[device_name] = device_result
                
            #building_power = matrix[0][building_power_row_index]
            
            now = dateutil.parser.parse(timestamp_value)
            
            headers = {
                headers_mod.DATE: now.isoformat()
            }
            
            _log.debug("Simulation time: "+str(now))
            
            _log.debug("Returned simulation values: "+str(values))
                    
            for device_name, device_results in values.items(): 
                publish_topic = DEVICES_VALUE(campus='',
                                              building='',
                                              unit=device_name,
                                              point='all')
                self._publish_wrapper(publish_topic, 
                                      headers=headers, 
                                      message=[device_results,{}])
                
            publish_topic = DEVICES_VALUE(campus='',
                                          building='',
                                          unit=building_power_device,
                                          point='all')
            self._publish_wrapper(publish_topic, 
                                  headers=headers, 
                                  message=[{building_power_point: building_power},{}])

        
        def _publish_wrapper(self, topic, headers, message):
            while True:
                try:
                        _log.debug("publishing: " + topic)
                        self.vip.pubsub.publish('pubsub', 
                                            topic, 
                                            headers=headers, 
                                            message=message).get(timeout=10.0)
                                            
                        _log.debug("finish publishing: " + topic)
                except Again:
                    _log.warn("publish delayed: " + topic + " pubsub is busy")
                    gevent.sleep(random.random())
                except VIPError as ex:
                    _log.warn("driver failed to publish " + topic + ": " + str(ex))
                    break
                else:
                    break
        
                    
    return MATLABProxyAgent(**kwargs)
            
    
    
def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(matlab_proxy_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
