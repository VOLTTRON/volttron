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
The Venstar  Driver allows control and monitoring of Venstar Thermostats via an HTTP API
"""

import logging
import time
import copy

import grequests

from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from volttron.platform.vip.agent import Agent, Core, RPC, PubSub

_log = logging.getLogger("venstar_tstat")
#VENSTAR_LOGGER.setLevel(logging.WARNING)


class Register(BaseRegister):
    """
    Generic class for containing information about the points exposed by the Venstar API


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
    """Create an interface for the Venstar Thermostat using the standard BaseInterface convention
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.device_path = kwargs.get("device_path")
        self.logger = _log

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the platform driver with configuration 
        stanza and registry config file, we ignore the registry config, using 
        standard layout for the thermostat properties
        """
        _log.debug(f"{config_dict=}")
        self.device_address = config_dict['device_address']
        self.timeout = config_dict.get('timeout', 5)
        self.init_time = time.time()

        for entry in self.get_data()[0]:
            if entry == 'name':
                continue
            _log.debug(f"inserting register {entry=}")
            self.insert_register(Register(entry, "", ""))

    def _get_tstat_configuration(self):
        """
        Retrieves the current state/configuration from the device
        """
        req = (grequests.get(
            "http://{tstat_host}/query/info".format(ted_host=self.device_address))
            )
        system, = grequests.map(req)
        if system.status_code != 200:
            raise Exception(
                "Invalid response from meter, check config, received status code: {}".format(system.status_code))
        config = {}
        return config
    
    def _create_registers(self, ted_config):
        """
        Processes the config scraped from the device and generates
        register for each available parameter
        """
        return

    def _build_url_encode_venstar(self, points):
        VENSTAR_MODE_MAP = { 
            "off": 0,
            "heat": 1,
            "cool": 2,
            "auto": 3,
            "ERROR": 4
        }
        data = ""
        for key, value in points.items():
            if key not in ["mode", "cooltemp", "heattemp", "cooltempmin", "cooltempmax", "heattempmin", "heattempmax", "fan"]:
                continue
            if key == "mode":
                value = VENSTAR_MODE_MAP[value]
            #needs to be url encoded instead of json
            if data == "":
                data = f"{data}{key}={value}"
            else:
                data = f"{data}&{key}={value}"
        return data

    def _set_points(self, points):
        points = points['data']
        _log.debug(f"setting {points=}")

        #all control requests with mode must have cooltemp and heattemp, and setpointdelta must be respected
        if not points.get('cooltemp') or not points.get('heattemp'):
            _log.error("cooltemp and heattemp must both be provided")
            return
        if points['mode'] == "auto":
            delta = (points.get('cooltemp') - points.get('heattemp'))/2
            if delta > points.get('setpointdelta'):
                _log.error(f"setpoint delta must not be greater than specified. actual {delta=}, setpointdelta: {points.get('setpointdelta')}")
                return
            if delta < 0:
                _log.error("cooltemp must be greater than heattemp")
                return

        data = self._build_url_encode_venstar(points)
        h = {"content-type": "application/x-www-form-urlencoded"}
        _log.debug(f"making POST request to thermostat: {data=}")
        requests = (grequests.post(f'http://{self.device_address}/control', timeout=self.timeout, headers=h, data=data),)
        response, = grequests.map(requests)
        if response.status_code != 200:
            raise Exception(
                    "Invalid response from thermostat, check config, received status code: {}, response: {}".format(response.status_code, response.text))



    def _set_point(self, point_name, value):
        self._set_points({point_name: value})


    def get_point(self, point_name):
        points = self._scrape_all()
        return points.get(point_name)


    def get_data(self):
        requests = [grequests.get(url, timeout=self.timeout) for url in (
            "http://{tstat_host}/query/info".format(
                tstat_host=self.device_address),
        )
        ]
        system, = grequests.map(requests)
        if not system:
            _log.error(f"No data received. Is thermostat API functionality enabled?")
            return
        for response in (system,):
            if response.status_code != 200:
                raise Exception(
                    "Invalid response from meter, check config, received status code: {}".format(response.status_code))
        return (system.json(),)

    def _scrape_all(self):
        output = {}
        system_data, = self.get_data()
        output = system_data
        del output['name']
        return output
