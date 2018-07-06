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

import logging
import settings
import math
import time
import datetime
import sys
import time
from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green,utils, matching, sched
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics


_log = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)

class DemandResponseAgent(PublishMixin, BaseAgent):
    """
        Doc for AFDD
    """
    def __init__(self, agent,**kwargs):
        self._agent = agent
        super(DemandResponseAgent, self).__init__(**kwargs)
        
    def go2(self):
        self.go()
        
    def go(self):
        self.start_timer=self.periodic_timer(10,self.get_signal)
            
    #def __init__(self, **kwargs):
        #super(Agent,self).__init__(**kwargs)
        #self.after_timer = None
     
    def pre_cpp_timer(self,csp_normal):
        print("Pre-cooling for CPP Event")  #pre-cool change cooling set point
        self.pre_timer = self.periodic_timer(5, self.pre_cpp_cooling,{'csp':settings.csp_norm})
        
    def pre_cpp_cooling(self,csp):
        if csp['csp']> settings.csp_pre:
            csp['csp']=csp['csp']-1
            print(csp)
        elif csp['csp']<=settings.csp_pre:
            csp['csp']=settings.csp_pre
            self.pre_timer.cancel()
            print(csp)
            
    def accelerated_pre_cooling_timer(self,pre_slope, csp):
        print("Accelerated pre-cooling for CPP Event")
        self.pre_timer = self.periodic_timer(5, self.accelerated_pre_cooling,pre_slope,{'csp':csp})
        
    def accelerated_pre_cooling(self,pre_slope,csp):
        if csp['csp']> settings.csp_pre:
            csp['csp']=csp['csp']-1*pre_slope
            print(csp)
        elif csp['csp']<=settings.csp_pre:
            csp['csp']=settings.csp_pre
            print(csp) 
            self.pre_timer.cancel()
            
    def during_cpp(self):
       print("During CPP Event")
      
   
        
    def after_cpp_timer(self,csp_normal):
        #Pull current cooling setpoint from controller CSP
        #CSP= PULL FROM CONTROLLER (GET NEW DATA)
        
        print(csp_normal)
        print("After CPP Event, returning to normal operations")
        self.after_timer = self.periodic_timer(3, self.after_cpp_cooling, csp_normal,{'csp':80})

        #set cooling setpoint down by 1 degree every 30 minutes until it reaches normal
        
             
    def after_cpp_cooling(self,csp_normal,csp):
        print("After_CPP_COOLING")
       
        if csp['csp'] > csp_normal:
            csp['csp']=csp['csp']-1
            print(csp)
            print(datetime.datetime.now())
        elif csp['csp'] <= csp_normal:
            self.after_timer.cancel()
            csp['csp']=csp_normal
            
            print(csp)
            self.go()
            
    def get_signal(self):
        #Pull signal from source
        voltron_data = self._agent.get_new_data()
        mixed_air_temperature = float(voltron_data["MixedAirTemperature"]) 
        time_now=time.mktime(datetime.datetime.now().timetuple())
        time_pre=time.mktime(datetime.datetime.now().replace(hour=settings.pre_cpp_hour,minute=0,second=0, microsecond=0).timetuple())
        time_event=time.mktime(datetime.datetime.now().replace(hour=settings.during_cpp_hour,minute=51,second=0, microsecond=0).timetuple())
        time_after=time.mktime(datetime.datetime.now().replace(hour=settings.after_cpp_hour,minute=54,second=0, microsecond=0).timetuple())
        print(time_now)
        print(time_event)
        #PULL NORMAL COOLING SETPOINT
        csp_normal=settings.csp_norm
        if (settings.signal and time_now<time_pre):
            print ("Scheduling") 
            pre_cpp_time=datetime.datetime.now().replace(hour=settings.pre_cpp_hour,minute=25,second=10, microsecond=0)
            self.schedule(pre_cpp_time,sched.Event(self.pre_cpp_timer, (csp_normal,)))
            during_cpp_time=datetime.datetime.now().replace(hour=settings.during_cpp_hour,minute=26,second=20, microsecond=0)
            self.schedule(during_cpp_time,sched.Event(self.during_cpp))
            after_cpp_time=datetime.datetime.now().replace(hour=settings.after_cpp_hour,minute=27,second=30, microsecond=0)
            self.schedule(after_cpp_time,sched.Event(self.after_cpp_timer, (csp_normal,)))
            self.start_timer.cancel()
        elif(settings.signal and time_now>time_pre and time_now<time_event):
            print("Scheduling")
            self.start_timer.cancel()
            pre_slope=(time_event-time_now)/(3600)
            during_cpp_time=datetime.datetime.now().replace(hour=settings.during_cpp_hour,minute=46,second=20, microsecond=0)
            self.schedule(during_cpp_time,sched.Event(self.during_cpp))
            after_cpp_time=datetime.datetime.now().replace(hour=settings.after_cpp_hour,minute=47,second=10, microsecond=0)
            self.schedule(after_cpp_time,sched.Event(self.after_cpp_timer, (csp_normal,)))
            self.accelerated_pre_cooling_timer(pre_slope,csp_normal)
        elif(settings.signal and time_now>time_event and time_now<time_after):
            print("Too late to pre-cool!")
            self.start_timer.cancel()
            after_cpp_time=datetime.datetime.now().replace(hour=settings.after_cpp_hour,minute=54,second=10, microsecond=0)
            self.schedule(after_cpp_time,sched.Event(self.after_cpp_timer, (csp_normal,)))
            self.during_cpp()
        print("CPP Event Missed")
        self.go()
