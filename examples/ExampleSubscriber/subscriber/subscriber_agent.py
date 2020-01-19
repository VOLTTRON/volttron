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

from datetime import datetime
import logging
import random
import sys

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.scheduling import periodic




utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'

'''
Structuring the agent this way allows us to grab config file settings 
for use in subscriptions instead of hardcoding them.
'''

def subscriber_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    oat_point= config.get('oat_point',
                          'devices/Building/LAB/Device/OutsideAirTemperature')
    mixed_point= config.get('mixed_point',
                            'devices/Building/LAB/Device/MixedAirTemperature')
    damper_point= config.get('damper_point',
                             'devices/Building/LAB/Device/DamperSignal')
    all_topic = config.get('all_topic', 
                           'devices/Building/LAB/Device/all')
    query_point= config.get('query_point',
                            'Building/LAB/Device/OutsideAirTemperature')
    
    
    class ExampleSubscriber(Agent):
        '''
        This agent demonstrates usage of the 3.0 pubsub service as well as 
        interfacting with the historian. This agent is mostly self-contained, 
        but requires the historian to be running to demonstrate the query feature.
        '''
    
        def __init__(self, **kwargs):
            super(ExampleSubscriber, self).__init__(**kwargs)
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            # Demonstrate accessing a value from the config file
            self._agent_id = config['agentid']
    
    

        @PubSub.subscribe('pubsub', all_topic)
        def match_device_all(self, peer, sender, bus,  topic, headers, message):
            '''
            This method subscribes to all points under a device then pulls out 
            the specific point it needs.
            The first element of the list in message is a dictionairy of points 
            under the device. The second element is a dictionary of metadata for points.
            '''
                       
            print("Whole message", message)
            
            #The time stamp is in the headers
            print('Date', headers['Date'])
            
            #Pull out the value for the point of interest
            print("Value", message[0]['OutsideAirTemperature'])
            
            #Pull out the metadata for the point
            print('Unit', message[1]['OutsideAirTemperature']['units'])
            print('Timezone', message[1]['OutsideAirTemperature']['tz'])
            print('Type', message[1]['OutsideAirTemperature']['type'])
           

    
        @PubSub.subscribe('pubsub', oat_point)
        def on_match_OAT(self, peer, sender, bus,  topic, headers, message):
            '''
            This method subscribes to the specific point topic.
            For these topics, the value is the first element of the list 
            in message.
            '''
            
            print("Whole message", message)
            print('Date', headers['Date'])
            print("Value", message[0])
            print("Units", message[1]['units'])
            print("TimeZone", message[1]['tz'])
            print("Type", message[1]['type'])
            
    
        @PubSub.subscribe('pubsub', '')
        def on_match_all(self, peer, sender, bus,  topic, headers, message):
            ''' This method subscibes to all topics. It simply prints out the 
            topic seen.
            '''
            
            print(topic)
#     
        # Demonstrate periodic decorator and settings access
        @Core.schedule(periodic(10))
        def lookup_data(self):
            '''
            This method demonstrates how to query the platform historian for data
            This will require that the historian is already running on the platform.
            '''
            
            try: 
                
                result = self.vip.rpc.call(
                                           #Send this message to the platform historian
                                           #Using the reserved ID
                                           'platform.historian', 
                                           #Call the query method on this agent
                                           'query', 
                                           #query takes the keyword arguments of:
                                           #topic, then optional: start, end, count, order
#                                            start= "2015-10-14T20:51:56",
                                           topic=query_point,
                                           count = 20,
                                           #RPC uses gevent and we must call .get(timeout=10)
                                           #to make it fetch the result and tell 
                                           #us if there is an error
                                           order = "FIRST_TO_LAST").get(timeout=10)
                print('Query Result', result)
            except Exception as e:
                print ("Could not contact historian. Is it running?")
                print(e)

        @Core.schedule(periodic(10))
        def pub_fake_data(self):
            ''' This method publishes fake data for use by the rest of the agent.
            The format mimics the format used by VOLTTRON drivers.
            
            This method can be removed if you have real data to work against.
            '''
            
            #Make some random readings
            oat_reading = random.uniform(30,100)
            mixed_reading = oat_reading + random.uniform(-5,5)
            damper_reading = random.uniform(0,100)
            
            # Create a message for all points.
            all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading, 
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                        'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'}, 
                        'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                        }]
            
            #Create messages for specific points
            oat_message = [oat_reading,{'units': 'F', 'tz': 'UTC', 'type': 'float'}]
            mixed_message = [mixed_reading,{'units': 'F', 'tz': 'UTC', 'type': 'float'}]
            damper_message = [damper_reading,{'units': '%', 'tz': 'UTC', 'type': 'float'}]
            
            #Create timestamp
            now = utils.format_timestamp(datetime.utcnow())
            headers = {
                headers_mod.DATE: now,
                headers_mod.TIMESTAMP: now
            }
            
            #Publish messages
            self.vip.pubsub.publish(
                'pubsub', all_topic, headers, all_message)
            
            self.vip.pubsub.publish(
                'pubsub', oat_point, headers, oat_message)
            
            self.vip.pubsub.publish(
                'pubsub', mixed_point, headers, mixed_message)
            
            self.vip.pubsub.publish(
                'pubsub', damper_point, headers, damper_message)
            


    return ExampleSubscriber(**kwargs)
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(subscriber_agent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
