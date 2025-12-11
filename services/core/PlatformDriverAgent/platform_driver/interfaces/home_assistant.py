# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}


import random
from math import pi
import json
import sys
from platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from volttron.platform.agent import utils
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
    def __init__(self, read_only, pointName, units, reg_type, attributes, entity_id, entity_point, default_value=None,
                 description=''):
        super(HomeAssistantRegister, self).__init__("byte", read_only, pointName, units, description='')
        self.reg_type = reg_type
        self.attributes = attributes
        self.entity_id = entity_id
        self.value = None
        self.entity_point = entity_point


def _post_method(url, headers, data, operation_description):
    err = None
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            _log.info(f"Success: {operation_description}")
        else:
            err = f"Failed to {operation_description}. Status code: {response.status_code}. " \
                  f"Response: {response.text}"

    except requests.RequestException as e:
        err = f"Error when attempting - {operation_description} : {e}"
    if err:
        _log.error(err)
        raise Exception(err)


class Interface(BasicRevert, BaseInterface):
    
    # Dispatch Table: Maps device domain → Write processing method
    # Future additions of equipment only need to be written here
    WRITE_HANDLERS = {
        "light": "_write_light",
        "input_boolean": "_write_input_boolean",
        "climate": "_write_climate",
        "switch": "_write_switch",
        "cover": "_write_cover",
        "fan": "_write_fan", 
    }


    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.point_name = None
        self.ip_address = None
        self.access_token = None
        self.port = None
        self.units = None

    def configure(self, config_dict, registry_config_str):
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

        entity_data = self.get_entity_data(register.entity_id)
        if register.point_name == "state":
            result = entity_data.get("state", None)
            return result
        else:
            value = entity_data.get("attributes", {}).get(f"{register.point_name}", 0)
            return value

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)

        if register.read_only:
            raise IOError(f"Trying to write read-only point: {point_name}")

        # Volttron Type Conversion
        register.value = register.reg_type(value)

        entity_id = register.entity_id
        domain = entity_id.split(".")[0]          
        handler_name = self.WRITE_HANDLERS.get(domain)

        if handler_name is None:
            raise ValueError(f"Unsupported device domain: {domain}")

        handler = getattr(self, handler_name)
        return handler(register)


    def get_entity_data(self, point_name):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        # the /states grabs current state AND attributes of a specific entity
        url = f"http://{self.ip_address}:{self.port}/api/states/{point_name}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()  # return the json attributes from entity
        else:
            error_msg = f"Request failed with status code {response.status_code}, Point name: {point_name}, " \
                        f"response: {response.text}"
            _log.error(error_msg)
            raise Exception(error_msg)

    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        for register in read_registers + write_registers:
            entity_id = register.entity_id
            entity_point = register.entity_point
            try:
                entity_data = self.get_entity_data(entity_id)  # Using Entity ID to get data
                if "climate." in entity_id:  # handling thermostats.
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        # Giving thermostat states an equivalent number.
                        if state == "off":
                            register.value = 0
                            result[register.point_name] = 0
                        elif state == "heat":
                            register.value = 2
                            result[register.point_name] = 2
                        elif state == "cool":
                            register.value = 3
                            result[register.point_name] = 3
                        elif state == "auto":
                            register.value = 4
                            result[register.point_name] = 4
                        else:
                            error_msg = f"State {state} from {entity_id} is not yet supported"
                            _log.error(error_msg)
                            ValueError(error_msg)
                    # Assigning attributes
                    else:
                        attribute = entity_data.get("attributes", {}).get(f"{entity_point}", 0)
                        register.value = attribute
                        result[register.point_name] = attribute
                # handling light, input_boolean, switch states
                elif ("light." in entity_id) or ("input_boolean." in entity_id) or ("switch." in entity_id):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        # Converting light states to numbers.
                        if state == "on":
                            register.value = 1
                            result[register.point_name] = 1
                        elif state == "off":
                            register.value = 0
                            result[register.point_name] = 0
                    else:
                        attribute = entity_data.get("attributes", {}).get(f"{entity_point}", 0)
                        register.value = attribute
                        result[register.point_name] = attribute
                else:  # handling all devices that are not thermostats or light states
                    if entity_point == "state":

                        state = entity_data.get("state", None)
                        register.value = state
                        result[register.point_name] = state
                    # Assigning attributes
                    else:
                        attribute = entity_data.get("attributes", {}).get(f"{entity_point}", 0)
                        register.value = attribute
                        result[register.point_name] = attribute
            except Exception as e:
                _log.error(f"An unexpected error occurred for entity_id: {entity_id}: {e}")

        return result

    def parse_config(self, config_dict):
        if config_dict is None:
            return
        for regDef in config_dict:

            if not regDef['Entity ID']:
                continue

            read_only = str(regDef.get('Writable', '')).lower() != 'true'
            entity_id = regDef['Entity ID']
            entity_point = regDef['Entity Point']
            self.point_name = regDef['Volttron Point Name']
            self.units = regDef['Units']
            description = regDef.get('Notes', '')
            default_value = ("Starting Value")
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
                entity_point,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(self.point_name, register.value)

            self.insert_register(register)


    # Independent Handler for switch
    def _write_switch(self, register):
        entity_id = register.entity_id
        entity_point = register.entity_point
        value = register.value

        if entity_point != "state":
            raise ValueError("Switch only supports writing 'state'")

        if value == 1:
            return self.turn_on_switch(entity_id)
        elif value == 0:
            return self.turn_off_switch(entity_id)
        else:
            raise ValueError("Switch value must be 0 or 1")


    # Independent Handler for cover
    def _write_cover(self, register):
        entity_id = register.entity_id
        point = register.entity_point
        value = register.value

        # 0=close, 1=open, 2=stop
        if point == "state":
            if value == 1:
                return self.open_cover(entity_id)
            elif value == 0:
                return self.close_cover(entity_id)
            elif value == 2:
                return self.stop_cover(entity_id)
            else:
                raise ValueError("Cover state must be 0(close), 1(open), 2(stop)")

        # --- Processing Position (Percentage 0-100) ---
        elif point == "position":
            if not (0 <= value <= 100):
                raise ValueError("Cover position must be between 0 and 100")
            return self.set_cover_position(entity_id, value)

        # --- Processing tilt (angle 0~100) ---
        elif point == "tilt":
            if not (0 <= value <= 100):
                raise ValueError("Cover tilt must be 0~100")
            return self.set_cover_tilt(entity_id, value)

        else:
            raise ValueError(f"Unsupported cover point: {point}")


    # Independent Handler for fan
    def _write_fan(self, register):
        entity_id = register.entity_id
        point = register.entity_point
        value = register.value

        # ---------------------
        # Fan State (on/off)
        # ---------------------
        if point == "state":
            if value == 1:
                return self.turn_on_fan(entity_id)
            elif value == 0:
                return self.turn_off_fan(entity_id)
            else:
                raise ValueError("Fan state must be 0(off) or 1(on)")

        # ---------------------
        # Fan Speed (0~100)
        # ---------------------
        elif point == "percentage":
            if not (0 <= value <= 100):
                raise ValueError("Fan percentage must be 0~100")
            return self.set_fan_percentage(entity_id, value)

        # ---------------------
        # Fan Direction (0=forward, 1=reverse)
        # ---------------------
        elif point == "direction":
            if value == 0:
                direction = "forward"
            elif value == 1:
                direction = "reverse"
            else:
                raise ValueError("Fan direction must be 0(forward) or 1(reverse)")
            return self.set_fan_direction(entity_id, direction)

        # ---------------------
        # Optional Toggle
        # ---------------------
        elif point == "toggle":
            return self.toggle_fan(entity_id)

        else:
            raise ValueError(f"Unsupported fan point: {point}")



    # Independent Handler for light
    def _write_light(self, register):
        entity_id = register.entity_id
        entity_point = register.entity_point
        value = register.value

        if entity_point == "state":
            if value == 1:
                return self.turn_on_lights(entity_id)
            elif value == 0:
                return self.turn_off_lights(entity_id)
            else:
                raise ValueError("Light state must be 0 or 1")

        elif entity_point == "brightness":
            if not (0 <= value <= 255):
                raise ValueError("Brightness must be 0 to 255")
            return self.change_brightness(entity_id, value)

        else:
            raise ValueError(f"Unsupported light point: {entity_point}")


    def _write_input_boolean(self, register):
        entity_id = register.entity_id
        value = register.value

        if value == 1:
            return self.set_input_boolean(entity_id, "on")
        elif value == 0:
            return self.set_input_boolean(entity_id, "off")
        else:
            raise ValueError("input_boolean state must be 0 or 1")

    
    def _write_climate(self, register):
        entity_id = register.entity_id
        value = register.value
        entity_point = register.entity_point

        if entity_point == "state":
            modes = {0: "off", 2: "heat", 3: "cool", 4: "auto"}
            if value not in modes:
                raise ValueError("Climate mode must be 0,2,3,4")
            return self.change_thermostat_mode(entity_id, modes[value])

        elif entity_point == "temperature":
            return self.set_thermostat_temperature(entity_id, value)

        else:
            raise ValueError(f"Unsupported climate point: {entity_point}")




    # The following are the API methods for various types of devices
    # ===================================================================
    # ===================================================================
    # ===================================================================
    # ========== COVER API METHODS ==========
    def open_cover(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/open_cover"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"open cover {entity_id}")

    def close_cover(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/close_cover"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"close cover {entity_id}")

    def stop_cover(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/stop_cover"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"stop cover {entity_id}")

    def set_cover_position(self, entity_id, position):
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/set_cover_position"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"entity_id": entity_id, "position": position}
        _post_method(url, headers, payload, f"set cover {entity_id} position to {position}")

    def set_cover_tilt(self, entity_id, tilt_position):
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/set_cover_tilt_position"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"entity_id": entity_id, "tilt_position": tilt_position}
        _post_method(url, headers, payload, f"set cover tilt of {entity_id} to {tilt_position}")




    # ========== FAN API METHODS ==========
    def turn_on_fan(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn on fan {entity_id}")


    def turn_off_fan(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn off fan {entity_id}")


    def toggle_fan(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/toggle"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"toggle fan {entity_id}")


    def set_fan_percentage(self, entity_id, percentage):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/set_percentage"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id, "percentage": percentage}
        _post_method(url, headers, payload, f"set fan {entity_id} percentage to {percentage}")


    def set_fan_direction(self, entity_id, direction):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/set_direction"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id, "direction": direction}
        _post_method(url, headers, payload, f"set fan {entity_id} direction to {direction}")




    # ========== LIGHT API METHODS ==========
    def turn_off_lights(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "entity_id": entity_id,
        }
        _post_method(url, headers, payload, f"turn off {entity_id}")

    def turn_on_lights(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
        }

        payload = {
            "entity_id": f"{entity_id}"
        }
        _post_method(url, headers, payload, f"turn on {entity_id}")




    # ========== SWITCH API METHODS ==========
    def turn_off_switch(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/switch/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn off {entity_id}")

    def turn_on_switch(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/switch/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn on {entity_id}")



    
    # ========== CLIMATE API METHODS ==========
    def change_thermostat_mode(self, entity_id, mode):
        # Check if enttiy_id startswith climate.
        if not entity_id.startswith("climate."):
            _log.error(f"{entity_id} is not a valid thermostat entity ID.")
            return
        # Build header
        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_hvac_mode"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "content-type": "application/json",
        }
        # Build data
        data = {
            "entity_id": entity_id,
            "hvac_mode": mode,
        }
        # Post data
        _post_method(url, headers, data, f"change mode of {entity_id} to {mode}")

    def set_thermostat_temperature(self, entity_id, temperature):
        # Check if the provided entity_id starts with "climate."
        if not entity_id.startswith("climate."):
            _log.error(f"{entity_id} is not a valid thermostat entity ID.")
            return

        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_temperature"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "content-type": "application/json",
        }

        if self.units == "C":
            converted_temp = round((temperature - 32) * 5/9, 1)
            _log.info(f"Converted temperature {converted_temp}")
            data = {
                "entity_id": entity_id,
                "temperature": converted_temp,
            }
        else:
            data = {
                "entity_id": entity_id,
                "temperature": temperature,
            }
        _post_method(url, headers, data, f"set temperature of {entity_id} to {temperature}")

    def change_brightness(self, entity_id, value):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
        }
        # ranges from 0 - 255
        payload = {
            "entity_id": f"{entity_id}",
            "brightness": value,
        }

        _post_method(url, headers, payload, f"set brightness of {entity_id} to {value}")

    def set_input_boolean(self, entity_id, state):
        service = 'turn_on' if state == 'on' else 'turn_off'
        url = f"http://{self.ip_address}:{self.port}/api/services/input_boolean/{service}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "entity_id": entity_id
        }

        response = requests.post(url, headers=headers, json=payload)

        # Optionally check for a successful response
        if response.status_code == 200:
            print(f"Successfully set {entity_id} to {state}")
        else:
            print(f"Failed to set {entity_id} to {state}: {response.text}")
