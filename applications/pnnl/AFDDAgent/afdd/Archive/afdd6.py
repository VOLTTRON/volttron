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
modified 8/2/13 by lute362
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
        damper=float(voltron_data["DamperSignal"])
        mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
        outdoor_air_temperature = float(voltron_data["OutdoorAirTemperature"])
        return_air_temperature  = float(voltron_data["ReturnAirTemperature"])
        
        if(math.fabs(outdoor_air_temperature-return_air_temperature)>4):
              
                if (damper <= minimum_damper_command): #economizer is off
                #OAF= [(mixed_air_temperature -return_air_temperature )/(outdoor_air_temperature -return_air_temperature )]
                    oaf = self.calculate_oaf(self,minutes_to_average,sleeptime)
                    
                    if(min_oa-oaf> afdd6_threshold):
                        afdd5=61
                        self.log_status("Insufficient outdoor air intake")
                        return afdd5
                    else:
                        afdd5=60
                        self.log_status("No fault detected during fault diagnostic")
                        return afdd5
                else: #economizer is on.
                # set the outside Air temp to the Return Air Temp + 10 degrees
                # if correct check the fraction again. 
                    status=self.command_outdoor_air_temperature_vpoint(return_air_temperature+10)
                    
                    if not (status):
                        afdd3=69
                        self.log_status("Lock not received from Catalyst")    
                        return afdd3
                    
                    self.sleep(sleeptime)
                    voltron_data = self._parent.get_new_data()
                    damper=float(voltron_data["DamperSignal"])
                    
                    if damper > minimum_damper_command:
                        afdd5=68
                        self.log_status("Damper will not close diagnostic can not continue")
                          
                    self.sleep(time_to_steady_state)
                 
                    #OAF= [(mixed_air_temperature -return_air_temperature )/(outdoor_air_temperature -return_air_temperature )]
                    oaf = self.calculate_oaf(self,minutes_to_average,sleeptime)
                    if(min_oa-oaf> afdd5_threshold):
                        afdd5=61
                        self.log_status("Insufficient outdoor-air intake")
                        return afdd5
                    else:
                        afdd=60
                        self.log_status("No fault detected during fault diagnostic")

        self.log_status("Fault diagnostic prerequisites not met at this time, unable to proceed")
        return
        
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
        
        for n in range(num_minutes):
            
            voltron_data = self._parent.get_new_data()
            
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"]) # Point name follows RTUNetwork wiki)
            return_air_temperature = float(voltron_data["ReturnAirTemperature"]) # Point name follows RTUNetwork wiki)
            outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
            oaf +=(mixed_air_temperature-return_air_temperature)/(outdoor_air_temperature-return_air_temperature)
            sleep(sleeptime) # Pause for 60 seconds
            
        oaf = oaf/num_minutes
        return oaf
          
