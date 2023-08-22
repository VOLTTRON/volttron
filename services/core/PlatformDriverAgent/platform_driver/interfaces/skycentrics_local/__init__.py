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
import json
import mqtt

from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from volttron.platform.vip.agent import Agent, Core, RPC, PubSub

_log = logging.getLogger("skycentrics_local")

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
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.get_data

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the platform driver with configuration 
        stanza and registry config file
        """
        pass
    
    def _create_registers(self, ted_config):
        """
        Processes the config scraped from the device and generates
        register for each available parameter
        """
        return

    def _set_points(self, points):
        pass

    def _set_point(self, point_name, value):
        pass

    
    def get_point(self, point_name):
        """Get specified point"""
        points = self._scrape_all()
        return points.get(point_name)

    def on_connect(self):
        """Run when MQTT client initially connects"""
        _log.info("Connected to MQTT broker")
        self.client.subscribe("#")

    def get_data(self, client, userdata, message):
        """
        Continuously listen for messages from the MQTT broker
        """
        payload = json.loads(message.payload)
        _log.debug(f"{payload=}")


    def _scrape_all(self):
        output = {}
        system_data, = self.get_data()
        output = system_data
        del output['name']
        return output
