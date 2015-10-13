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

import greenlet
from zmq.utils import jsonapi

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import topics
#from volttron.platform.messaging import headers as headers_mod

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


class CommandSetError(Exception):
    pass


def DemandResponseAgent(config_path, **kwargs):
    """DR application for time of use pricing"""
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
    command_timeout = config.get('command-timeout',
                                 settings.default_command_timeout)
    data_timeout = config.get('data-timeout', settings.default_data_timeout)
    
    csp_pre = config.get('csp_pre', 
                    settings.csp_pre)
    csp_cpp = config.get('csp_cpp', 
                    settings.csp_cpp)
    damper_cpp = config.get('damper_cpp', 
                    settings.damper_cpp)
    fan_reduction = config.get('fan_reduction',
                    settings.fan_reduction)
    pre_time = config.get('pre_time',
                    settings.pre_time)
    after_time = config.get('after_time', 
                    settings.after_time)
    time_step = config.get('time_step', 
                    settings.after_time)
    Schedule = config.get('Schedule')

    class Agent(PublishMixin, BaseAgent):
        """Class agent"""
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.schedule_state = False
            self.fan1_norm = 0
            self.fan2_norm = 0
            self.csp_norm = 0
            self.accel_slope = 0
            self.cooling_slope = 0
            self.min_damper = 0
            self.override_flag = False
            self.lock_timer = None
            self.lock_acquired = False
            self.timers = []
            self.tasks = []
            self.tasklet = None
            self.data_queue = green.WaitQueue(self.timer)
            self.value_queue = green.WaitQueue(self.timer)
            self.running = False

        def setup(self):
            """acquire lock fom actuator agent"""
            super(Agent, self).setup()
           
        @matching.match_exact(topics.DEVICES_VALUE(point='CoolCall1', **rtu_path))    
        def dr_signal(self, topic, headers, message, match):
            data = jsonapi.loads(message[0])
            if not self.running and bool(data):
                print("start")
                self.running = True
                time_now = time.mktime(datetime.datetime.now().timetuple())
                self.update_schedule_state(time_now)
                #self.schedule(next_time, self.update_schedule_state)
                if (self.schedule_state):
                    self.start()
                else:
                    _log.debug("DR signal is False or day is not an occupied day")
                    
        def update_schedule_state(self, unix_time):
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            now = datetime.datetime.fromtimestamp(unix_time)
            day=now.weekday()
            if Schedule[day]:
                self.schedule_state = True
                #TODO: set this up to handle platform not running. 
                #This will hang after a while otherwise.
                self.lock_timer = super(Agent, self).periodic_timer(1, self.publish, topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)
            else:
                self.schedule_state = False
                self.publish(topics.ACTUATOR_LOCK_RELEASE(**rtu_path), headers)  
            
        @matching.match_exact(topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path))
        def _on_lock_sent(self, topic, headers, message, match):
            """lock request received"""
            self.lock_timer.cancel()

        @matching.match_exact(topics.ACTUATOR_LOCK_RESULT(**rtu_path))
        def _on_lock_result(self, topic, headers, message, match):
            """lock result"""
            msg = jsonapi.loads(message[0])
            holding_lock = self.lock_acquired
            if headers['requesterID'] == agent_id:
                self.lock_acquired = msg == 'SUCCESS'
            elif msg == 'SUCCESS':
                self.lock_acquired = False
            if self.lock_acquired and not holding_lock:
                self.start()

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def _on_new_data(self, topic, headers, message, match):
            """watching for new data"""
            data = jsonapi.loads(message[0])
            self.data_queue.notify_all(data)
            
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **rtu_path))
        def _on_set_result(self, topic, headers, message, match):
            """set value in conroller"""
            self.value_queue.notify_all((match.group(1), True))
    
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def _on_set_error(self, topic, headers, message, match):
            """watch for actuator error"""
            self.value_queue.notify_all((match.group(1), False))

        def _sleep(self, timeout=None):
            """built in sleep in green"""
            _log.debug('sleep({})'.format(timeout))
            green.sleep(timeout, self.timer)

        def _get_new_data(self, timeout=data_timeout):#timeout=data_timeout
            """wait for new data"""
            _log.debug('get_new_data({})'.format(timeout))
            return self.data_queue.wait(timeout)

        def _command_equip(self, point_name, value, timeout):
            """set value in controller"""
            _log.debug('set_point({}, {}, {})'.format(point_name, value, timeout))
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.publish(topics.ACTUATOR_SET(point=point_name, **rtu_path),
                         headers, str(value))
            while True:
                point, success = self.value_queue.wait(timeout)
                if point == point_name:
                    if success:
                        return
                    raise CommandSetError()
                    
            
        def _time_out(self):
            """if timeout occurs"""
            if (self.fan1_norm and self.fan2_norm and 
              self.min_damper and self.csp_norm):
                try:
                    self._command_equip('CoolSupplyFanSpeed1', self.fan1_norm)
                    self._command_equip('CoolSupplyFanSpeed2', self.fan2_norm)
                    self._command_equip('ESMDamperMinPosition', self.min_damper)
                    self._command_equip('StandardDamperMinPosition', self.csp_norm)
                except green.Timeout:
                    pass
            for timer in self.timers:
                timer.cancel()
            del self.timers[:]
            current = greenlet.getcurrent()
            for task in self.tasks:
                if task is not current:
                    task.parent = current
                    task.throw()
            print 'adding current task to task list'
            self.tasks[:] = [current]
            self._sleep(600)#If controller loses volttron heartbeat will reset
            self.running = False
         
        @matching.match_exact(topics.DEVICES_VALUE(point='Occupied', **rtu_path)) # for now look for Occuppied, DR Override will be added
        def _override(self, topic, headers, message, match):
            """watch for override from controller"""
            data = jsonapi.loads(message[0])
            if not bool(data):
                self.greenlet(self._on_override)
                

        def _on_override(self): 
            if not self.override_flag:
                self.override_flag = True
                _log.debug("Override initiated")
                for timer in self.timers:
                    timer.cancel()
                del self.timers[:]
                current = greenlet.getcurrent()
                for task in self.tasks:
                    if task is not current:
                        task.parent = current
                        task.throw()
            if self.fan1_norm:        
                try:
                    self._command_equip('CoolSupplyFanSpeed1', self.fan1_norm)
                    self._command_equip('CoolSupplyFanSpeed2', self.fan2_norm)
                    self._command_equip('ESMDamperMinPosition', self.min_damper )
                    self._command_equip('ReturnAirCO2Stpt', self.csp_norm)
                except green.Timeout:
                    self._sleep(43200) #if override wait for 12 hours then resume
                    self._go()        #catalyst will default to original operations with no volttron heatbeat
                self._sleep(43200)
                self.override_flag = False
                self.running = False
            elif  not self.fan1_norm and not self.override_flag:
                self.override_flag = True
                self._sleep(43200)
                self.override_flag=False
                self.running = False
            
                     
        def start(self):
            """Starting point for DR application"""
            self.override_flag = False
            self.greenlet(self._go)
        
        def _go(self):
            """start main DR procedure"""
            self._command_equip('StandardDamperChangeOverSetPoint', 75,20)
            self._command_equip('CoolSupplyFanSpeed2', 90,20)
            self._command_equip('CoolSupplyFanSpeed1', 75,20)
            self._command_equip('StandardDamperMinPosition', 65,20)
            try:
                self._command_equip('ESMDamperMinPosition', 5,20)
                
                voltron_data = self._get_new_data()
            except CommandSetError:
                self._time_out()
            except green.Timeout:
                self._time_out()
            self.min_damper = float(voltron_data["ESMDamperMinPosition"]) 
            self.fan1_norm = float(voltron_data["CoolSupplyFanSpeed1"])
            self.fan2_norm = float(voltron_data["CoolSupplyFanSpeed2"])
            self.csp_norm = float(voltron_data["ReturnAirCO2Stpt"])
            _log.debug("Zone normal cooling temperature setpoint:  " + repr(self.csp_norm))
            _log.debug("Supply fan cooling speed 1:  " + repr(self.fan1_norm))
            _log.debug("Supply fan cooling speed 2:  " + repr(self.fan2_norm))
            _log.debug("Normal minimum damper position:  " + repr(self.min_damper))
            self.get_signal()
                
        def _pre_cpp_timer(self):
            """Schedule to run in get_signal"""
            _log.debug("Pre-cooling for CPP Event")  #pre-cool change cooling set point
            self._pre_csp()
            self.pre_timer = self.periodic_timer(settings.pre_time, self._pre_cpp_cooling)
            
        def _pre_cpp_cooling(self):
            """start pre cooling procedure"""
            self.greenlet(self._pre_csp)
            
        def _pre_csp(self):
            """set cooling temp set point"""
            try:
                voltron_data = self._get_new_data()
            except green.Timeout:
                self._time_out()
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            if csp_now > csp_pre and not csp < csp_pre:
                try:
                    csp = csp_now - self.cooling_slope
                    self._command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self._time_out()
            elif csp_now <= csp_pre and not csp < csp_pre:
                try:
                    self._command_equip("ReturnAirCO2Stpt", settings.csp_pre)
                except green.Timeout:
                    self._time_out()
                self.pre_timer.cancel()
                
        def _accelerated_pre_cpp_timer(self):
            """if DR signal is received after normal pre"""
            _log.debug("Pre-cooling for CPP Event")  #pre-cool change cooling set point
            self._accelerated_pre_csp()
            self.pre_timer = self.periodic_timer(settings.pre_time, self._accelerated_cpp_cooling) 
              
        def _accelerated_cpp_cooling(self):
            """start accelerated pre-cooling"""
            self.greenlet(self._accelerated_pre_csp)
                
        def _accelerated_pre_csp(self):
            """set cooling temp set point"""
            _log.debug("Accelerated pre-cooling for CPP Event")
            try:
                voltron_data = self._get_new_data()
            except green.Timeout:
                self._time_out()  
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            csp  = csp_now - self.accel_slope
            if csp_now > csp_pre and not csp < csp_pre:
                try:
                    self._command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self._time_out()
            elif csp_now <= csp_pre or csp < csp_pre:
                try:
                    self._command_equip("ReturnAirCO2Stpt", settings.csp_pre)
                except green.Timeout:
                    self._time_out()
                self.pre_timer.cancel() 

        def _during_cpp_timer(self):
            """during CPP scheduled in get_signal"""
            self.greenlet(self._during_cpp)
                  
        def _during_cpp(self):
            """start CPP procedure"""
              # remove when done testing
            _log.debug("During CPP Event")
            damper_cpp = settings.damper_cpp
            fan_reduction = settings.fan_reduction
            csp_cpp = settings.csp_cpp
            cpp_fan1 = self.fan1_norm - self.fan1_norm * fan_reduction
            cpp_fan2 = self.fan2_norm - self.fan2_norm * fan_reduction
            try:
                self._command_equip("CoolSupplyFanSpeed1", cpp_fan1)
                self._command_equip("CoolSupplyFanSpeed2", cpp_fan2)
                self._command_equip("ReturnAirCO2Stpt", csp_cpp)
                self._command_equip('ESMDamperMinPosition', damper_cpp)
            except green.Timeout:
                self._time_out()
            
        def _after_cpp_timer(self):
            """after CPP scheduled in get_signal"""
            self.greenlet( self._restore_fan_damper)
            _log.debug("After CPP Event, returning to normal operations")
            self.greenlet(self._restore_cooling_setpoint)
            timer = settings.after_time
            self.after_timer = self.periodic_timer(timer, self._after_cpp_cooling)
             
        def _after_cpp_cooling(self):
            """Start after CPP procedure"""
            _log.debug("After_CPP_COOLING")
            self.greenlet(self._restore_cooling_setpoint)
            
        def _restore_fan_damper(self):
            """restore original fan speeds"""
            try:
                self._command_equip("ESMDamperMinPosition", self.min_damper)
                self._command_equip("CoolSupplyFanSpeed1", self.fan1_norm)
                self._command_equip("CoolSupplyFanSpeed2", self.fan2_norm)
            except green.Timeout:
                self._time_out()
            
        def _restore_cooling_setpoint(self):
            """restore normal cooling temp setpoint"""
            try:
                voltron_data = self._get_new_data()
            except green.Timeout:
                self._time_out()
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            if csp_now > self.csp_norm:
                csp = csp_now - self.cooling_slope
                try:
                    self._command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self._time_out()
            elif csp_now <= self.csp_norm:
                self.after_timer.cancel()
                try:
                    self._command_equip("ReturnAirCO2Stpt", self.csp_norm)
                    self._sleep(60)
                    self.running = False
                except green.Timeout:
                    self._time_out()
                
        def periodic_timer(self, *args, **kwargs):
            timer = super(Agent, self).periodic_timer(*args, **kwargs)
            self.timers.append(timer)
            return timer

        def schedule(self, time, event):
            super(Agent, self).schedule(time, event)
            self.timers.append(event)
        
        def greenlet(self, *args, **kwargs):
            task = greenlet.greenlet(*args, **kwargs)
            self.tasks.append(task)
            current = greenlet.getcurrent()
            if current.parent is not None:
                task.parent = current.parent
            task.switch()

        def get_signal(self):
            """get and format DR signal and schedule DR proc."""
            time_now = time.mktime(datetime.datetime.now().timetuple())
            time_pre = time.mktime(datetime.datetime.now().replace(hour=settings.pre_cpp_hour, minute=0, second=0, microsecond=0).timetuple())
            time_event = time.mktime(datetime.datetime.now().replace(hour=settings.during_cpp_hour, minute=12, second=0, microsecond=0).timetuple())
            time_after = time.mktime(datetime.datetime.now().replace(hour=settings.after_cpp_hour, minute=14, second=0, microsecond=0).timetuple())
        
            if (settings.signal and time_now<time_pre):
                _log.debug ("Scheduling1") 
                time_step = settings.pre_time / 3600
                #self.cooling_slope = (self.csp_norm - settings.csp_pre) / ((((time_event - time_pre) / 3600) - 0.5) * time_step) 
                self.cooling_slope = 1  # for testing use a constant
                temp = ((time_event - time_pre) / 3600)
                _log.debug ("cooling slope: " + repr(self.cooling_slope))
                self.schedule(time_pre, sched.Event(self._pre_cpp_timer))
                self.schedule(time_event, sched.Event(self._during_cpp_timer))
                after_cpp_time = datetime.datetime.now().replace(hour=settings.after_cpp_hour, minute=59, second=0, microsecond=0)
                self.schedule(time_after, sched.Event(self._after_cpp_timer))
                #self.start_timer.cancel()
            elif(settings.signal and time_now>time_pre and time_now<time_event):
                _log.debug("Scheduling2")
                #self.start_timer.cancel()
                #self.accel_slope = (self.csp_norm - settings.csp_pre) / ((time_event - time_now) / (3600))
                self.accel_slope = 2 #for testing use a constant
                #self.cooling_slope = (self.csp_norm - settings.csp_pre) / ((((time_event - time_pre) / 3600) - 0.5) * time_step) 
                self.cooling_slope = 1  # for testing use a constant
                self.schedule(time_event, sched.Event(self._during_cpp_timer))
                self.schedule(time_after, sched.Event(self._after_cpp_timer))
                self._accelerated_pre_cpp_timer() 
            elif(settings.signal and time_now>time_event and time_now<time_after):
                _log.debug("Too late to pre-cool!")
                #self.start_timer.cancel()
                self.schedule(time_after, sched.Event(self._after_cpp_timer))
                self._during_cpp()
            else:
                _log.debug("CPP Event Is Over")
                #self.start_timer.cancel()
                self._sleep(60)
                self.get_signal()
                
    Agent.__name__ = 'DemandResponseAgent'
    return Agent(**kwargs)


def main(argv = sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(DemandResponseAgent,
                       description = 'VOLTTRON platform™ DR agent',
                       argv=argv)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
   
