# Copyright (c) 2019, ACE IoT Solutions LLC.
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

from volttron.platform.agent import utils
from master_driver.interfaces import BaseRegister, BaseInterface, BasicRevert

import logging

import grequests
import time

import xml.etree.ElementTree as ET

ted_meter_logger = logging.getLogger("ted_meter")
ted_meter_logger.setLevel(logging.WARNING)

mtu_register_map = {
    'Value': {'units': 'kW', 'multiplier': .001, "description": "Present Demand in kW", "point_name": "load_kw"},
    'KVA': {'units': 'kVA', 'multiplier': .001, "description": "Present Demand in kVA", "point_name": "load_kva"},
    'PF': {'units': 'ratio', 'multiplier': .001, "description": "Present Power Factor in unitless form", "point_name": "power_factor"},
    'Phase': {'units': 'degrees', 'multiplier': 1, "description": "Present Phase Angle in Degrees", "point_name":  "phase_angle"},
    'Voltage': {'units': 'Volts', 'multiplier': .1, "description": "Present Voltage in Volts", "point_name": "voltage"},
    'PhaseCurrent': {'units': 'Amps', 'multiplier': 1, "description": "Present Phase Current in Amps", "point_name": "phase_current"},
    'PhaseVoltage': {'units': 'Volts', 'multiplier': 1, "description": "Present Phase Voltage in Volts", "point_name": "phase_voltage"},
}

system_register_map = {
    'MTD': {'units': 'kWh', 'multiplier': .001, "description": "Totalized Consumption in kWh", "point_name": "consumption"}
}

spyder_register_map = {
    'Now': {'units': 'kW', 'multiplier': .001, "point_name": "load", "description": "Current Demand in kW"},
    'MTD': {'units': 'kWh', 'multiplier': .001, "point_name": "consumption", "description": "Totalized Consumption in kWh"}
}


class Register(BaseRegister):
    def __init__(self, read_only, volttron_point_name, units, description, point_name):
        super(Register, self).__init__("byte",
                                       read_only,
                                       volttron_point_name,
                                       units,
                                       description=description)


