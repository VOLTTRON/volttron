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

from sys import exit
import math
import settings

class economizing_when_rtu_should_not:
    """

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
        outdoor_air_temperature = float(voltron_data["OutsideAirTemperature"])
        return_air_temperature = float(voltron_data["ReturnAirTemperature"])
        cool_call=float(voltron_data["CoolCall1"])
        heat_call=float(voltron_data["HeatCall1"])
        oatemp_vpoint =float(voltron_data["OutsideAirTemperatureVirtualPoint"])
        cfm = 5000 # constant for now
        offset=2.0

        #configuration file: afdd_config.ini
        seconds_to_steady_state = settings.seconds_to_steady_state 
        desired_oa_volume=settings.desired_oa_volume
        #afdd4_threshold=settings.afdd4_threshold  not used
        
        economizer_type = settings.economizertype
        
        if economizer_type==0:  #add to configuration file type zero is ddb or highlimit
            highlimit=return_air_temperature
        else:
            highlimit=settings.highlimit
            
        if heat_call==1:
            afdd4=48
            self.log_status("Conditions are not favorable for proactive economizer fault detection")
            return afdd4
                
    # Main Algorithm
    
        if cool_call==1:    
            if (outdoor_air_temperature+offset) < highlimit:
                    status1 = self.command_outdoor_air_temperature_vpoint(return_air_temperature + 10)
                    if not status1:
                        afdd4=49
                        self.log_status("Lock not received from Catalyst")
                        return afdd4
                    
                    else:
                        sleep(seconds_to_steady_state)
                        status = self.get_damper_status(self)
                        if status:
                            afdd4=40
                            self.log_status("Economizer controls functioning properly")
                            return afdd4
                        else:
                            afdd4=41
                            potential_cooling_savings = 1.08*cfm*((0.05*outdoor_air_temperature+0.95*return_air_temperature)-mixed_air_temperature) #sensible cooling load estimation in BTU/hr
                            self.log_status("Damper should be at minimum but is commanded open, potentially wasting energy")
                            return afdd4
            else:
                status=self.get_damper_status(self)
                if status:
                    afdd4=40
                    self.log_status("Economizer controls functioning properly")
                    return afdd4
                else:
                    afdd4=41
                    potential_cooling_savings = 1.08*cfm*((0.05*outdoor_air_temperature+0.95*return_air_temperature)-mixed_air_temperature) #sensible cooling load estimation in BTU/hr
                    self.log_status("Damper should be at minimum but is commanded open, potentially wasting energy")
                    return afdd4
        else:
            status=self.get_damper_status(self)
            if status:
                afdd4=40
                self.log_status("Economizer controls functioning properly")
                return afdd4
            else:
                afdd4=41
                potential_cooling_savings = 1.08*cfm*((0.05*outdoor_air_temperature+0.95*return_air_temperature)-mixed_air_temperature) #sensible cooling load estimation in BTU/hr
                self.log_status("Damper should be at minimum but is commanded open, potentially wasting energy")
                return afdd4
        
                
 ###################################################################################################     
 
    def log_status(self,code):
        # print or log code and exit  
        # need to release OAtemp_vpoint and CoolCall1
        
        print(code)
              
    def command_outdoor_air_temperature_vpoint(self,value):
        """ Command outdoor air damper to a new position """
        status1 = 0
        status1 = self._parent.command_equip("OutsideAirTemperaturevirtualpoint",value)
        return status1

    def get_damper_status(self):
       
        #Check heating and cooling status.  If the unit either heating or cooling, turn it off 
      
        damper = 0
        supply_fan_command = 0
        status = 0
        voltron_data = self._parent.get_new_data()
        supply_fan_command=float(voltron_data["SupplyFanSpeed"])
        damper = float(voltron_data["Damper"]) # Point name follows RTUNetwork wiki
        if (supply_fan_command==75 and 6 < damper< 7) or (supply_fan_command==90 and 5 < damper < 6) or (supply_fan_command==40 and 12 < damper < 13):
            status = 1
        else: 
            status = 0
        return status
        
 
