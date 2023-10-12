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
The Shelly EM driver allows data collection from Shelly EM Devices, future work could support other models of Shelly Meters
"""

import logging
import time

import grequests

from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert


_log = logging.getLogger("shelly_em")

SHELLY_EM_REGISTER_MAP = {
    "power": {
        "register_name": "active_power",
        "metadata": {"units": "W", "description": "Active Power"},
    },
    "voltage": {
        "register_name": "voltage",
        "metadata": {"units": "V", "description": "Voltage"},
    },
    "reactive": {
        "register_name": "reactive_power",
        "metadata": {"units": "VAR", "description": "Reactive Power"},
    },
    "total": {
        "register_name": "total_energy",
        "metadata": {"units": "Wh", "description": "Total Energy"},
    },
    "total_returned": {
        "register_name": "total_export",
        "metadata": {"units": "Wh", "description": "Total Export"},
    },
}


class Register(BaseRegister):
    """
    Register class for Shelly EM
    """

    def __init__(self, volttron_point_name, units, description):
        super(Register, self).__init__(
            "byte", True, volttron_point_name, units, description=description
        )


class Interface(BasicRevert, BaseInterface):
    """
    Shelly EM Interface
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
        self.device_address = config_dict["device_address"]
        self.channel_config = config_dict["channel_config"]
        self.timeout = config_dict.get("timeout", 5)
        self.init_time = time.time()
        self._create_registers()
    

    def transform_meter(self, meter: dict, channel_name: str, multiplier: float) -> dict:
        output = {}
        for field in meter:
            if field != "is_valid":
                output[f"{channel_name}/{SHELLY_EM_REGISTER_MAP[field]['register_name']}"] = meter[field] * multiplier
        return output
    
    def process_status(self, status: dict) -> dict:
        output = {}
        for i, meter in enumerate(status["emeters"]):
            config_channel = f"channel_{i+1}"
            if config_channel in self.channel_config:
                output.update(
                    self.transform_meter(
                        meter,
                        self.channel_config[config_channel]["name"],
                        self.channel_config[config_channel]["multiplier"],
                    )
                )
        output["wifi_signal"] = status["wifi_sta"]["rssi"]
        return output

    def _get_shelly_data(self):
        """
        Query API for all available data points
        """

        def exception_handler(request, exception):
            _log.debug(f"Request failed: {exception} while loading {request}")

        output = {}
        req = [grequests.get(f"http://{self.device_address}/status")]
        (res,) = grequests.map(req, exception_handler=exception_handler)
        res.raise_for_status()
        return self.process_status(res.json())

    def _create_registers(self):
        """
        Processes the config scraped from the Shelly device and generates
        register for each available parameter
        """

        for reg, regDef in SHELLY_EM_REGISTER_MAP.items():
            self.insert_register(
                Register(
                    regDef["register_name"], regDef["metadata"]["units"], regDef["metadata"]["description"]
                )
            )

    def _set_points(self, points):
        """
        no writable points, so skipping set_points method
        """
        pass

    def _set_point(self, point_name, value):
        """
        no writable points, so skipping set_point method
        """
        pass

    def get_point(self, point_name):
        """
        Return a desired point
        """
        points = self._scrape_all()
        return points.get(point_name)

    def _scrape_all(self):
        """
        Get all Shelly EM data points
        """
        return self._get_shelly_data()
