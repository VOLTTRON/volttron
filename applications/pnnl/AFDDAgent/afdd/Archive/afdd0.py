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
Created on Jun 26, 2013

@author: Anthony Bladek
Created from example code OADModulation.py code as an example.
modified by lute362 on August 1, 2013 
'''
from math import abs
from time import sleep
from sys import exit
import settings

class AFDD_Modulation:
    '''
    classdocs
    '''


    def __init__(self, parent):
        '''
        Constructor
        Use example code from afddagent for structure
        '''
        self._parent = parent
        
        
    def run(self,voltron_data):
        '''Voltron_data is input from controller
           self is this module and its parameters. 
        '''
        voltron_data = self._parent.get_new_data()
        cool_cmd = boolean(voltron_data["CoolCommand1"])
        sleeptime=settings.sleeptime
        seconds_to_steady_state=settings.seconds_to_steady_state
        status = self.shutdown_rtu_compressor()
        minutes_to_average=settings.minutes_to_average
        # could take up to 5 minutes to shut down. 
           
        #make sure RTU is shutdown
        #if not wait another 5 minutes and then error out.
        for n in range(1, 5): 
            status = self.get_rtu_status() 
            if not (status): break
            self.sleep(sleeptime)
    
        if ((n == 5) and status):
            ## log still running after 5 minutes ...
            ## exit the function
            self.log_status("Compressor still running 5 minutes after shutdown")
            afdd0=8
            return afdd0
            #Continue with processing.   
            # Need to open damper (OAD) all the way
            #Command outdoor air damper to fully open position

        status = self.command_OAD(100)
        if (status): # fully open position
            # Verify steady-state conditional
            # wait for steady-state conditions to be established
            self.sleep(seconds_to_steady_state)
        else:
            # if status is not true or "1" need to do something?
            self.log_status("Damper command failed trying to open to fully open position")
            afdd0=9
            return afdd0

        abs_diff = self.absolute_diff(self,minutes_to_average, sleepTime) 
        
        # check the diff if > threshold
        if(abs_diff < settings.afdd0_threshold):
            status = self.command_OAD(0)
            if (status): # fully open position
            # Verify steady-state conditionl
            # wait for steady-state conditions to be established
                self.sleep(seconds_to_steady_state)
            else:
                self.log_status("Damper command failed trying to go to fully closed position")
                afdd0=9
                return afdd0
                
            abs_diff = self.absolute_diff(self,minutes_to_average, sleepTime)
            
            if(abs_diff < settings.afdd0_threshold):
                afdd0=0
                self.log_status("No Fault Detected during diagnostic 0")
                return afdd0
                
            afdd0=3
            self.log_status("Some Message")
            return affd0
            
        afdd0=2
        self.log_status("Some Message")
        return afdd0
      
    def absolute_diff(self,num_minutes, sleepTime):
        # get the voltron data
        diff_da_ma = 0.
        return_air_temperature = 0.
        mixed_air_temperature = 0.
        n = 0
        
        for n in range(1, num_minutes):
            voltron_data = self._parent.get_new_data()
            mixed_air_temperature = float(voltron_data["MixedAirTemperature"]) # Point name follows RTUNetwork wiki)
            discharge_air_temperature = float(voltron_data["DischargeAirTemperature"]) # Point name follows RTUNetwork wiki)
            diff_da_ma += math.fabs(discharge_air_temperature - mixed_air_temperature)
            sleep(sleepTime) # Pause for 60 seconds
            
        diff_da_ma = diff_da_ma/n
        return diff_da_ma
      
    def shutDown_rtu_compressor(self):
        """Shutdown the compressor, in preparation for the proactive testing
        """ 
        #TODO: send a compressor shutdown commend to the controller. What data point control this????
        status = 0
        status = self._parent.command_equip("CoolCommand1",0)
        
        return status
    def get_rtu_status(self):
        """ 
        Check heating and cooling status.  If the unit either heating or cooling, turn it off 
        """
        coolingCommand = 0
        heatingCommand = 0
        status = 0
        voltron_data = self._parent.get_voltron_data()
        cooling_command = boolean(voltron_data["CoolCommand1"]) # Point name follows RTUNetwork wiki
        if (cooling_command): 
            status = 1
        else: 
            status = 0
        
        return status
    
    def command_OAD(self,position):
        """ Command outdoor air damper to a new position """
        status = 0
        status = self._parent.command_equip("DamperSignal",position)
        return status
    
    def log_message(self,msg):
        _log.debug(code)  
        
        
    def sleep(self,sleeptime):
        self._parent.sleep(sleeptime)

    def log_status(self,code):
        # print or log code and exit  
        # need to release OAtemp_vpoint and CoolCall1
        
        _log.debug(code)
