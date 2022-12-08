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

from csv import DictReader
import logging
import requests

from platform_driver.interfaces import (
    BaseInterface,
    BaseRegister,
    BasicRevert,
    DriverInterfaceError,
)

_log = logging.getLogger("rainforest_eagle")


auth = None
macid = None
address = None


class Register(BaseRegister):
    def __init__(self, name, units, description):
        super(Register, self).__init__(
            register_type="byte",
            read_only=True,
            pointName=name,
            units=units,
            description=description,
        )


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, register_config):
        global auth, macid, address
        _log.debug(f"configuring rainforest gateway: {config_dict=} {register_config=}")

        username = config_dict["username"]
        password = config_dict["password"]
        auth = (username, password)
        macid = config_dict["macid"]
        address = config_dict["address"]

        device_list = self.get_device_list()
        power_meter = {}
        for device in device_list.values():
            if device["ModelId"] == "electric_meter":
                power_meter = device

        var_list = [
            "zigbee:CurrentSummationDelivered",
            "zigbee:CurrentSummationReceived",
            "zigbee:InstantaneousDemand",
        ]

        get_variables_dict = self.get_variables_list(power_meter, var_list)
        _log.debug(f"{get_variables_dict=}")
        var_metadata = {}
        var_values = {}
        for d in get_variables_dict:
            # remove zigbee: prefix
            name = d["Name"][7:]
            units = d["Units"]
            description = d["Description"]
            self.insert_register(Register(name, units, description))

        _log.debug(f"{var_values=}")

    def get_point(self, point_name):
        return self.get_variable(self, point_name)

    def get_variable(self, device, variable):
        _log.debug(f"getting {variable} from {device}")
        command = f"""<Command>
                        <Name>device_query</Name>
                        <Format>JSON</Format>
                        <DeviceDetails>
                            <HardwareAddress>{device['HardwareAddress']}</HardwareAddress>
                        </DeviceDetails>
                        <Components>
                            <Component>
                                <Name>Main</Name>
                                <Variables>
                                    <Variable>
                                        <Name>{variable}</Name>
                                    </Variable>
                                </Variables>
                            </Component>
                        </Components>
                    </Command>
                    """

        result = requests.post(address, auth=auth, data=command)
        if result.status_code != requests.codes.ok:
            return str(result.status_code)
        _log.info(f"Queried device {device['Name']} for variable {variable}: {result=}")
        device_result = result.json()
        requested_values = device_result["Device"]["Components"]["Component"][
            "Variables"
        ]
        return requested_values["Variable"]

    def get_variables_list(self, device, var_list):
        returned_vars = []
        for variable in var_list:
            command = f"""<Command>
                            <Name>device_query</Name>
                            <Format>JSON</Format>
                            <DeviceDetails>
                                <HardwareAddress>{device['HardwareAddress']}</HardwareAddress>
                            </DeviceDetails>
                            <Components>
                                <Component>
                                    <Name>Main</Name>
                                    <Variables>
                                        <Variable>
                                            <Name>{variable}</Name>
                                        </Variable>
                                    </Variables>
                                </Component>
                            </Components>
                        </Command>
                        """
            result = requests.post(address, auth=auth, data=command).json()
            returned_vars.append(
                result["Device"]["Components"]["Component"]["Variables"]["Variable"]
            )
        return returned_vars

    def get_device_list(self):
        # consider using dicttoxml to set up command as dictionary?
        command = """<Command>
                     <Name>device_list</Name>
                     <Format>JSON</Format>
                   </Command>"""
        result = requests.post(address, auth=auth, data=command)

        if result.status_code != requests.codes.ok:
            return str(result.status_code)

        device_list = result.json()["DeviceList"]
        _log.debug(f"{device_list=}")
        return device_list

    def scrape_power_meter(self):
        device_list = self.get_device_list()
        power_meter = {}
        for device in device_list.values():
            if device["ModelId"] == "electric_meter":
                power_meter = device

        var_list = [
            "zigbee:CurrentSummationDelivered",
            "zigbee:CurrentSummationReceived",
            "zigbee:InstantaneousDemand",
        ]
        values = {}
        for d in self.get_variables_list(power_meter, var_list):
            # remove zigbee: prefix
            name = d["Name"][7:]
            values[name] = d['Value']
        return values

    def _set_point(self, point_name, value):
        pass

    def scrape_all(self):
        return self._scrape_all()

    def _scrape_all(self) -> dict:
        # scrape points
        result = self.scrape_power_meter()
        _log.debug(f"{result=}")
        return result