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

"""
The TED Driver allows scraping of TED Pro Meters via an HTTP API
"""

import logging
import time
import copy
import xml.etree.ElementTree as ET

import grequests

from volttron.platform.agent import utils
from master_driver.interfaces import BaseRegister, BaseInterface, BasicRevert


TED_METER_LOGGER = logging.getLogger("ted_meter")
TED_METER_LOGGER.setLevel(logging.WARNING)

MTU_REGISTER_MAP = {
    'Value': {'units': 'kW', 'multiplier': .001, "description": "Present Demand in kW", "point_name": "load_kw", "haystack_tags": {
        "power": True,
        "elec": True,
        "meter": True,
        "ac": True,
        "active": True
    }},
    'KVA': {'units': 'kVA', 'multiplier': .001, "description": "Present Demand in kVA", "point_name": "load_kva", "haystack_tags": {
        "power": True,
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "apparent": True
    }},
    'PF': {'units': 'ratio', 'multiplier': .001, "description": "Present Power Factor in unitless form", "point_name": "power_factor", "haystack_tags": {
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "pf": True
    }},
    'Phase': {'units': 'degrees', 'multiplier': 1, "description": "Present Phase Angle in Degrees", "point_name":  "phase_angle", "haystack_tags": {
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "angle": True
    }},
    'Voltage': {'units': 'Volts', 'multiplier': .1, "description": "Present Voltage in Volts", "point_name": "voltage", "haystack_tags": {
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "volt": True
    }},
    'PhaseCurrent': {'units': 'Amps', 'multiplier': 1, "description": "Present Phase Current in Amps", "point_name": "phase_current", "haystack_tags": {
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "current": True
    }},
    'PhaseVoltage': {'units': 'Volts', 'multiplier': 1, "description": "Present Phase Voltage in Volts", "point_name": "phase_voltage", "haystack_tags": {
        "elec": True,
        "meter": True,
        "ac": True,
        "sensor": True,
        "volt": True
    }},
}

SYSTEM_REGISTER_MAP = {
    'MTD': {'units': 'kWh', 'multiplier': .001, "description": "Month to Day Consumption", "point_name": "mtd", "haystack_tags": {
        "elec": True,
        "energy": True,
        "meter": True,
        "ac": True,
        "sensor": True
    }}
}

SPYDER_REGISTER_MAP = {
    'Now': {'units': 'kW', 'multiplier': .001, "point_name": "load", "description": "Current Demand in kW", "haystack_tags": {
        "elec": True,
        "power": True,
        "meter": True,
        "ac": True,
        "sensor": True
    }},
    'MTD': {'units': 'kWh', 'multiplier': .001, "point_name": "mtd", "description": "Month to Day Consumption", "haystack_tags": {
        "elec": True,
        "energy": True,
        "meter": True,
        "ac": True,
        "sensor": True
    }}
}


class Register(BaseRegister):
    """
    Generic class for containing information about a the points exposed by the TED Pro API


    :param register_type: Type of the register. Either "bit" or "byte". Usually "byte".
    :param pointName: Name of the register.
    :param units: Units of the value of the register.
    :param description: Description of the register.

    :type register_type: str
    :type pointName: str
    :type units: str
    :type description: str

    The TED Meter Driver does not expose the read_only parameter, as the TED API does not
    support writing data.
    """

    def __init__(self, volttron_point_name, units, description):
        super(Register, self).__init__("byte",
                                       True,
                                       volttron_point_name,
                                       units,
                                       description=description)


