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


import os
import os.path
import abc
import argparse
from shutil import copy, rmtree
from test_settings import (virtual_device_host, device_types, config_dir, 
                           volttron_install, master_driver_file,
                           host_config_location)
from volttron.platform import jsonapi

class DeviceConfig(object, metaclass=abc.ABCMeta):
    def __init__(self, host_address, instance_number, registry_config, interval=60, heart_beat_point=None):
        self.configuration = {"registry_config": registry_config,
                              "driver_type": self.device_type(),
                              "timezone": 'US/Pacific',
                              "interval": interval}

        if heart_beat_point is not None:
            self.configuration["heart_beat_point"] = heart_beat_point
        
        self.configuration["driver_config"] = self.get_driver_config(host_address, instance_number)
        

    def __str__(self):
        return jsonapi.dumps(self.configuration,
                          indent=4, separators=(',', ': '))
    
    @abc.abstractmethod
    def device_type(self):
        pass

    @staticmethod
    @abc.abstractmethod
    def get_driver_config(host_address, instance_number):
        pass
    
    @abc.abstractmethod
    def get_virtual_driver_commandline(self):
        pass

class BACnetConfig(DeviceConfig):
    starting_port = 47808
        
    def device_type(self):
        return "bacnet"
        
    @staticmethod
    def get_driver_config(host_address, instance_number):
        return {"device_address": host_address + ":" + str(BACnetConfig.starting_port + instance_number)}
    

    def get_virtual_driver_commandline(self):
        config_file = os.path.basename(self.configuration["registry_config"])
        interface = self.configuration["driver_config"]["device_address"]
        return "bacnet.py {config} {interface}".format(config=config_file, interface=interface)

class ModbusConfig(DeviceConfig):
    starting_port = 50200
        
    def device_type(self):
        return "modbus"
        
    @staticmethod
    def get_driver_config(host_address, instance_number):
        return {"device_address": host_address,
                "port": ModbusConfig.starting_port + instance_number}
    
    def get_virtual_driver_commandline(self):
        config_file = os.path.basename(self.configuration["registry_config"])
        port = self.configuration["driver_config"]["port"]
        host_address = self.configuration["driver_config"]["device_address"]
        return "modbus.py {config} {interface} --port={port}".format(config=config_file, 
                                                                     interface=host_address, 
                                                                     port=port)
        
class FakeConfig(DeviceConfig):        
    def device_type(self):
        return "fakedriver"
        
    @staticmethod
    def get_driver_config(host_address, instance_number):
        return {}    

    def get_virtual_driver_commandline(self):
        return ""

device_config_classes = {"bacnet":BACnetConfig,
                         "modbus":ModbusConfig,
                         "fake":FakeConfig}

def build_device_configs(device_type, host_address, count, reg_config_ref, config_dir, interval, output_path):
    #command line to start virtual devices.
    command_lines = []

    try:
        os.makedirs(output_path)
    except os.error:
        pass
    
    klass = device_config_classes[device_type]
    for i in range(count):
        config_instance = klass(host_address, i, reg_config_ref,
                                interval=interval)
        
        file_name = device_type + str(i)
        file_path = os.path.join(output_path, file_name)
        
        with open(file_path, 'w') as f:
            f.write(str(config_instance)+'\n')

        command_lines.append(config_instance.get_virtual_driver_commandline())
        
    return command_lines

def build_all_configs(device_type, host_address, count, reg_config, config_dir,
                      scalability_test, scalability_test_iterations, driver_scrape_interval,
                      publish_only_depth_all, interval, campus, building):
    '''For command line interface'''
    print(config_dir)
    
    config_dir = os.path.abspath(config_dir)

    registry_config_dir = os.path.join(config_dir, "registry_configs")
    devices_dir = os.path.join(config_dir, 'devices', campus, building)

    if os.path.exists(devices_dir):
        rmtree(devices_dir, ignore_errors=True)

    if os.path.exists(registry_config_dir):
        rmtree(registry_config_dir, ignore_errors=True)

    try:
        os.makedirs(registry_config_dir)
    except os.error:
        pass
    

    copy(reg_config, registry_config_dir)

    reg_config_ref = "config://registry_configs/" + os.path.basename(reg_config)
    
    command_lines = build_device_configs(device_type, host_address, count, reg_config_ref, config_dir, interval, devices_dir)
    
    build_master_config(config_dir,
                        scalability_test, scalability_test_iterations,
                        driver_scrape_interval, publish_only_depth_all)
        
    
def build_master_config(config_dir,
                        scalability_test, scalability_test_iterations,
                        driver_scrape_interval, publish_only_depth_all):
    """Takes the input from multiple called to build_device_configs and create the master config."""
    configuration = {}
    configuration['scalability_test'] = scalability_test
    configuration['scalability_test_iterations'] = scalability_test_iterations
    configuration['driver_scrape_interval'] = driver_scrape_interval

    if publish_only_depth_all:
        configuration["publish_breadth_first_all"] = False
        configuration["publish_depth_first"] = False
        configuration["publish_breadth_first"] = False
        
    config_str = jsonapi.dumps(configuration, indent=4, separators=(',', ': '))
    
    agent_config = os.path.join(config_dir, "config")
    
    with open(agent_config, 'w') as f:
        f.write(config_str+'\n')
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create driver configuration files for scalability test.")
    
    parser.add_argument('--count', type=int, default=1, 
                        help='number of devices to configure')
    
    parser.add_argument('--scalability-test', action='store_true', 
                        help='Configure master driver for a scalability test')
    
    parser.add_argument('--publish-only-depth-all', action='store_true', 
                        help='Configure drivers to only publish depth first all.')
    
    parser.add_argument('--driver-scrape-interval', type=float, default=0.02,
                        help='Configure interval between individual device publishes.')
    
    parser.add_argument('--scalability-test-iterations', type=int, default=5, 
                        help='Scalability test iterations')
    
    parser.add_argument('device_type', choices=['bacnet', 'modbus', 'fake'], 
                        help='type of device to use for testing')
    
    parser.add_argument('registry_config', 
                        help='registry configuration to use for test devices')
    
    parser.add_argument('virtual_device_host', 
                        help='host of the test devices',
                        default=virtual_device_host)
    
    parser.add_argument('--config-dir', help='output directory for configurations',
                        default=config_dir)
    
    parser.add_argument('--interval', help='Scrape interval setting for all drivers',
                        type=float,
                        default=60.0)
    
    parser.add_argument('--campus', 
                        help='campus name used for testing',
                        default='')
    
    parser.add_argument('--building', 
                        help='building name used for testing',
                        default='')
    
    args = parser.parse_args()
    build_all_configs(args.device_type,
                      args.virtual_device_host, args.count, args.registry_config, 
                      args.config_dir, args.scalability_test, args.scalability_test_iterations,
                      args.driver_scrape_interval, args.publish_only_depth_all,
                      args.interval, args.campus, args.building)
    
    
    
