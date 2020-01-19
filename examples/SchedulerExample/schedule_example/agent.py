# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


import datetime
import logging
import sys
import uuid

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.messaging import topics, headers as headers_mod

from . import settings


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

def DatetimeFromValue(ts):
    ''' Utility for dealing with time
    '''
    if isinstance(ts, int):
        return datetime.utcfromtimestamp(ts)
    elif isinstance(ts, float):
        return datetime.utcfromtimestamp(ts)
    elif not isinstance(ts, datetime):
        raise ValueError('Unknown timestamp value')
    return ts

def schedule_example(config_path, **kwargs):

    config = utils.load_config(config_path)
    agent_id = config['agentid']

    class SchedulerExample(Agent):
        '''This agent can be used to demonstrate scheduling and 
        acutation of devices. It reserves a non-existant device, then
        acts when its time comes up. Since there is no device, this 
        will cause an error.
        '''
    
    
        def __init__(self, **kwargs):
            super(SchedulerExample, self).__init__(**kwargs)
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self._agent_id = config['agentid']

        @Core.receiver('onstart')            
        def startup(self, sender, **kwargs):
#             self.publish_schedule()
            self.use_rpc()
    
    
    
        @PubSub.subscribe('pubsub', topics.ACTUATOR_SCHEDULE_ANNOUNCE(campus='campus',
                                             building='building',unit='unit'))
        def actuate(self, peer, sender, bus,  topic, headers, message):
            print ("response:",topic,headers,message)
            if headers[headers_mod.REQUESTER_ID] != agent_id:
                return
            '''Match the announce for our fake device with our ID
            Then take an action. Note, this command will fail since there is no 
            actual device'''
            headers = {
                        'requesterID': agent_id,
                       }
            self.vip.pubsub.publish(
            'pubsub', topics.ACTUATOR_SET(campus='campus',
                                             building='building',unit='unit',
                                             point='point'),
                                     headers, str(0.0))
    
        
        def publish_schedule(self):
            '''Periodically publish a schedule request'''
            headers = {
                        'AgentID': agent_id,
                        'type': 'NEW_SCHEDULE',
                        'requesterID': agent_id, #The name of the requesting agent.
                        'taskID': agent_id + "-ExampleTask", #The desired task ID for this task. It must be unique among all other scheduled tasks.
                        'priority': 'LOW', #The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
                    } 
            
            start = str(datetime.datetime.now())
            end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))
    
    
            msg = [
                   ['campus/building/unit',start,end]
                   #Could add more devices
    #                 ["campus/building/device1", #First time slot.
    #                  "2014-1-31 12:27:00",     #Start of time slot.
    #                  "2016-1-31 12:29:00"],     #End of time slot.
    #                 ["campus/building/device2", #Second time slot.
    #                  "2014-1-31 12:26:00",     #Start of time slot.
    #                  "2016-1-31 12:30:00"],     #End of time slot.
    #                 ["campus/building/device3", #Third time slot.
    #                  "2014-1-31 12:30:00",     #Start of time slot.
    #                  "2016-1-31 12:32:00"],     #End of time slot.
                    #etc...
                ]
            self.vip.pubsub.publish(
            'pubsub', topics.ACTUATOR_SCHEDULE_REQUEST, headers, msg)
            
            
        def use_rpc(self):
            try: 
                start = str(datetime.datetime.now())
                end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))
    
                msg = [
                   ['campus/building/unit3',start,end]
                   ]
                result = self.vip.rpc.call(
                                           'platform.actuator', 
                                           'request_new_schedule',
                                           agent_id, 
                                           "some task",
                                           'LOW',
                                           msg).get(timeout=10)
                print("schedule result", result)
            except Exception as e:
                print ("Could not contact actuator. Is it running?")
                print(e)
                return
            
            try:
                if result['result'] == 'SUCCESS':
                    result = self.vip.rpc.call(
                                           'platform.actuator', 
                                           'set_point',
                                           agent_id, 
                                           'campus/building/unit3/some_point',
                                           '0.0').get(timeout=10)
                    print("Set result", result)
            except Exception as e:
                print ("Expected to fail since there is no real device to set")
                print(e)    
                
                
            
            
    Agent.__name__ = 'ScheduleExampleAgent'
    return SchedulerExample(**kwargs)
            
    
    
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(schedule_example, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
