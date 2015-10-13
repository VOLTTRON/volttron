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
#Authors Kyle Monson and Robert Lutes

import datetime
import logging
import sys
import time
import math

from zmq.utils import jsonapi
from dateutil import parser
from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import topics
from volttron.platform.messaging import headers as headers_mod

def DemandResponseAgent(config_path, **kwargs):
    """DR application for time of use pricing"""
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
    
    schedule = config.get('Schedule')
    datefmt = '%Y-%m-%d %H:%M:%S'
    damper_cpp = config.get('damper_cpp', 0.0)
    fan_reduction = config.get('fan_reduction', 0.1)
    max_precool_hours = config.get('max_precool_hours', 5)
    cooling_stage_differential = config.get('cooling_stage_differential', 1.0)
    '''cpp_end_hour = config.get('cpp_end_hour', 18)
    'cpp_end_minute = config.get('cpp_end_minute', 0)''' 
    #point names for controller 
    cooling_stpt = config.get('cooling_stpt')
    heating_stpt = config.get('heating_stpt')
    min_damper_stpt = config.get('min_damper_stpt')
    cooling_stage_diff = config.get('cooling_stage_diff')
    cooling_fan_sp1 = config.get('cooling_fan_sp1')
    cooling_fan_sp2 = config.get('cooling_fan_sp2')
    override_command = config.get('override_command')
    occupied_status = config.get('occupied_status')
    space_temp = config.get('space_temp')
    volttron_flag = config.get('volttron_flag')
    
    class Agent(PublishMixin, BaseAgent):
        """Class agent"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            
            self.normal_firststage_fanspeed = config.get('normal_firststage_fanspeed', 75.0)
            self.normal_secondstage_fanspeed = config.get('normal_secondstage_fanspeed', 90.0)
            self.normal_damper_stpt = config.get('normal_damper_stpt', 5.0)
            self.normal_coolingstpt = config.get('normal_coolingstpt', 74.0)
            self.normal_heatingstpt = config.get('normal_heatingstpt', 67.0)
            self.smap_path = config.get('smap_path')
            self.default_cooling_stage_differential  = 0.5
            self.current_spacetemp = 0.0
            self.building_thermal_constant = config.get('building_thermal_constant', 4.0)
            self.timestep_length = config.get('timestep_length', 900)
            self.csp_cpp = config.get('csp_cpp', 80.0)
            self.csp_pre = config.get('csp_pre', 67.0)
            self.restore_window = int(((self.csp_cpp - self.normal_coolingstpt)/self.building_thermal_constant) *3600)  
            
            self.state = 'STARTUP'
            self.e_start_msg = None
            self.error_handler = None
            self.actuator_handler = None
            self.pre_cool_idle = None
            self.e_start = None
            self.e_end = None
            self.pre_stored_spacetemp =None
            
            self.device_schedule = {}
            self.all_scheduled_events = {}
            self.currently_running_dr_event_handlers = []
            self.headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, 'requesterID': agent_id}
            utils.setup_logging()
            self._log = logging.getLogger(__name__)
            
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})                   
        @matching.match_exact(topics.ACTUATOR_SCHEDULE_RESULT())
        def schedule_result(self, topic, headers, message, match):
            msg = jsonapi.loads(message[0])
            self._log.info('Schedule Request Acknowledged')
            self.task_timer.cancel()
            task_id = headers.get('taskID', 0)
            response_type = headers.get('type', 0)
            schedule_start = self.device_schedule[task_id]["schedule_start"]
            event_start = schedule_start + datetime.timedelta(minutes = 1)
            schedule_end = self.device_schedule[task_id]["schedule_end"]
            e_start = self.device_schedule[task_id]["event_start"]
            e_end = self.device_schedule[task_id]["event_end"]
            
            if response_type == 'NEW_SCHEDULE' and self.error_handler == None:
                if msg.get('result',0) == 'SUCCESS':
                    event = sched.Event(self.pre_cool_setup, args=[e_start, e_end])
                    self.schedule(event_start, event) 
                    self.all_scheduled_events[e_start] = event 
                elif msg.get('result',0) =='FAILURE' and schedule_start < schedule_end:
                    schedule_start = schedule_start + datetime.timedelta(minutes = 10)
                    headers = {         
                                'type':  'NEW_SCHEDULE',
                               'requesterID': agent_id,
                               'taskID': task_id,
                               'priority': 'High'
                               }
                    self.task_timer = self.periodic_timer(20, self.publish_json,
                                      topics.ACTUATOR_SCHEDULE_REQUEST(), headers,
                                      [["{campus}/{building}/{unit}".format(**rtu_path),str(schedule_start),schedule_end]])
                elif schedule_start >= schedule_end:
                    return
            if self.error_handler is not None:
                self.error_handler()
                    
     
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id}) 
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def _on_error_result(self, topic, headers, message, match):
            """ERROR result"""
            point = match.group(1)
            msg = jsonapi.loads(message[0])
            point = match.group(1)
            today = datetime.datetime.now().date()
            for key,schedule in self.device_schedule.items():
                if schedule["date"] == today:
                    schedule_start = schedule["schedule_start"]
                    schedule_end = schedule["schedule_end"]
                    task_id = key
                    break
                       
            self._log.info('Error Results: '+ str(point) + '  '+ str(msg))
            if msg.get('type',0) == 'LockError':
                headers = {         
                            'type':  'NEW_SCHEDULE',
                           'requesterID': agent_id,
                           'taskID': task_id,
                           'priority': 'HIGH'
                               }
                self.task_timer = self.periodic_timer(20, self.publish_json,
                                      topics.ACTUATOR_SCHEDULE_REQUEST(), headers,
                                      [["{campus}/{building}/{unit}".format(**rtu_path),str(schedule_start),str(schedule_end)]])
                
            elif self.error_handler is not None:
                self._log.info('Running error handler')
                self.error_handler()
                

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def _on_new_data(self, topic, headers, message, match):
            """watching for new data"""
            data = jsonapi.loads(message[0])
            self.current_spacetemp = float(data[space_temp])
            dr_override = bool(int(data[override_command]))
            occupied = bool(int(data[occupied_status]))
            
            if dr_override and self.state not in ('IDLE', 'CLEANUP', 'STARTUP'):
                self._log.info('User Override Initiated')
                self.cancel_event(cancel_type='OVERRIDE')
            
            if not occupied and self.state in ('DR_EVENT', 'RESTORE'):
                self.cancel_event()
 
            if self.state == 'STARTUP':
                self._log.info('Finished Startup')
                self.state = 'IDLE'
                
        @matching.match_exact(topics.OPENADR_EVENT())
        def _on_dr_event(self, topic, headers, message, match):
            if self.state == 'STARTUP':
                self._log.info('DR event ignored because of startup.')
                return
            """handle openADR events"""
            msg = jsonapi.loads(message[0])
            self._log.info('EVENT Received:  ' + str(msg))
            e_id = msg['id']
            e_status = msg['status']
            e_start = msg['start_at']
            task_id = msg['id']
            #e_start = datetime.datetime.strptime(e_start,datefmt)
            today = datetime.datetime.now().date()
            e_end = msg['end_at']
            e_end = parser.parse(e_end, fuzzy=True)
            e_start = parser.parse(e_start, fuzzy=True)
            dr_date = e_start.date()
            current_datetime = datetime.datetime.now()
            
            if current_datetime > e_end:
                self._log.info('Too Late Event is Over')
                return
            
            if e_status == 'cancelled':
                if e_start in self.all_scheduled_events:
                    self._log.info('Event Cancelled')
                    self.all_scheduled_events[e_start].cancel()
                    del self.all_scheduled_events[e_start]
                    
                if e_start.date() == today and (self.state == 'PRECOOL' or self.state == 'DR_EVENT'):
                    self.cancel_event()
                return

            if today > e_start.date():
                if e_start in self.all_scheduled_events:
                    self.all_scheduled_events[e_start].cancel()
                    del self.all_scheduled_events[e_start]
                return
            
            for item in self.all_scheduled_events:
                if e_start.date() == item.date():
                    if e_start.time() != item.time():
                        self._log.info( 'Updating Event')
                        self.all_scheduled_events[item].cancel()
                        del self.all_scheduled_events[item]
                        if e_start.date() == today and (self.state == 'PRECOOL' or self.state == 'DR_EVENT'):
                            self.cancel_event(cancel_type='UPDATING')
                        break
                    elif e_start.time() == item.time():
                        self._log.info("same event")
                        return
            
            #Don't schedule an event if we are currently in OVERRIDE state.    
            if e_start.date() == today and (self.state == 'OVERRIDE'):
                return
            
           
            schedule_start = e_start - datetime.timedelta(hours = max_precool_hours)  
            schedule_end = e_end + datetime.timedelta(seconds = self.restore_window)
            schedule_end = schedule_end + datetime.timedelta(minutes = 10)
            self.device_schedule[task_id]={"date": dr_date,
                                                "schedule_start": schedule_start,
                                                "schedule_end": schedule_end,
                                                "event_start": e_start,
                                                "event_end": e_end}
            headers = {         
                               'type':  'NEW_SCHEDULE',
                               'requesterID': agent_id,
                               'taskID': task_id,
                               'priority': 'HIGH'
                               }
            self.task_timer = self.periodic_timer(20, self.publish_json,
                                      topics.ACTUATOR_SCHEDULE_REQUEST(), 
                                      headers,
                                      [["{campus}/{building}/{unit}".format(**rtu_path),str(schedule_start),str(schedule_end)]])
                           
                
        def pre_cool_setup(self, e_start, e_end):
            if self.state == 'OVERRIDE':
                self._log.info("Override today")
                return
            
            if self.pre_cool_idle == False:
                return
            
            now = datetime.datetime.now()
            day=now.weekday()

            if not schedule[day]:
                self._log.info("Unoccupied today")
                return
            
            if self.state == 'PRECOOL' and self.pre_cool_idle == True:
                for event in self.currently_running_dr_event_handlers:
                    event.cancel()
                self.currently_running_dr_event_handlers = []
                    
            self.state = 'PRECOOL'
            e_start_unix = time.mktime(e_start.timetuple())
            e_end_unix = time.mktime(e_end.timetuple())   

            event_start = now + datetime.timedelta(minutes=15)   
            event = sched.Event(self.pre_cool_setup, args=[e_start, e_end])
            self.schedule(event_start, event) 
            self.all_scheduled_events[e_start] = event 
            self.schedule_builder(e_start_unix, e_end_unix)            
                    
        def modify_temp_set_point(self, csp, hsp):
            self.publish(topics.ACTUATOR_SET(point=volttron_flag, **rtu_path), self.headers, str(3.0))
            self.publish(topics.ACTUATOR_SET(point=min_damper_stpt, **rtu_path), self.headers, str(self.normal_damper_stpt))
            self.publish(topics.ACTUATOR_SET(point=cooling_stage_diff, **rtu_path), self.headers, str(self.default_cooling_stage_differential))
            self.publish(topics.ACTUATOR_SET(point=cooling_stpt, **rtu_path), self.headers, str(csp))
            self.publish(topics.ACTUATOR_SET(point=heating_stpt, **rtu_path), self.headers, str(hsp))
           
            if self.pre_cool_idle == True:
                self.pre_cool_idle = False
            
            def backup_run():
                self.modify_temp_set_point(csp, hsp)
                self.error_handler = None
                
            self.error_handler = backup_run
            
        def start_dr_event(self):
            self.state = 'DR_EVENT'
            self.publish(topics.ACTUATOR_SET(point=volttron_flag, **rtu_path), self.headers, str(3.0))
            self.publish(topics.ACTUATOR_SET(point=cooling_stpt, **rtu_path), self.headers, str(self.csp_cpp))
            
            new_fan_speed = self.normal_firststage_fanspeed - (self.normal_firststage_fanspeed*fan_reduction)
            new_fan_speed = max(new_fan_speed,0)
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp1, **rtu_path), self.headers, str(new_fan_speed))
            
            new_fan_speed = self.normal_secondstage_fanspeed - (self.normal_firststage_fanspeed*fan_reduction)
            new_fan_speed = max(new_fan_speed,0)
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp2, **rtu_path), self.headers, str(new_fan_speed))            
            
            self.publish(topics.ACTUATOR_SET(point=min_damper_stpt, **rtu_path), self.headers, str(damper_cpp))
            self.publish(topics.ACTUATOR_SET(point=cooling_stage_diff, **rtu_path), self.headers, str(cooling_stage_differential))
            mytime = int(time.time())
            content = {
                "Demand Response Event": {
                     "Readings": [[mytime, 1.0]],
                     "Units": "TU",
                     "data_type": "double"
                 }
            }
            self.publish(self.smap_path, self.headers, jsonapi.dumps(content))    
            def backup_run():
                self.start_dr_event()
                self.error_handler = None
                
            self.error_handler = backup_run
            
        def start_restore_event(self, csp, hsp):
            self.state = 'RESTORE'
            self._log.info('Restore:  Begin restoring normal operations')
            self.publish(topics.ACTUATOR_SET(point=cooling_stpt, **rtu_path), self.headers, str(csp))
            self.publish(topics.ACTUATOR_SET(point=heating_stpt, **rtu_path), self.headers, str(hsp)) #heating
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp1, **rtu_path), self.headers, str(self.normal_firststage_fanspeed))
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp2, **rtu_path), self.headers, str(self.normal_secondstage_fanspeed))            
            
            self.publish(topics.ACTUATOR_SET(point=min_damper_stpt, **rtu_path), self.headers, str(self.normal_damper_stpt))
            self.publish(topics.ACTUATOR_SET(point=cooling_stage_diff, **rtu_path), self.headers, str(self.default_cooling_stage_differential))
                
            def backup_run():
                self.start_restore_event(csp, hsp)
                self.error_handler = None
                
            self.error_handler = backup_run
            
        def cancel_event(self, cancel_type='NORMAL'):
            if cancel_type == 'OVERRIDE':
                self.state = 'OVERRIDE'
                smap_input = 3.0
            elif cancel_type != 'UPDATING':
                self.state = 'CLEANUP'
                smap_input = 2.0
    
                            
            self.publish(topics.ACTUATOR_SET(point=cooling_stpt, **rtu_path), self.headers, str(self.normal_coolingstpt))
            self.publish(topics.ACTUATOR_SET(point=heating_stpt, **rtu_path), self.headers, str(self.normal_heatingstpt))
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp1, **rtu_path), self.headers, str(self.normal_firststage_fanspeed))
            self.publish(topics.ACTUATOR_SET(point=cooling_fan_sp2, **rtu_path), self.headers, str(self.normal_secondstage_fanspeed))            
            
            self.publish(topics.ACTUATOR_SET(point=min_damper_stpt, **rtu_path), self.headers, str(self.normal_damper_stpt))
            self.publish(topics.ACTUATOR_SET(point=cooling_stage_diff, **rtu_path), self.headers, str(self.default_cooling_stage_differential))
            self.publish(topics.ACTUATOR_SET(point=volttron_flag, **rtu_path), self.headers,str(0))
            
            for event in self.currently_running_dr_event_handlers:
                event.cancel()
                
            if cancel_type != 'UPDATING':
                mytime = int(time.time())
                content = {
                    "Demand Response Event": {
                         "Readings": [[mytime, smap_input]],
                         "Units": "TU",
                         "data_type": "double"
                     }
                }
                self.publish(self.smap_path, self.headers, jsonapi.dumps(content))
            self.device_schedule = {}
            self.all_scheduled_events = {}   
            self.currently_running_dr_event_handlers = []
            def backup_run():
                self.cancel_event()
                self.error_handler = None
                
            self.error_handler = backup_run
            
            expected_values = {cooling_stpt: self.normal_coolingstpt,
                               heating_stpt: self.normal_heatingstpt,
                               cooling_fan_sp1: self.normal_firststage_fanspeed,
                               cooling_fan_sp2: self.normal_secondstage_fanspeed,
                               min_damper_stpt: self.normal_damper_stpt,
                               cooling_stage_diff: self.default_cooling_stage_differential}
            
            EPSILON = 0.5  #allowed difference from expected value
            
            def result_handler(point, value):
                #print "actuator point being handled:", point, value
                expected_value = expected_values.pop(point, None)
                if expected_value is not None:
                    diff = abs(expected_value-value)
                    if diff > EPSILON:
                        self._log.info( "Did not get back expected value for:  " + str(point))
                        
                if not expected_values:
                    self.actuator_handler = None
                    
                    self.error_handler = None
                    self.state = 'IDLE' if not cancel_type == 'OVERRIDE' else 'OVERRIDE'
                    
            
            if cancel_type != 'UPDATING':
                self.actuator_handler = result_handler
            else:
                self.actuator_handler = None
            
            if cancel_type == 'OVERRIDE':
                def on_reset():
                    self.error_handler = None
                    self.state = 'IDLE'    
                    
                today = datetime.datetime.now()
                reset_time = today + datetime.timedelta(days=1)
                reset_time = reset_time.replace(hour=0, minute =0, second = 0)             
                
                event = sched.Event(on_reset)
                self.schedule(reset_time, event) 
          
        def schedule_builder(self,start_time, end_time):
            """schedule all events for a DR event."""
            current_time = time.time()
            if current_time > end_time:
                return

            self._log.info('Scheduling all DR actions')  
            pre_hsp = self.csp_pre - 5.0

            ideal_cooling_window = int(((self.current_spacetemp - self.csp_pre)/self.building_thermal_constant) *3600)  
            ideal_precool_start_time = start_time - ideal_cooling_window
            
            max_cooling_window = start_time - current_time
            
            cooling_window = ideal_cooling_window if ideal_cooling_window < max_cooling_window else max_cooling_window
            
            precool_start_time = start_time - cooling_window
            pre_cool_step = 0
            if (max_cooling_window > 0):
                self._log.info('Schedule Pre Cooling')
                num_cooling_timesteps = int(math.ceil(float(cooling_window) / float(self.timestep_length)))         
                cooling_step_delta = (self.normal_coolingstpt - self.csp_pre) / num_cooling_timesteps
                
                if num_cooling_timesteps <= 0:
                    num_cooling_timesteps=1
                    
                for step_index in range (1, num_cooling_timesteps):
                    if step_index == 1:
                        pre_cool_step = 2*self.timestep_length
                    else:
                        pre_cool_step += self.timestep_length
                        
                    event_time = start_time - pre_cool_step
                    csp = self.csp_pre + ((step_index-1) * cooling_step_delta)
                    
                    self._log.info('Precool step:  '+ str(datetime.datetime.fromtimestamp(event_time)) + '   CSP:  ' + str(csp))
                    event = sched.Event(self.modify_temp_set_point, args = [csp, pre_hsp])
                    self.schedule(event_time, event)
                    self.currently_running_dr_event_handlers.append(event)
            
            else:
                self._log.info('Too late to pre-cool!')
            
            restore_start_time = end_time
            num_restore_timesteps = int(math.ceil(float(self.restore_window) / float(self.timestep_length)))         
            restore_step_delta = (self.csp_pre - self.normal_coolingstpt) / num_restore_timesteps
                
            self._log.info('Schedule DR Event: ' + str(datetime.datetime.fromtimestamp(start_time)) +'   CSP:  ' + str(self.csp_cpp))
            event = sched.Event(self.start_dr_event)
            self.schedule(start_time, event)
            self.currently_running_dr_event_handlers.append(event)
            
            self._log.info('Schedule Restore Event:  '+ str(datetime.datetime.fromtimestamp(end_time)) + '   CSP:  ' + str(self.csp_pre-restore_step_delta))
            event = sched.Event(self.start_restore_event, args = [self.csp_pre-restore_step_delta, self.normal_heatingstpt])
            self.schedule(end_time, event)
            self.currently_running_dr_event_handlers.append(event)
                
            for step_index in range (1, num_restore_timesteps):
                event_time = end_time + (step_index * self.timestep_length)
                csp = self.csp_pre - ((step_index + 1) * restore_step_delta)
                
                self._log.info('Restore step: ' + str(datetime.datetime.fromtimestamp(event_time)) +'   CSP:  ' + str(csp))
                event = sched.Event(self.modify_temp_set_point, args = [csp, self.normal_heatingstpt])
                self.schedule(event_time, event)
                self.currently_running_dr_event_handlers.append(event)
            
            event_time = end_time + (num_restore_timesteps * self.timestep_length)
            self._log.info('Schedule Cleanup Event:  ' + str(datetime.datetime.fromtimestamp(event_time)))
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
