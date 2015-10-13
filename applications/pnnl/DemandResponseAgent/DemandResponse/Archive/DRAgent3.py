# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}
import datetime
import logging
import settings
import sys
import time
from zmq.utils import jsonapi
import math

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import topics
from volttron.platform.messaging import headers as headers_mod

debug_flag = False
if not debug_flag:
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
else:
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.NOTSET, stream=sys.stderr,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt= '%m-%d-%y %H:%M:%S',
                    filename='/home/volttrondev/workspace/rtunetwork/Agents/DemandResponseAgent/DemandResponse/log1.txt',
                    filemode='a')
    fmt_str = '%(asctime)s   %(levelname)-8s    %(message)s'
    formatter = logging.Formatter(fmt_str,datefmt = '%m-%d-%y %H:%M:%S')
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)


def DemandResponseAgent(config_path, **kwargs):
    """DR application for time of use pricing"""
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
    command_timeout = config.get('command-timeout',
                                 settings.default_command_timeout)
    csp_pre = config.get('csp_pre', 
                    settings.csp_pre)
    csp_cpp = config.get('csp_cpp', 
                    settings.csp_cpp)
    damper_cpp = config.get('damper_cpp', 
                    settings.damper_cpp)
    fan_reduction = config.get('fan_reduction',
                    settings.fan_reduction)
    time_steps_perhour = config.get('time_steps_perhour',
                    settings.pre_time)
    
    Schedule = config.get('Schedule')
    
    max_precool_hours = config.get('max_precool_hours')
    
    
    datefmt = '%m-%d-%y %H:%M'
    

    cpp_end_hour = config.get('cpp_end_hour') 
    
    timestep_length = config.get('timestep_length')
    
    building_thermal_constant = config.get('building_thermal_constant')
    
    class Agent(PublishMixin, BaseAgent):
        """Class agent"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.default_firststage_fanspeed = 0.0
            self.default_secondstage_fanspeed = 0.0
            self.default_damperstpt = 0.0
            self.default_coolingstpt = 0.0
            self.default_heatingstpt = 65.0
            
            self.current_spacetemp = 72.0
            
            self.state = 'STARTUP'
            self.e_start_msg = None
            self.lock_handler = None
            self.error_handler = None
            self.actuator_handler = None
            
            self.all_scheduled_events = {}
            self.currently_running_dr_event_handlers = []
            self.headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, 'requesterID': agent_id}

        @matching.match_exact(topics.ACTUATOR_LOCK_RESULT(**rtu_path))
        def _on_lock_result(self, topic, headers, message, match):
            """lock result"""
            msg = jsonapi.loads(message[0])
            if headers['requesterID'] == agent_id:
                if msg == 'SUCCESS' and self.lock_handler is not None:
                    self.lock_handler()
                if msg == 'FAILURE' and self.error_handler is not None:
                    self.error_handler(msg)
                    
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def _on_error_result(self, topic, headers, message, match):
            """lock result"""
            if headers.get('requesterID', '') == agent_id:
                if self.error_handler is not None:
                    self.error_handler(match, jsonapi.loads(message[0]))
                    
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **rtu_path))
        def _on_actuator_result(self, topic, headers, message, match):
            """lock result"""
            msg = jsonapi.loads(message[0])
            print 'Actuator Results:', match, msg                    
            if headers['requesterID'] == agent_id:
                if self.actuator_handler is not None:
                    self.actuator_handler(match, jsonapi.loads(message[0]))

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def _on_new_data(self, topic, headers, message, match):
            """watching for new data"""
            data = jsonapi.loads(message[0])
#             self.current_spacetemp = float(data["ZoneTemp"])
            self.current_spacetemp = 76
            droveride = bool(int(data["CoolCall2"]))
            occupied = bool(int(data["Occupied"]))
            
            if droveride and self.state not in ('IDLE', 'CLEANUP', 'STARTUP'):
                print 'User Override Initiated'
                self.cancel_event()
            
            if not occupied and self.state in ('DR_EVENT', 'RESTORE'):
                self.cancel_event()
                
            if self.state == 'IDLE' or self.state=='STARTUP':
                #self.default_coolingstpt = float(data["CoolingStPt"])
                #self.default_heatingstpt = float(data["HeatingStPt"])
                self.default_coolingstpt = 75.0
                self.default_heatingstpt = 65.0
                self.default_firststage_fanspeed = float(data["CoolSupplyFanSpeed1"])
                self.default_secondstage_fanspeed = float(data["CoolSupplyFanSpeed2"])
                self.default_damperstpt = float(data["ESMDamperMinPosition"])
                
            if self.state == 'STARTUP':
                self.state = 'IDLE'
                
        @matching.match_exact(topics.OPENADR_EVENT())
        def _on_dr_event(self, topic, headers, message, match):
            if self.state == 'STARTUP':
                print "DR event ignored because of startup."
                return
            """handle openADR events"""
            msg = jsonapi.loads(message[0])
            print('EVENT Received')
            print(msg)
            e_id = msg['id']
            e_status = msg['status']
            e_start = msg['start']
            e_start = datetime.datetime.strptime(e_start, datefmt)
            today = datetime.datetime.now().date()
            #e_start_day = e_start.date()
            #e_end = e_start.replace(hour=cpp_end_hour, minute =0, second = 0)
            current_datetime = datetime.datetime.now()
            e_end = e_start  + datetime.timedelta(minutes=2)
            
            if current_datetime > e_end:
                print 'Too Late Event is Over'
                return
            
            
            if e_status == 'cancelled':
                if e_start in self.all_scheduled_events:
                    print 'Event Cancelled'
                    self.all_scheduled_events[e_start].cancel()
                    del self.all_scheduled_events[e_start]
                    
                if e_start.date() == today and (self.state == 'PRECOOL' or self.state == 'DR_EVENT'):
                    self.cancel_event()
                return
                    
            #TODO: change this to UTC later
            #utc_now = datetime.datetime.utcnow()

            if today > e_start.date():
                if e_start in self.all_scheduled_events:
                    self.all_scheduled_events[e_start].cancel()
                    del self.all_scheduled_events[e_start]
                    
                return
            
            for item in self.all_scheduled_events.keys():
                if e_start.date() == item.date():
                    if e_start.time() != item.time():
                        print "Updating Event"
                        self.all_scheduled_events[item].cancel()
                        del self.all_scheduled_events[item]
                        if e_start.date() == today and (self.state == 'PRECOOL' or self.state == 'DR_EVENT'):
                            self.update_running_event()
                            self.state = 'IDLE'
                        break
                    elif e_start.time() == item.time():
                        print "same event"
                        return
            #if e_id in self.all_scheduled_dr_events and update is None:
#                 if e_id == self.currently_running_msg:
#                 return
                #return
                
            #Minutes used for testing   
            #event_start = e_start - datetime.timedelta(hours = max_precool_hours)  
            event_start = e_start - datetime.timedelta(minutes = max_precool_hours)
            
            event = sched.Event(self.pre_cool_get_lock, args=[e_start, e_end])
            self.schedule(event_start, event) 
            self.all_scheduled_events[e_start] = event                
                
        def pre_cool_get_lock(self, e_start,e_end):
            
            now = datetime.datetime.now()
            day=now.weekday()
          
            if not Schedule[day]:
                print"Unoccupied today"
                return
                
            self.state = 'PRECOOL'
            
            #e_end = e_start.replace(hour=cpp_end_hour, minute =0, second = 0)
            #e_end = e_start + datetime.timedelta(minutes=2)
            e_start_unix = time.mktime(e_start.timetuple())
            e_end_unix = time.mktime(e_end.timetuple())
           
            def run_schedule_builder():
                #current_time = time.mktime(current_time.timetuple())
                self.schedule_builder(e_start_unix, e_end_unix,
                                      current_spacetemp=77.0,
                                      pre_csp=csp_pre,
                                      building_thermal_constant=building_thermal_constant,
                                      normal_coolingstpt=76.0,
                                      timestep_length=timestep_length,
                                      dr_csp=csp_cpp)
                self.lock_handler=None
            
            self.lock_handler = run_schedule_builder
            
            headers = {
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                'requesterID': agent_id}
            self.publish(topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)
            
        def modify_temp_set_point(self, csp, hsp):
            self.publish(topics.ACTUATOR_SET(point='StandardDamperChangeOverSetPoint', **rtu_path), self.headers, str(csp))
            self.publish(topics.ACTUATOR_SET(point='StandardDamperMinPosition', **rtu_path), self.headers, str(hsp))
            
            def backup_run():
                self.modify_temp_set_point(csp, hsp)
                self.lock_handler=None
                
            self.lock_handler = backup_run
            
        def start_dr_event(self):
            self.state = 'DR_EVENT'
            self.publish(topics.ACTUATOR_SET(point='StandardDamperChangeOverSetPoint', **rtu_path), self.headers, str(csp_cpp))
            
            new_fan_speed = self.default_firststage_fanspeed - (self.default_firststage_fanspeed * fan_reduction)
            new_fan_speed = max(new_fan_speed,0)
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed1', **rtu_path), self.headers, str(new_fan_speed))
            
            new_fan_speed = self.default_secondstage_fanspeed - (self.default_firststage_fanspeed * fan_reduction)
            new_fan_speed = max(new_fan_speed,0)
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed2', **rtu_path), self.headers, str(new_fan_speed))            
            
            self.publish(topics.ACTUATOR_SET(point='ESMDamperMinPosition', **rtu_path), self.headers, str(damper_cpp))
                
            def backup_run():
                self.start_dr_event()
                self.lock_handler=None
                
            self.lock_handler = backup_run
            
        def start_restore_event(self, csp, hsp):
            self.state = 'RESTORE'
            print 'Restore:  Begin restoring normal operations'
            self.publish(topics.ACTUATOR_SET(point='StandardDamperChangeOverSetPoint', **rtu_path), self.headers, str(csp))
            self.publish(topics.ACTUATOR_SET(point='StandardDamperMinPosition', **rtu_path), self.headers, str(hsp)) #heating
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed1', **rtu_path), self.headers, str(self.default_firststage_fanspeed))
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed2', **rtu_path), self.headers, str(self.default_secondstage_fanspeed))            
            
            self.publish(topics.ACTUATOR_SET(point='ESMDamperMinPosition', **rtu_path), self.headers, str(self.default_damperstpt))
                
            def backup_run():
                self.start_restore_event(csp, hsp)
                self.lock_handler=None
                
            self.lock_handler = backup_run
            
        def update_running_event(self):
            self.publish(topics.ACTUATOR_SET(point='StandardDamperChangeOverSetPoint', **rtu_path), self.headers, str(self.default_coolingstpt))
            self.publish(topics.ACTUATOR_SET(point='StandardDamperMinPosition', **rtu_path), self.headers, str(self.default_heatingstpt))
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed1', **rtu_path), self.headers, str(self.default_firststage_fanspeed))
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed2', **rtu_path), self.headers, str(self.default_secondstage_fanspeed))            
            
            self.publish(topics.ACTUATOR_SET(point='ESMDamperMinPosition', **rtu_path), self.headers, str(self.default_damperstpt))
            
            for event in self.currently_running_dr_event_handlers:
                event.cancel()
            self.currently_running_dr_event_handlers = []
            
        def cancel_event(self):
            self.state = 'CLEANUP'
            self.publish(topics.ACTUATOR_SET(point='StandardDamperChangeOverSetPoint', **rtu_path), self.headers, str(self.default_coolingstpt))
            self.publish(topics.ACTUATOR_SET(point='StandardDamperMinPosition', **rtu_path), self.headers, str(self.default_heatingstpt))
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed1', **rtu_path), self.headers, str(self.default_firststage_fanspeed))
            self.publish(topics.ACTUATOR_SET(point='CoolSupplyFanSpeed2', **rtu_path), self.headers, str(self.default_secondstage_fanspeed))            
            
            self.publish(topics.ACTUATOR_SET(point='ESMDamperMinPosition', **rtu_path), self.headers, str(self.default_damperstpt))
            
            for event in self.currently_running_dr_event_handlers:
                event.cancel()
                
            self.currently_running_dr_event_handlers = []
            def backup_run():
                self.cancel_event()
                self.lock_handler=None
                
            self.lock_handler = backup_run
            
            expected_values = {'StandardDamperChangeOverSetPoint': self.default_coolingstpt,
                               'StandardDamperMinPosition': self.default_heatingstpt,
                               'CoolSupplyFanSpeed1': self.default_firststage_fanspeed,
                               'CoolSupplyFanSpeed2': self.default_secondstage_fanspeed,
                               'ESMDamperMinPosition': self.default_damperstpt}
            
            EPSILON = 0.5  #allowed difference from expected value
            
            def result_handler(point, value):
                #print "actuator point being handled:", point, value
                expected_value = expected_values.pop(point, None)
                if expected_value is not None:
                    diff = abs(expected_value-value)
                    if diff > EPSILON:
                        _log.debug( "Did not get back expected value for", point)
                        
                if not expected_values:
                    self.actuator_handler = None
                    self.lock_handler=None
                    self.state = 'IDLE'
                    
                    headers = {
                        headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                        'requesterID': agent_id}
                    self.publish(topics.ACTUATOR_LOCK_RELEASE(**rtu_path), headers)
            
            self.actuator_handler = result_handler
          
        def schedule_builder(self,start_time, end_time, 
                             current_spacetemp,
                             pre_csp,
                             building_thermal_constant,
                             normal_coolingstpt,
                             timestep_length,
                             dr_csp):
            """schedule all events for a DR event."""
           

            print 'Scheduling all DR actions'   
            pre_hsp = pre_csp - 5.0
            current_time = time.time()
            ideal_cooling_window = int(((current_spacetemp - pre_csp)/building_thermal_constant) *3600)  
            ideal_precool_start_time = start_time - ideal_cooling_window
            
            max_cooling_window = start_time - current_time
            
            cooling_window = ideal_cooling_window if ideal_cooling_window < max_cooling_window else max_cooling_window
            
            precool_start_time = start_time - cooling_window
     
            if (max_cooling_window > 0):
                print "Schedule Pre Cooling" 
                num_cooling_timesteps = int(math.ceil(float(cooling_window) / float(timestep_length)))         
                cooling_step_delta = (normal_coolingstpt - pre_csp) / num_cooling_timesteps
                
                for step_index in range (1, num_cooling_timesteps+1):
                    event_time = start_time - (step_index * timestep_length)
                    csp = pre_csp + ((step_index-1)*cooling_step_delta)
                    
                    print 'Precool step:', datetime.datetime.fromtimestamp(event_time), csp
                    event = sched.Event(self.modify_temp_set_point, args = [csp, pre_hsp])
                    self.schedule(event_time, event)
                    self.currently_running_dr_event_handlers.append(event)
            
            else:
                print "Too late to pre-cool!"
            
            restore_window = int(((dr_csp - normal_coolingstpt)/building_thermal_constant) *3600)  
            restore_start_time = end_time
            num_restore_timesteps = int(math.ceil(float(restore_window) / float(timestep_length)))         
            restore_step_delta = (dr_csp - normal_coolingstpt) / num_restore_timesteps
                
            print 'Schedule DR Event:', datetime.datetime.fromtimestamp(start_time), dr_csp
            event = sched.Event(self.start_dr_event)
            self.schedule(start_time, event)
            self.currently_running_dr_event_handlers.append(event)
            
            print 'Schedule Restore Event:', datetime.datetime.fromtimestamp(end_time), dr_csp-restore_step_delta
            event = sched.Event(self.start_restore_event, args = [dr_csp-restore_step_delta, self.default_heatingstpt])
            self.schedule(end_time, event)
            self.currently_running_dr_event_handlers.append(event)
                
            for step_index in range (1, num_restore_timesteps):
                event_time = end_time + (step_index * timestep_length)
                csp = dr_csp - ((step_index + 1) * restore_step_delta)
                
                print 'Restore step:', datetime.datetime.fromtimestamp(event_time), csp
                event = sched.Event(self.modify_temp_set_point, args = [csp, self.default_heatingstpt])
                self.schedule(event_time, event)
                self.currently_running_dr_event_handlers.append(event)
            
            event_time = end_time + (num_restore_timesteps * timestep_length)
            print 'Schedule Cleanup Event:', datetime.datetime.fromtimestamp(event_time)
            event = sched.Event(self.cancel_event)
            self.schedule(event_time,event)
            self.currently_running_dr_event_handlers.append(event)
               
    Agent.__name__ = 'DemandResponseAgent'
    return Agent(**kwargs) 

def main(argv = sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DemandResponseAgent,
                       description = 'VOLTTRON platform DR agent',
                       argv=argv)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
   


