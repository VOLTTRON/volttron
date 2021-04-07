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
from platform_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from csv import DictReader, DictWriter
import logging

# Use the csv fields and default dictionary to create a CSV "device" for testing
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
    """
    Register class for reading and writing to specific lines of a CSV file
    """
    def __init__(self, csv_path, read_only, pointName, units, reg_type,
                 default_value=None, description=''):
        # set inherited values
        super(CsvRegister, self).__init__("byte", read_only, pointName, units,
                                          description=description)
        # set the path to the CSV this register belongs to
        self.csv_path = csv_path

    def get_state(self):
        """
        Iterate over the CSV, find the row where the Point Name matches the name of this register
        :return: The Point Value of the row that matches the register
        """
        # Iterate over the lines of the CSV
        if os.path.isfile(self.csv_path):
            with open(self.csv_path, "r") as csv_device:
                reader = DictReader(csv_device)
                for point in reader:
                    # This is the current "register"
                    if point.get("Point Name") == self.point_name:
                        # so get it's value
                        point_value = point.get("Point Value")
                        # The "device" doesn't have the correct fields or is missing a value
                        if not point_value:
                            raise RuntimeError("Point {} not set on CSV Device".format(self.point_name))
                        else:
                            return point_value
            # If we get here, we never encountered a row with Point Name equal to the register name
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            # Our device hasn't been created, or the path to this device is incorrect
            raise RuntimeError("CSV device at {} does not exist".format(self.csv_path))

    def set_state(self, value):
        """
        Set the value of the row this register represents in the CSV file
        :param value: the value to set in the row
        :return: The new value of the row
        """
        # We're going to have to re-write the data, so keep track of the points that are in the file
        points = []
        # Keep track of if we encountered the correct register
        found = False
        # Open the CSV file
        with open(self.csv_path, "r") as csv_device:
            reader = DictReader(csv_device)
            field_names = reader.fieldnames
            # Iterate over it to find the row this register represents
            for point in reader:
                if point["Point Name"] == self.point_name:
                    # Write over the current value, then add it to the list of values from the CSV
                    found = True
                    point_copy = point
                    point_copy["Point Value"] = value
                    points.append(point_copy)
                else:
                    # Copy values which don't correspond to our register as they are
                    points.append(point)

        if not found:
            # We never encountered a row that matches our register
            raise RuntimeError("Point {} not found on CSV Device".format(self.point_name))
        else:
            # We found and wrote our register, so update the "device" by writing out the CSV
            with open(self.csv_path, "w") as csv_device:
                writer = DictWriter(csv_device, fieldnames=field_names)
                writer.writeheader()
                writer.writerows([dict(row) for row in points])
        # Let the Interface know that we succeeded in updating the point
        return self.get_state()


class Interface(BasicRevert, BaseInterface):
    """
    "Device Interface" for reading and writing rows of a CSV as a Volttron connected device
    """
    def __init__(self, **kwargs):
        # Configure the base interface
        super(Interface, self).__init__(**kwargs)
        # We wont have a path to our "device" until we've been configured
        self.csv_path = None

    def configure(self, config_dict, registry_config_str):
        """
        Set the Interface attributes from the configurations provided by the Platform Driver, and create the "device" if
        it doesn't already exist
        :param config_dict: Dictionary of configuration values passed from the Platform Driver
        :param registry_config_str: String representation of the registry configuration passed from the Platform Driver
        """
        # Set the CSV interface's necessary attributes from the configuration
        self.csv_path = config_dict.get("csv_path", "csv_device.csv")
        # If the configured path doesn't exist, create the CSV "device" file using the global defaults
        # so that we have something to test against
        if not os.path.isfile(self.csv_path):
            _log.info("Creating csv 'device'")
            with open(self.csv_path, "w+") as csv_device:
                writer = DictWriter(csv_device, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                writer.writerows(CSV_DEFAULT)
        # Then parse the registry configuration to create our registers
        self.parse_config(registry_config_str)

    def get_point(self, point_name):
        """
        Read the value of the register which matches the passed point name
        :param point_name: The point name of the register the user wishes to read
        :return: the value of the register which matches the point name
        """
        # Determine which register instance is configured for the point we desire
        register = self.get_register_by_name(point_name)
        # then return that register's state
        return register.get_state()

    def _set_point(self, point_name, value):
        """
        Read the value of the register which matches the passed point name
        :param point_name: The point name of the register the user wishes to set
        :param value: The value the user wishes to update the register with
        :return: The value of the register after updates
        """
        # Determine which register instance is configured for the point we desire
        register = self.get_register_by_name(point_name)
        # We don't want to try to overwrite "write-protected" data so throw an error
        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)
        # set the state, and return the new value
        return register.set_state(value)

    def _scrape_all(self):
        """
        Loop over all of the registers configured for this device, then return a mapping of register name to its value
        :return: Results dictionary of the form {<register point name>: <register value>, ...}
        """
        # Create a dictionary to hold our results
        result = {}
        # Get all of the registers that are configured for this device, whether they can be written to or not
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        # For each register, create an entry in the results dictionary with its name as the key and state as the value
        for register in read_registers + write_registers:
            result[register.point_name] = register.get_state()
        # Return the results
        return result

    def parse_config(self, config_dict):
        """
        Given a registry configuration, configure registers and add them to our list of configured registers
        :param config_dict: Registry configuration entry
        """
        # There's nothing to configure, so don't bother
        if config_dict is None:
            return
        # Iterate over the registry configuration entries
        for index, regDef in enumerate(config_dict):
            # Skip lines that have no point name yet
            if not regDef.get('Point Name'):
                continue
            # Extract the values of the configuration, and format them for our purposes
            read_only = regDef.get('Writable', "").lower() != 'true'
            point_name = regDef.get('Volttron Point Name')
            if not point_name:
                point_name = regDef.get("Point Name")
            if not point_name:
                # We require something we can use as a name for the register, so don't try to create a register without
                # the name
                raise ValueError("Registry config entry {} did not have a point name or volttron point name".format(
                    index))
            description = regDef.get('Notes', '')
            units = regDef.get('Units', None)
            default_value = regDef.get("Default Value", "").strip()
            # Truncate empty string or 0 values to None
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            # Make sure the type specified in the configuration is mapped to an actual Python data type
            reg_type = type_mapping.get(type_name, str)
            # Create an instance of the register class based on the configuration values
            register = CsvRegister(
                self.csv_path,
                read_only,
                point_name,
                units,
                reg_type,
                default_value=default_value,
                description=description)
            # Update the register's value if there is a default value provided
            if default_value is not None:
                self.set_default(point_name, register.value)
            # Add the register instance to our list of registers
            self.insert_register(register)
