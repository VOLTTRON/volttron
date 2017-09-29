# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, 
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official,
# policies either expressed or implied, of the FreeBSD Project.
#opt_comman

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
import sys
import requests
import datetime
import logging
import csv
from dateutil.parser import parse

from volttron.platform.agent.utils import jsonapi
from volttron.platform.agent import utils
from volttron.platform.agent import matching
from volttron.platform.messaging import headers as headers_mod, topics

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.async import AsyncCall
from volttron.platform.agent import utils
from volttron.platform.vip.agent import *

import settings

utils.setup_logging()
_log = logging.getLogger(__name__)


'''
*************************************************************************************************************
Personal weather agent derivated from the weather agent included in services/core
two main functions:
-periodically read temperature, cloud cover, and solarradiation data
-periodically read the forecast

The user key should figure in the settings file
http://www.wunderground.com/weather/api/
*************************************************************************************************************
'''


'''
*************************************************************************************************************
Topic selection among the data available 
'''
topic_conditions = [ "station_id", "temp_f", "wind_mph", "dewpoint_f", "pressure_in" , "relative_humidity","solarradiation"]
                 

topic_forecast=[ ["temp", "english"], "sky",  ["wspd", "english"]  ]


'''
*************************************************************************************************************
Agent and initialization: 
'''
class WeatherData(Agent):

        def __init__(self, config_path, **kwargs):
            super(WeatherData, self).__init__(**kwargs)
            self.config = utils.load_config(config_path)
            

        '''
        *************************************************************************************************************
        On start method: Building the request URL and waiting for appropriate time to start data acquisition
        '''
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
        
            '****** Reading the config file and build the URL  *****'
                       
            agent_id = self.config['agentid']
            poll_time = self.config['poll_time']
            state=self.config['state']
            city=self.config['city']
            zip_code = self.config["zip"]
            
            base = "http://api.wunderground.com/api/" +  settings.KEY
            self.requestUrl_conditions = base + "/conditions/q/"+zip_code + ".json"
            self.requestUrl_forecast = base + "/hourly/q/"+ state + "/" +city + ".json"
            
            now = datetime.datetime.now()
            self.hour=now.hour
            self.request_forecast=self.config['request_forecast']
            self.request_conditions=self.config['request_conditions']
            self.init=True
            
            self.data_path_base=self.config['database']
                          
            
            '*****   Start data acquisition   *********'
            
            if self.init and self.request_forecast :
                self.init=False
                self.weather_forecast() 
            
            if (poll_time < 180) or (poll_time % 60 !=0):
                _log.debug("Invalid poll_time : Too low or non minute expressed")
            else:
                now=datetime.datetime.now()
                _log.debug("Waiting to start querying the data... ")  #If poll_time = 5min, wait until appropriate time stamp (up to 4min59s!)
                while (now.minute % (poll_time/60) != 0):
                    now=datetime.datetime.now()
                _log.debug("... Start periodic URL Request")   
                self.weather = self.core.periodic(poll_time,self.weather_conditions,wait=0)       
                                    
        
        '''
        *************************************************************************************************************
        Function called on periodic or request for weather conditions on poll_time 
        '''       
        def weather_conditions(self):
            
            '*****   Request  weather conditions to write   *********' 
            now = datetime.datetime.now()
            
            if self.request_conditions:
                
                _log.debug("Requesting url: "+self.requestUrl_conditions)
                
                
                try : r = requests.get(self.requestUrl_conditions)
                
                except :
                    _log.debug("Impossible to perform the weather conditions data request : check the URL or Connection")
                    data=[now ,now.month, now.day,  now.hour  , now.minute] 
                    for element in topic_conditions:
                        data.append("NaN")
                        
                        
                else:
                    r.raise_for_status()
                    parsed_json = r.json()
                
                
                    try : observation = parsed_json['current_observation']
                    except :
                        _log.debug("No data available")
                        data=[now ,now.month, now.day,  now.hour  , now.minute] 
                        for element in topic_conditions:
                            data.append("NaN")
                
                 
                    else:
                        observation = convert(observation)
                        data=[now,  now.month, now.day, now.hour ,  now.minute] 
                        for element in topic_conditions:
                            data.append(observation[element])
                 
 
                '*****   write condition in appropriate file   *********' 
                data_path=self.data_path_base + "conditions_" + str(now.year) + "_" + str(now.month) +".csv"
                myfile= csv.writer(open(data_path, 'a'))
                myfile.writerow(data)
            
            
            '*****  determine wether requesting hourly forecast or not (hourly synchronized)  *********' 
            if now.hour!= self.hour and self.request_forecast:
                self.hour=now.hour
                self.weather_forecast()
                        
                        
        '''
        *************************************************************************************************************
        If required, function called to request the hourly 24h forecast 
        '''
        def weather_forecast(self):
            
            '*****   Request  24h weather forecast to write   *********' 
            now = datetime.datetime.now()
            _log.debug("Requesting url: "+self.requestUrl_forecast)
            
            try : r = requests.get(self.requestUrl_forecast)
                
            except :
                _log.debug("Impossible to perform the weather forecasts data request : check the URL or Connection")
                data=[now ,now.month, now.day,  now.hour ]
                for element in topic_forecast:
                    if type(element)==str:
                        element_data_path=self.data_path_base + "forecast_" + element +"_" +str(now.year) + "_" + str(now.month) +".csv"
                    elif type(element)==list:    
                        element_data_path=self.data_path_base + "forecast_" + element[0] +"_" +str(now.year) + "_" + str(now.month) +".csv"
                    myfile= csv.writer(open(element_data_path, 'a'))
                    myfile.writerow(data)                
        
            else:
                r.raise_for_status()
                parsed_json = r.json()
                
                try : forecast= parsed_json['hourly_forecast']
                except :
                    _log.debug("Impossible to perform the weather forecast request : check the URL")     
                else:
                    forecast = convert(forecast)
                  
                
                '*****   Read/Write 24h forecasted elements - 1 file per element  *********'                                          
                for element in topic_forecast:
                    element_data=[ now ,now.month, now.day, now.hour]
                    for hour in range(0,23):
                        hourly_values=forecast[hour]
                        if type(element)==str:
                            element_data.append(hourly_values[element])
                        elif type(element)==list:
                            element_data.append(hourly_values[element[0]][element[1]])               
                    
                    
                    if type(element)==str:
                        element_data_path=self.data_path_base + "forecast_" + element +"_" +str(now.year) + "_" + str(now.month) +".csv"
                    elif type(element)==list:    
                        element_data_path=self.data_path_base + "forecast_" + element[0] +"_" +str(now.year) + "_" + str(now.month) +".csv"
                    myfile= csv.writer(open(element_data_path, 'a'))
                    myfile.writerow(element_data)
                    

'''
*************************************************************************************************************
Convert data downloaded
'''
def convert(_input):
    if isinstance(_input, dict):
        return {convert(key): convert(value) for key, value in _input.iteritems()}
    elif isinstance(_input, list):
        return [convert(element) for element in _input]
    elif isinstance(_input, unicode):
        return _input.encode('utf-8')
    else:
        return _input


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(WeatherData)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
