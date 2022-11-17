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
The Candidus Driver allows control and monitoring of Candidus devices via Candidus API
"""

import logging
import time
import copy

import grequests

from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from volttron.platform.vip.agent import Agent, Core, RPC, PubSub


_log = logging.getLogger("candidus")

CANDIDUS_REGISTER_MAP = {'lightLevelPercent': {'units': '%',
    'description': 'commanded light control level'},
    'ppfdTarget': {'units': 'PPFD',
        'description': 'set point for desired PPFD'},
    'cumulativeSunDLI': {'units': 'PPF',
        'description': 'cumulative value of natural daylight PPF'},
    'cumulativeLEDDLI': {'units': 'PPF',
        'description': 'cumulative value of LED PPF'},
    'sensorPPFD': {'units': 'PPFD',
        'description': 'current PPFD at sensor'}
    }


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
        #self.device_address = config_dict['driver_config']['device_address']
        self.device_address = config_dict['device_address']
        self.zone_no = config_dict['zone']
        self.timeout = config_dict.get('timeout', 5)
        self.init_time = time.time()
        self._create_registers()
        # self.ted_config = self._get_ted_configuration()
        # self._create_registers(self.ted_config)
        # if self.track_totalizers:
        #     self._get_totalizer_state()


    def _get_candidus_data(self):
        def exception_handler(request, exception):
            _log.debug(f"Request failed: {exception} while loading {request}")
        output = {}
        req = [grequests.get(f"http://{self.device_address}:1880/DLIupdate", params={"zone": self.zone_no})]
        _log.debug(req[0].url)
        res, = grequests.map(req, exception_handler=exception_handler)
        res.raise_for_status()
        for regName, value in res.json().items():
            if regName in CANDIDUS_REGISTER_MAP:
                output[regName] = value

        return output




    
    def _create_registers(self):
        """
        Processes the config scraped from the TED Pro device and generates
        register for each available parameter
        """
        
        for reg, regDef in CANDIDUS_REGISTER_MAP.items():
            self.insert_register(Register(reg, regDef["units"], regDef["description"]))


    def _set_points(self, points):
        pass



    def _set_point(self, point_name, value):
        """
        TED has no writable points, so skipping set_point method
        """
        _log.debug(f"calling venstar _set_point")
        pass


    def get_point(self, point_name):
        points = self._scrape_all()
        return points.get(point_name)



    def _scrape_all(self):
        return self._get_candidus_data()

