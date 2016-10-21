# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
# 
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
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
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the FreeBSD Project.
#

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

#}}}


from datetime import datetime, timedelta
import time
from time import strftime
import os
import sys
import httplib, urllib
import json
import requests
import xml.etree.ElementTree as ET
from requests import ConnectionError

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics

import settings
from settings import DEBUG as DEBUG


requests.adapters.DEFAULT_RETRIES = 5

date_format = "%s000.0"
readable_format = "%m/%d/%Y %H:%M:%S"




def SMDSAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            value = kwargs.pop(name)
        except KeyError:
            return config[name]

    agent_id = get_config('agentid')
    time_window_minutes = get_config('time_window_minutes')
    rtu_path = {
        'campus': get_config('campus'),
        'building': get_config('building'),
        'unit': get_config('unit'),
    }

    class Agent(PublishMixin, BaseAgent):
        '''This agent grabs a day's worth of data for a Catalyst's Data points
        out of the historian. It then sends the data on to an application
        in the cloud.
        '''
    
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self._raw_air_temp = None
            self._raw_fan_speed = None
            self._raw_unit_power = None
            
            
        
        def setup(self):
            self._agent_id = get_config('agentid')
            self._service_url = get_config('service_url')
            self._provider_id = get_config('provider_id')
            self._unit_power_chan = get_config('unit_power_chan')
            self._outdoor_temp_chan = get_config('outdoor_temp_chan')
            self._fan_supply_chan = get_config('fan_supply_chan')
            self._campusid = get_config('campus')
            self._buildingid = get_config('building')
            self._deviceid = get_config('unit')
            
