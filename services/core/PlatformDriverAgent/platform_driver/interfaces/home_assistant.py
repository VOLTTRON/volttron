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


class HomeAssistantRegister(BaseRegister):
    def __init__(self, read_only, pointName, units, reg_type, attributes,
                 default_value=None, description=''):
        super(HomeAssistantRegister, self).__init__("byte", read_only, pointName, units,
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

class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.point_name = None
        self.previous_states = {} # storing previous states to only send commands when changed 
  
    def configure(self, config_dict, registry_config_str): # grabbing from config
        self.ip_address = config_dict.get("ip_address", "0.0.0.0")
        self.access_token = config_dict.get("access_token", "access_token")
        self.volttron_topic = config_dict.get("volttron_topic", "devices")
        self.points_to_grab_from_topic = config_dict.get("points_to_grab_from_topic", "points_to_grab_from_topic")
        self.port = config_dict.get("port", "port")
        self.registry_config = config_dict.get("registry_config","registry_config")
        self.parse_config(registry_config_str) 

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise RuntimeError(
                "Trying to write to a point configured read only: " + point_name)
        
        previous_value = register.value # store the previous value 
        register.value = register.reg_type(value) # setting the value
        print(f"{previous_value} {register}")

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
            url = f"http://{self.ip_address}:{self.port}/api/states/{entity_id}" # the /states grabs cuurent state AND attributes of a specific entity
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
    

    def parse_config(self, configDict):

        if configDict is None:
            return
        for regDef in configDict: # go through items in config and skip if its not point name

            if not regDef['Point Name']:
                continue

            read_only = str(regDef.get('Writable', '')).lower() != 'true' #convert writeable to string and it worked!

            self.point_name = regDef['Volttron Point Name']
            self.units = regDef['Units']

            #set_thermostat_temperature(65)
            #change_thermostat_mode("cool") # heat, cool, auto, off

                        
            self.new = regDef['Volttron Point Name']
            description = regDef.get('Notes', '')
            
            default_value = str(regDef.get("Starting Value", 'sin')).strip()
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            reg_type = type_mapping.get(type_name, str)
            attributes = regDef.get('Attributes', {})
            register_type = HomeAssistantRegister

            register = register_type(
                read_only,
                self.point_name,
                self.units,
                reg_type,
                attributes,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(self.point_name, register.value)

            self.insert_register(register)

        
        self._create_subscriptions(self.volttron_topic) # running function to subscribe to topic specified in config


    def turn_off_lights(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            payload = {
                "entity_id": entity_id,
            }
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                _log.info(f"Turned off {entity_id}")
        except:
            pass

    def turn_on_lights(self, entity_id, brightness_level):
        url2 = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
        }
        try:
            # ranges from 0 - 255 for most lights
            payload = {
                "entity_id": f"{entity_id}",
                "brightness": brightness_level,
            }
            response = requests.post(url2, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                    _log.info(f"Turned on {entity_id}")
        except:
            pass

    def change_thermostat_mode(self, mode):
        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_hvac_mode"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "content-type": "application/json",
        }
        point_names = [y.strip() for y in self.point_name.split('\n')]
        for entity in point_names:
            if entity.startswith("climate."):
                data = {
                    "entity_id": entity,
                    "hvac_mode": mode,
                }
                response = requests.post(url, headers=headers, json=data)
        
                if response.status_code == 200:
                    _log.info(f"Successfully changed the mode of {entity} to {mode}")
                else:
                    _log.info(f"Failed to change the mode of {entity}. Response: {response.text}")

    def set_thermostat_temperature(self, temperature):
        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_temperature"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "content-type": "application/json",
        }
        point_names = [y.strip() for y in self.point_name.split('\n')]
        for entity in point_names:
            if entity.startswith("climate."):
                if self.units == "C":
                    converted_temp = round((temperature - 32) * 5/9, 1)
                    _log.info(f"converted temp {converted_temp}")
                    data = {
                        "entity_id": entity,
                        "temperature": converted_temp,
                    }
                    response = requests.post(url, headers=headers, json=data)
                else:
                    data2 = {
                        "entity_id": entity,
                        "temperature": temperature,
                    }
                    response = requests.post(url, headers=headers, json=data2)
        
                if response.status_code == 200:
                    _log.info(f"Successfully changed the temp of {entity} to {temperature}")
                else:
                    _log.info(f"Failed to change the temp of {entity}. Response: {response.text}")

    def _create_subscriptions(self, topic):
        """
        Unsubscribe from all pub/sub topics and create a subscription to a topic in the configuration which triggers
        the _handle_publish callback
        """
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)    
    def _handle_publish(self, peer, sender, bus, topic, headers, messages):
        for message in messages:
            for entity_id, entity_data in message.items():

                state = entity_data.get("state", None)
                brightness = entity_data.get("brightness", None)
                temperature = entity_data.get("temperature", None)

                previous_state = self.previous_states.get(entity_id, None)
                previous_brightness = self.previous_states.get(f"{entity_id}_brightness", None)
                previous_temperature = self.previous_states.get(f"{entity_id}_temperature", None)

                #LIGHTS
                if entity_id.startswith("light."):
                    if state != previous_state:  # if state changed
                        if state == "on":
                            _log.info(f"{entity_id} value has been detected as on")
                            self.turn_on_lights(entity_id, 255 if brightness is None else brightness)
                        elif state == "off":
                            _log.info(f"{entity_id} detected as off!")
                            self.turn_off_lights(entity_id)
                        else:
                            continue

                    # this handles brightness change even when state doesn't change
                    if brightness != previous_brightness:
                        print(f"{entity_id} brightness has been detected and changed to {brightness} / 254")
                        self.turn_on_lights(entity_id, brightness)

                    self.previous_states[entity_id] = state
                    self.previous_states[f"{entity_id}_brightness"] = brightness # example previous_states[light.entity_brightness] = brightness

                # THERMOSTATS
                elif entity_id.startswith("climate."):

                    if state != previous_state:
                        if state == "cool":
                            self.change_thermostat_mode("cool")
                            _log.info(f"{entity_id} value has been changed to cool")
                        elif state == "heat":
                            _log.info(f"{entity_id} value has been changed to heat")
                            self.change_thermostat_mode("heat")
                        elif state == "off":
                            _log.info(f"{entity_id} value has been changed to off")
                            self.change_thermostat_mode("off")
                        else: 
                            continue
                    if temperature != previous_temperature:
                        print(f"{entity_id} temperature has been detected and changed to {temperature} degrees F")
                        self.set_thermostat_temperature(temperature)

                    self.previous_states[entity_id] = state
                    self.previous_states[f"{entity_id}_temperature"] = temperature # example previous_states[light.entity_brightness] = brightness
                else:
                    continue

        
