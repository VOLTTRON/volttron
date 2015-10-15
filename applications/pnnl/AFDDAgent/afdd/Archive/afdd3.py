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
from time import sleep
import settings

class No_economizer:
    """Detects problems with economizer controls or operations.

    Usage:  ...

    The purpose of this proactive diagnostic measure is to identify faulty 
    economizer systems on a rooftop unit (RTU).  If the economizer does not
    operate when outdoor conditions are favorable for economizing there are
    missed opportunities for free cooling, thus causing an energy penalty during 
    periods when free cooling is available.
    
    When a call for cooling comes from the space thermostat and conditions are favorable
    for economizing (outdoor air temperature is less than return air temperature) the outdoor
    air damper should fully open.  The outdoor air fraction, an indication of the relative amount of 
    outdoor air brought into the RTU, should ideally be close to a value of one.

    Then, the process checks if the conditions are favorable for the proactive 
    testing
    """
    
    def __init__(self, parent):
        """parent is the afddagent or whatever object creating an instance of this class
        """
        self._parent = parent
        config_json = resource_string(__name__, 'afdd_config.ini')
        self._config = json.loads(config_json)
    
    def run(self, voltron_data):
        #Data from Voltron
        voltron_data = self._parent.get_new_data()
        mixed_air_temperature = float(voltron_data["MixedAirTemperature"])
        return_air_temperature = float(voltron_data["ReturnAirTemperature"])
        outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
        zone_temp=float(voltron_data["ZoneTemp"])
        zone_tempsp=float(voltron_data["ZoneTempSP"])
    
       
        damper=float(voltron_data["DamperSignal"])
        cool_call=float(voltron_data["CoolCall1"])
        oatemp_vpoint =float(voltron_data["OutsideAirTemperatureVirtualPoint"])
        cfm=5000 #constant for now
        offset=2.0
        
        #settings.py file
        SecondsToSteadyState = settings.seconds_to_steady_state
        sleeptime = settings.sleeptime
        economizertype = settings.economizertype
        minutes_to_average=settings.minutes_to_average
      
        
        if economizertype==0:
            highlimit=return_air_temperature
        else:
            highlimit=self._config["highlimit"]
        
    
    # check Prerequisites
        if(heat_call==1 or math.fabs(outdoor_air_temperature-return_air_temperature)<settings.afdd_threshold):
           afdd3=38
           self.log_status("Conditions not favorable for proactive economizer fault detection")
           return afdd3
        
                
    # Main Algorithm
        if cool_call==1:
        
            if (outdoor_air_temperature-offset) < highlimit:
            
                if damper==100:
                    
                    oaf=self.calculate_oaf(self,minutes_to_average, sleeptime)
                    if 1.0-oaf > afdd3_threshold:
                        afdd3=32
                        potential_cooling_savings = 1.08*cfm*(mixed_air_temperature-outdoor_air_temperature) #sensible cooling load estimation in BTU/hr
                        self.log_status("Insufficient outdoor air when economizing")
                        return afdd3
                    else:
                        afdd3=30
                        self.log_status("Economizer functioning properly")
                        return afdd3
                else:
                    afdd3=33
                    potential_cooling_savings = 1.08*cfm*(mixed_air_temperature-outdoor_air_temperature) #sensible cooling load estimation in BTU/hr
                    self.log_status("RTU not economizing when outdoor conditions are favorable for economizing")
                    return afdd3 
            else:
                status=self.command_outdoor_air_temperature_vpoint(return_air_temperature-10)
                if not (status):
                    afdd3=39
                    self.log_status("Lock not received from Catalyst")    
                    return afdd3
                    
                self.sleep(seconds_to_steady_state)  
                voltron_data = self._parent.get_new_data()
                damper=float(voltron_data["DamperSignal"])
                
                if damper==100:
                    oaf=self.calculate_oaf(self,minutes_to_average, sleeptime)
                    
                    if 1.0-oaf > afdd3_threshold:
                        afdd3=32
                        potential_cooling_savings = 1.08*cfm*(mixed_air_temperature-outdoor_air_temperature) #sensible cooling load estimation in BTU/hr
                        self.log_status("Insufficient outdoor air when economizing")
                        return afdd3
                    else:
                        afdd3=30
                        self.log_status("Economizer functioning properly")
                        return afdd3
                else:
                    afdd3=33
                    potential_cooling_savings = 1.08*cfm*(mixed_air_temperature-outdoor_air_temperature) #sensible cooling load estimation in BTU/hr
                    self.log_status("RTU not economizing when outdoor conditions are favorable for economizing")
                    return afdd3       
        afdd3=31 
        return afdd3            
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
      
  
        