#             self._time_window_minutes = int(self.config['time_window_minutes'])
            self._backlog_hours = get_config('backlog_hours')
    
            
            # Always call the base class setup()
            super(Agent, self).setup()
            
            self.setup_topics()
            
            self._catching_up = True
    
            self._last_update = datetime.now() - timedelta(hours = self._backlog_hours)
            self._query_end_time = None
            
            self.publish_requests()
    
    
        def setup_topics(self):
            
            self.request_temptopic = topics.ARCHIVER_REQUEST(point='OutsideAirTemperature', **rtu_path)
            self.request_powertopic = topics.ARCHIVER_REQUEST(point='UnitPower', **rtu_path)
            self.request_fantopic = topics.ARCHIVER_REQUEST(point='SupplyFanSpeed', **rtu_path) 
            
        @matching.match_headers({headers_mod.TO: agent_id})
        @matching.match_exact(topics.ARCHIVER_RESPONSE(point='OutsideAirTemperature', **rtu_path))
        def on_temp_response(self, topic, headers, message, match):
            '''Method for dealing with temp data from smap'''
            if DEBUG:
                print "Topic: {topic}, Headers: {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            
            self._raw_air_temp = message[0]
            self.go_if_ready()
            
        @matching.match_exact(topics.ARCHIVER_RESPONSE(point='UnitPower', **rtu_path))
        @matching.match_headers({headers_mod.TO: agent_id})
        def on_unit_power(self, topic, headers, message, match):
            '''Method for dealing with power data from smap'''
            if DEBUG:
                print "Topic: {topic}, Headers: {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            self._raw_unit_power = message[0]
            self.go_if_ready()
            
        @matching.match_headers({headers_mod.TO: agent_id})
        @matching.match_exact(topics.ARCHIVER_RESPONSE(point='SupplyFanSpeed', **rtu_path))
        def on_fan_speed(self, topic, headers, message, match):
            '''Method for dealing with fan data from smap'''
            if DEBUG:
                print "Topic: {topic}, Headers: {headers}, Message: {message}".format(
                    topic=topic, headers=headers, message=message)
            self._raw_fan_speed = message[0]
            self.go_if_ready()
            
    
        def go_if_ready(self):
            if (self._raw_air_temp != None and self._raw_fan_speed != None and self._raw_unit_power != None):
                message = self.convert_raw()
                worked = self.post_data(message)
                if (worked):
                    self._raw_air_temp = None
                    self._raw_fan_speed = None
                    self._raw_unit_power = None
                    self._last_update = self._query_end_time
                    if self._catching_up:
    #                     self.publish_requests
                        self.timer(1, self.publish_requests)
                        
                
                
    
        def make_dataset(self, message, channelid, units):
            list = eval(message)
            values = []
            if DEBUG:
                print len(list)
                
            if len(list) >= 1:
            
                start_time = list[0][0]
                
                time_index = start_time
                
                for data in list:
                    values.append({"Utc": "/Date({})/".format(str(int(data[0]))),
                                           "Val": data[1]})
            
            return {"ChannelId": channelid,
                            "Units": units,
                            "Values": values}
    
        def convert_raw(self):
            dataset = []
            
            dataset.append(self.make_dataset(self._raw_air_temp,
                                              self._provider_id+"/"+self._outdoor_temp_chan, 
                                              "DegreesF"))
            
            dataset.append(self.make_dataset(self._raw_fan_speed,
                                              self._provider_id+"/"+self._fan_supply_chan, 
                                              "%"))
            
            dataset.append(self.make_dataset(self._raw_unit_power,
                                              self._provider_id+"/"+self._unit_power_chan, 
                                              "kW"))
                
            providerid = self._provider_id
            reply = {"ProviderId" : providerid,
                     "Datalogs" : dataset}
            
    #         reply = json.dumps(reply).replace('/','\/')
            if DEBUG:
                print json.dumps(reply, sort_keys=True,
                             indent=4, separators=(',', ': '))
            
            
            
            return reply
    
       
        # Periodically get data and push to cloud service
        @periodic(time_window_minutes * 60)    
        def publish_requests(self):
            '''Publish lookup requests to the ArchiverAgent
            '''
            
            now = datetime.now()
            
            if (now - self._last_update) > timedelta (minutes = time_window_minutes): 
                self._catching_up = True
                self._query_end_time = self._last_update + timedelta (minutes = time_window_minutes)
            else: 
                self._catching_up = False
                self._query_end_time = now
            
            
    #             if DEBUG:
            #Print a readable time range
            start = self._last_update.strftime(readable_format)
            end = (self._query_end_time).strftime(readable_format)
            print '({start}, {end})'.format(start=start, end=end)
            
            start = self._last_update.strftime(date_format)
            end = (self._query_end_time).strftime(date_format)
    
            if DEBUG:
                print '({start}, {end})'.format(start=start, end=end)
            
            headers = {headers_mod.FROM: agent_id, headers_mod.TO: 'ArchiverAgent'}
            
            self.publish(self.request_temptopic,headers,'({start}, {end})'.format(start=start, end=end))
            self.publish(self.request_powertopic,headers,'({start}, {end})'.format(start=start, end=end))
            self.publish(self.request_fantopic,headers,'({start}, {end})'.format(start=start, end=end))
            
            
        def post_data(self, params):
            
            post_data=json.dumps(params)
    
            headers_post = {'Content-Type': 'application/json',
                       'User-Agent' : 'RTUNetwork',
                       'Accept': 'application/json', 'Connection':'close'}
            done = False
            tries = 0
            while (done != True and tries < 5):
                try:
                    response = requests.post(self._service_url, data=post_data, headers=headers_post)
                    done = True
                except ConnectionError as e:
                    print '{}: {}: {}'.format(str(tries), str(e), post_data)
                    tries += 1
                
            worked = False
            
            if (response.content != None and response.content != ""):
            
                root = ET.fromstring(response.content)
                
                is_error = root.find('{http://schemas.datacontract.org/2004/07/RestServiceWebRoles}IsError').text
                transaction_id = root.find('{http://schemas.datacontract.org/2004/07/RestServiceWebRoles}TransactionId').text
                
                worked = is_error.lower() == 'false' and int(transaction_id) > 0
            else:
                worked = False
            
            return worked
        
    Agent.__name__ = 'SMDSAgent'
    return Agent(**kwargs)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''

    utils.default_main(SMDSAgent,
                   description='SDMS Agent',
                   argv=argv)


if __name__ == '__main__':
    '''Entry point for scripts.'''
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
