# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

from datetime import datetime, timedelta
import logging

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

_log = logging.getLogger(__name__)
type_mapping = {"string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool}

DEFAULT_SEP2_AGENT_ID = 'sep2agent'
DEFAULT_CACHE_EXPIRATION_SECS = 5


class SEP2Register(BaseRegister):
    """Register for all SEP2 interface attributes."""

    def __init__(self, read_only, point_name, sep2_resource_name, sep2_field_name,
                 units, data_type, default_value=None, description=''):
        """
            Create a register for a point.

        :param read_only: True = Read-only, False = Read/Write.
        :param point_name: Volttron-given name of point.
        :param sep2_resource_name: The SEP2 resource mapped to the point.
        :param sep2_field_name: The SEP2 field mapped to the point.
        :param units: Required by parent class. Not used by SEP2.
        :param data_type: Python data type of register. Used to cast API call results.
        :param default_value: Default value of register.
        :param description: Basic description of register.
        """
        super(SEP2Register, self).__init__("byte", read_only, point_name, units, description=description)
        self.point_name = point_name
        self.sep2_resource_name = sep2_resource_name
        self.sep2_field_name = sep2_field_name
        self.data_type = data_type
        self._value = 'value not set'
        self._timestamp = datetime.now()
        # Cast the initial value to the correct data type
        if default_value is None:
            self.set_value(self.data_type(0))
        else:
            try:
                self.set_value(self.data_type(default_value))
            except ValueError:
                self.set_value(self.data_type())

    @property
    def value(self):
        return self._value

    def set_value(self, x):
        """Cast the point value to the correct data type, set the register value, update the cache timestamp."""
        try:
            self._value = self.data_type(x)
        except ValueError:
            _log.critical("{} value of {} cannot be cast to {}".format(self.point_name, x, self.data_type))
            self._value = x
        self._timestamp = datetime.now()
        return self._value

    def is_stale(self):
        return datetime.now() > self._timestamp + timedelta(seconds=DEFAULT_CACHE_EXPIRATION_SECS)


class Interface(BasicRevert, BaseInterface):
    """
        SEP2 device driver interface.

        This driver gets, and sends, device data by issuing RPC calls to SEP2Agent,
        (see its source code in services/core/SEP2Agent), which communicates with
        SEP2 devices via a web interface.

        For further information about this subsystem, please see the VOLTTRON
        SEP 2.0 DER Support specification, which is located in VOLTTRON readthedocs
        under specifications/sep2_agent.html.

        Test drivers for the SEP2 interface can be configured as follows:

            cd $VOLTTRON_ROOT
            export DRIVER_ROOT=$VOLTTRON_ROOT/services/core/MasterDriverAgent/master_driver
            volttron-ctl config store platform.driver sep2.csv $DRIVER_ROOT/sep2.csv --csv
            volttron-ctl config store platform.driver devices/sep2_1 $DRIVER_ROOT/test_sep2_1.config
            volttron-ctl config store platform.driver devices/sep2_2 $DRIVER_ROOT/test_sep2_2.config
            echo SEP2 drivers configured for MasterDriver:
            volttron-ctl config list platform.driver
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.sfdi = ''
        self.sep2_agent_id = DEFAULT_SEP2_AGENT_ID
        self.cache_expiration_secs = DEFAULT_CACHE_EXPIRATION_SECS
        self.points_configured = False

    def configure(self, config_dict, registry_config):
        for label, config_val in config_dict.items():
            _log.debug('from config: {} = {}'.format(label, config_val))
            setattr(self, label, config_val)
        if registry_config:
            # Create a SEP2Register for each point in the registry's CSV definitions.
            for regDef in registry_config:
                default_value = regDef.get('Starting Value', None)
                register = SEP2Register(regDef['Writable'].lower() != 'true',
                                        regDef['Volttron Point Name'],
                                        regDef['SEP2 Resource Name'],
                                        regDef['SEP2 Field Name'],
                                        regDef.get('Units', ''),
                                        type_mapping.get(regDef.get("Type", 'string'), str),
                                        default_value=default_value if default_value != '' else None,
                                        description=regDef.get('Notes', ''))
                self.insert_register(register)
            # Send the EndDevice's point definitions to the SEP2Agent.
            self.call_agent_config_points()

    def get_point_map(self):
        """Return a dictionary of all register definitions, indexed by Volttron Point Name."""
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            point_map[register.point_name] = {'SEP2 Resource Name': register.sep2_resource_name,
                                              'SEP2 Field Name': register.sep2_field_name}
        return point_map

    def get_point(self, point_name, **kwargs):
        """Get the point value, fetching it from SEP2Agent if not already cached."""
        register = self.get_register_by_name(point_name)
        if register.is_stale():
            # Refresh the cached value from SEP2Agent
            point_value = register.set_value(self.call_agent_rpc('get_point', point_name=point_name))
        else:
            point_value = register.value
        _log.debug('Getting {} point value = {}'.format(point_name, point_value))
        return point_value

    def get_register_value(self, point_name):
        return self.get_register_by_name(point_name).value

    def _set_point(self, point_name, point_value):
        """Set the register value of a point, and send the value to SEP2Agent."""
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError('Trying to write to a point configured read only: {}'.format(point_name))
        _log.debug('Setting {} point value = {}'.format(point_name, point_value))
        register.set_value(point_value)
        # Before responding, send the new register value to SEP2Agent.
        self.call_agent_rpc('set_point', point_name=point_name, value=point_value)
        return point_value

    def _scrape_all(self):
        """Scrape the values of all registers, fetching them from SEP2Agent."""
        for point_name, point_value in self.call_agent_rpc('get_points').items():
            if point_name in self.point_map.keys():
                self.get_register_by_name(point_name).set_value(point_value)
        read_registers = self.get_registers_by_type('byte', True)
        write_registers = self.get_registers_by_type('byte', False)
        return {r.point_name: r.value for r in read_registers + write_registers}

    def call_agent_rpc(self, rpc_name, point_name=None, value=None):
        """Issue a SEP2Agent RPC call (get_point, get_points, or set_point), and return the result."""
        if not self.points_configured:
            # This EndDevice's points haven't been successfully configured. Try to do so.
            self.call_agent_config_points()
        if self.points_configured:
            debug_line = 'EndDevice {}: Sent {}{}{}'.format(self.sfdi,
                                                            rpc_name,
                                                            ' for ' + point_name if point_name else '',
                                                            ' with ' + str(value) if value else '')
            try:
                if point_name:
                    if value:
                        response = self.vip.rpc.call(self.sep2_agent_id, rpc_name, self.sfdi, point_name, value)
                    else:
                        response = self.vip.rpc.call(self.sep2_agent_id, rpc_name, self.sfdi, point_name)
                else:
                    response = self.vip.rpc.call(self.sep2_agent_id, rpc_name, self.sfdi)
                result = response.get(timeout=10)
                _log.debug('{0}, received {1}'.format(debug_line, str(result)))
            except Exception as err:
                self.points_configured = False      # Force a fresh config_points() call on the next iteration
                result = {}
                _log.error('{0}, received error: {1}'.format(debug_line, str(err)))
        else:
            result = {}
        return result

    def call_agent_config_points(self):
        """Issue a SEP2Agent RPC call to initialize the point configuration."""
        point_map = self.get_point_map()
        try:
            response = self.vip.rpc.call(self.sep2_agent_id, 'config_points', self.sfdi, point_map)
            response.get(timeout=10)
            _log.debug('EndDevice {0}: Sent config_points'.format(self.sfdi))
            self.points_configured = True
        except Exception as err:
            _log.error('EndDevice {0}: Failed to config_points: {1}'.format(self.sfdi, str(err)))
            self.points_configured = False      # Force a fresh config_points() call on the next iteration
