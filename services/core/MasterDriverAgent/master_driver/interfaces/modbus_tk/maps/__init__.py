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

from master_driver.interfaces.modbus_tk.client import Field, Client
from master_driver.interfaces.modbus_tk import helpers
from collections import Mapping

import csv
import re
import os
import yaml


class MapException(Exception):
    pass

# Types that can be specified in the map csv file.
data_type_map = dict(
    bool=helpers.BOOL,
    char=helpers.CHAR,
    int16=helpers.SHORT,
    uint16=helpers.USHORT,
    int32=helpers.INT,
    uint32=helpers.UINT,
    int64=helpers.INT64,
    uint64=helpers.UINT64,
    float=helpers.FLOAT
)

transform_map = dict(
    scale=helpers.scale,
    scale_int=helpers.scale_int,
    mod10k=helpers.mod10k
)

table_map = dict(
    discrete_output_coils=helpers.COIL_READ_WRITE,
    discrete_input_contacts=helpers.COIL_READ_ONLY,
    analog_input_registers=helpers.REGISTER_READ_ONLY,
    analog_output_holding_registers=helpers.REGISTER_READ_WRITE
)


class CSVRegister(object):
    """
        Parses a row from the csv representing a modbus register.
    """

    def __init__(self, map, registry_dict):
        self._map = map
        self._reg_dict = registry_dict

    @property
    def _name(self):
        try:
            return self._reg_dict['Register Name']
        except KeyError:
            raise MapException("Register Name does not exist")

    @property
    def _datatype(self):
        """
            Transforms the CSV type value into a supported type.
            @todo Modbus client needs to correctly handle odd string length.

        :return: Modbus Type (using struct)
        """
        csv_type = self._reg_dict.get('Type', 'UNDEFINED').strip()

        if csv_type == 'UNDEFINED':
            raise MapException("Type required for each field: %s" % self._reg_dict)

        if csv_type.startswith('string'):
            match = re.match('string\[(\d+)\]', csv_type)
            if match:
                length = int(match.group(1))
                datatype = helpers.string(length)
        else:
            datatype = data_type_map.get(csv_type.lower(), csv_type)

        return datatype

    @property
    def _units(self):
        return self._reg_dict.get('Units', '')

    @property
    def _precision(self):
        return int(self._reg_dict.get('Precision', '0'))

    @property
    def _transform(self):
        # "scale(0.001)", "scale_int(1.0)", "mod10k(True)", or None for no_op

        transform_func = helpers.no_op
        csv_transform = self._reg_dict.get('Transform', None)

        if csv_transform:
            match = re.match('(\w+)\(([a-zA-z0-9.]*)\)', csv_transform)
            func = match.group(1)
            arg = match.group(2)

            try:
                transform_func = transform_map[func](arg)
            except (ValueError, TypeError) as err:
               raise Exception(err)

        return transform_func

    @property
    def _writable(self):
        return helpers.str2bool(self._reg_dict.get('Writable', 'False'))

    @property
    def _table(self):
        """ Select one of the four modbus tables.
        """
        table = self._reg_dict.get('Table', '')
        if table:
            return table_map[table]
        else:
            if self._datatype == helpers.BOOL:
                return helpers.COIL_READ_WRITE if self._writable else helpers.COIL_READ_ONLY
            else:
                return helpers.REGISTER_READ_WRITE if self._writable else helpers.REGISTER_READ_ONLY

    @property
    def _op_mode(self):
        return helpers.OP_MODE_READ_WRITE if helpers.str2bool(self._reg_dict.get('Writable', 'False')) \
            else helpers.OP_MODE_READ_ONLY

    @property
    def _address(self):
        addr = self._reg_dict['Address'].lower()
        # Hex address supported
        return int(addr, 16) if 'x' in addr else int(addr)

    @property
    def _description(self):
        return self._reg_dict.get('Description', 'UNKNOWN')

    def get_field(self):
        """Return a modbus field that can be added to a Modbus client instance.
        """
        return Field(self._name,
                     self._address,
                     self._datatype,
                     self._units,
                     self._precision,
                     self._transform,
                     self._table,
                     self._op_mode)


class Map(object):
    """A Modbus register map read from CSV.

       The Map knows how to generate a subclass of modbus.Client with
       all the Fields (Registers) defined in the CSV.
    """

    def __init__(self, file='', map_dir='', addressing='offset',  name='', endian='big', description='', registry_config_lst=''):
        self._filename = file
        self._map_dir = map_dir

        if addressing not in ('offset', 'offset_plus', 'address'):
            raise MapException("addressing must be one of: (offset, offset_plus, address)")
        elif addressing == 'address':
            self._addressing = helpers.ADDRESS_MODBUS
        elif addressing == 'offset_plus':
            self._addressing = helpers.ADDRESS_OFFSET_PLUS_ONE
        else:
            self._addressing = helpers.ADDRESS_OFFSET

        self._endian = helpers.LITTLE_ENDIAN if endian.lower() == 'little' else helpers.BIG_ENDIAN
        self._name = name
        self._description = description
        self._registry_config_lst = registry_config_lst
        self._registers = dict()

    def _convert_csv_registers(self):
        """Loading contents of the csv into dictionary
        """
        if self._map_dir:
            if self._map_dir not in self._filename:
                self._filename = self._map_dir + '/' + self._filename
            with open(self._filename) as csv_file:
                csv_reader = csv.DictReader(csv_file)
                self._registry_config_lst = [{key: val for key, val in row.items()} for row in csv_reader]

    def _load_registers(self):
        """Process the registers list, loading each register dictionary into field
        """
        if self._filename:
            self._convert_csv_registers()
        if self._registry_config_lst is None:
            raise MapException('No registers defined in your csv config')
        for registry_dict in self._registry_config_lst:
            if registry_dict['Register Name'].startswith('#'):  # ignore comment
                continue
            csv_register = CSVRegister(self, registry_dict)
            register_field = csv_register.get_field()
            self._registers[register_field.name] = register_field

    def get_class(self):
        """
            Generates the subclass of modbus.Client combining attributes from
            the catalog YAML file and the fields defined in the CSV referenced by
            the YAML.

        :return:  subclass of ModbusClient
        """
        class_attrs = dict(byte_order=self._endian,
                           addressing=self._addressing)
        self._load_registers()
        class_attrs.update(self._registers)
        modbus_client_class = type(self._name.replace(' ', '_'),
                                   (Client,),
                                   class_attrs)
        return modbus_client_class


class Catalog(Mapping):

    _data = None

    def __init__(self):
        """
            Load the catalog of modbus maps into _data once.
            The catalog resides in the maps.yaml file. Each entry
            looks like:

            - name: Elkor WattsOn
              endian: big
              addressing: offset
              file: elkor_wattson.csv

        """
        super(Catalog, self).__init__()
        if Catalog._data is None:
            Catalog._data = dict()
            yaml_path = 'maps.yaml'
            if os.path.dirname(__file__):
                yaml_path = os.path.dirname(__file__) + '/' + yaml_path

            with open(yaml_path, 'rb') as yaml_file:
                for map in yaml.load(yaml_file):
                    Catalog._data[map['name']] = Map(file=map.get('file',''),
                                                     map_dir=os.path.dirname(__file__),
                                                     addressing=map.get('addressing','offset'),
                                                     name=map['name'],
                                                     endian=map.get('endian','big'),
                                                     description=map.get('description',''))

    def __getitem__(self, item):
        return self._data[item]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)