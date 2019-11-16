# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import os
from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from csv import DictReader, DictWriter
import logging

CSV_FIELDNAMES = ["Point Name", "Point Value"]
CSV_DEFAULT = [
    {
        "Point Name": "test1",
        "Point Value": 0
    },
    {
        "Point Name": "test2",
        "Point Value": 1
    },
    {
        "Point Name": "test3",
        "Point Value": "testpoint"
    }]


_log = logging.getLogger(__name__)
type_mapping = {"string": str,
                "int": int,
                "integer": int,
                "float": float,
                "bool": bool,
                "boolean": bool}


class CsvRegister(BaseRegister):
    def __init__(self, csv_path, read_only, pointName, units, reg_type,
                 default_value=None, description=''):
        super(CsvRegister, self).__init__("byte", read_only, pointName, units,
                                          description=description)
        self.csv_path = csv_path

    def get_state(self):
        if os.path.isfile(self.csv_path):
            with open(self.csv_path, "r") as csv_device:
                reader = DictReader(csv_device)
                for point in reader:
                    if point.get("Point Name") == self.point_name:
                        point_value = point.get("Point Value")
                        if not point_value:
                            raise RuntimeError("Point {} not set on CSV Device".format(self.point_name))
                        else:
                            return point_value
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            raise RuntimeError("CSV device at {} does not exist".format(self.csv_path))

    def set_state(self, value):
        _log.info("Setting state for {} on CSV Device".format(self.point_name))
        field_names = []
        points = []
        found = False
        with open(self.csv_path, "r") as csv_device:
            reader = DictReader(csv_device)
            field_names = reader.fieldnames
            for point in reader:
                if point["Point Name"] == self.point_name:
                    found = True
                    point_copy = point
                    point_copy["Point Value"] = value
                    points.append(point_copy)
                else:
                    points.append(point)

        if not found:
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            with open(self.csv_path, "w") as csv_device:
                writer = DictWriter(csv_device, fieldnames=field_names)
                writer.writeheader()
                writer.writerows([dict(row) for row in points])
        return self.get_state()


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.csv_path = None

    def configure(self, config_dict, registry_config_str):
        self.csv_path = config_dict.get("csv_path", "csv_device.csv")
        if not os.path.isfile(self.csv_path):
            _log.info("Creating csv 'device'")
            with open(self.csv_path, "w+") as csv_device:
                writer = DictWriter(csv_device, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                writer.writerows(CSV_DEFAULT)
        self.parse_config(registry_config_str)

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)

        return register.get_state()

    def set_point(self, point_name, value):
        _log.debug("Point {} being set to {}".format(point_name, value))
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)

        register.set_state(value)
        return register.get_state()

    def scrape_all(self):
        _log.info("Scraping all registers")
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            result[register.point_name] = register.get_state()

        return result

    def parse_config(self, config_dict):
        if config_dict is None:
            return

        for index, regDef in enumerate(config_dict):
            # Skip lines that have no point name yet
            if not regDef.get('Point Name'):
                continue

            read_only = regDef.get('Writable', "").lower() != 'true'
            point_name = regDef.get('Volttron Point Name')
            if not point_name:
                point_name = regDef.get("Point Name")
            if not point_name:
                raise ValueError("Registry config entry {} did not have a point name or volttron point name".format(
                    index))
            description = regDef.get('Notes', '')
            units = regDef.get('Units', None)
            default_value = regDef.get("Default Value", "").strip()
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            reg_type = type_mapping.get(type_name, str)

            register = CsvRegister(
                self.csv_path,
                read_only,
                point_name,
                units,
                reg_type,
                default_value=default_value,
                description=description)

            if default_value is not None:
                self.set_default(point_name, register.value)

            self.insert_register(register)
