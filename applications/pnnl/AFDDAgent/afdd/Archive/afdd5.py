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

'''
Created on Jul 8, 2013

@author: d3x533
modified 7/29/13 by lute362
'''


import sys
import math
import settings

class ExcessiveOutdoorAir:
    '''
    classdocs
    '''

    def __init__(self, parent):
        '''
        Constructor
        Create Excessive Outdoor Air Module
        '''
        self._parent = parent
    
        
    def run(self,voltron_data):
        sleeptime=settings.sleeptime
        minutes_to_average=settings.minutes_to_average
        afdd5_threshold=settings.afdd5_threshold
        min_oa=settings.min_oa
        minimum_damper_command=settings.minimum_damper_command
        voltron_data = self._parent.get_new_data()
        damper = float(voltron_data[self.damper_name])
        mixed_air_temperature = float(voltron_data[mat_name])
        outdoor_air_temperature = float(voltron_data[ self.oat_name])
        return_air_temperature  = float(voltron_data[self.rat_name])
        cool_call1 = int(voltron_data[self.coolcall1_name])
        cool_call2 = int(voltron_data[self.coolcall2_name])
        
        if not cool_call1  and not cool_call2 < 1:  #if there is no call or cooling air intake should be at ventilation minimum
            oaf = self.calculate_oaf(self.minutes_to_average, mat_name) # check OAF 
            print 'OAF:  ', oaf
            if(oaf - self.minimum_oa > self.afdd5_oaf_threshold): # Check to see if excess air is being brought into RTU
                if not self.mat_missing:
                    potential_cooling_savings = 1.08*self.cfm * ((0.05 * outdoor_air_temperature + 0.95*return_air_temperature)-mixed_air_temperature)
                    potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                    print 'fault kWh impact: ', potential_cooling_savings
                _log.debug("Excessive outdoor-air intake")
                return 51.0, potential_cooling_savings
            else:
                _log.debug("No fault detected during fault diagnostic")
                return 50.0, potential_cooling_savings           
        else: #Cooling is on 
            if (outdoor_air_temperature - self.afdd5_econ_differential) > return_air_temperature: #Check economizer condtions
                if (damper <= self.afdd5_min_damper): #Damper should be at minimum
                #OAF= [(mixed_air_temperature -return_air_temperature )/(outdoor_air_temperature -return_air_temperature )]
                    oaf = self.calculate_oaf(self.minutes_to_average, mat_name) #check OAF 
                    print 'OAF:  ', oaf
                    if(oaf - self.minimum_oa > self.afdd5_oaf_threshold): #Check to see if excess air is being brought into RTU
                        if not self.mat_missing:
                            potential_cooling_savings = 1.08*self.cfm * ((0.05 * outdoor_air_temperature + 0.95*return_air_temperature)-mixed_air_temperature)
                            potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                            print 'fault kWh impact: ', potential_cooling_savings
                        _log.debug("Excessive outdoor-air intake")
                        return 51.0, potential_cooling_savings
                    else:
                        _log.debug("No fault detected during fault diagnostic")
                        return 50.0, potential_cooling_savings
                else:
                    _log.debug("Damper should be at minimum, possible control fault")
                    return 53.0, potential_cooling_savings
            else:
                temp_diff = (return_air_temperature +  self.afdd5_econ_differential) - outdoor_air_temperature
                status = self.command_outdoor_air_temperature_bias(temp_diff + self.afdd5_econ_differential)
            
                if not (status):
                    _log.debug("Outside-air temperature bias was not set, controller lock error")    
                    return 54.0, potential_cooling_savings
            
                self._agent.sleep(self.seconds_to_steady_state)
                voltron_data = self._agent.get_new_data()
                mixed_air_temperature = float(voltron_data[mat_name])
                outdoor_air_temperature = float(voltron_data[ self.oat_name])
                return_air_temperature  = float(voltron_data[self.rat_name])
                damper = float(voltron_data[self.damper_name])
            
                if damper > self.afdd5_min_damper:
                    _log.debug("Damper will not close, possible control fault")
                    if not self.mat_missing:
                        potential_cooling_savings = 1.08 * self.cfm *((0.05 * outdoor_air_temperature + 0.95 * return_air_temperature) - mixed_air_temperature)
                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                    return 53.0, potential_cooling_savings

                #OAF= [(mixed_air_temperature -return_air_temperature )/(outdoor_air_temperature -return_air_temperature )]
                oaf = self.calculate_oaf(self.minutes_to_average, mat_name)
                if(oaf - self.minimum_oa > self.afdd5_oaf_threshold):
                    if not self.mat_missing:
                        voltron_data = self._agent.get_new_data()                    
                        mixed_air_temperature  = float(voltron_data[self.mat_name])
                        outdoor_air_temperature  = float(voltron_data[ self.oat_name])
                        return_air_temperature  = float(voltron_data[self.rat_name])
                        potential_cooling_savings = 1.08 * self.cfm *((0.05 * outdoor_air_temperature + 0.95 * return_air_temperature) - mixed_air_temperature)
                        potential_cooling_savings = potential_cooling_savings/(1000*self.EER)
                    print 'fault kWh impact: ', potential_cooling_savings
                    _log.debug("Excessive outdoor-air intake")
                    return 51.0, potential_cooling_savings
                else:
                    potential_cooling_savings = 0
                    _log.debug("No fault detected during fault diagnostic")
                    return 50.0, potential_cooling_savings
###################################################################################################  
    def log_message(self,msg):
        _log.debug(code)  
        
        
    def sleep(self,sleeptime):
        self._parent.sleep(sleeptime)
        
        
             
    def log_status(self,code):
        # print or log code and exit  
        # need to release OAtemp_vpoint and CoolCall1
        
        _log.debug(code)
        
    def command_outdoor_air_temperature_vpoint(self,value):
        """ Command outdoor air damper to a new position """
        status = 0
        status = self._parent.command_equip("OutsideAirTemperaturevirtualpoint",value)
        if not status:
            return False
        return True
    
    def calculate_oaf(self,num_minutes, sleeptime):
        oaf = 0.
        return_air_temperature = 0.
        mixed_air_temperature = 0.
        outdoor_air_temperature-0
        n = 0
        
        for n in range(1, num_minutes):
            
            voltron_data = self._parent.get_new_data()
            
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"]) # Point name follows RTUNetwork wiki)
            return_air_temperature = float(voltron_data["ReturnAirTemperature"]) # Point name follows RTUNetwork wiki)
            outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
            oaf +=(mixed_air_temperature-return_air_temperature)/(outdoor_air_temperature-return_air_temperature)
            sleep(sleeptime) # Pause for 60 seconds
            
        oaf = oaf/n
        return oaf
          
            
