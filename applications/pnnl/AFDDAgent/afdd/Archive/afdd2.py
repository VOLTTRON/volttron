# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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

from math import abs
import settings

class TemperatureSensor:
    """
    Usage:  ...
    
        The purpose of this proactive diagnostic measure is to identify faulty 
        temperature sensors on a rooftop unit (RTU).  
    

    """

    def __init__(self, parent):
        """parent is the afddagent or whatever object creating an instance of this class
        """
        self._parent = parent

    def run(self,voltron_data):
        #Data from Voltron
        self.log_message("Rob: AFDD2 is running...")
        voltron_data = self._parent.get_new_data()
        
        
        #configuration file: afdd_config.ini
        seconds_to_steady_state = settings.seconds_to_steady_state #self._config["afdd2_seconds_to_steady_state"]
        afdd2_temperature_sensor_threshold = settings.afdd2_temperature_sensor_threshold

        # Main Algorithm
        status = sensor_error_check(self)
        if (status):
            status1=self.command_damper(0)
            if not status1:
                afdd2=29
                self.log_status("Lock not Received from controller to close damper")
                return afdd2

            self.sleep(seconds_to_steady_state)
            voltron_data = self._parent.get_new_data()
            return_air_temperature = float(voltron_data["ReturnAirTemperature"])
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
            sensorcondition_1=math.fabs(mixed_air_temperature-return_air_temperature)# probably should do average over a number of minutes
    
            if sensorcondition_1 < afdd2_temperature_sensor_threshold:
                afdd2=21 #OA
                self.log_status("Outdoor-air temperature sensor problem")
                return afdd2
    
            status1=self.command_damper(100)
    
            if not status1:
                afdd2=29
                self.log_status("Lock not Received from controller to open damper")
                return afdd2
    
            self.sleep(seconds_to_steady_state)
            voltron_data = self._parent.get_new_data()
            outdoor_air_temperature = float(voltron_data["OutAirTemperature"])
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
            sensorcondition_2=math.fabs(mixed_air_temperature-outdoor_air_temperature)# probably should do average over a number of minutes
    
            if sensorcondition_2 < afdd2_temperature_sensor_threshold:
                afdd2=22
                self.log_status("Return-air temperature sensor problem")
                return afdd2
    
            #If it comes here => both tests fail
            afdd2=23
            self.log.status("Mixed-air temperature sensor problem")
            return afdd2
    
        afdd2=20
        self.log_status("No Temperature Sensor faults detected")
        return afdd2
    
    def sensor_error_check(self):
        status=0
        voltron_data = self._parent.get_new_data()
        return_air_temperature = float(voltron_data["ReturnAirTemperature"])
        outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
        mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
        
        if (mixed_air_temperature<outdoor_air_temperature and mixed_air_temperature<return_air_temperature):
            status=1
            return status
        if (mixed_air_temperature>outdoor_air_temperature and mixed_air_temperature>return_air_temperature):
            status=1
            return status
        return status
        
    def log_message(self,msg):
        _log.debug(code)
    
    def sleep(self,sleeptime):
        self._parent.sleep(sleeptime)
         
    def log_status(self,code):
        # print or log code and exit  ll
        # need to release OAtemp_vpoint and CoolCall1

        #print(code)
        _log.debug(code)

    def command_damper(self,command):
        """ Command outdoor air damper to a new position """
        status = self._parent.command_equip('DamperSignal',command)
        if not status:
            return False
        return True
    
    
    
