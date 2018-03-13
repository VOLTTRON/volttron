# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / Kisensum.
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
# United States Department of Energy, nor SLAC, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

from datetime import datetime, timedelta
import logging

from . import BaseInterface, BaseRegister, BasicRevert

_log = logging.getLogger(__name__)
type_mapping = {"string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool}

DEFAULT_DNP3_AGENT_ID = 'dnp3agent'
DEFAULT_CACHE_EXPIRATION_SECS = 5


class DNP3Register(BaseRegister):
    """Register for each DNP3 interface field (point)."""

    def __init__(self, read_only, point_name, group, index, scaling, units, data_type):
        """
            Create a register for a point.

        :param read_only: (boolean) Whether the field is read-only, based on the config's Writable column.
        :param point_name: (string) Volttron-given name of point.
        :param group: (string) Group of the DNP3 field mapped to the point.
        :param index: (string) Index of the DNP3 field mapped to the point.
        :param scaling: (integer) The field's scaling factor.
        :param units: (string) A description of the field's units.
        :param data_type: (type) Python data type of the register. Used to cast API call results.
        """
        super(DNP3Register, self).__init__("byte", read_only, point_name, units)
        self.point_name = point_name
        self.group = group
        self.index = index
        self.scaling = scaling
        self._value = 'value not set'
        self._timestamp = datetime.now()
        self.data_type = data_type
        self.set_value(self.data_type(0))           # Cast the initial value to the correct data type

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
        """Whether it is time to refresh the register's cached value."""
        return datetime.now() > self._timestamp + timedelta(seconds=DEFAULT_CACHE_EXPIRATION_SECS)


class Interface(BasicRevert, BaseInterface):
    """
        DNP3 device driver interface.

        This driver gets, and sends, DNP3 device data by issuing RPC calls to DNP3Agent,
        (see its source code in services/core/DNP3Agent), which communicates with the
        DNP3 master via a web interface.

        Test drivers for the DNP3 interface can be configured as follows:

        export VOLTTRON_ROOT=<your VOLTTRON install directory>
        export DRIVER_ROOT=$VOLTTRON_ROOT/services/core/MasterDriverAgent
        cd $VOLTTRON_ROOT
        volttron-ctl config store platform.driver dnp3.csv $DRIVER_ROOT/example_configurations/dnp3.csv --csv
        volttron-ctl config store platform.driver devices/dnp3 $DRIVER_ROOT/example_configurations/test_dnp3.config
    """

    def __init__(self, **kwargs):
        """Initialize the DNP3 interface."""
        super(Interface, self).__init__(**kwargs)
        self.dnp3_agent_id = DEFAULT_DNP3_AGENT_ID      # This gets overridden by the config file if it's defined there.
        self.cache_expiration_secs = DEFAULT_CACHE_EXPIRATION_SECS
        self.points_configured = False

    def configure(self, config_dict, registry_config):
        """Load the config from driver and registry config, as set up in the VOLTTRON config store."""
        for label, config_val in config_dict.items():
            _log.debug('from config: {} = {}'.format(label, config_val))
            setattr(self, label, config_val)
        if registry_config:
            # Create a DNP3Register for each point in the registry's CSV definitions.
            for regDef in registry_config:
                register = DNP3Register(regDef['Writable'].lower() != 'true',
                                        regDef['Volttron Point Name'],
                                        int(regDef['Group']),
                                        int(regDef['Index']),
                                        regDef.get('Scaling', 1.0),
                                        regDef.get('Units', ''),
                                        type_mapping.get(regDef.get('Type', 'string'), str))
                self.insert_register(register)

    def get_point_map(self):
        """
            Return a dictionary that maps each register's VOLTTRON point name to its DNP3 group and index.
        """
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            point_map[register.point_name] = {
                'group': register.group,
                'index': register.index
            }
        return point_map

    def get_point(self, point_name, **kwargs):
        """
            Get a point value by (VOLTTRON) point name.

            Fetch it from the DNP3Agent if it's not already fresh in the cache.
        """
        register = self.get_register_by_name(point_name)
        if register.is_stale():
            # Refresh the cached value from DNP3Agent
            point_value = register.set_value(self.call_agent_rpc('get_point', point_name=point_name))
        else:
            point_value = register.value
        _log.debug('Getting {} point value = {}'.format(point_name, point_value))
        return point_value

    def get_register_value(self, point_name):
        return self.get_register_by_name(point_name).value

    def _set_point(self, point_name, point_value):
        """Set the register value of a point, and send the value to DNP3Agent."""
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError('Trying to write to a point configured read only: {}'.format(point_name))
        _log.debug('Setting {} point value = {}'.format(point_name, point_value))
        register.set_value(point_value)
        # Before responding, send the new register value to DNP3Agent.
        self.call_agent_rpc('set_point', point_name=point_name, value=point_value)
        return point_value

    def _scrape_all(self):
        """Scrape the values of all registers, fetching them from DNP3Agent."""
        for point_name, point_value in self.call_agent_rpc('get_points').iteritems():
            if point_name in self.point_map.keys():
                self.get_register_by_name(point_name).set_value(point_value)
        read_registers = self.get_registers_by_type('byte', True)
        write_registers = self.get_registers_by_type('byte', False)
        return {r.point_name: r.value for r in read_registers + write_registers}

    def call_agent_rpc(self, rpc_name, point_name=None, value=None):
        """Issue a DNP3Agent RPC call (get_point, get_points, or set_point), and return the result."""
        result = {}
        if not self.points_configured:
            # The driver's point definitions haven't been successfully configured yet. Try to do so.
            self.call_agent_config_points()
        if self.points_configured:
            debug_line = 'Sent {}{}{}'.format(rpc_name,
                                              ' for ' + point_name if point_name else '',
                                              ' with ' + str(value) if value else '')
            try:
                if point_name:
                    if value:
                        response = self.vip.rpc.call(self.dnp3_agent_id, rpc_name, point_name, value)
                    else:
                        response = self.vip.rpc.call(self.dnp3_agent_id, rpc_name, point_name)
                else:
                    response = self.vip.rpc.call(self.dnp3_agent_id, rpc_name)
                result = response.get(timeout=10)
                _log.debug('{0}, received {1}'.format(debug_line, str(result)))
            except Exception, err:
                self.points_configured = False      # Force a fresh config_points() call on the next iteration
                _log.error('{0}, received error: {1}'.format(debug_line, str(err)))
        return result

    def call_agent_config_points(self):
        """
            Issue a DNP3Agent RPC call to initialize the driver's point configuration.

            The point_map dictionary maps VOLTTRON point name to DNP3 group and index
            for each point that's configured by the driver:

                {
                    "point_name_1": {
                        "group": dnp3_group_number,
                        "index": dnp3_index_number
                    }
                    "point_name_2": {
                        "group": dnp3_group_number,
                        "index": dnp3_index_number
                    }
        """
        try:
            response = self.vip.rpc.call(self.dnp3_agent_id, 'config_points', self.get_point_map())
            response.get(timeout=10)
            _log.debug('Sent config_points')
            self.points_configured = True
        except Exception, err:
            _log.error('Failed to config_points: {}'.format(str(err)))
            self.points_configured = False      # Force a fresh config_points() call on the next iteration
