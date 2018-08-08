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

    def __init__(self, read_only, volttron_name, dnp3_name, scaling, units, data_type):
        """
            Create a register for a point.

        :param read_only: (boolean) Whether the field is read-only, based on the config's Writable column.
        :param volttron_name: (string) Volttron-given name of point.
        :param dnp3_name: (string) DNP3 name of point.
        :param scaling: (integer) The field's scaling factor.
        :param units: (string) A description of the field's units.
        :param data_type: (type) Python data type of the register. Used to cast API call results.
        """
        super(DNP3Register, self).__init__("byte", read_only, volttron_name, dnp3_name, units)
        self.volttron_name = volttron_name
        self.dnp3_name = dnp3_name
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
        if x is None:
            self._value = None
        else:
            try:
                self._value = self.data_type(x)
            except (ValueError, TypeError):
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
        """Load driver config from the registry, as set up in the VOLTTRON config store."""

        def registry_property(reg_row, property_name, prop_type=None, default=None):
            """Get a single value from the registry's CSV definitions and do some validity checking."""
            reg_prop = reg_row.get(property_name, default)
            if reg_prop is None:
                raise ValueError('Missing {} property in DNP3 registry config, row = {}'.format(property_name, reg_row))
            if prop_type:
                try:
                    reg_prop = type_mapping[prop_type](reg_prop)
                except TypeError:
                    raise TypeError('{} property {} in DNP3 registry config must be {}'.format(property_name,
                                                                                               reg_prop,
                                                                                               prop_type))
            return reg_prop

        for label, config_val in config_dict.items():
            _log.debug('from config: {} = {}'.format(label, config_val))
            setattr(self, label, config_val)
        if registry_config:
            # Create a DNP3Register for each row in the registry config.
            for reg_def in registry_config:
                self.insert_register(DNP3Register(
                    registry_property(reg_def, 'Writable').lower() != 'true',
                    registry_property(reg_def, 'Volttron Point Name'),
                    registry_property(reg_def, 'DNP3 Point Name'),
                    registry_property(reg_def, 'Scaling', prop_type="float", default=1.0),
                    registry_property(reg_def, 'Units', default=''),
                    type_mapping.get(reg_def.get('Data Type', 'string'), str))
                )

    def all_registers(self):
        """Return a list of all registers. The read-only registers are placed before the read-write registers."""
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        return read_registers + write_registers

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
        for point_name, point_value in self.call_agent_rpc('get_configured_points').iteritems():
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

            The point_map dictionary maps VOLTTRON point name to DNP3 point name
            for each point that's configured by the driver:

                {
                    volttron_point_name_1: dnp3_point_name_1,
                    volttron_point_name_2: dnp3_point_name_2,
                    ...
                }
        """
        try:
            # Create a dictionary that maps each register's VOLTTRON point name to its DNP3 point name.
            point_map = {r.volttron_name: r.dnp3_name for r in self.all_registers()}
            response = self.vip.rpc.call(self.dnp3_agent_id, 'config_points', point_map)
            response.get(timeout=10)
            _log.debug('Sent config_points')
            self.points_configured = True
        except Exception, err:
            _log.error('Failed to config_points: {}'.format(str(err)))
            self.points_configured = False      # Force a fresh config_points() call on the next iteration
