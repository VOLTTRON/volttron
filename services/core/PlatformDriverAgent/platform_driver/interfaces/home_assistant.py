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
type_mapping = {
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "bool": bool,
    "boolean": bool,
}


class HomeAssistantRegister(BaseRegister):
    def __init__(
        self,
        read_only,
        pointName,
        units,
        reg_type,
        attributes,
        entity_id,
        entity_point,
        default_value=None,
        description="",
    ):
        super(HomeAssistantRegister, self).__init__(
            "byte", read_only, pointName, units, description=""
        )
        self.reg_type = reg_type
        self.attributes = attributes
        self.entity_id = entity_id
        self.value = None
        self.entity_point = entity_point


def _post_method(url, headers, data, operation_description):
    """
    Shared helper for POST calls to the Home Assistant HTTP API.
    Logs and raises an error if the request fails.
    """
    err = None
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            _log.info(f"Success: {operation_description}")
        else:
            err = (
                f"Failed to {operation_description}. "
                f"Status code: {response.status_code}. Response: {response.text}"
            )

    except requests.RequestException as e:
        err = f"Error when attempting - {operation_description} : {e}"

    if err:
        _log.error(err)
        raise Exception(err)


class Interface(BasicRevert, BaseInterface):
    """
    Home Assistant driver interface.

    Reads and writes entity state/attributes via the Home Assistant HTTP API.
    Supports multiple domains:
    - climate
    - light
    - input_boolean
    - fan
    - switch
    - cover
    - generic entities (read-only via state/attributes)
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.point_name = None
        self.ip_address = None
        self.access_token = None
        self.port = None
        self.units = None

    def configure(self, config_dict, registry_config_str):
        """
        Configure the driver from the driver configuration and
        parse the registry entries.
        """
        self.ip_address = config_dict.get("ip_address", None)
        self.access_token = config_dict.get("access_token", None)
        self.port = config_dict.get("port", None)

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
        """
        Read a single point from Home Assistant, using entity_id and entity_point
        from the registry configuration.
        """
        register = self.get_register_by_name(point_name)

        entity_data = self.get_entity_data(register.entity_id)
        if register.point_name == "state":
            result = entity_data.get("state", None)
            return result
        else:
            value = entity_data.get("attributes", {}).get(f"{register.point_name}", 0)
            return value

    def _set_point(self, point_name, value):
        """
        Write a single point to Home Assistant.

        The logic branches on HA domain:
        - light.*: on/off and brightness
        - input_boolean.*: on/off
        - climate.*: hvac mode and temperature
        - fan.*: on/off and speed/percentage
        - switch.*: on/off
        - cover.*: open/close and position
        """
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError(
                "Trying to write to a point configured read only: " + point_name
            )

        register.value = register.reg_type(value)
        entity_point = register.entity_point

        # ---- LIGHT ----
        if register.entity_id.startswith("light."):
            if entity_point == "state":
                if isinstance(register.value, int) and register.value in [0, 1]:
                    if register.value == 1:
                        self.turn_on_lights(register.entity_id)
                    elif register.value == 0:
                        self.turn_off_lights(register.entity_id)
                else:
                    error_msg = (
                        f"State value for {register.entity_id} "
                        f"should be an integer value of 1 or 0"
                    )
                    _log.info(error_msg)
                    raise ValueError(error_msg)

            elif entity_point == "brightness":
                # Brightness is 0–255 in Home Assistant
                if isinstance(register.value, int) and 0 <= register.value <= 255:
                    self.change_brightness(register.entity_id, register.value)
                else:
                    error_msg = (
                        "Brightness value should be an integer between 0 and 255"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            else:
                error_msg = (
                    f"Unexpected point_name {point_name} for register "
                    f"{register.entity_id}"
                )
                _log.error(error_msg)
                raise ValueError(error_msg)

        # ---- INPUT BOOLEAN ----
        elif register.entity_id.startswith("input_boolean."):
            if entity_point == "state":
                if isinstance(register.value, int) and register.value in [0, 1]:
                    if register.value == 1:
                        self.set_input_boolean(register.entity_id, "on")
                    elif register.value == 0:
                        self.set_input_boolean(register.entity_id, "off")
                else:
                    error_msg = (
                        f"State value for {register.entity_id} "
                        f"should be an integer value of 1 or 0"
                    )
                    _log.info(error_msg)
                    raise ValueError(error_msg)
            else:
                _log.info("Currently, input_booleans only support state")

        # ---- CLIMATE ----
        elif register.entity_id.startswith("climate."):
            if entity_point == "state":
                # 0,2,3,4 used as numeric encoding for off/heat/cool/auto
                if isinstance(register.value, int) and register.value in [0, 2, 3, 4]:
                    if register.value == 0:
                        self.change_thermostat_mode(
                            entity_id=register.entity_id, mode="off"
                        )
                    elif register.value == 2:
                        self.change_thermostat_mode(
                            entity_id=register.entity_id, mode="heat"
                        )
                    elif register.value == 3:
                        self.change_thermostat_mode(
                            entity_id=register.entity_id, mode="cool"
                        )
                    elif register.value == 4:
                        self.change_thermostat_mode(
                            entity_id=register.entity_id, mode="auto"
                        )
                else:
                    error_msg = (
                        "Climate state should be an integer "
                        "value of 0, 2, 3, or 4"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            elif entity_point == "temperature":
                self.set_thermostat_temperature(
                    entity_id=register.entity_id, temperature=register.value
                )

            else:
                error_msg = (
                    "Currently set_point is supported only for "
                    "thermostats state and temperature "
                    f"{register.entity_id}"
                )
                _log.error(error_msg)
                raise ValueError(error_msg)

        # ---- FAN ----
        elif register.entity_id.startswith("fan."):
            if entity_point == "state":
                if isinstance(register.value, int) and register.value in [0, 1]:
                    if register.value == 1:
                        self.turn_on_fan(register.entity_id)
                    elif register.value == 0:
                        self.turn_off_fan(register.entity_id)
                else:
                    error_msg = (
                        f"State value for {register.entity_id} "
                        f"should be an integer value of 1 or 0"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            elif entity_point == "percentage":
                # Fan percentage is typically 0–100
                if isinstance(register.value, int) and 0 <= register.value <= 100:
                    self.set_fan_speed(register.entity_id, register.value)
                else:
                    error_msg = (
                        "Fan percentage should be an integer between 0 and 100"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            else:
                error_msg = (
                    f"Unexpected point_name {point_name} for fan "
                    f"{register.entity_id}"
                )
                _log.error(error_msg)
                raise ValueError(error_msg)

        # ---- SWITCH ----
        elif register.entity_id.startswith("switch."):
            if entity_point == "state":
                if isinstance(register.value, int) and register.value in [0, 1]:
                    if register.value == 1:
                        self.turn_on_switch(register.entity_id)
                    elif register.value == 0:
                        self.turn_off_switch(register.entity_id)
                else:
                    error_msg = (
                        f"State value for {register.entity_id} "
                        f"should be an integer value of 1 or 0"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)
            else:
                error_msg = (
                    f"Unexpected point_name {point_name} for switch "
                    f"{register.entity_id}"
                )
                _log.error(error_msg)
                raise ValueError(error_msg)

        # ---- COVER ----
        elif register.entity_id.startswith("cover."):
            # We treat state as a numeric encoding of open/closed
            # 1 = open, 0 = closed
            if entity_point == "state":
                if isinstance(register.value, int) and register.value in [0, 1]:
                    if register.value == 1:
                        self.open_cover(register.entity_id)
                    elif register.value == 0:
                        self.close_cover(register.entity_id)
                else:
                    error_msg = (
                        f"State value for {register.entity_id} "
                        f"should be an integer value of 1 or 0"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            elif entity_point == "position":
                # 0–100 position percentage for covers
                if isinstance(register.value, int) and 0 <= register.value <= 100:
                    self.set_cover_position(register.entity_id, register.value)
                else:
                    error_msg = (
                        "Cover position should be an integer between 0 and 100"
                    )
                    _log.error(error_msg)
                    raise ValueError(error_msg)

            else:
                error_msg = (
                    f"Unexpected point_name {point_name} for cover "
                    f"{register.entity_id}"
                )
                _log.error(error_msg)
                raise ValueError(error_msg)

        # ---- FALLBACK ----
        else:
            error_msg = (
                f"Unsupported entity_id: {register.entity_id}. "
                "Currently set_point is supported only for thermostats, "
                "lights, fans, switches, covers and input_booleans"
            )
            _log.error(error_msg)
            raise ValueError(error_msg)

        return register.value

    def get_entity_data(self, point_name):
        """
        Retrieve the raw state + attributes payload for an entity from Home Assistant.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"http://{self.ip_address}:{self.port}/api/states/{point_name}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = (
                f"Request failed with status code {response.status_code}, "
                f"Point name: {point_name}, response: {response.text}"
            )
            _log.error(error_msg)
            raise Exception(error_msg)

    def _scrape_all(self):
        """
        Scrape all configured registers and return a dictionary mapping
        Volttron point names to their current values.
        """
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        for register in read_registers + write_registers:
            entity_id = register.entity_id
            entity_point = register.entity_point
            try:
                entity_data = self.get_entity_data(entity_id)

                # ---- CLIMATE ----
                if entity_id.startswith("climate."):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        # Map thermostat string states to numeric codes
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
                            error_msg = (
                                f"State {state} from {entity_id} is not yet supported"
                            )
                            _log.error(error_msg)
                            raise ValueError(error_msg)
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

                # ---- LIGHT / INPUT_BOOLEAN ----
                elif entity_id.startswith("light.") or entity_id.startswith(
                    "input_boolean."
                ):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        # Map on/off to 1/0
                        if state == "on":
                            register.value = 1
                            result[register.point_name] = 1
                        elif state == "off":
                            register.value = 0
                            result[register.point_name] = 0
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

                # ---- FAN ----
                elif entity_id.startswith("fan."):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        if state == "on":
                            register.value = 1
                            result[register.point_name] = 1
                        elif state == "off":
                            register.value = 0
                            result[register.point_name] = 0
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

                # ---- SWITCH ----
                elif entity_id.startswith("switch."):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        if state == "on":
                            register.value = 1
                            result[register.point_name] = 1
                        elif state == "off":
                            register.value = 0
                            result[register.point_name] = 0
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

                # ---- COVER ----
                elif entity_id.startswith("cover."):
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        # Map cover states to numeric codes
                        # Open/opening -> 1, closed/closing -> 0
                        if state in ("open", "opening"):
                            register.value = 1
                            result[register.point_name] = 1
                        elif state in ("closed", "closing"):
                            register.value = 0
                            result[register.point_name] = 0
                        else:
                            # Unknown state – leave at 0 but log
                            _log.warning(
                                f"Unsupported cover state {state} from {entity_id}"
                            )
                            register.value = 0
                            result[register.point_name] = 0
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

                # ---- DEFAULT FALLBACK ----
                else:
                    # Generic entity:
                    # - state is returned as-is
                    # - attributes read from attributes dict
                    if entity_point == "state":
                        state = entity_data.get("state", None)
                        register.value = state
                        result[register.point_name] = state
                    else:
                        attribute = entity_data.get("attributes", {}).get(
                            f"{entity_point}", 0
                        )
                        register.value = attribute
                        result[register.point_name] = attribute

            except Exception as e:
                _log.error(
                    f"An unexpected error occurred for entity_id: {entity_id}: {e}"
                )

        return result

    def parse_config(self, config_dict):
        """
        Build HomeAssistantRegister objects from the registry config.
        """
        if config_dict is None:
            return

        for regDef in config_dict:
            if not regDef["Entity ID"]:
                continue

            read_only = str(regDef.get("Writable", "")).lower() != "true"
            entity_id = regDef["Entity ID"]
            entity_point = regDef["Entity Point"]
            self.point_name = regDef["Volttron Point Name"]
            self.units = regDef["Units"]
            description = regDef.get("Notes", "")
            default_value = "Starting Value"
            type_name = regDef.get("Type", "string")
            reg_type = type_mapping.get(type_name, str)
            attributes = regDef.get("Attributes", {})
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
                description=description,
            )

            if default_value is not None:
                self.set_default(self.point_name, register.value)

            self.insert_register(register)

    # --------------------------- LIGHT HELPERS ---------------------------

    def turn_off_lights(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn off {entity_id}")

    def turn_on_lights(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {"entity_id": f"{entity_id}"}
        _post_method(url, headers, payload, f"turn on {entity_id}")

    def change_brightness(self, entity_id, value):
        """
        Set brightness for a light (0–255).
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": f"{entity_id}", "brightness": value}
        _post_method(url, headers, payload, f"set brightness of {entity_id} to {value}")

    # ------------------------ CLIMATE HELPERS ---------------------------

    def change_thermostat_mode(self, entity_id, mode):
        if not entity_id.startswith("climate."):
            _log.error(f"{entity_id} is not a valid thermostat entity ID.")
            return

        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_hvac_mode"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "content-type": "application/json",
        }
        data = {"entity_id": entity_id, "hvac_mode": mode}
        _post_method(url, headers, data, f"change mode of {entity_id} to {mode}")

    def set_thermostat_temperature(self, entity_id, temperature):
        if not entity_id.startswith("climate."):
            _log.error(f"{entity_id} is not a valid thermostat entity ID.")
            return

        url = f"http://{self.ip_address}:{self.port}/api/services/climate/set_temperature"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "content-type": "application/json",
        }

        if self.units == "C":
            converted_temp = round((temperature - 32) * 5 / 9, 1)
            _log.info(f"Converted temperature {converted_temp}")
            data = {"entity_id": entity_id, "temperature": converted_temp}
        else:
            data = {"entity_id": entity_id, "temperature": temperature}

        _post_method(
            url,
            headers,
            data,
            f"set temperature of {entity_id} to {temperature}",
        )

    # --------------------- INPUT BOOLEAN HELPERS ------------------------

    def set_input_boolean(self, entity_id, state):
        """
        Set an input_boolean to on/off.
        """
        service = "turn_on" if state == "on" else "turn_off"
        url = (
            f"http://{self.ip_address}:{self.port}/api/services/input_boolean/{service}"
        )
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {"entity_id": entity_id}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            _log.info(f"Successfully set {entity_id} to {state}")
        else:
            _log.error(
                f"Failed to set {entity_id} to {state}: {response.status_code} "
                f"{response.text}"
            )

    # --------------------------- FAN HELPERS ----------------------------

    def turn_on_fan(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {"entity_id": f"{entity_id}"}
        _post_method(url, headers, payload, f"turn on {entity_id}")

    def turn_off_fan(self, entity_id):
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {"entity_id": f"{entity_id}"}
        _post_method(url, headers, payload, f"turn off {entity_id}")

    def set_fan_speed(self, entity_id, speed):
        """
        Set fan speed as percentage (0–100).
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/fan/set_speed"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id, "speed": speed}
        _post_method(url, headers, payload, f"set speed of {entity_id} to {speed}")

    # -------------------------- SWITCH HELPERS --------------------------

    def turn_on_switch(self, entity_id):
        """
        Turn on a switch device.
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/switch/turn_on"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn on switch {entity_id}")

    def turn_off_switch(self, entity_id):
        """
        Turn off a switch device.
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/switch/turn_off"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"turn off switch {entity_id}")

    # --------------------------- COVER HELPERS --------------------------

    def open_cover(self, entity_id):
        """
        Open a cover (e.g., blind, garage door).
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/open_cover"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"open cover {entity_id}")

    def close_cover(self, entity_id):
        """
        Close a cover.
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/close_cover"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}
        _post_method(url, headers, payload, f"close cover {entity_id}")

    def set_cover_position(self, entity_id, position):
        """
        Set cover position (0–100).
        """
        url = f"http://{self.ip_address}:{self.port}/api/services/cover/set_cover_position"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id, "position": position}
        _post_method(
            url,
            headers,
            payload,
            f"set position of {entity_id} to {position}",
        )
