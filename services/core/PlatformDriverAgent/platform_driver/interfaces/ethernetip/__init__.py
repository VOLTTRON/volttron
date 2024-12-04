# Copyright (c) 2020, ACE IoT Solutions LLC.
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
The Ethernet/IP Driver allows communication with PLCs and PACs that utilize the Ethernet/IP Common Industrial Protocol (CIP)
"""

import logging
import time
import copy

import pycomm3

from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert

utils.setup_logging()
_log = logging.getLogger(__name__)

class SLCRegister(BaseRegister):
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

    """

    def __init__(self, volttron_point_name, range_id, index, units, read_only, description):
        super(SLCRegister, self).__init__("byte",
                                       read_only,
                                       volttron_point_name,
                                       units,
                                       description=description)
        self.range_id = range_id
        self.index = index


class LogixRegister(BaseRegister):
    """
    Generic class for containing information about a the points exposed by the TED Pro API


    :param register_type: Type of the register. Either "bit" or "byte". Usually "byte".
    :param pointName: Name of the register.
    :param units: Units of the value of the register.
    :param description: Description of the register.

    :type register_type: str
    :type pointName: str
    :type tag_name: str
    :type units: str
    :type description: str

    """

    def __init__(self, volttron_point_name, tag_name, units, read_only, description):
        super(LogixRegister, self).__init__("byte",
                                       read_only,
                                       volttron_point_name,
                                       units,
                                       description=description)
        self.tag_name = tag_name


class Interface(BasicRevert, BaseInterface):
    """Create an interface for the TED device using the standard BaseInterface convention
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.device_path = kwargs.get("device_path")

    def parse_config(self, configDict):
        if configDict is None:
            return
        
        for regDef in configDict:
            # Skip lines that have no address yet.
            if not regDef['Volttron Point Name']:
                continue
            point_path = regDef['Volttron Point Name']        
            read_only = regDef.get('Writable', '').lower() == 'true'
            tag_name = regDef.get('Tag Name')
            range_id = regDef.get('Range ID')
            index = regDef.get('Index')
            description = regDef.get('Notes', '')
            units = regDef.get('Units')
            driver_type = regDef.get('Driver Type')
            if driver_type in ('', None):
                driver_type = 'Logix'
            
            default_value = regDef.get("Default Value", "")
            if default_value is None:
                default_value = ""
            else:
                default_value = default_value.strip()
            if driver_type == 'Logix':
                register = LogixRegister(point_path, tag_name, units, read_only, 
                             description=description)
            if driver_type == 'SLC':
                register = SLCRegister(point_path, range_id, index, units,
                        read_only, description=description)
            
            self.insert_register(register)
            
            # if not read_only:
            #     if default_value:
            #         if isinstance(register, ModbusBitRegister):
            #             try:
            #                 value = bool(int(default_value))
            #             except ValueError:
            #                 value = default_value.lower().startswith('t') or default_value.lower() == 'on'
            #             self.set_default(point_path, value)
            #         else:
            #             try:
            #                 value = register.python_type(default_value)
            #                 self.set_default(point_path, value)
            #             except ValueError:
            #                 _log.warning("Unable to set default value for {}, bad default value in configuration. "
            #                              "Using default revert method.".format(point_path))
            #                 
            #     else:
            #         _log.info("No default value supplied for point {}. Using default revert method.".format(point_path))

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the master driver with configuration 
        stanza and registry config file, we ignore the registry config, as we
        , male Dom here, How are you?
        build the registers based on the configuration collected from TED Pro
        Device
        """

        self.device_address = config_dict['device_address']
        self.micro800 = config_dict.get('micro800', False)
        self.timeout = config_dict.get('timeout', 5)
        self.init_time = time.time()
        self.parse_config(registry_config_str) 



    def _set_point(self, point_name, value):
        """
        NotImplemented
        """
        pass

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        if isinstance(register, LogixRegister):
            with pycomm3.LogixDriver(self.device_address, micro800=self.micro800) as plc:
                return plc.read(register.tag_name)
        elif isinstance(register, SLCRegister):
            with pycomm3.SLCDriver(self.device_address) as plc:
                return plc.read(f'{register.range_id}:{register.index}')


    def _scrape_all(self):
        results = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        all_registers = read_registers + write_registers
        slc_registers = []
        logix_registers = []
        slc_results = []
        logix_results = []
        for register in all_registers:
            if isinstance(register, LogixRegister):
                logix_registers.append(register)
            if isinstance(register, SLCRegister):
                slc_registers.append(register)
        if len(slc_registers) > 0:
            with pycomm3.SLCDriver(self.device_address) as plc:
                slc_results = plc.read(*[f'{reg.range_id}:{reg.index}' for reg in slc_registers])

        if len(logix_registers) > 0:
            with pycomm3.LogixDriver(self.device_address, micro800=self.micro800) as plc:
                logix_results = plc.read(*[reg.tag_name for reg in logix_registers])

        for register, result in zip(slc_registers + logix_registers,
            slc_results + logix_results):
            try:
                assert result.error is None
                results[register.point_name] = float(result.value)
            except Exception as e:
                _log.error("Error reading point: {}".format(repr(e)))

        return results
