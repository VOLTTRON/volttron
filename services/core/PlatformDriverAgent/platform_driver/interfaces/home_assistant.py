# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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


import random
import datetime
import math
from math import pi
import json
import sys
from platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from volttron.platform.agent import utils #added this to pull from config store 
from volttron.platform.vip.agent import Agent
from csv import DictReader
from io import StringIO
import logging
import requests
from requests import get


_log = logging.getLogger(__name__)
type_mapping = {"string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool}


class FakeRegister(BaseRegister):
    def __init__(self, read_only, pointName, units, reg_type, attributes,
                 default_value=None, description=''):
        super(FakeRegister, self).__init__("byte", read_only, pointName, units,
                                           description='')
        self.reg_type = reg_type
        self.attributes = attributes

        if default_value is None:
            self.value = self.reg_type(random.uniform(0, 100))
        else:
            try:
                self.value = self.reg_type(default_value)
            except ValueError:
                self.value = self.reg_type()

class EKGregister(BaseRegister):

    def __init__(self, read_only, pointName, units, reg_type,
                 default_value=None, description=''):
        super(EKGregister, self).__init__("byte", read_only, pointName, units,
                                          description='')
        self._value = 1;

        math_functions = ('acos', 'acosh', 'asin', 'asinh', 'atan', 'atan2',
                          'atanh', 'sin', 'sinh', 'sqrt', 'tan', 'tanh')
        if default_value in math_functions:
            self.math_func = getattr(math, default_value)
        else:
            _log.error('Invalid default_value in EKGregister.')
            _log.warning('Defaulting to sin(x)')
            self.math_func = math.sin

    @property
    def value(self):
        now = datetime.datetime.now()
        seconds_in_radians = pi * float(now.second) / 30.0

        yval = self.math_func(seconds_in_radians)

        return self._value * yval

    @value.setter
    def value(self, x):
        self._value = x

class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.point_name = None


        
    def configure(self, config_dict, registry_config_str): # grabbing from config
        self.ip_address = config_dict.get("ip_address", "0.0.0.0")
        self.access_token = config_dict.get("access_token", "cool")
        self.volttron_topic = config_dict.get("volttron_topic", "devices")
        self.points_to_grab_from_topic = config_dict.get("points_to_grab_from_topic", "points_to_grab_from_topic")
        self.registry_config = config_dict.get("registry_config","registry_config")
        self.parse_config(registry_config_str) 
        #print(self.registry_config)
        

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        print(f"point name {point_name}, {register}")
        if register.read_only:
            raise RuntimeError(
                "Trying to write to a point configured read only: " + point_name)

        register.value = register.reg_type(value) # setting the value
        return register.value

    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        def get_entity_data(entity_id):
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            url = f"http://{self.ip_address}:8123/api/states/{entity_id}" # the /states grabs cuurent state AND attributes of a specific entity
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json() # return the json attributes from entity
            else:
                _log.error(f"Request failed with status code {response.status_code}: {entity_id} {response.text}")
                return None

        for register in read_registers + write_registers:
            
            entity_id = register.point_name
            attributes = register.attributes
            entity_data = get_entity_data(entity_id) # assign arrtributes to entity_data  


            if entity_data is not None: # if not none extract the state and entity id
                state = entity_data.get("state", None)
                entity_id = entity_data.get("entity_id", None)

                if state == "unavailable": # check if the state it unavailable in home assistant. 
                    print("\n")
                    _log.error(f"{entity_id} is unavailable\n")

                #check if state_replace is in the register attributes 
                state_replace = attributes.get('state_replace')

                result[entity_id] = { # creating new entry in result dictionary using the point name
                    #"value": state, # redundent
                    "entity_id": entity_id,
                    state_replace if state_replace else "state": state # the if checks if its not none if it finds something state_replace is the key. state_replace is a string and state is at the end. 
                }
 
                # Loop through the attributes of the register and fetch corresponding values from entity_data
                for attribute_name, attribute_key in attributes.items():
                    attribute_value = entity_data["attributes"].get(attribute_key, None)
                    if attribute_value is not None:
                        result[entity_id][attribute_name] = attribute_value
            else:
                result[entity_id] = { # dictionary in a dictionary
                    "value": register.value
                }

        return result

    def change_thermostat_mode(self, thermostat_entity_id, mode):
        url = f"http://{self.ip_address}:8123/api/services/climate/set_hvac_mode"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "content-type": "application/json",
        }
        
        data = {
            "entity_id": thermostat_entity_id,
            "hvac_mode": mode,
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print(f"Successfully changed the mode of {thermostat_entity_id} to {mode}")
        else:
            print(f"Failed to change the mode of {thermostat_entity_id}. Response: {response.text}")
        
    
    def set_thermostat_temperature(self, entity_id, temperature):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"http://{self.ip_address}:8123/api/services/climate/set_temperature"
        payload = {
            "entity_id": entity_id,
            "temperature": temperature,
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            _log.info(f"Set temperature for {entity_id} to {temperature}")
        else:
            _log.error(f"Failed to set temperature for {entity_id}: {response.text}")
 
    


    def parse_config(self, configDict):

        def turn_on_lights(brightness_level):
            url2 = f"http://{self.ip_address}:8123/api/services/light/turn_on"
            
            headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
            point_names = point_name.split('\n')
            for entity in point_names:
                if entity.startswith("light"): # this will ensure that only lights are conrolled and not other devices
                    try:
                        brightness_level = 255 # ranges from 0 - 255 for most lights
                        payload = {
                            "entity_id": f"{entity}",
                            "brightness": brightness_level,
                        }
                        response = requests.post(url2, headers=headers, data=json.dumps(payload))
                        if response.status_code == 200:
                            _log.info(f"Turned on {entity}")
                    except:
                        continue
                else:
                    continue
                    #print(f"entity {entity} not a light")
        def turn_off_lights():
            url2 = f"http://{self.ip_address}:8123/api/services/light/turn_off"
            
            headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
            point_names = point_name.split('\n')
            for entity in point_names:
                if entity.startswith("light"):
                    try:
                        
                        payload = {
                            "entity_id": f"{entity}",
                            
                        }
                        response = requests.post(url2, headers=headers, data=json.dumps(payload))
                        if response.status_code == 200:
                            _log.info(f"Turned on {entity}")
                    except:
                        continue
                else:
                    continue
        

        if configDict is None:
            return
        for regDef in configDict:
            print(f"regdef = {regDef}")
            # Skip lines that have no address yet.
            if not regDef['Point Name']:
                continue

            read_only = str(regDef.get('Writable', '')).lower() != 'true' #convert writeable to string and it worked!

            point_name = regDef['Volttron Point Name']
            print(f"Extracted point name: {point_name}")

            #get_ha_values(point_name) # calling get_ha_values
            brightness_level = 255 # 0 - 255
            turn_on_lights(brightness_level)
            # turn_off_lights()
            self.change_thermostat_mode('climate.thermostat', 'off') # heat, cool, auto, off
            self.set_thermostat_temperature('climate.thermostat', 29)

            self.change_thermostat_mode('climate.resedio', 'heat') # heat, cool, auto, off
            self.set_thermostat_temperature('climate.resedio', 80)
                        
            self.new = regDef['Volttron Point Name']
            description = regDef.get('Notes', '')
            units = regDef['Units']
            default_value = str(regDef.get("Starting Value", 'sin')).strip()
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            reg_type = type_mapping.get(type_name, str)
            attributes = regDef.get('Attributes', None)
            register_type = FakeRegister if not point_name.startswith('EKG') else EKGregister

            register = register_type(
                read_only,
                point_name,
                units,
                reg_type,
                attributes,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(point_name, register.value)

            self.insert_register(register)


        
        self._create_subscriptions(self.volttron_topic) # running function to subscribe to topic specified in config
        

    def _create_subscriptions(self, topic):
        """
        Unsubscribe from all pub/sub topics and create a subscription to a topic in the configuration which triggers
        the _handle_publish callback
        """
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)    
    def _handle_publish(self, peer, sender, bus, topic, headers, message):
    
        
        # values_to_pull = ["EKG", "EKG_Cos"]
        for value in self.points_to_grab_from_topic:
            for element in message:
                if value in element:
                    print("element", value)
                    data1 = json.dumps(element[f"{value}"]) #data 1 is the json dump of the member from member as a string
                    print("data1", data1)
                    _log.info(f"Matching Value Found: {value} with data: {data1}")
                    url = f"http://{self.ip_address}:8123/api/states/sensor.{value}"
                    headers = {
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    }                 
                    data2 = f'{{"state": {data1}}}'
                    try: # it wont connect and wont throw a status code if you are on the wrong network or have the wrong ip. 
                        response = requests.post(url, headers=headers, data=data2) # posted data to HA is data2. maybe create a try
                        if response.status_code == 200:
                            _log.info(f"----------Sent {data2} from {value} successfully----------")
                        else:
                            _log.info(f"Failed to send {data2} to Home Assistant")
                    except requests.exceptions.ConnectionError as e:
                        _log.info(f"\n-----Connection Error, make sure you are on the same network as home assistant and have correct IP----- {e}\n")
                    break
                else:
                    _log.error(f"{value} not in {element}")
            else:        
                _log.error(f"{element} not in {message}")
        


