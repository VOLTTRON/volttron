# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

from gevent import monkey
from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from platform_driver.interfaces.modbus_tk import helpers
from platform_driver.interfaces.modbus_tk.maps import Map

import logging
import struct
import re

monkey.patch_socket()

modbus_logger = logging.getLogger("pymodbus")
modbus_logger.setLevel(logging.WARNING)

utils.setup_logging()
_log = logging.getLogger(__name__)


parity_map = dict(
    none='N',
    even='E',
    odd='O',
    mark='M',
    space='S'
)

config_keys = ["name", "device_type", "device_address", "port", "slave_id", "baudrate", "bytesize", "parity",
               "stopbits", "xonxoff", "addressing", "endian", "write_multiple_registers", "register_map"]

register_map_columns = ["register name", "address", "type", "units", "writable", "default value", "transform", "table",
                        "mixed endian", "description"]


class ModbusInterfaceException(Exception):
    pass


class ModbusTKRegister(BaseRegister):
    """
        Modbus TK register class.

    :param point_name: the register point name
    :param default_value: the default value of writable register
    :param field: modbus client field

    :type point_name: str
    :type default_value: parse str to the register type
    :type field: Field
    """
    def __init__(self, point_name, default_value, field, description=''):
        datatype = 'bit' if field.type == helpers.BOOL else 'byte'

        super(ModbusTKRegister, self).__init__(
            datatype, not field.writable, point_name, field.units, description=description
        )

        self.name = field.name
        self.type = field.type
        self.default_value = self.get_default_value(field.type, default_value)

    def get_python_type(self, datatype):
        """
            Get python type from field data type

        :param datatype: register type

        :type datatype: str

        :return: python type
        """
        # Python 2.7 strings are byte arrays, this no longer works for 3.x
        if isinstance(datatype, tuple) and datatype[0] == 's':
            return str
        try:
            parse_struct = struct.Struct(datatype)
        except TypeError:
            parse_struct = struct.Struct(datatype[0])

        struct_types = [type(x) for x in parse_struct.unpack(('\x00' * parse_struct.size).encode('utf-8'))]

        if len(struct_types) != 1:
            raise ValueError("Invalid length Modbus Register for point {}".format(self.point_name))
        return struct_types[0]

    def get_default_value(self, datatype, str_value):
        """
            Convert default value from str to the register type

        :param datatype: register type
        :param str_value: default value in str

        :type datatype: str
        :type str_value: str
        """
        python_type = self.get_python_type(datatype)
        if str_value:
            if python_type is int:
                return int(str_value)
            elif python_type is float:
                return float(str_value)
            elif python_type is bool:
                return helpers.str2bool(str_value)
            elif python_type is str:
                return str_value
            else:
                raise ValueError("Invalid data type for point {}: {}".format(self.point_name, python_type))
        else:
            return None

    def get_state(self, modbus_client):
        """
            Read value of the register and return it

        :param modbus_client: the modbus tk client parsed from configure

        :type modbus_client: Client
        """
        state = getattr(modbus_client, self.name)
        return state.decode('utf-8') if isinstance(state, bytes) else state

    def set_state(self, modbus_client, value):
        """
            Set value for the register and return the actual value that is set

        :param modbus_client: the modbus tk client that is parsed from configure
        :param value: setting value for writable register

        :type modbus_client: Client
        :type value: same type as register type
        """
        setattr(modbus_client, self.name, value)
        modbus_client.write_all()

        return self.get_state(modbus_client)


