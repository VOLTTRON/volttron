# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
# pylint: disable-msg=C0103
# pylint: disable-msg=W0142
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
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
import logging
import sys
import settings
import greenlet
from zmq.utils import jsonapi
from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import topics
#from volttron.platform.messaging import headers as headers_mod
import time
import datetime
global fan1_norm
global fan2_norm
global csp_norm 
global min_damper
global accel_slope
global cooling_slope
global override_flag
fan1_norm = 0
fan2_norm = 0
csp_norm = 0
accel_slope = 0
cooling_slope = 0
min_damper = 0
override_flag = False
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

    
def dragent(config_path, **kwargs):
    """DR application for time of use pricing"""
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
   
    class Agent(PublishMixin, BaseAgent):
        """Class agent"""
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.lock_timer = None
            self.lock_acquired = False
            self.tasklet = None
            self.data_queue = green.WaitQueue(self.timer)
            self.value_queue = green.WaitQueue(self.timer)

        def setup(self):
            """acquire lock fom actuator agent"""
            super(Agent, self).setup()
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.lock_timer = self.periodic_timer(1, self.publish, topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)
            
        @matching.match_exact(topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path))
        def __on_lock_sent(self, topic, headers, message, match):
            """lock recieved"""
            self.lock_timer.cancel()

        @matching.match_exact(topics.ACTUATOR_LOCK_RESULT(**rtu_path))
        def __on_lock_result(self, topic, headers, message, match):
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
        def __on_new_data(self, topic, headers, message, match):
            """watching for new data"""
            data = jsonapi.loads(message[0])
            self.data_queue.notify_all(data)
            
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **rtu_path))
        def __on_set_result(self, topic, headers, message, match):
            """set value in conroller"""
            self.value_queue.notify_all((match.group(1), True))
    
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def __on_set_error(self, topic, headers, message, match):
            """watch for actuator error"""
            self.value_queue.notify_all((match.group(1), False))

        def __sleep(self, timeout=None):
            """built in sleep in green"""
            #_log.debug('sleep({})'.format(timeout))
            green.sleep(timeout, self.timer)

        def __get_new_data(self, timeout=None):
            """wait for new data"""
            _log.debug('get_new_data({})'.format(timeout))
            return self.data_queue.wait(timeout)

        def __command_equip(self, point_name, value, timeout=None):
            """set value in controller"""
            _log.debug('set_point({}, {}, {})'.format(point_name, value, timeout))
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.publish(topics.ACTUATOR_SET(point=point_name, **rtu_path),
                         headers, str(value))
            try:
                return self.value_queue.wait(timeout)
            except green.Timeout:
                return None
            
        def __time_out(self):
            """if timeout occurs"""
            global fan1_norm
            global fan2_norm
            global csp_norm 
            global min_damper
            if fan1_norm == 0:
                self.__sleep(600)#If controller loses volttron heartbeat will reset
                self.start()     #wait at least this long 
            else:
                try:
                    self.__command_equip('CoolSupplyFanSpeed1', fan1_norm)
                except green.Timeout:
                    self.__sleep(600)
                    self.start()
                try:
                    self.__command_equip('CoolSupplyFanSpeed2', fan2_norm)
                except green.Timeout:
                    self.__sleep(600)
                    self.start()
                try:
                    self.__command_equip('ESMDamperMinPosition', min_damper)
                except green.Timeout:
                    self.__sleep(600)
                    self.start()
                try:
                    self.__command_equip('ReturnAirCO2Stpt', csp_norm)
                except green.Timeout:
                    self.__sleep(600)
                    self.start() 
            
         
        @matching.match_exact(topics.DEVICES_VALUE(point='Occupied', **rtu_path))
        def __overide(self, topic, headers, message, match):
            """watch for override from controller"""
            data = jsonapi.loads(message[0])
            if not bool(data):
                self.tasklet = greenlet.greenlet(self.__on_override)
                self.tasklet.switch()
                

        def __on_override(self): 
            global fan1_norm
            global fan2_norm
            global csp_norm
            global min_damper
            global override_flag
            
            if fan1_norm != 0 and not override_flag:
                override_flag = True
                _log.debug('Override initiated')
                try:
                    self.__command_equip('CoolSupplyFanSpeed1', fan1_norm)
                except green.Timeout:
                    self.__sleep(43200) #if override wait for 12 hours then resume
                    self.start()        #catalyst will default to original operations with no volttron heatbeat
                try:
                    self.__command_equip('CoolSupplyFanSpeed2', fan2_norm)
                except green.Timeout:
                    self.__sleep(43200)
                    self.start()
                try:
                    self.__command_equip('ESMDamperMinPosition', min_damper )
                except green.Timeout:
                    self.__sleep(43200)
                    self.start()
                try:
                    self.__command_equip('ReturnAirCO2Stpt', csp_norm)
                except green.Timeout:
                    self.__sleep(43200)
                    self.start()
            elif fan1_norm == 0 and not override_flag:
                override_flag = True
                self.__sleep(43200)
                self.start()
                
                    
        def start(self):
            """Starting point for DR application"""
            global override
            override_flag = False
            self.tasklet = greenlet.greenlet(self.__go)
            self.tasklet.switch()
        
        def __go(self):
            """start main DR procedure"""
            #self.__command_equip('CoolSupplyFanSpeed1', 75)
            #self.__command_equip('CoolSupplyFanSpeed2', 90)
            #self.__command_equip('ESMDamperMinPosition', 5)
            global fan1_norm
            global fan2_norm
            global csp_norm
            global min_damper
            try:
                self.__command_equip('ReturnAirCO2Stpt', 74)
            except green.Timeout:
                self.__time_out()
            try:
                voltron_data = self.__get_new_data()
            except green.Timeout:
                self.__time_out()
                # Gracefully handle exception
            min_damper = float(voltron_data["ESMDamperMinPosition"]) 
            fan1_norm = float(voltron_data["CoolSupplyFanSpeed1"])
            fan2_norm = float(voltron_data["CoolSupplyFanSpeed2"])
            csp_norm = float(voltron_data["ReturnAirCO2Stpt"])
            _log.debug("Zone normal cooling temperature setpoint:  " + repr(csp_norm))
            _log.debug("Supply fan cooling speed 1:  " + repr(fan1_norm))
            _log.debug("Supply fan cooling speed 2:  " + repr(fan2_norm))
            _log.debug("Normal minimum damper position:  " + repr(min_damper))
            self.tasklet = greenlet.greenlet(self.get_signal)
            self.tasklet.switch()
                
        def __pre_cpp_timer(self):
            """Schedule to run in get_signal"""
            _log.debug("Pre-cooling for CPP Event")  #pre-cool change cooling set point
            self.tasklet = greenlet.greenlet(self.__pre_csp)
            self.tasklet.switch()
            self.pre_timer = self.periodic_timer(settings.pre_cooling_time, self.__pre_cpp_cooling)
            
        def __pre_cpp_cooling(self):
            """start pre cooling procedure"""
            self.tasklet = greenlet.greenlet(self.__pre_csp)
            self.tasklet.switch()
            
        def __pre_csp(self):
            """set cooling temp. set point"""
            self.__sleep(1)
            try:
                voltron_data = self.__get_new_data()
            except green.Timeout:
                self.__time_out()
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            if csp_now > settings.csp_pre:
                try:
                    csp = csp_now - cooling_slope
                    self.__command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self.__time_out()
            elif csp_now <= settings.csp_pre:
                try:
                    self.__command_equip("ReturnAirCO2Stpt", settings.csp_pre)
                except green.Timeout:
                    self.__time_out()
                self.pre_timer.cancel()
                
        def __accelerated_pre_cpp_timer(self):
            """if DR signal is received after normal pre"""
            _log.debug("Pre-cooling for CPP Event")  #pre-cool change cooling set point
            self.tasklet = greenlet.greenlet(self.__accelerated_pre_csp)
            self.tasklet.switch()
            self.pre_timer = self.periodic_timer(settings.pre_time, self.__accelerated_cpp_cooling) 
              
        def __accelerated_cpp_cooling(self):
            """start accelerated pre-cooling"""
            self.tasklet = greenlet.greenlet(self.__accelerated_pre_csp)
            self.tasklet.switch()
                
        def __accelerated_pre_csp(self):
            """set cooling temp set point"""
            _log.debug("Accelerated pre-cooling for CPP Event")
            global accel_slope
            self.__sleep(2)
            try:
                voltron_data = self.__get_new_data()
            except green.Timeout:
                self.__time_out()  
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            csp  = csp_now - accel_slope
            if csp_now > settings.csp_pre:
                try:
                    self.__command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self.__time_out()
            elif csp_now <= settings.csp_pre:
                try:
                    self.__command_equip("ReturnAirCO2Stpt", settings.csp_pre)
                except green.Timeout:
                    self.__time_out()
                self.pre_timer.cancel() 

        def __during_cpp_timer(self):
            """during CPP scheduled in get_signal"""
            self.tasklet = greenlet.greenlet(self.__during_cpp)
            self.tasklet.switch() 
                  
        def __during_cpp(self):
            """start CPP procedure"""
            _log.debug("During CPP Event")# remove when done testing
            self.__sleep(2)
            global fan1_norm
            global fan2_norm
            cpp_damper = settings.cpp_damper
            fan_reduction = settings.fan_reduction
            cpp_csp = settings.cpp_csp
            cpp_fan1 = fan1_norm- fan1_norm * fan_reduction
            cpp_fan2 = fan2_norm- fan2_norm * fan_reduction
            self.__sleep(1)
            try:
                self.__command_equip("CoolSupplyFanSpeed1", cpp_fan1)
            except green.Timeout:
                self.__time_out()
            try:
                self.__command_equip("CoolSupplyFanSpeed2", cpp_fan2)
            except green.Timeout:
                self.__time_out()
            try:
                self.__command_equip("ReturnAirCO2Stpt", cpp_csp)
            except green.Timeout:
                self.__time_out()
            try:
                self.__command_equip('ESMDamperMinPosition', cpp_damper)
            except green.Timeout:
                self.__time_out()
            
        def __after_cpp_timer(self):
            """after CPP scheduled in get_signal"""
            self.tasklet = greenlet.greenlet(self.__restore_fan_damper)
            self.tasklet.switch()
            _log.debug("After CPP Event, returning to normal operations")
            self.tasklet = greenlet.greenlet(self.__restore_cooling_setpoint)
            self.tasklet.switch()
            timer = settings.after_time
            self.after_timer = self.periodic_timer(timer, self.__after_cpp_cooling)
             
        def __after_cpp_cooling(self):
            """Start after CPP procedure"""
            _log.debug("After_CPP_COOLING")
            self.tasklet = greenlet.greenlet(self.__restore_cooling_setpoint)
            self.tasklet.switch()
            
        def __restore_fan_damper(self):
            """restore original fan speeds"""
            global fan1_norm
            global fan2_norm
            global min_damper
            self.__sleep(2) # so screen _log.debugs in correct order remove after testing.
            try:
                self.__command_equip("ESMDamperMinPosition", min_damper)
            except green.Timeout:
                self.__time_out()
            try:
                self.__command_equip("CoolSupplyFanSpeed1", fan1_norm)
            except green.Timeout:
                self.__time_out()
            try:
                self.__command_equip("CoolSupplyFanSpeed2", fan2_norm)
            except green.Timeout:
                self.__time_out()
            
        def __restore_cooling_setpoint(self):
            """restore normal cooling temp setpoint"""
            global csp_norm
            self.__sleep(2) #remove after testing
            try:
                voltron_data = self.__get_new_data()
            except green.Timeout:
                self.__time_out()
            csp_now = float(voltron_data["ReturnAirCO2Stpt"]) 
            if csp_now > csp_norm:
                csp = csp_now - cooling_slope
                try:
                    self.__command_equip("ReturnAirCO2Stpt", csp)
                except green.Timeout:
                    self.__time_out()
            elif csp_now <= csp_norm:
                self.after_timer.cancel()
                try:
                    self.__command_equip("ReturnAirCO2Stpt", csp_norm)
                except green.Timeout:
                    self.__time_out()
                
        def get_signal(self):
            """get and format DR signal and schedule DR proc."""
            #Pull signal from source
            self.__sleep(2) #remove after testing
            global csp_norm
            global cooling_slope
            global accel_slope
            time_now = time.mktime(datetime.datetime.now().timetuple())
            time_pre = time.mktime(datetime.datetime.now().replace(hour = settings.pre_cpp_hour, minute = 23, second=0, microsecond = 0).timetuple())
            time_event = time.mktime(datetime.datetime.now().replace(hour = settings.during_cpp_hour, minute = 25, second = 0, microsecond = 0).timetuple())
            time_after = time.mktime(datetime.datetime.now().replace(hour = settings.after_cpp_hour, minute = 27, second = 0, microsecond = 0).timetuple())
            if (settings.signal and time_now<time_pre):
                _log.debug ("Scheduling1") 
                time_step = settings.pre_cooling_time/3600
                #cooling_slope = (csp_norm-settings.csp_pre)/((((time_event-time_pre)/3600)-0.5)*time_step) 
                cooling_slope = 1  # for testing use a constant
                temp = ((time_event-time_pre)/3600)
                _log.debug ("cooling slope: "+ repr(cooling_slope))
                pre_cpp_time = datetime.datetime.now().replace(hour = settings.pre_cpp_hour, minute = 23, second = 0, microsecond = 0)
                self.schedule(pre_cpp_time, sched.Event(self.__pre_cpp_timer))
                during_cpp_time = datetime.datetime.now().replace(hour = settings.during_cpp_hour, minute=25, second = 0, microsecond = 0)
                self.schedule(during_cpp_time, sched.Event(self.__during_cpp_timer))
                after_cpp_time = datetime.datetime.now().replace(hour = settings.after_cpp_hour, minute = 27, second = 0, microsecond = 0)
                self.schedule(after_cpp_time, sched.Event(self.__after_cpp_timer))
                #self.start_timer.cancel()
            elif(settings.signal and time_now>time_pre and time_now<time_event):
                _log.debug("Scheduling2")
                #self.start_timer.cancel()
                #accel_slope = (csp_norm-settings.csp_pre)/((time_event-time_now)/(3600))
                accel_slope = 2 #for testing use a constant
                during_cpp_time = datetime.datetime.now().replace(hour = settings.during_cpp_hour, minute = 36, second =20, microsecond = 0)
                self.schedule(during_cpp_time, sched.Event(self.__during_cpp_timer))
                after_cpp_time = datetime.datetime.now().replace(hour = settings.after_cpp_hour, minute = 39, second = 10, microsecond = 0)
                self.schedule(after_cpp_time, sched.Event(self.__after_cpp_timer))
                self.__accelerated_pre_cpp_timer() 
            elif(settings.signal and time_now>time_event and time_now<time_after):
                _log.debug("Too late to pre-cool!")
                #self.start_timer.cancel()
                after_cpp_time = datetime.datetime.now().replace(hour=settings.after_cpp_hour, minute = 17, second = 0, microsecond = 0)
                self.schedule(after_cpp_time, sched.Event(self.__after_cpp_timer))
                self.tasklet = greenlet.greenlet(self.__during_cpp)
                self.tasklet.switch()
            else:
                _log.debug("CPP Event Is Over")
                #self.start_timer.cancel()
                self.__sleep(60)
                self.get_signal()
                
    Agent.__name__ = 'dragent'
    return Agent(**kwargs)


def main(argv = sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(dragent,
                       description = 'VOLTTRON platform™ DR agent',
                       argv=argv)
if __name__ == "__main__":
    main()
