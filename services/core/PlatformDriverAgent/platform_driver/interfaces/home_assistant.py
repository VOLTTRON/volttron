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
from math import pi
import json
import sys
from platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from volttron.platform.agent import utils #added this to pull from config store 
from volttron.platform.vip.agent import Agent
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
    def __init__(self, read_only, pointName, units, reg_type, attributes, entity_id,
                 default_value=None, description=''):
        super(HomeAssistantRegister, self).__init__("byte", read_only, pointName, units,
                                           description='')
        self.reg_type = reg_type
        self.attributes = attributes
        self.entity_id = entity_id
        self.value = None

class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.point_name = None
  
    def configure(self, config_dict, registry_config_str): # grabbing from config
        self.ip_address = config_dict.get("ip_address", None)
        self.access_token = config_dict.get("access_token", None)
        self.port = config_dict.get("port", None)

        # Check for None values
        if self.ip_address is None:
            _log.error("IP address is not set.")
            raise ValueError("IP address is required.")
        if self.access_token is None:
            _log.error("Access token is not set.")
            raise ValueError("Access token is required.")
        if self.port is None:
            _log.error("Port is not set.")
            raise ValueError("Port is required.")
        
        self.parse_config(registry_config_str) 
        
    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise RuntimeError(
                "Trying to write to a point configured read only: " + point_name)
        register.value = register.reg_type(value) # setting the value
        
        # Changing lights values in home assistant based off of register value. 
        entity_id = register.entity_id
        if register.value == True:
            self.turn_on_lights(entity_id)
        elif register.value == False:
            self.turn_off_lights(entity_id)
        elif isinstance(register.value, int):
            value = register.value
            self.change_brightness(entity_id, value)
            print(f"Changed brightness of {entity_id} to {register.value}")
        return register.value
    
    def get_entity_data(self, point_name):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"http://{self.ip_address}:{self.port}/api/states/{point_name}" # the /states grabs cuurent state AND attributes of a specific entity
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json() # return the json attributes from entity
        else:
            _log.error(f"Request failed with status code {response.status_code}: {point_name} {response.text}")
            return None
        
    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        for register in read_registers + write_registers:
            entity_id = register.entity_id 
            entity_data = self.get_entity_data(entity_id) # Using Entity ID to get data

            # Assigning state 
            if register.point_name == "state":
                
                state = entity_data.get("state", None)
                register.value = state
                result[register.point_name] = state
            # Assigning attributes
            else:
                attribute = entity_data.get("attributes", {}).get(f"{register.point_name}", 0)
                register.value = attribute
                result[register.point_name] = attribute

        return result

    def parse_config(self, configDict):

        if configDict is None:
            return
        for regDef in configDict:

            if not regDef['Entity ID']:
                continue

            read_only = str(regDef.get('Writable', '')).lower() != 'true' #convert writeable to string and it worked!
            entity_id = regDef['Entity ID']
            self.point_name = regDef['Volttron Point Name']
            self.units = regDef['Units']
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
                entity_id,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(self.point_name, register.value)

            self.insert_register(register)

    def turn_off_lights(self, point_name):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            payload = {
                "entity_id": point_name,
            }
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                _log.info(f"Turned off {point_name}")
        except:
            pass

    def turn_on_lights(self, entity_id):
        url2 = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
        }
        try:
            payload = {
                "entity_id": f"{entity_id}"
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

    def change_brightness(self, point_name, value):
        url2 = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        actual_point_name = point_name.replace("_brightness", "").replace("__", ".")
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
        }
        try:
            # ranges from 0 - 255 for most lights
            payload = {
                "entity_id": f"{actual_point_name}",
                "brightness": value,
            }
            response = requests.post(url2, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                    _log.info(f"Turned on {actual_point_name}")
        except:
            pass      