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

import math
import settings
from sys import exit


class damperModulation:
    """Detects problems with outdoor air damper system.

    Usage:  ...

    The purpose of this proactive diagnostic measure is to identify faulty 
    outdoor air damper (damper) system on a rooftop unit (RTU).  When the damper 
    (economizer damper) is not modulating it may result in lack of ventilation 
    or energy waste.  For example, if the damper is stuck in a fully closed 
    position, the RTU will fail to provide any ventilation and also leads to a 
    missed opportunity for free cooling, thus causing an energy penalty during 
    periods when free cooling is available.

    The OA damper will be commanded fully open and fully closed in sequence 
    through a proactive diagnostic approach. The outdoor air temperature, 
    mixed air temperature and return air temperature will be recorded until 
    the mixed air and return air temperatures reach steady state condition for 
    both commands.  By comparing the temperatures conclusions can be drawn as 
    to the state of the damper.

    First the process checks if the outdoor, return, mixed and discharge air 
    temperatures are within expected limits ...

    Then, the process checks if the conditions are favorable for the proactive 
    testing

    """
    
    def __init__(self, parent):
        """parent is the afddagent or whatever object creating an instance of this class
        """
        self._parent = parent
        config_json = resource_string(__name__, 'afdd_config.ini')
        self._config = json.ldampers(config_json)
    
    def run(self, voltron_data):
        #Data from Voltron
        voltron_data = self._parent.get_new_data()
        mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
        return_air_temperature = float(voltron_data["ReturnAirTemperature"])
        outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
        discharge_air_temperature = float(voltron_data["DischargeAirTemperature"])
        
        #Output from Preprocess: once a month: read from file
        oa_sensor_error = 0
        ra_sensor_error = 0
        ma_sensor_error = 0
       
        status = 0
        
        #settings file
        min_oa_temperature= settings.minoa_temperature
        max_oa_temperature = settings.maxoa_temperature
        afdd1_threshold1 = settings.afdd1_threshold1
        afdd1_threshold2 = settings.afdd1_threshold2
        oalow_limit = settings.oalow_limit
        oahigh_limit = settings.oalow_limit
        ralow_limit = settings.ralow_limit
        rahigh_limit = settings.rahigh_limit
        malow_limit = settings.malow_limit
        mahigh_limit = settings.mahigh_limit
        seconds_to_steady_state = settings.seconds_to_steady_state
        sleeptime = settings.sleeptime
        
    # check sensor accuracy
     
        if ((outdoor_air_temperature < oalow_limit) or (outdoor_air_temperature > oahigh_limit)):
            oa_sensor_error = 1
        if ((return_air_temperature < ralow_limit) or (return_air_temperature > rahigh_limit)):
            ra_sensor_error = 1
        if ((mixed_air_temperature < malow_limit) or (mixed_air_temperature > mahigh_limit)):
            ma_sensor_error = 1
            afdd1=11
            return afdd1
    
    # Verify conditions favorable for proactive diagnostics
        
        if ((outdoor_air_temperature > minoa_temperature)
            and (outdoor_air_temperature < maxoa_temperature) 
            and (math.fabs(return_air_temperature - outdoor_air_temperature) > afdd1_threshold1)):
            
            status = self.get_rtu_status()
            #Check RTU status, if the RTU compressor(s) is ON, turn it OFF in preparation
            #for proactive diagnostics ...
            self.sleep(sleeptime)
            if (status): 
                status = shutDown_rtu_compressor()
                #Turned off the compressor .... 
                #It may take a few minutes for the compressor to turn off, 
                #so need to pause for sometime and re-check the status 
        
                # could take up to 300 seconds
                for n in range(1, 5): 
                    status = get_rtu_status() 
                    if not (status): break
                    sleep(sleeptime)
                self.sleep(seconds_to_steady_state)
                if ((n == 5) and status):
                    ## log still running after 5 minutes ...
                    ## exit the function
                    self.log_status("Compressor still running 5 minutes after shutdown")
                    afdd1=18
                    return afdd1
            #Conditions appear to be favorable for proactive diagnostics
            #ready to launch proactive diagnostics!
                    
            #Command outdoor air damper to fully open position
            status=self.command_damper(100)
            self.sleep(sleeptime)
            if (status): # fully open position
                # Verify steady-state conditionl
                # wait for steady-state conditions to be established
                sleep(seconds_to_steady_state)
                diff_ra_ma1 = self.diff_ra_ma(5, sleeptime)
            else:
                # if status is not true or "1" need to do something?
                self.log_status("Damper command failed trying to open to fully open position")
                afdd1=19
                return afdd1
            
            status =self.command_damper(0)
            self.sleep(sleeptime)
            if (status): # fully closed position
                # wait for steady-state conditions to be established
                # Verify steady-state condition
                sleep(sectods_to_steady_state)
                diff_ra_ma2 = self.diff_ra_ma(5, sleeptime)
            else:
                # if status is not true or "1" need to do something?
                self.log_status("Damper command failed trying to close to fully closed position")
                afdd1=19
                return afdd1
            if (math.abs(diff_ra_ma1 - diff_ra_ma2) < afdd1_threshold2):
                self.log_status("No Modulation of outdoor-air damper")
                afdd1=12
                return afdd1
            else:
                # wait of conditions to be favorable ...
                self.log_status("Outdoor-air damper is modulating, no fault detected")
                afdd1=10
                return afdd1 
        else:   
            afdd1=17
            self.log_status("Conditions are not favorable for running fault diagnostic")
            return affd1
             
    def log_status(self,code):
        # print or log code and exit  
        print(code)
        
    def diff_ra_ma(self,num_minutes, sleeptime):
        diff_ra_ma = 0.
        return_air_temperature = 0.
        mixed_air_temperature = 0.
        n = 0
        
        for n in range(1, num_minutes):
            
            voltron_data = self._parent.get_new_data()
            
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"]) # Point name follows RTUNetwork wiki)
            return_air_temperature = float(voltron_data["ReturnAirTemperature"]) # Point name follows RTUNetwork wiki)
            diff_ra_ma += (return_air_temperature - mixed_air_temperature)
            sleep(sleeptime) # Pause for 60 seconds
            
        diff_ra_ma = diff_ra_ma/n
        return diff_ra_ma
      
    def command_damper(self,position):
        """ Command outdoor air damper to a new position """
        status = 0
        status = self._parent.command_equip("DamperSignal",position)
        return status
        
    def get_rtu_status(self):
        """ 
        Check heating and cooling status.  If the unit either heating or cooling, turn it off 
        """
        cooling_command = 0
       
        status = 0
        voltron_data = self._parent.get_new_data()
        
        cooling_command = boolean(voltron_data["CoolCommand1"]) # Point name follows RTUNetwork wiki
        if (cooling_command): 
            status = 1
        else: 
            status = 0
        
        return status
    
    def shutdown_rtu_compressor(self):
        """Shutdown the compressor, in preparation for the proactive testing
        """ 
        #TODO: send a compressor shutdown commend to the controller. What data point control this????
        status = 0
        status = self._parent.command_equip("CoolCommand1",0)
        
        return status
    def sleep(self,sleeptime):
        self._parent.sleep(sleeptime)