class Interface(BasicRevert, BaseInterface):
    """Create an interface for the TED device using the standard BaseInterface convention
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.logger = TED_METER_LOGGER
        self.device_path = kwargs.get("device_path")

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the master driver with configuration 
        stanza and registry config file, we ignore the registry config, as we
        build the registers based on the configuration collected from TED Pro
        Device
        """
        self.device_address = config_dict['device_address']
        self.username = config_dict.get('username')
        self.password = config_dict.get('password')
        self.timeout = config_dict.get('timeous', 5)
        self.scrape_spyders = config_dict.get('scrape_spyder', False)
        self.track_totalizers = config_dict.get('track_totalizers', True)
        self.init_time = time.time()
        self.ted_config = self._get_ted_configuration()
        self._create_registers(self.ted_config)
        if self.track_totalizers:
            self._get_totalizer_state()

    def _get_totalizer_state(self):
        """
        Sets up the totalizer state in the config store to allow perstistence
        of cumulative totalizers, despite regular resets of the totalizers on
        the device.
        """
        try:
            totalizer_state = self.vip.config.get("state/ted_meter/{}".format(self.device_path))
        except KeyError:
            totalizer_state = {register_name: {
                "total": 0, "last_read": 0
            } for register_name in self.get_register_names(
            ) if self.get_register_by_name(register_name).units == "kWh" and "_totalized" in register_name}
            self.vip.config.set("state/ted_meter/{}".format(self.device_path), totalizer_state)
        self.totalizer_state = totalizer_state

    def _get_ted_configuration(self):
        """
        Retrieves the TED Pro configuration from the device, used to build the registers
        """
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
        spyders = [[{"group": i, "name": y.find("Description").text} for i, y in enumerate(x.findall("Group")) if y.find(
            "UseCT").text != "0"] for x in system_tree.findall(".//Spyder") if x.find("Enabled").text == "1"]
        config["MTUs"] = mtus
        config["Spyders"] = spyders
        return config
    
    def insert_register(self, register):
        """
        We override the default insert_register behavior so that we can
        automatically create additional totalized registers when 
        ``track_totalizers`` is True
        """
        super(Interface, self).insert_register(register)
        if self.track_totalizers:
            if register.units == 'kWh':
                totalized_register = copy.deepcopy(register)
                totalized_register.point_name = register.point_name + "_totalized"
                super(Interface, self).insert_register(totalized_register)

    def _create_registers(self, ted_config):
        """
        Processes the config scraped from the TED Pro device and generates
        register for each available parameter
        """
        for i, spyder in enumerate(ted_config['Spyders']):
            for group in spyder:
                for key, value in SPYDER_REGISTER_MAP.items():
                    point_name = 'spyder-{}/{}/{}'.format(
                        i+1, group["name"], value["point_name"])
                    self.insert_register(Register(
                        point_name, value["units"], value["description"]
                    ))
        for mtu in ted_config["MTUs"]:
            for key, value in MTU_REGISTER_MAP.items():
                if key in ('PhaseCurrent', 'PhaseVoltage'):
                    for conductor in ('a', 'b', 'c'):
                        point_name = 'mtu-{}/{}-{}'.format(
                            mtu["MTUNumber"], value["point_name"], conductor)
                        self.insert_register(Register(
                            point_name, value["units"], value["description"]
                        ))
                else:
                    point_name = 'mtu-{}/{}'.format(
                        mtu["MTUNumber"], value["point_name"])
                    self.insert_register(Register(
                        point_name, value["units"], value["description"]
                    ))
        for key, value in SYSTEM_REGISTER_MAP.items():
            point_name = 'system/{}'.format(value["point_name"])
            self.insert_register(Register(
                point_name,
                value["units"],
                value["description"],
            ))

    def _set_point(self, point_name, value):
        """
        TED has no writable points, so skipping set_point method
        """
        pass

    def get_point(self, point_name):
        points = self._scrape_all()
        return points.get(point_name)

    def get_data(self):
        """
        returns a tuple of ETree objects corresponding to the three aapi endpoints
        """
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
            mtu_tree = system_tree.find(".MTUVal/MTU" + mtu["MTUNumber"])
            for prop in mtu_tree:
                if prop.tag in ["PhaseCurrent", "PhaseVoltage"]:
                    for conductor in prop:
                        point_name = 'mtu-{}/{}-{}'.format(
                            mtu["MTUNumber"], MTU_REGISTER_MAP[prop.tag]["point_name"], conductor.tag.lower())
                        output[point_name] = float(conductor.text)
                elif prop.tag in MTU_REGISTER_MAP:
                    point_name = 'mtu-{}/{}'.format(
                        mtu["MTUNumber"], MTU_REGISTER_MAP[prop.tag]["point_name"])
                    output[point_name] = int(
                        prop.text) * MTU_REGISTER_MAP[prop.tag]["multiplier"]

        spyder_data = list(spyder_tree.findall(".//Spyder"))
        for i, spyder in enumerate(self.ted_config['Spyders']):
            group_data = list(spyder_data[i].findall("Group"))
            for group in spyder:
                for key, value in SPYDER_REGISTER_MAP.items():
                    point_name = 'spyder-{}/{}/{}'.format(
                        i+1, group["name"], value["point_name"])
                    read_value = int(group_data[group["group"]].find(
                        key).text)
                    if value["units"] == 'kWh' and self.track_totalizers:
                        output[point_name + "_totalized"] = self._get_totalized_value(
                            point_name, read_value, value["multiplier"])
                    output[point_name] = read_value * value["multiplier"]

        for key, value in SYSTEM_REGISTER_MAP.items():
            point_name = 'system/{}'.format(value["point_name"])
            read_value = int(dashdata_tree.find(
                key).text)
            if value["units"] == 'kWh' and self.track_totalizers:
                output[point_name + "_totalized"] = self._get_totalized_value(
                    point_name, read_value, value["multiplier"])
            output[point_name] = read_value * value["multiplier"]
        return output

    def _get_totalized_value(self, point_name, read_value, multiplier):
        """
        processes the read value and returns the totalized value, based on the
        internal state tracking
        """

        totalizer_point_name = point_name + '_totalized'
        totalizer_value = self.totalizer_state.get(totalizer_point_name)
        if totalizer_value is not None:
            total, last_read = totalizer_value["total"], totalizer_value["last_read"]
            if read_value >= total:
                self.totalizer_state[totalizer_point_name]["total"] = read_value
                actual = read_value
            else:
                if read_value >= last_read:
                    self.totalizer_state[totalizer_point_name]["total"] += read_value - last_read 
                else:
                    self.totalizer_state[totalizer_point_name]["total"] += read_value
                actual = self.totalizer_state[totalizer_point_name]["total"]
            self.totalizer_state[totalizer_point_name]["last_read"] = read_value
            self.vip.config.set('state/ted_meter/{}'.format(self.device_path),
                                self.totalizer_state)
        else:
            actual = read_value
        return actual * multiplier
