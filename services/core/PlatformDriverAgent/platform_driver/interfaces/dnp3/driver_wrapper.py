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
import abc
import random
import datetime
import math
from math import pi

from platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
# from ...platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from csv import DictReader
from io import StringIO
import logging
import sys

import requests

from typing import List, Type, Dict, Union, Optional, TypeVar
from time import sleep

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
# _log = logging.getLogger("data_retrieval_demo")
_log.addHandler(stdout_stream)
_log.setLevel(logging.DEBUG)
_log.setLevel(logging.WARNING)

# TODO: parse to python_type based on literal. i.e., locate("int")("1") -> int(1)
# Design the data type validation logic (recommend but not enforce?)
type_mapping = {"string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool}

# Type alias
RegisterValue = Union[int, str, float, bool]
Register = TypeVar("Register", bound=BaseRegister)


class WrapperRegister(BaseRegister):
    """
    Template Register, host boilerplate code
    """

    # TODO: do we need to separate read-only and writable register? How a writable register looks like?
    # TODO: e.g., How the set-value pass to the register class?
    # TODO: (Mimic what happen to get_register_value method, we might need a controller method.
    def __init__(self, driver_config: dict, point_name: str, data_type: RegisterValue, units: str, read_only: bool,
                 default_value=None, description='', csv_config={}, *args, **kwargs):
        """
        Parameters  # TODO: clean this up,
        ----------
        config_dict: associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.

        read_only: associated with `Writable` in driver-config.csv
        point_name: associated with `Volttron Point Name` in driver-config.csv
        units: associated with `Units` in driver-config.csv
        reg_type: ?? # TODO: clean this up,
        default_value: ?? # TODO: clean this up,
        description: ?? # TODO: clean this up,

        Associated with Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
            read_only = regDef['Writable'].lower() != 'true'
            point_name = regDef['Volttron Point Name']
            description = regDef.get('Notes', '')
            units = regDef['Units']
            default_value = regDef.get("Starting Value", 'sin').strip()
        """
        super().__init__("byte", read_only, point_name, units, description='')
        self._value: str = ""
        self.driver_config: dict = driver_config

        self.point_name: str = point_name
        self.data_type_str: str = data_type  # "byte" or "bit"
        self.units: Optional[str] = units
        self.read_only: bool = read_only
        self.default_value: Optional[RegisterValue] = default_value
        self.description: str = description
        self.csv_config: list = csv_config

    @property
    def value(self):
        self._value = self.get_register_value()  # pre-requite methods
        return self._value

    @value.setter
    def value(self, x: RegisterValue):
        if self.read_only:
            raise RuntimeError(  # TODO: Is RuntimeError necessary
                "Trying to write to a point configured read only: " + self.point_name)  # TODO: clean up
        self._value = x

    @abc.abstractmethod
    def get_register_value(self, **kwargs) -> RegisterValue:
        """
        Override this to get register value
        Examples 1 retrieve:
            def get_register_value():
                some_url: str = self.config_dict.get("url")
                return self.get_restAPI_value(url=some_url)
            def get_restAPI_value(url=some_url)
                ...
        Returns
        -------

        """

    @abc.abstractmethod
    def set_register_value(self, value, **kwargs) -> Optional[RegisterValue]:  # TODO: need an example/redesign for this
        pass
    #     """
    #     Override this to set register value. (Only for writable==True/read_only==False)
    #     Examples:
    #         def set_register_value():
    #             some_temperature: int = get_comfortable_temperature(...)
    #             self.value(some_temperature)
    #         def get_comfortable_temperature(**kwargs) -> int:
    #             ...
    #     Returns
    #     -------
    #
    #     """


# alias
ImplementedRegister = Union[WrapperRegister, Type[WrapperRegister]]


class DriverConfig:
    """
    For validate driver configuration, e.g., driver-config.csv
    """

    def __init__(self, csv_config: List[dict]):
        self.csv_config: List[dict] = csv_config
        """

        Parameters
        ----------
        csv_config

        Returns
        -------
        Examples:
            [{'Point Name': 'Heartbeat', 'Volttron Point Name': 'Heartbeat', 'Units': 'On/Off',
            'Units Details': 'On/Off', 'Writable': 'TRUE', 'Starting Value': '0', 'Type': 'boolean',
            'Notes': 'Point for heartbeat toggle'},
            {'Point Name': 'Catfact', 'Volttron Point Name': 'Catfact', 'Units': 'No cat fact',
            'Units Details': 'No cat fact', 'Writable': 'TRUE', 'Starting Value': 'No cat fact', 'Type': 'str',
            'Notes': 'Cat fact extract from REST API'}]
        """

    @staticmethod
    def _validate_header(point_config: dict):
        """
        Require the header include the following keys
        "PointName", "DataType", "Units", "ReadOnly", "DefaultValue", "Description"
        (or allow parsing with minimal effort)
        "PointName" <- "Point Name", "point name", "point-name", but not "point names" or "the point name"
        Parameters
        ----------
        point_config

        Returns
        -------

        """

        def _to_alpha_lower(key: str):
            return ''.join([x.lower() for x in key if x.isalpha()])

        new_dict = {_to_alpha_lower(k): v for k, v in point_config.items()}
        new_keys = new_dict.keys()

        standardized_valid_names = ["Volttron Point Name", "Data Type", "Units", "Writable", "Default Value", "Notes"]
        for valid_name in standardized_valid_names:
            if valid_name.lower() not in new_keys:
                raise ValueError(f"`{valid_name}` is not in the config")
        return new_dict

    def key_validate(self) -> List[dict]:
        """

        Returns
            EXAMPLE:
            {'pointname': 'Heartbeat',
            'datatype': 'boolean',
            'units': 'On/Off',
            'readonly': 'TRUE',
            'defaultvalue': '0',
            'description': 'Point for heartbeat toggle',
            'volttronpointname': 'Heartbeat',
            'unitsdetails': 'On/Off'}
        -------

        """
        key_validate_csv = [self._validate_header(point_config) for point_config in self.csv_config]
        return key_validate_csv


class WrapperInterface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.point_map: Dict[str, ImplementedRegister] = {}  # {register.point_name: register}
        self.register_types: List[
            ImplementedRegister] = []  # TODO: add sanity check for restister_types, e.g., count == register counts

        self.csv_config = None  # TODO: try to get this value, potentially from def configure. get inspiration from modbus_tk testing
        self.driver_config_in_json_config = None  # TODO: try to get this value, potentially from def configure

        # TODO: clean up this public interface
        # from *.csv configure file "driver_config": {...}
        # self.driver_config: dict = {}

    def configure(self, driver_config_in_json_config: dict, csv_config: List[
        dict]):  # TODO: ask driver.py, BaseInterface.configure to update signature when evoking
        """
        Used by driver.py
            def get_interface(self, driver_type, config_dict, config_string):
                interface.configure(config_dict, config_string)

        Parameters  # TODO: follow BaseInterface.configure signatures. But the names are wrong.
        ----------
        driver_config_in_json_config: associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.
        csv_config: associated with the whole driver-config.csv file
            Examples:
            [{'Point Name': 'Heartbeat', 'Volttron Point Name': 'Heartbeat', 'Units': 'On/Off',
            'Units Details': 'On/Off', 'Writable': 'TRUE', 'Starting Value': '0', 'Type': 'boolean',
            'Notes': 'Point for heartbeat toggle'},
            {'Point Name': 'Catfact', 'Volttron Point Name': 'Catfact', 'Units': 'No cat fact',
            'Units Details': 'No cat fact', 'Writable': 'TRUE', 'Starting Value': 'No cat fact', 'Type': 'str',
            'Notes': 'Cat fact extract from REST API'}]

        """
        # print("========================================== csv_config, ", csv_config)
        # print("========================================== driver_config_in_json_config, ", driver_config_in_json_config)
        self.csv_config = csv_config
        self.driver_config_in_json_config = driver_config_in_json_config

        # TODO configuration validation, i.e., self.config_check(...)
        # self.config_check
        self.parse_config(csv_config, driver_config_in_json_config)

    @staticmethod
    @abc.abstractmethod
    def pass_register_types(csv_config: dict, driver_config_in_json_config: List[dict],
                            register_type_list: List[ImplementedRegister] = None) -> List[ImplementedRegister]:
        """
        For ingesting the register types list
        Will be used by concrete Interface class inherit this template

        Parameters
        ----------
        driver_config_in_json_config: associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.
        csv_config: associated with the whole driver-config.csv file
            Examples:
            [{'Point Name': 'Heartbeat', 'Volttron Point Name': 'Heartbeat', 'Units': 'On/Off',
            'Units Details': 'On/Off', 'Writable': 'TRUE', 'Starting Value': '0', 'Type': 'boolean',
            'Notes': 'Point for heartbeat toggle'},
            {'Point Name': 'Catfact', 'Volttron Point Name': 'Catfact', 'Units': 'No cat fact',
            'Units Details': 'No cat fact', 'Writable': 'TRUE', 'Starting Value': 'No cat fact', 'Type': 'str',
            'Notes': 'Cat fact extract from REST API'}]
        register_type_list:
            Example:
            [RestAPIRegister, RestAPIRegister, RestAPIRegister, RandomBoolRegister]
        """
        pass
        return register_type_list

    def parse_config(self, csv_config, driver_config_in_json_config):  # TODO: this configDict is from *.csv not .config
        # print("========================================== csv_config, ", csv_config)
        # print("========================================== driver_config_in_json_config, ", driver_config_in_json_config)

        # driver_config: DriverConfig = DriverConfig(csv_config)
        # valid_csv_config = DriverConfig(csv_config).key_validate()
        # print("========================================== valid_csv_config, ", valid_csv_config)

        if csv_config is None:  # TODO: leave it now. Later for central data check
            return

        register_types: List[ImplementedRegister] = self.pass_register_types(csv_config, driver_config_in_json_config)
        valid_csv_config = csv_config  # TODO: Design the config check (No config check for now.)
        for reg_def, register_type_iter in zip(valid_csv_config, register_types):
            # Skip lines that have no address yet. # TODO: understand why
            if not reg_def['Point Name']:
                continue

            point_name = reg_def['Volttron Point Name']
            type_name = reg_def.get("Data Type", 'string')
            reg_type = type_mapping.get(type_name, str)
            units = reg_def['Units']
            read_only = reg_def['Writable'].lower() != 'true'  # TODO: watch out for this is opposite logic

            description = reg_def.get('Notes', '')

            # default_value = reg_def.get("defaultvalue", 'sin').strip()
            default_value = reg_def.get(
                "Default Value")  # TODO: redesign default value logic, e.g., beable to map to real python type
            if not default_value:
                default_value = None

            # register_type = FakeRegister if not point_name.startswith('Cat') else CatfactRegister  # TODO: change this
            register_type = register_type_iter  # TODO: Inconventional, document this.

            # print("========================================== point_name, ", point_name)
            # print("========================================== reg_type, ", reg_type)
            # print("========================================== units, ", units)
            # print("========================================== read_only, ", read_only)
            # print("========================================== default_value, ", default_value)
            # print("========================================== description, ", description)
            # print("========================================== reg_def, ", reg_def)
            # Note: the following is to init a register_type object, e.g., WrapperRegister
            try:
                # register: WrapperRegister = register_type(driver_config=driver_config_in_json_config,
                #                                           point_name=point_name,
                #                                           data_type=reg_type,  # TODO: make it more clear in documentation
                #                                           units=units,
                #                                           read_only=read_only,
                #                                           default_value=default_value,
                #                                           description=description,
                #                                           csv_config=csv_config,
                #                                           reg_def=reg_def)

                register: WrapperRegister = self.create_register(driver_config=driver_config_in_json_config,
                                                                 point_name=point_name,
                                                                 data_type=reg_type,
                                                                 # TODO: make it more clear in documentation
                                                                 units=units,
                                                                 read_only=read_only,
                                                                 default_value=default_value,
                                                                 description=description,
                                                                 csv_config=csv_config,
                                                                 reg_def=reg_def,
                                                                 register_type=register_type)
                if default_value is not None:
                    self.set_default(point_name, register.value)

                self.insert_register(register)
            except Exception as e:
                print(e)



    def create_register(self, driver_config,
                        point_name,
                        data_type,
                        units,
                        read_only,
                        default_value,
                        description,
                        csv_config,
                        reg_def,
                        register_type, *args, **kwargs) -> ImplementedRegister:
        pass
        """
        Factory method to init (WrapperRegister) register object
        
        :param register_type: the class name of the to-be-created register, e.g., WrapperRegister
        :param driver_config_in_json_config: json config file, 
        :param csv_config: csv config file, Dict[str, str]
        
        """
        register: WrapperRegister = register_type(driver_config=driver_config,
                                                  point_name=point_name,
                                                  data_type=data_type,  # TODO: make it more clear in documentation
                                                  units=units,
                                                  read_only=read_only,
                                                  default_value=default_value,
                                                  description=description,
                                                  csv_config=csv_config,
                                                  reg_def=reg_def)
        return register

    def insert_register(self, register: WrapperRegister):
        """
        Inserts a register into the :py:class:`Interface`.

        :param register: Register to add to the interface.
        :type register: :py:class:`BaseRegister`
        """
        register_point: str = register.point_name
        self.point_map[register_point] = register

        register_type = register.get_register_type()
        self.registers[register_type].append(register)

    def get_point(self, point_name, **kwargs) -> RegisterValue:
        """
        Override BasicInvert method
        Note: this method should be evoked by vip agent
        EXAMPLE:
            rs = a.vip.rpc.call("platform.driver", "get_point",
              "campus-vm/building-vm/Dnp3",
               "AnalogInput_index0").get()
        """
        register: WrapperRegister = self.get_register_by_name(point_name)
        val = self.get_reg_point(register)
        return val

    # def _set_point(self, point_name: str,
    #                value_to_set: RegisterValue):  # TODO: this method has some problem. Understand the logic: overall + example

    def set_point(self, point_name, value):
        """
        Override/Restate BasicInvert method for convenience
        Note: this method should be evoked by vip agent
        EXAMPLE:
            rs = a.vip.rpc.call("platform.driver", "set_point",
              "campus-vm/building-vm/Dnp3",
               "AnalogInput_index0", 0.543).get()
        """
        # result = self._set_point(point_name, value)
        # self._tracker.mark_dirty_point(point_name)
        return super().set_point(point_name, value)

    def _set_point(self, point_name, value, **kwargs):
        """
        Parameters
        ----------
        point_name
        value

        Returns
        -------

        """
        # value_to_set = value
        register: ImplementedRegister = self.get_register_by_name(point_name)

        # response = self.set_reg_point_w_verification(value_to_set=value, register=register)
        response = self.set_reg_point_async_w_verification(value_to_set=value, register=register)
        return response

    @staticmethod
    def get_reg_point(register: ImplementedRegister):
        """
        Core logic for get_point
        """
        return register.value

    @staticmethod
    def set_reg_point(register: ImplementedRegister, value_to_set: RegisterValue):
        """
        Core logic for set_point, i.e., _set_point without verification
        Note: Can be used for vip-agent-mock testing
        """
        set_pt_response = register.set_register_value(value=value_to_set)
        return set_pt_response

    @classmethod
    def set_reg_point_w_verification(cls, value_to_set: RegisterValue, register: ImplementedRegister,
                                     relax_verification=True):
        """
        Core logic for set_point, i.e., _set_point with verification
        Note: Can be used for vip-agent-mock testing
        """
        # Note: leave register method to verify, e.g., check writability.

        # set point workflow
        set_pt_response = cls.set_reg_point(register=register, value_to_set=value_to_set)

        # verify with get_point
        get_pt_response = cls.get_reg_point(register)

        success_flag_strict = (get_pt_response == value_to_set)
        success_flag_relax = (str(get_pt_response) == str(value_to_set))
        if relax_verification:
            success_flag = success_flag_relax
        else:
            success_flag = success_flag_strict

        response = {"success_flag": success_flag,
                    "value_to_set": value_to_set,
                    "set_pt_response": set_pt_response,
                    "get_pt_response": get_pt_response}
        if not success_flag:
            _log.warning(f"Set value failed, {response}")
        return response

    @classmethod
    def set_reg_point_async_w_verification(cls, value_to_set: RegisterValue, register: ImplementedRegister,
                                           relax_verification=True):
        """
        Counterpart of set_reg_point_w_verification for asynchronous workflow with delay and retry.
        """

        # set point workflow
        set_pt_response = cls.set_reg_point(register=register, value_to_set=value_to_set)

        # verify with get_point
        get_pt_response = cls.get_reg_point(register)

        def check_success_flag():
            _success_flag_strict = (get_pt_response == value_to_set)
            _success_flag_relax = (str(get_pt_response) == str(value_to_set))
            if relax_verification:
                _success_flag = _success_flag_relax
            else:
                _success_flag = _success_flag_strict
            return _success_flag

        # note: only delay and retry the read/get logic NOT the send/set logic
        # note: hard-coded delay time and number of retry. Use small delay, large retry number strategy.
        # For local instances, 2 sec should be sufficient.
        retry_delay = 0.2
        retry_max = 20
        retry_count = 0
        success_flag = check_success_flag()
        while not success_flag and retry_count < retry_max:
            sleep(retry_delay)
            retry_count += 1

            get_pt_response = cls.get_reg_point(register)

            success_flag = check_success_flag()

        response = {"success_flag": success_flag,
                    "value_to_set": value_to_set,
                    "set_pt_response": set_pt_response,
                    "get_pt_response": get_pt_response}
        if not success_flag:
            _log.warning(f"Set value failed, {response}")
        return response

    def _scrape_all(self) -> Dict[str, any]:
        result: Dict[str, RegisterValue] = {}  # Dict[register.point_name, register.value]
        read_registers = self.get_registers_by_type(reg_type="byte",
                                                    read_only=True)  # TODO: Parameterize the "byte" hard-code here
        write_registers = self.get_registers_by_type(reg_type="byte", read_only=False)
        all_registers: List[ImplementedRegister] = read_registers + write_registers
        for register in all_registers:
            result[register.point_name] = register.value
        return result

    def get_register_by_name(self, name: str) -> WrapperRegister:
        """
        Get a register by it's point name.

        :param name: Point name of register.
        :type name: str
        :return: An instance of BaseRegister
        :rtype: :py:class:`BaseRegister`
        """
        try:
            return self.point_map[name]
        except KeyError:
            raise DriverInterfaceError("Point not configured on device: " + name)


class WrapperInterfaceNew:
    """
    Use composition instead of inheritance
    """

    def __init__(self, *args, **kwargs):
        # self.basic_revert = BasicRevert(**kwargs)
        # self.basic_interface = BaseInterface(**kwargs)
        self.basic_revert = BasicRevert()
        self.basic_interface = BaseInterface()
        self._tracker = self.basic_revert._tracker

        self.point_map: Dict[str, ImplementedRegister] = {}  # {register.point_name: register}
        self.register_types: List[
            ImplementedRegister] = []  # TODO: add sanity check for restister_types, e.g., count == register counts

        self.csv_config = None  # TODO: try to get this value, potentially from def configure. get inspiration from modbus_tk testing
        self.driver_config_in_json_config = None  # TODO: try to get this value, potentially from def configure

    def configure(self, driver_config_in_json_config: dict, csv_config: List[
        dict]):  # TODO: ask driver.py, BaseInterface.configure to update signature when evoking
        """
        Used by driver.py
            def get_interface(self, driver_type, config_dict, config_string):
                interface.configure(config_dict, config_string)

        Parameters  # TODO: follow BaseInterface.configure signatures. But the names are wrong.
        ----------
        driver_config_in_json_config: associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.
        csv_config: associated with the whole driver-config.csv file
            Examples:
            [{'Point Name': 'Heartbeat', 'Volttron Point Name': 'Heartbeat', 'Units': 'On/Off',
            'Units Details': 'On/Off', 'Writable': 'TRUE', 'Starting Value': '0', 'Type': 'boolean',
            'Notes': 'Point for heartbeat toggle'},
            {'Point Name': 'Catfact', 'Volttron Point Name': 'Catfact', 'Units': 'No cat fact',
            'Units Details': 'No cat fact', 'Writable': 'TRUE', 'Starting Value': 'No cat fact', 'Type': 'str',
            'Notes': 'Cat fact extract from REST API'}]

        """
        # print("========================================== csv_config, ", csv_config)
        # print("========================================== driver_config_in_json_config, ", driver_config_in_json_config)
        self.csv_config = csv_config
        self.driver_config_in_json_config = driver_config_in_json_config

        # TODO configuration validation, i.e., self.config_check(...)
        # self.config_check
        self.parse_config(csv_config, driver_config_in_json_config)

    def parse_config(self, csv_config, driver_config_in_json_config,
                     register_type_list):  # TODO: this configDict is from *.csv not .config
        # print("========================================== csv_config, ", csv_config)
        # print("========================================== driver_config_in_json_config, ", driver_config_in_json_config)

        # driver_config: DriverConfig = DriverConfig(csv_config)
        # valid_csv_config = DriverConfig(csv_config).key_validate()
        # print("========================================== valid_csv_config, ", valid_csv_config)

        if csv_config is None:  # TODO: leave it now. Later for central data check
            return

        # register_types: List[ImplementedRegister] = register_type_list
        register_types: List[ImplementedRegister] = self.pass_register_types(csv_config, driver_config_in_json_config)
        valid_csv_config = csv_config  # TODO: Design the config check (No config check for now.)
        for reg_def, register_type_iter in zip(valid_csv_config, register_types):
            # Skip lines that have no address yet. # TODO: understand why
            if not reg_def['Point Name']:
                continue

            point_name = reg_def['Volttron Point Name']
            type_name = reg_def.get("Data Type", 'string')
            reg_type = type_mapping.get(type_name, str)
            units = reg_def['Units']
            read_only = reg_def['Writable'].lower() != 'true'  # TODO: watch out for this is opposite logic

            description = reg_def.get('Notes', '')

            # default_value = reg_def.get("defaultvalue", 'sin').strip()
            default_value = reg_def.get(
                "Default Value")  # TODO: redesign default value logic, e.g., beable to map to real python type
            if not default_value:
                default_value = None

            # register_type = FakeRegister if not point_name.startswith('Cat') else CatfactRegister  # TODO: change this
            register_type = register_type_iter  # TODO: Inconventional, document this.

            # print("========================================== point_name, ", point_name)
            # print("========================================== reg_type, ", reg_type)
            # print("========================================== units, ", units)
            # print("========================================== read_only, ", read_only)
            # print("========================================== default_value, ", default_value)
            # print("========================================== description, ", description)
            # print("========================================== reg_def, ", reg_def)
            # Note: the following is to init a register_type object, e.g., WrapperRegister
            try:
                register: WrapperRegister = self.create_register(driver_config=driver_config_in_json_config,
                                                                 point_name=point_name,
                                                                 data_type=reg_type,
                                                                 # TODO: make it more clear in documentation
                                                                 units=units,
                                                                 read_only=read_only,
                                                                 default_value=default_value,
                                                                 description=description,
                                                                 csv_config=csv_config,
                                                                 reg_def=reg_def,
                                                                 register_type=register_type)

                if default_value:
                    self.basic_revert.set_default(point_name, register.value)

                self.insert_register(register)

            except Exception as e:
                print(e)

    @staticmethod
    @abc.abstractmethod
    def pass_register_types(csv_config: dict, driver_config_in_json_config: List[dict],
                            register_type_list: List[ImplementedRegister] = None) -> List[ImplementedRegister]:
        """
        For ingesting the register types list
        Will be used by concrete Interface class inherit this template

        Parameters
        ----------
        driver_config_in_json_config: associated with `driver_config` in driver-config.config (json-like file)
                    user inputs are put here, e.g., IP address, url, etc.
        csv_config: associated with the whole driver-config.csv file
            Examples:
            [{'Point Name': 'Heartbeat', 'Volttron Point Name': 'Heartbeat', 'Units': 'On/Off',
            'Units Details': 'On/Off', 'Writable': 'TRUE', 'Starting Value': '0', 'Type': 'boolean',
            'Notes': 'Point for heartbeat toggle'},
            {'Point Name': 'Catfact', 'Volttron Point Name': 'Catfact', 'Units': 'No cat fact',
            'Units Details': 'No cat fact', 'Writable': 'TRUE', 'Starting Value': 'No cat fact', 'Type': 'str',
            'Notes': 'Cat fact extract from REST API'}]
        register_type_list:
            Example:
            [RestAPIRegister, RestAPIRegister, RestAPIRegister, RandomBoolRegister]
        """
        pass
        return register_type_list

    def create_register(self, driver_config,
                        point_name,
                        data_type,
                        units,
                        read_only,
                        default_value,
                        description,
                        csv_config,
                        reg_def,
                        register_type, *args, **kwargs) -> ImplementedRegister:
        pass
        """
        Factory method to init (WrapperRegister) register object

        :param register_type: the class name of the to-be-created register, e.g., WrapperRegister
        :param driver_config_in_json_config: json config file, 
        :param csv_config: csv config file, Dict[str, str]

        """
        register: WrapperRegister = register_type(driver_config=driver_config,
                                                  point_name=point_name,
                                                  data_type=data_type,  # TODO: make it more clear in documentation
                                                  units=units,
                                                  read_only=read_only,
                                                  default_value=default_value,
                                                  description=description,
                                                  csv_config=csv_config,
                                                  reg_def=reg_def)
        return register

    def insert_register(self, register: WrapperRegister):
        """
        Inserts a register into the :py:class:`Interface`.

        :param register: Register to add to the interface.
        :type register: :py:class:`BaseRegister`
        """
        register_point: str = register.point_name
        self.point_map[register_point] = register

        register_type = register.get_register_type()
        self.basic_interface.registers[register_type].append(register)

    def get_point(self, point_name, **kwargs) -> RegisterValue:
        register: WrapperRegister = self.get_register_by_name(point_name)
        # val: RegisterValue = register.get_register_value()

        # return "testing_value"
        return register.value

    def get_register_by_name(self, name: str) -> Register:
        return self.basic_interface.get_register_by_name(name)

    def set_point(self, point_name, value):
        """
        Implementation of :py:meth:`BaseInterface.set_point`

        Passes arguments through to :py:meth:`BasicRevert._set_point`
        """
        # return self.basic_revert.set_point(point_name, value)
        result = self._set_point(point_name, value)
        self._tracker.mark_dirty_point(point_name)
        return result

    def _set_point(self, point_name, value, **kwargs):
        """
        Parameters
        ----------
        point_name
        value

        Returns
        -------

        """
        value_to_set = value
        register: ImplementedRegister = self.get_register_by_name(point_name)
        # Note: leave register method to verify, e.g., check writability.
        # register.value(value_to_set)
        # value_response: RegisterValue = register.value

        set_pt_response = register.set_register_value(value=value_to_set)
        # verify with get_point
        get_pt_response = self.get_point(point_name=point_name)

        success_flag_strict = (get_pt_response == value_to_set)
        success_flag_relax = (str(get_pt_response) == str(value_to_set))
        success_flag = success_flag_relax

        response = {"success_flag": success_flag,
                    "value_to_set": value_to_set,
                    "set_pt_response": set_pt_response,
                    "get_pt_response": get_pt_response}
        if not success_flag:
            _log.warning(f"Set value failed, {response}")
        return response

    def scrape_all(self):
        """
        Implementation of :py:meth:`BaseInterface.scrape_all`
        """
        return self.basic_revert.scrape_all()


class DriverInterfaceError(Exception):
    pass