class Interface(BasicRevert, BaseInterface):
    """Create an interface for the TED device using the standard BaseInterface convention
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.logger = ted_meter_logger

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the master driver with configuration stanza and registry config file"""
        self.device_address = config_dict['device_address']
        self.username = config_dict.get('username')
        self.password = config_dict.get('password')
        self.timeout = config_dict.get('timeous', 5)
        self.scrape_spyders = config_dict.get('scrape_spyder', False)
        self.track_totalizers = config_dict.get('track_totalizers', True)
        self.init_time = time.time()
        self.ted_config = self._get_ted_configuration()
        self.logger.error(self.device_path)
        self._create_registers(self.ted_config)
        self._get_totalizer_state()

    def _get_totalizer_state(self):
        try:
            totalizer_state = self.vip.config.get("state/ted_meter")
        except KeyError:
            totalizer_state = {register_name: {"total": 0, "last_read": 0} for register_name in self.get_register_names(
            ) if self.get_register_by_name(register_name).units == "kWh"}
            self.vip.config.set("state/drivers/ted_meter", totalizer_state)
        self.totalizer_state = totalizer_state

    def _get_ted_configuration(self):
        req = (grequests.get(
            "http://{ted_host}/api/SystemSettings.xml".format(ted_host=self.device_address), auth=(self.username, self.password), timeout=self.timeout),)
        system, = grequests.map(req)
        if system.status_code != 200:
            raise Exception(
                "Invalid response from meter, check config, received status code: {}".format(system.status_code))
        config = {}
        system_tree = ET.ElementTree(ET.fromstring(system.text))
        mtus = [{"MTUNumber": x.find("MTUNumber").text, "MTUID": x.find(
            "MTUID").text} for x in system_tree.findall('.//MTU') if x.find("MTUID").text != "000000"]
        Spyders = [[{"group": i, "name": y.find("Description").text} for i, y in enumerate(x.findall("Group")) if y.find(
            "UseCT").text != "0"] for x in system_tree.findall(".//Spyder") if x.find("Enabled").text == "1"]
        config["MTUs"] = mtus
        config["Spyders"] = Spyders
        return config

    def _create_registers(self, ted_config):
        for i, Spyder in enumerate(ted_config['Spyders']):
            for group in Spyder:
                for key, value in spyder_register_map.items():
                    point_name = 'spyder-{}/{}/{}'.format(
                        i+1, group["name"], value["point_name"])
                    self.insert_register(Register(
                        True, point_name, value["units"], value["description"], point_name))
        for mtu in ted_config["MTUs"]:
            for key, value in mtu_register_map.items():
                if key in ('PhaseCurrent', 'PhaseVoltage'):
                    for conductor in ('a', 'b', 'c'):
                        point_name = 'mtu-{}/{}-{}'.format(
                            mtu["MTUNumber"], value["point_name"], conductor)
                        self.insert_register(Register(
                            True, point_name, value["units"], value["description"], point_name
                        ))
                else:
                    point_name = 'mtu-{}/{}'.format(
                        mtu["MTUNumber"], value["point_name"])
                    self.insert_register(Register(
                        True, point_name, value["units"], value["description"], point_name
                    ))
        for key, value in system_register_map.items():
            point_name = 'system/{}'.format(value["point_name"])
            self.insert_register(Register(
                True,
                point_name,
                value["units"],
                value["description"],
                point_name
            ))

    def _set_point(self):
        pass

    def get_point(self):
        pass

    def get_data(self):
        requests = [grequests.get(url, auth=(self.username, self.password), timeout=self.timeout) for url in (
            "http://{ted_host}/api/SystemOverview.xml?T=0&D=0&M=0".format(
                ted_host=self.device_address),
            "http://{ted_host}/api/SpyderData.xml?T=0&D=0&M=0".format(
                ted_host=self.device_address),
            "http://{ted_host}/api/DashData.xml?T=0&D=0&M=0".format(
                ted_host=self.device_address)
        )
        ]
        system, spyder, dashdata = grequests.map(requests)
        for response in (system, spyder, dashdata):
            if response.status_code != 200:
                raise Exception(
                    "Invalid response from meter, check config, received status code: {}".format(response.status_code))
        system_tree = ET.ElementTree(ET.fromstring(system.text))
        spyder_tree = ET.ElementTree(ET.fromstring(spyder.text))
        dashdata_tree = ET.ElementTree(ET.fromstring(dashdata.text))
        return (system_tree, spyder_tree, dashdata_tree)

    def _scrape_all(self):
        output = {}
        data = {"MTUs": [],
                "Spyders": []}
        system_tree, spyder_tree, dashdata_tree = self.get_data()
        for mtu in self.ted_config["MTUs"]:
            MTU_Data = {}
            MTU_Data.update(mtu)
            mtu_tree = system_tree.find(".MTUVal/MTU" + mtu["MTUNumber"])
            for prop in mtu_tree:
                if prop.tag in ["PhaseCurrent", "PhaseVoltage"]:
                    for conductor in prop:
                        point_name = 'mtu-{}/{}-{}'.format(
                            mtu["MTUNumber"], mtu_register_map[prop.tag]["point_name"], conductor.tag.lower())
                        output[point_name] = conductor.text
                elif prop.tag in mtu_register_map:
                    point_name = 'mtu-{}/{}'.format(
                        mtu["MTUNumber"], mtu_register_map[prop.tag]["point_name"])
                    output[point_name] = int(
                        prop.text) * mtu_register_map[prop.tag]["multiplier"]

        spyder_data = list(spyder_tree.findall(".//Spyder"))
        for i, Spyder in enumerate(self.ted_config['Spyders']):
            group_data = list(spyder_data[i].findall("Group"))
            ted_meter_logger.error(group_data)
            for group in Spyder:
                for key, value in spyder_register_map.items():
                    point_name = 'spyder-{}/{}/{}'.format(
                        i+1, group["name"], value["point_name"])
                    read_value = int(group_data[group["group"]].find(
                        key).text) * value["multiplier"]
                    if value["units"] == 'kWh' and self.track_totalizers:
                        output[point_name] = self._get_totalized_value(
                            point_name, read_value)
                    else:
                        output[point_name] = read_value

        
        for key, value in system_register_map.items():
            point_name = 'system/{}'.format(value["point_name"])
            read_value = int(dashdata_tree.find(
                key).text) * value["multiplier"]
            if value["units"] == 'kWh' and self.track_totalizers:
                output[point_name] = self._get_totalized_value(
                    point_name, read_value)
            else:
                output[point_name] = read_value
        return output

    def _get_totalized_value(self, point_name, read_value):
        totalizer_value = self.totalizer_state.get(point_name)
        if totalizer_value is not None:
            if read_value >= totalizer_value:
                self.totalizer_state[point_name]["total"] = read_value
                actual = read_value
            else:
                if read_value >= self.totalizer_state[point_name]["last_read"]:
                    self.totalizer_state[point_name]["total"] += read_value - \
                        self.totalizer_state[point_name]["last_read"]
                    actual = self.totalizer_state[point_name]["total"]
                else:
                    self.totalizer_state[point_name]["total"] += read_value
                actual = self.totalizer_state[point_name]["total"]
            self.totalizer_state[point_name]["last_read"] = read_value
            self.vip.config.set('state/drivers/ted_meter', self.totalizer_state)
        else:
            actual = read_value
        return actual
