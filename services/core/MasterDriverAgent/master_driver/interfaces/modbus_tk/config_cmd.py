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

from __future__ import print_function
from master_driver.interfaces.modbus_tk.helpers import str2bool

import cmd
import yaml
import os
import json
import subprocess32


class VolttronException(Exception):
    pass


class ConfigCmd (cmd.Cmd):
    """
        Modbus TK command tool to generate drivers configs including map.yaml, <driver_name>.config, <reg_csv_file>.csv

    :param self._directories: dictionary of directories including keys map_dir, config_dir, csv_dir
    :param self._device_type_maps: list of all device types in maps.yaml
    """

    def __init__(self):
        cmd.Cmd.__init__(self)

        self._directories = dict(
            map_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "maps")),
            config_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "maps")),
            csv_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "maps"))
        )

        self._device_type_maps = self.set_device_type_maps()

    def set_device_type_maps(self):
        """
            If maps.yaml exists, set device_type_maps to the list of all device types in maps.yaml
        """
        device_type_maps = list()
        file_name = self.get_existed_file(self._directories['map_dir'], "maps.yaml")
        yaml_file = "{0}/{1}".format(self._directories['map_dir'], file_name)
        if file_name and os.stat(yaml_file).st_size:
            with open("{0}/maps.yaml".format(self._directories['map_dir'])) as yaml_file:
                device_type_maps = yaml.load(yaml_file)
        return device_type_maps

    def _sh(self, shell_command):
        """
            Run shell command
        """
        try:
            return_value = subprocess32.check_output(shell_command, shell=True, stderr=subprocess32.PIPE, timeout=5)
        except subprocess32.TimeoutExpired:
            return_value = "Timeout Error: Volttron is not running"
        except subprocess32.CalledProcessError:
            return_value = "File does not exist in Volttron"
        return return_value

    def list_volttron_config(self, successful_message):
        """
            List of all driver config and csv files in Volttron platform.driver

        :param successful_message: the message print out when successful
        """
        sh = self._sh('volttron-ctl config list platform.driver')
        if not sh.startswith('Timeout Error'):
            print("\n" + successful_message)
            print("List of all driver config and csv in VOLTTRON platform.driver:")
        print(sh)

    def get_device_type_descriptions(self):
        """
            Print all device types and their descriptions
        """
        print("\n" + "DEVICE TYPE".ljust(25) + "| DESCRIPTION")
        for d in self._device_type_maps:
            print("{name:24} | {description}".format(**d))

    def write_to_map_yaml(self):
        """
            Write all information from self._device_type_maps to maps.yaml
        """
        dir = self.get_existed_directory(self._directories['map_dir'], 'map_dir')
        if dir:
            with open("{0}/maps.yaml".format(self._directories['map_dir']), 'w') as yaml_file:
                yaml.dump(self._device_type_maps, yaml_file, default_flow_style=False)

    def get_existed_directory(self, dir, dir_type):
        """
            Check if the directory exists, if not, option to change the directory.
            Return None if the directory does not exist, or the correct existed directory otherwise.
            Update self._device_type_maps if map_dir is changed.

        :param dir: directory
        :param dir_type: directory type (for examples: csv_dir, config_dir, map_dir)
        """
        while True:
            if not os.path.isdir(dir):
                print("The directory {0} '{1}' does not exist".format(dir_type,
                                                                      dir))
                print("Change to another directory [y/n]: ", end='')
                option = raw_input().lower()
                if option and str2bool(option):
                    print("Enter the new {0} directory: ".format(dir_type), end='')
                    dir = raw_input()
                else:
                    return None
            else:
                if dir != self._directories[dir_type]:
                    self._directories[dir_type] = dir
                    if dir_type == 'map_dir':
                        self._device_type_maps = self.set_device_type_maps()
                return dir

    def get_existed_file(self, file_dir, file_name):
        """
            Check if the file exists, if not, option to change the directory or change the file.
            Return None if the file does not exist, or the correct existed file otherwise.

        :param file_dir: the directory of the file
        :param file_name: name of the file (for examples: watts_on.csv, watts_on.config, maps.yaml)
        """
        try:
            file_type = file_name.split('.')[1]
            file_dir = self.get_existed_directory(file_dir,
                                                  "{0}_dir".format('map' if file_type == 'yaml' else file_type))
            if file_dir:
                while True:
                    if not os.path.exists("{0}/{1}".format(file_dir, file_name)):
                        print ("'{0}' file '{1}' does not exist in the directory '{2}'".format(file_type,
                                                                                               file_name,
                                                                                               file_dir))
                        if file_name == 'maps.yaml':
                            print("\nPlease select an option: \n"
                                  "1: Change map_dir: '{0}' to another directory \n"
                                  "2: Add maps.yaml to the directory {0}".format(file_dir))
                            option = raw_input()
                            if option not in ("1", "2"):
                                print("Undefined option")
                                self.do_quit('')
                            else:
                                if option == '1':
                                    self.do_edit_directories("map_dir")
                                    self.get_existed_file(self._directories['map_dir'], file_name)
                                else:
                                    open("{0}/{1}".format(file_dir, file_name), 'w')
                                    print("Added maps.yaml to the directory '{0}'".format(file_dir))
                        else:
                            print("\nPlease select an option: \n"
                                  "1: Choose another {0} file \n"
                                  "2: Change {0}_dir: '{1}' to another directory \n"
                                  "3: Add {2} to the directory {1}".format(file_type,
                                                                           file_dir,
                                                                           file_name))
                            option = raw_input()
                            if option not in ('1', '2', '3'):
                                print("Undefined option")
                                self.do_quit('')
                            else:
                                if option == '1':
                                    print("List of all {0} files in the {0}_dir: {1}".format(
                                        file_type,
                                        ', '.join([f for f in os.listdir(file_dir) if f.endswith(file_type)]))
                                    )
                                    print("Enter another {0} file: ".format(file_type), end='')
                                    file_name = raw_input()
                                    file_name = file_name if file_name.endswith(file_type) else "{0}.{1}".format(
                                        file_name,
                                        file_type)
                                    self.get_existed_file(file_dir, file_name)
                                elif option == '2':
                                    self.do_edit_directories("{0}_dir".format(file_type))
                                    self.get_existed_file(self._directories["{0}_dir".format(file_type)], file_name)
                                else:
                                    if file_type == 'config':
                                        self.do_add_driver_config('')
                                    else:
                                        print("Please add the file {0} to the directory {1}".format(file_name,
                                                                                                    file_dir))
                                        self.do_quit('')
                    return file_name
            else:
                return None
        except IndexError:
            print("Please include the file type for the file, for example: watts_on.csv.")
            print("Enter a new file: ", end='')
            return self.get_existed_file(file_dir, raw_input())

    ##########################
    #  Directories Commands  #
    ##########################

    def do_list_directories(self, line):
        """
            List all set-up directories.
            Option to edit directories.
        """

        dir_type_map = {
            'map_dir': 'Map Directory',
            'csv_dir': 'CSV Config Directory',
            'config_dir': 'Diver Config Directory'
        }

        print("\n" + "DIRECTORY TYPE".ljust(23) + "| DIRECTORY PATH")
        for dir_key in self._directories.keys():
            print("{0:22} | {1}".format(dir_type_map[dir_key], self._directories[dir_key]))

        print("\nDo you want to edit directories [y/n]? Press <Enter> to exit: ", end='')
        option = raw_input().lower()
        if option and str2bool(option):
            self.do_edit_directories('')

    def do_edit_directories(self, line):
        """
            Add/Edit map directory, driver config directory, and csv config directory
            Press <Enter> if no change needed
            Option to change the directory the edited directory does not exist

                Edit a specific directory: edit_directories <directory_type>
                                           <directory_type>: map_dir, csv_dir, config_dir
                Edit all directory:        edit_directory
        """
        if not line:
            for dir_key in self._directories.keys():
                print("Enter the directory path for {0}. Press <Enter> if no change needed: ".format(dir_key), end='')
                dir_path = raw_input()
                dir = self.get_existed_directory(dir_path, dir_key) if dir_path else None
                if not dir or dir == self._directories[dir_key]:
                    print("No change made to '{0}'".format(dir_key))
                else:
                    self._directories[dir_key] = dir
        else:
            if line not in self._directories:
                print("Directory type '{0}' does not exist".format(line))
                print("Please select another directory type from: {0}".format([k for k in self._directories.keys()]))
                print("Enter a directory type. Press <Enter> if edit all: ", end='')
                self.do_edit_directories(raw_input().lower())
            else:
                print("Enter the directory path for {0}. Press <Enter> if no change needed: ".format(line), end='')
                dir_path = raw_input()
                dir = self.get_existed_directory(dir_path, line) if dir_path else None
                if not dir or dir == self._directories[line]:
                    print("No change made to {0}".format(line))
                else:
                    self._directories[line] = dir

        self.do_list_directories('')

    ##########################
    #  Device Types Commands #
    ##########################

    def do_list_device_type_description(self, line):
        """
            List all device types and their descriptions from maps.yaml.
            Option to edit device description.
        """
        self.get_device_type_descriptions()

        print("\nDo you want to edit a device type description [y/n]? Press <Enter> to exit: ", end='')
        option = raw_input().lower()
        existed = False
        if option and str2bool(option):
            while not existed:
                print("Enter a device type: ", end='')
                device_type = raw_input()
                for t in self._device_type_maps:
                    if t['name'] == device_type:
                        existed = True
                        print("Enter the description for {0}: ".format(device_type), end='')
                        t['description'] = raw_input()
                        self.write_to_map_yaml()
                        self.do_list_device_type_description('')
                if not existed:
                    print("Device type {0} does not exit. Do you want to choose another device type [y/n]. "
                          "Press <Enter> to exit: ".format(device_type), end='')
                    option = raw_input().lower()
                    if not option or not str2bool(option):
                        existed = True

    def do_list_all_device_types(self, line):
        """
            List all the device types information in maps.yaml
            Option to add more device type to maps.yaml
        """
        map_yml = self.get_existed_file(self._directories['map_dir'], 'maps.yaml')
        if map_yml:
            for device_type in self._device_type_maps:
                print("\nDEVICE TYPE: {0}".format(device_type['name'].upper()))
                for k in device_type.keys():
                    if k is not 'name':
                        print("{0:25} | {1}".format(k, device_type[k]))

            print('\nDo you want to add or edit a device type [add/edit]? Press <Enter> to exit: ', end='')
            option = raw_input().lower()
            if option == 'add':
                self.do_add_device_type('')
            elif option == 'edit':
                self.do_edit_device_type('')

    def do_device_type(self, line):
        """
            List information of a selected device type from maps.yaml
            Option to select another device type

            Get a specific device type information: device_type <name>
                                                    <name>: name of a device type in maps.yaml
            List all device before selecting name:  device_type
        """

        existed = False
        name = line

        if not name:
            self.get_device_type_descriptions()
            print("\nEnter a device type: ", end='')
            name = raw_input()

        for device_type in self._device_type_maps:
            if device_type.get('name', None) == name:
                existed = True
                print("\nDEVICE TYPE: {0}".format(device_type['name'].upper()))
                for k in device_type.keys():
                    if k is not 'name':
                        print("{0:25} | {1}".format(k, device_type[k]))

        if not existed:
            print("Device type '{0}' does not exist".format(name))

        print("\nDo you want to select another device type [y/n]? Press <Enter> to exit: ", end='')
        option = raw_input().lower()
        if option and str2bool(option):
            self.do_device_type('')

    def do_add_device_type(self, line):
        """
            Add a new device type to maps.yaml

            Each entry look like:
                    addressing: offset
                    endian: big
                    write_multiple_registers: False
                    file: elkor_wattson.csv
                    name: elkor wattson
                    description: reading some selected registers from elkor wattson meter

            If addressing and endian do not match existed options, they will set to their default values
            Option to add more than one

            Add a specific device type: add_device_type <name>
                                        <name>: name of a device type want to add to maps.yaml
            Select name after the cmd:  add_device_type
        """

        edit = False
        device_type_name = line

        if not device_type_name:
            print('\nEnter device type: ', end='')
            device_type_name = raw_input().lower()

        yaml_file = self.get_existed_file(self._directories['map_dir'], 'maps.yaml')
        if yaml_file:
            for device_type in self._device_type_maps:
                if device_type.get('name', None) == device_type_name:
                    print("Device type {0} already existed. Edit it [y/n]: ".format(device_type_name), end='')
                    option = raw_input().lower()
                    if option and str2bool(option):
                        edit = True
                        self.do_edit_device_type(device_type_name)
                    else:
                        print("Please choose another name: ", end='')
                        self.do_add_device_type(raw_input().lower())

        if not edit:
            print('Endian (default to big): ', end='')
            endian = raw_input().lower()
            if endian not in ('big', 'little', 'mixed'):
                endian = 'big'

            print('Addressing (default to offset): ', end='')
            addressing = raw_input().lower()
            if addressing not in ('offset', 'offset_plus', 'address'):
                addressing = 'offset'

            print('Write multiple registers (default to True) [T/F]: ', end='')
            write_multiple_registers = False if raw_input().lower() in ("f", "false") else True

            print('CSV file: ', end='')
            csv_file = raw_input()
            csv_file = csv_file if csv_file.endswith('.csv') else "{0}.csv".format(csv_file)
            csv_file = self.get_existed_file(self._directories['csv_dir'], csv_file)

            print('Description: ', end='')
            description = raw_input()

            # Add the new driver to self._device_type_maps
            self._device_type_maps.append(dict(
                name=device_type_name,
                endian=endian,
                addressing=addressing,
                write_multiple_registers=write_multiple_registers,
                file=csv_file,
                description=description
            ))

        # Option to add more
        print('\nDo you want to add more device type [y/n]? Press <Enter> to exit: ', end='')
        option = raw_input().lower()
        if option and str2bool(option):
            self.do_add_device_type('')
        else:
            # Add the new device type to maps.yaml when done adding
            self.write_to_map_yaml()

    def do_edit_device_type(self, line):
        """
            Edit an existed device type in maps.yaml
            Press <Enter> if no change needed
            If addressing and endian do not match existed options, they will remain as existed setting values

            Edit a specific device type:           edit_device_type <name>
                                                   <name>: name of a device type in maps.yaml
            List all device before selecting name: edit_device_type
        """
        device_type_name = line
        if not device_type_name:
            # Print all device types in maps.yaml
            self.get_device_type_descriptions()
            print('\nEnter a device type name you want to edit. Press <Enter> to exit: ', end='')
            device_type_name = raw_input().lower()

        existed = False
        edited = False

        # Edit the map if the driver name found
        if device_type_name:
            for device_type in self._device_type_maps:
                if device_type.get('name', None) == device_type_name:
                    existed = True

                    print('Change driver type name: ', end='')
                    new_name = raw_input().lower()
                    if new_name and new_name != device_type['name']:
                        device_type['name'] = new_name
                        edited = True

                    print('Change endian: ', end='')
                    new_endian = raw_input().lower()
                    if new_endian in ('big', 'little', 'mixed') and new_endian != device_type['endian']:
                        device_type['endian'] = new_endian
                        edited = True

                    print('Change addressing: ', end='')
                    new_addressing = raw_input().lower()
                    if new_addressing in ('offset', 'offset_plus', 'address') \
                            and new_addressing != device_type['addressing']:
                        device_type['addressing'] = new_addressing
                        edited = True

                    print('Change write multiple registers option [T/F]: ', end='')
                    new_write_multiple_registers = False if raw_input().lower() in ("f", "false") else True
                    if new_write_multiple_registers != device_type.get('write_multiple_registers', "True"):
                        device_type['write_multiple_registers'] = new_write_multiple_registers
                        edited = True

                    print('Change CSV file: ', end='')
                    new_file = raw_input().lower()
                    if new_file:
                        new_file = self.get_existed_file(self._directories['csv_dir'], new_file)
                    if new_file and new_file != device_type['file']:
                        device_type['file'] = new_file
                        edited = True

                    print('Change Description: ', end='')
                    new_description = raw_input()
                    if new_description and new_description != device_type['description']:
                        device_type['description'] = new_description
                        edited = True

            # Write to maps.yaml if any information changed
            if edited:
                self.write_to_map_yaml()
            if not existed:
                print("Device type name '{0}' does not exist".format(device_type_name))

            print("Do you want to edit another device [y/n]? Press <Enter> to exit: ", end='')
            option = raw_input().lower()
            if option and str2bool(option):
                self.do_edit_device_type('')

    ##########################
    # Driver Config Commands #
    ##########################

    def do_list_drivers(self, line):
        """
            List all driver in config_dir directory
        """
        dir = self.get_existed_directory(self._directories['config_dir'], 'config_dir')
        if dir:
            for d in os.listdir(dir):
                if d.endswith('.config'):
                    print(d.split('.')[0])

    def do_driver_config(self, line):
        """
            Get the driver config for the selected driver
            Option to select the driver if no selected driver found

            Get a specific driver config:            do_driver_config <name>
                                                     <name>: name of a driver config in config_dir
            List all driver before selecting a name: do_driver_config
        """
        driver_name = line
        if not driver_name:
            self.do_list_drivers('')
            print("\nEnter the driver name: ", end='')
            driver_name = raw_input()

        existed = False
        config_dir = self.get_existed_directory(self._directories['config_dir'], 'config_dir')
        if config_dir:
            for f in os.listdir(config_dir):
                if f.endswith('.config') and f.split('.')[0] == driver_name:
                    existed = True
                    with open("{0}/{1}.config".format(config_dir, driver_name), 'r') as config_file:
                        config_dict = json.load(config_file)
                        print("\nDRIVER: {0}".format(driver_name.upper()))
                        for k in config_dict.keys():
                            if k != 'driver_config':
                                print("{0:17}: {1}".format(k, config_dict[k]))
                            else:
                                driver_config = config_dict['driver_config']
                                print("{0:17}:".format(k))
                                for key in driver_config.keys():
                                    print("{0:17}  {1:17}: {2}".format('', key, driver_config[key]))
            if not existed:
                print("The driver '{0}' does not exist.".format(driver_name))

        else:
            print("Directory config_dir '{0}' does not exist.".format(self._directories['config_dir']))

    def do_add_driver_config(self, line):
        """
            Add/Edit the driver config <config_dir>/<driver name>.config for selected driver
                Example format:
                    {
                        "driver_config": {"name": "watts_on_1",
                                          "device_type": "watts_on",
                                          "device_address": "/dev/tty.usbserial-AL00IEEY",
                                          "port": 0,
                                          "slave_id": 2,
                                          "baudrate": 115200,
                                          "bytesize": 8,
                                          "parity": "none",
                                          "stopbits": 1,
                                          "xonxoff": 0,
                                          "addressing": "offset",
                                          "endian": "big",
                                          "write_multiple_registers": True,
                                          "register_map": "config://watts_on_map.csv"},
                        "driver_type": "modbus_tk",
                        "registry_config": "config://watts_on.csv",
                        "interval": 120,
                        "timezone": "UTC"
                    }
                If any config info does not match existed options, it'll set to its default value

            Option to select driver if no selected driver found
            Press <Enter> to exit

            Add a specific driver config: add_driver_config <name>
                                          <name>: name of a new driver config to add to config_dir
            Select name after the cmd:    add_driver_config
        """
        # Select device type
        device_type = dict()
        device_type_name = line
        if not device_type_name:
            self.get_device_type_descriptions()
            print('\nEnter device type name: ', end='')
            device_type_name = raw_input().lower()
        for device in self._device_type_maps:
            if device.get('name', None) == device_type_name:
                device_type = device

        # If device type exist, add driver config
        if device_type:
            print("Enter driver name: ", end='')
            name = raw_input().lower()
            config_dir = self.get_existed_directory(self._directories['config_dir'], 'config_dir')
            if config_dir:
                cont = True
                while cont:
                    cont = False
                    for f in os.listdir(config_dir):
                        if f.endswith('.config') and f.split('.')[0] == name:
                            self.do_driver_config(name)
                            print("Driver '{0}' already existed. Continue to edit the driver [y/n]: ".format(name),
                                  end='')
                            option = raw_input().lower()
                            if not option or not str2bool(option):
                                print("Please choose a different driver name OR press <Enter> to quit: ", end='')
                                name = raw_input().lower()
                                if not name:
                                    self.do_quit('')
                                cont = True

            print('Enter interval (default to 60 seconds): ', end='')
            try:
                interval = int(raw_input())
            except ValueError:
                interval = 60

            print('Enter device address: ', end='')
            device_address = raw_input().lower()

            print('Enter port (default to 5020 - 0 for no port): ', end='')
            try:
                port = int(raw_input())
            except ValueError:
                port = 5020

            print('Enter description: ', end='')
            description = raw_input()

            addressing = device_type.get('addressing', 'offset')

            endian = device_type.get('endian', 'big')
            print("Default endian for the selected device type '{0}' is '{1}'. Do you want to change it [y/n]: ".format(
                device_type_name, endian), end='')
            option = raw_input().lower()
            if option and str2bool(option):
                print('Enter new endian. Press <Enter> if no change needed: ', end='')
                new_endian = raw_input().lower()
                if new_endian in ('big', 'little', 'mixed'):
                    endian = new_endian

            write_multiple_registers = str2bool(str(device_type.get('write_multiple_registers', 'True')))

            csv_map = self.get_existed_file(self._directories['csv_dir'], device_type.get('file'))

            print('Enter CSV config file: ', end='')
            csv_config = raw_input()
            csv_config = csv_config if csv_config.endswith('.csv') else "{0}.csv".format(csv_config)
            csv_config = self.get_existed_file(self._directories['csv_dir'], csv_config)

            driver_config = {
                "driver_config": {"name": name,
                                  "device_type": device_type_name,
                                  "device_address": device_address,
                                  "port": port,
                                  "addressing": addressing,
                                  "endian": endian,
                                  "write_multiple_registers": write_multiple_registers,
                                  "register_map": "config://" + csv_map,
                                  "description": description},
                "driver_type": "modbus_tk",
                "registry_config": "config://" + csv_config,
                "interval": interval,
                "timezone": "UTC"
            }

            # RTU transport
            if not port:
                print('Enter slave id (default to 1): ', end='')
                try:
                    slave_id = int(raw_input())
                except ValueError:
                    slave_id = 1

                print('Enter baudrate (default to 9600): ', end='')
                try:
                    baudrate = int(raw_input())
                except ValueError:
                    baudrate = 9600

                print('Enter bytesize (default to 8): ', end='')
                try:
                    bytesize = int(raw_input())
                except ValueError:
                    bytesize = 8

                print('Enter bytesize (default to none): ', end='')
                parity = raw_input()
                if parity not in ('none', 'even', 'odd', 'mark', 'space'):
                    parity = 'none'

                print('Enter stopbits (default to 1): ', end='')
                try:
                    stopbits = int(raw_input())
                except ValueError:
                    stopbits = 1

                print('Enter xonxoff (default to 0): ', end='')
                try:
                    xonxoff = int(raw_input())
                except ValueError:
                    xonxoff = 0

                driver_config['driver_config'].update({
                    "slave_id": slave_id,
                    "baudrate": baudrate,
                    "bytesize": bytesize,
                    "parity": parity,
                    "stopbits": stopbits,
                    "xonxoff": xonxoff
                })

            with open("{0}/{1}.config".format(self._directories['config_dir'], name), 'w') as config_file:
                json.dump(driver_config, config_file, indent=2)

        else:
            print("Device type '{0}' does not exist".format(device_type_name))

    ##########################
    #    VOLTTRON Commands   #
    ##########################

    def do_load_volttron(self, line):
        """
            Load existed driver config and csv to volttron (Make sure volttron is running).
            Option to add file if the file does not exist.
        """
        driver_name = line
        if not driver_name:
            print("\nList of all existed drivers in the selected config directory: ")
            self.do_list_drivers('')
            print("\nEnter driver name: ", end='')
            driver_name = raw_input().lower()

        # Load driver config
        config_file = self.get_existed_file(self._directories['config_dir'], "{0}.config".format(driver_name))
        driver_name = config_file.split('.')[0]
        config_dir = self._directories['config_dir']
        config_path = "{0}/{1}".format(config_dir, config_file)

        if config_file:
            self._sh('volttron-ctl config store platform.driver devices/{0} {1}'.format(driver_name, config_path))
        else:
            self.do_load_volttron(driver_name)

        with open(config_path, 'r') as config_file:
            driver_config = json.load(config_file)

        csv_config = driver_config['registry_config'].split('//')[1]
        csv_map = driver_config['driver_config']['register_map'].split('//')[1]
        csv_dir = self._directories['csv_dir']

        # Load registry_config
        csv_config = self.get_existed_file(self._directories['csv_dir'], csv_config)
        if csv_config:
            self._sh('volttron-ctl config store platform.driver {1} {0}/{1} --csv'.format(csv_dir, csv_config))
        else:
            print('Please add csv file {1} to the directory {0}/{1} and redo load_volttron'.format(csv_dir, csv_config))

        # Load register_map
        csv_map = self.get_existed_file(self._directories['csv_dir'], csv_map)
        if csv_map:
            self._sh('volttron-ctl config store platform.driver {1} {0}/{1} --csv'.format(csv_dir, csv_map))
            self.list_volttron_config("Load successful!")
        else:
            print('Please add csv file {1} to the directory {0}/{1} and redo load_volttron'.format(csv_dir, csv_map))

    def do_delete_volttron_config(self, line):
        """
            Delete a driver config from volttron (Make sure volttron is running).
        """
        driver_name = line

        drivers = dict()
        for f in self._sh('volttron-ctl config list platform.driver').split('\n'):
            if f.startswith('devices'):
                drivers[f.split('/')[-1]] = f

        if not driver_name:
            print('\nList of all drivers in VOLTTRON platform.driver:')
            print("DRIVER NAME".ljust(16) + "| VOLTTRON PATH")
            for d in drivers.keys():
                print("{0:15} | {1}".format(d, drivers[d]))
            print ("\nEnter driver name to delete: ", end='')
            driver_name = raw_input()

        if driver_name not in drivers:
            print("\nDriver name '{0}' does not exist".format(driver_name))
            print("Do you want to select another driver to delete [y/n]? Press <Enter> to exit: ", end='')
            option = raw_input().lower()
            if option and str2bool(option):
                self.do_delete_volttron_config('')
        else:
            self._sh('volttron-ctl config delete platform.driver {0}'.format(drivers[driver_name]))
            self.list_volttron_config("Delete successful!")

    def do_delete_volttron_csv(self, line):
        """
            Delete a registry csv config from volttron (Make sure volttron is running).
        """
        csv_name = line

        csv_files = list()
        for f in self._sh('volttron-ctl config list platform.driver').split('\n'):
            if f.endswith('csv'):
                csv_files.append(f)

        if not csv_name:
            print("\nList of all registry csv files in VOLTTRON platform.driver:")
            for csv in csv_files:
                print(csv)
            print("\nEnter driver name to delete: ", end='')
            csv_name = raw_input()
            csv_name = "{0}.csv".format(csv_name) if not csv_name.endswith('.csv') else csv_name

        if csv_name not in csv_files:
            print("\nRegistry CSV config '{0}' does not exist".format(csv_name))
            print("Do you want to select another registry csv config to delete [y/n]? Press <Enter> to exit: ", end='')
            option = raw_input().lower()
            if option and str2bool(option):
                self.do_delete_volttron_csv('')
        else:
            self._sh('volttron-ctl config delete platform.driver {0}'.format(csv_name))
            self.list_volttron_config("Delete successful!")

    ##########################
    # Quit Cmd Tool Command  #
    ##########################

    def do_quit(self, line):
        """
            Quit the Modbus TK config cmd
        """
        exit()

if __name__ == '__main__':
    commander = ConfigCmd()
    commander.intro = "Welcome to Modbus TK Command. \n\n" \
                       "Here is the list of directories: \n" \
                       "\t map_dir:    {map_dir} \n\t config_dir: {config_dir} \n\t csv_dir:    {csv_dir} \n\n" \
                       "Start with <edit_directories> cmd to edit directories. \n" \
                       "Type <help> or <?> to list all commands.".format(**commander._directories)
    commander.prompt = "\nModbusTK > "
    commander.cmdloop()
    exit()