# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

from gevent import monkey
from volttron.platform.agent import utils
from master_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from master_driver.interfaces.modbus_tk import helpers
from master_driver.interfaces.modbus_tk.maps import Map

import logging
import struct

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

endian_map = dict(
    little=helpers.LITTLE_ENDIAN,
    big=helpers.BIG_ENDIAN
)


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
    def __init__(self, point_name, default_value, mixed_endian, field, description=''):
        datatype = 'bit' if field.type == helpers.BOOL else 'byte'

        super(ModbusTKRegister, self).__init__(
            datatype, not field.writable, point_name, field.units, description=description
        )

        self.name = field.name
        self.type = field.type
        self.default_value = self.get_default_value(field.type, default_value)
        self.mixed_endian = mixed_endian

        if self.mixed_endian and field.transform is not helpers.no_op:
            raise ModbusInterfaceException("Mixed Endian register does not support transform.")

    def get_python_type(self, datatype):
        """
            Get python type from field data type

        :param datatype: register type

        :type datatype: str

        :return: python type
        """
        try:
            parse_struct = struct.Struct(datatype)
        except TypeError:
            parse_struct = struct.Struct(datatype[0])

        struct_types = [type(x) for x in parse_struct.unpack('\x00' * parse_struct.size)]

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
                raise ValueError("Invalid data type for point {}".format(self.point_name))
        else:
            return None

    def mixed_endian_convert(self, datatype, value):
        """
            Reverse order of register

        :param datatype: register type
        :param value: register value to reverse
        """
        try:
            datatype = datatype[1:] if datatype.startswith((">", "<")) else datatype
            parse_struct = struct.Struct(">{}".format(datatype))
        except AttributeError:
            parse_struct = struct.Struct(">{}".format(datatype[0]))

        value_bytes = parse_struct.pack(value)
        register_values = []
        for i in xrange(0, len(value_bytes), 2):
            register_values.extend(struct.unpack(">H", value_bytes[i:i + 2]))
        register_values.reverse()
        convert_bytes = ''.join([struct.pack(">H", i) for i in register_values])

        return parse_struct.unpack(convert_bytes)[0]

    def get_state(self, modbus_client):
        """
            Read value of the register and return it

        :param modbus_client: the modbus tk client parsed from configure

        :type modbus_client: Client
        """
        get_value = getattr(modbus_client, self.name)

        if self.mixed_endian:
            get_value = self.mixed_endian_convert(self.type, get_value)

        return get_value

    def set_state(self, modbus_client, value):
        """
            Set value for the register and return the actual value that is set

        :param modbus_client: the modbus tk client that is parsed from configure
        :param value: setting value for writable register

        :type modbus_client: Client
        :type value: same type as register type
        """
        if self.mixed_endian:
            value = self.mixed_endian_convert(self.type, value)

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
            point_name = reg_dict.get('Volttron Point Name')
            register_name = reg_dict.get('Reference Point Name', point_name).replace(" ", "_").lower()
            address = reg_dict.get('Point Address')
            datatype = reg_dict['Modbus Register']

            unit = reg_dict.get('Units')
            writable = reg_dict.get('Writable')
            default_value = reg_dict.get('Default Value', None)
            description = reg_dict.get('Note', '')
            mixed_endian = helpers.str2bool(reg_dict.get('Mixed Endian', 'False').lower())

            new_registry_config_lst.append({'Volttron Point Name': point_name,
                                            'Register Name': register_name,
                                            'Address': address,
                                            'Type': datatype,
                                            'Units': unit,
                                            'Writable': writable,
                                            'Default Value': default_value,
                                            'Mixed Endian': mixed_endian,
                                            'Description': description})

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
        endian = endian_map[config_dict.get('endian', helpers.BIG)]
        write_single_values = not helpers.str2bool(str(config_dict.get('write_multiple_registers', "True")))

        # Convert original modbus csv config format to the new modbus_tk registry_config_lst
        if registry_config_lst and 'Point Address' in registry_config_lst[0]:
            registry_config_lst = self.parse_registry_config(registry_config_lst)

        register_map = dict((reg['Register Name'], reg) for reg in config_dict.get('register_map', registry_config_lst))

        # Get the list of selected register dictionary based on Register Name from registry_config_lst
        selected_registry_config_lst = list()
        for reg_dict in registry_config_lst:
            try:
                reg_name = reg_dict.get('Register Name')
                register_map[reg_name].update(reg_dict)
                selected_registry_config_lst.append(register_map[reg_name])
            except KeyError:
                _log.warning("No register name matching found: {0}".format(reg_name))

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
                reg_dict.get('Volttron Point Name'),
                reg_dict.get('Default Value', None),
                reg_dict.get('Mixed Endian', False),
                self.modbus_client.field_by_name(reg_dict.get('Register Name'))
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
        register = self.get_register_by_name(point_name)
        return register.get_state(self.modbus_client)

    def _set_point(self, point_name, value):
        """
            Set the value of a point on a device and ideally return the actual value set

        :param point_name: register point name
        :param value: setting value for writable register

        :type point_name: str
        :type value: same type as register type
        """
        register = self.get_register_by_name(point_name)
        return register.set_state(self.modbus_client, value)

    def _scrape_all(self):
        """Get a dictionary mapping point name to values of all defined registers
        """
        # return dict((self.name_map[field.name], value) for field, value, timestamp in self.modbus_client.dump_all())
        value_map = dict((self.name_map[field.name], value) for field, value, timestamp in self.modbus_client.dump_all())

        for point_name in value_map.keys():
            register = self.get_register_by_name(point_name)
            if register.mixed_endian:
                value_map[point_name] = register.mixed_endian_convert(register.type, value_map[point_name])

        return value_map