class Interface(BasicRevert, BaseInterface):
    """
        Create an interface of the device follows the standard form of BaseInterface

    :param name_map: dictionary mapping the register name to point name
    :param modbus_client: modbus tk client parsed from configure

    :type name_map: dictionary
    :type modbus_client: Client
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.name_map = dict()
        self.modbus_client = None

    def insert_register(self, register):
        """
            Insert register into ModbusTKRegister

        :param register: register to add to the interface

        :type register: ModbusTKRegister
        """
        super(Interface, self).insert_register(register)
        self.name_map[register.name] = register.point_name

    def parse_registry_config(self, old_registry_config_lst):
        """
            Convert original modbus csv format to the new modbus_tk registry_config_lst

        :param old_registry_config_lst: list of all register dictionaries in old volttron csv format

        :type old_registry_config_lst: list
        """
        new_registry_config_lst = []
        for reg_dict in old_registry_config_lst:
            point_name = reg_dict.get('volttron point name')
            register_name = reg_dict.get('reference point name', point_name).replace(" ", "_").lower()
            address = reg_dict.get('point address')
            datatype = reg_dict['modbus register']

            unit = reg_dict.get('units')
            writable = reg_dict.get('writable')
            default_value = reg_dict.get('default value', None)
            description = reg_dict.get('notes', '')
            mixed_endian = reg_dict.get('mixed endian', 'false').lower()

            new_registry_config_lst.append({'volttron point name': point_name,
                                            'register name': register_name,
                                            'address': address,
                                            'type': datatype,
                                            'units': unit,
                                            'writable': writable,
                                            'default value': default_value,
                                            'mixed endian': mixed_endian,
                                            'description': description})

        return new_registry_config_lst

    def configure(self, config_dict, registry_config_lst):
        """
            Parse driver and csv config to define client transport, add registers to ModbusTKRegister,
            and set default values for revert reading

        :param config_dict: dictionary of device configure
        :param registry_config_lst: the list of all register dictionary parsed from the csv file

        :type config_dict: dictionary
        :type registry_config_lst: list
        """

        # Convert keys to lowercase
        config_dict = dict((k.lower(), v) for k, v in config_dict.items())
        registry_config_lst = [dict((k.lower(), v) for k, v in i.items()) for i in registry_config_lst]

        # Log warning if registry_config_lst is empty
        if not registry_config_lst:
            _log.warning("Registry config csv is empty.")

        name = config_dict.get('name', 'UNKOWN')
        device_address = config_dict['device_address']
        port = config_dict.get('port', None)
        slave_address = config_dict.get('slave_id', 1)
        baudrate = config_dict.get('baudrate', 9600)
        bytesize = config_dict.get('bytesize', 8)
        parity = parity_map[config_dict.get('parity', 'none')]
        stopbits = config_dict.get('stopbits', 1)
        xonxoff = config_dict.get('xonxoff', 0)
        addressing = config_dict.get('addressing', helpers.OFFSET).lower()
        endian = config_dict.get('endian', 'big')
        write_single_values = not helpers.str2bool(str(config_dict.get('write_multiple_registers', "True")))

        # Convert original modbus csv config format to the new modbus_tk registry_config_lst
        if registry_config_lst and 'point address' in registry_config_lst[0]:
            registry_config_lst = self.parse_registry_config(registry_config_lst)

        # Get register map and convert everything to lowercase
        register_map = dict((reg['register name'], reg) for reg in
                            [dict((k.lower(), v) for k, v in i.items()) for i in
                             config_dict.get('register_map', registry_config_lst)])

        # Log warning for ignored config fields
        ignored_config_keys = [k for k in config_dict.keys() if k not in config_keys]
        if ignored_config_keys:
            _log.warning("%s: Ignored config fields: %s", name, ','.join(ignored_config_keys))

        try:
            # Log warning for ignored register map csv column
            ignored_register_map_csv_columns = [c for c in list(register_map.values())[0].keys() if c not in register_map_columns]
            if ignored_register_map_csv_columns:
                _log.warning("%s: Ignored register map csv columns: %s", name, ','.join(ignored_register_map_csv_columns))
        except IndexError:
            # Log warning if register_map is empty
            if not register_map:
                _log.warning("Register map csv is empty.")

        # Get the list of selected register dictionary based on Register Name from registry_config_lst
        selected_registry_config_lst = list()
        for reg_dict in registry_config_lst:
            reg_name = reg_dict.get('register name')
            try:
                register_map[reg_name].update(reg_dict)
                selected_registry_config_lst.append(register_map[reg_name])
            except KeyError:
                _log.warning("No register name matching found: %s", reg_name)

        # Log warning if selected_registry_config_lst is empty
        if not selected_registry_config_lst:
            _log.warning("The selected registry config list is empty.")

        # Generate the subclass of Client from the device config and register list
        modbus_client_class = Map(
            name=name,
            addressing=addressing,
            endian=endian,
            registry_config_lst=selected_registry_config_lst
        ).get_class()

        self.modbus_client = modbus_client_class(device_address=device_address,
                                                 port=port,
                                                 slave_address=slave_address,
                                                 write_single_values=write_single_values)

        # Set modbus client transport based on device configure
        if port:
            self.modbus_client.set_transport_tcp(
                hostname=device_address,
                port=port
            )
        else:
            self.modbus_client.set_transport_rtu(
                device=device_address,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                xonxoff=xonxoff
            )

        # Insert driver/interface registers
        for reg_dict in selected_registry_config_lst:
            register = ModbusTKRegister(
                reg_dict.get('volttron point name'),
                reg_dict.get('default value', None),
                self.modbus_client.field_by_name(reg_dict.get('register name'))
            )
            self.insert_register(register)
            if not register.read_only and register.default_value:
                self.set_default(register.point_name, register.default_value)


    def get_point(self, point_name):
        """
            Get the value of a point from a device and return it

        :param point_name: register point name

        :type point_name: str
        """
        return self.get_register_by_name(point_name).get_state(self.modbus_client)

    def _set_point(self, point_name, value):
        """
            Set the value of a point on a device and ideally return the actual value set

        :param point_name: register point name
        :param value: setting value for writable register

        :type point_name: str
        :type value: same type as register type
        """
        return self.get_register_by_name(point_name).set_state(self.modbus_client, value)

    def _scrape_all(self):
        """Get a dictionary mapping point name to values of all defined registers
        """
        return dict((self.name_map[field.name], value.decode('utf-8') if isinstance(value, bytes) else value) for
                    field, value, timestamp in self.modbus_client.dump_all())
