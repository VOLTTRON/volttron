#!python

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import json
import os
import abc
import argparse
import itertools
from test_settings import (virtual_device_host, device_types, config_dir, 
                           volttron_install, master_driver_file,
                           host_config_location)

class DeviceConfig(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, host_address, instance_number, registry_config, interval=60, publish_only_depth_all=False, campus='fakecampus', building='fakebuilding'):
        self.configuration = {"registry_config": registry_config,
                              "driver_type": self.device_type(),
                              "campus": campus,
                              "building": building,
                              "unit": self.device_type() + str(instance_number),
                              "timezone": 'US/Pacific',
                              "interval": interval,
                              "heart_beat_point": "Heartbeat"}
        
        self.configuration["driver_config"] = self.get_driver_config(host_address, instance_number)
        
        if publish_only_depth_all:
            self.configuration["publish_breadth_first_all"] = False
            self.configuration["publish_depth_first"] = False
            self.configuration["publish_breadth_first"] = False
        
    def __str__(self):
        return json.dumps(self.configuration,
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

def build_device_configs(device_type, host_address, count, reg_config, config_dir, interval, publish_only_depth_all, campus ,building ):    
    config_paths = []
    #command line to start virtual devices.
    command_lines = []
    
    try:
        os.makedirs(config_dir)
    except os.error:
        pass
    
    klass = device_config_classes[device_type]
    for i in range(count):
        config_instance = klass(host_address, i, reg_config, 
                                interval=interval,
                                publish_only_depth_all=publish_only_depth_all,
                                campus = campus,
                                building = building)
        
        file_name = device_type + str(i) + ".config"
        file_path = os.path.join(config_dir, file_name)
        
        with open(file_path, 'w') as f:
            f.write(str(config_instance)+'\n')
            
        config_paths.append(file_path)
        command_lines.append(config_instance.get_virtual_driver_commandline())
        
    return config_paths, command_lines

def build_all_configs(agent_config, device_type, host_address, count, reg_config, config_dir, 
                      scalability_test, scalability_test_iterations, stagger_driver_startup,
                      publish_only_depth_all, interval, campus, building):
    '''For command line interface'''
    print(config_dir)
    
    try:
        os.makedirs(config_dir)
    except os.error:
        pass
    
    config_dir = os.path.abspath(config_dir)
    reg_config = os.path.abspath(reg_config)
    
    config_list, command_lines = build_device_configs(device_type, host_address, count, reg_config, config_dir, interval, publish_only_depth_all, campus, building)
    
    build_master_config(agent_config, config_dir, config_list, 
                        scalability_test, scalability_test_iterations,
                        stagger_driver_startup)
        
    
def build_master_config(agent_config, config_dir, config_list, 
                        scalability_test, scalability_test_iterations,
                        stagger_driver_startup):
    """Takes the input from multiple called to build_device_configs and create the master config."""
    configuration = {"driver_config_list": config_list}
    configuration['scalability_test'] = scalability_test
    configuration['scalability_test_iterations'] = scalability_test_iterations
    configuration['staggered_start'] = stagger_driver_startup
        
    config_str = json.dumps(configuration, indent=4, separators=(',', ': '))
    
    agent_config = os.path.join(config_dir, agent_config)
    
    with open(agent_config, 'w') as f:
        f.write(config_str+'\n')
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create driver configuration files for scalability test.")
    parser.add_argument('--agent-config', metavar='CONFIG_NAME', 
                        help='name of the master driver config file',
                        default=master_driver_file)
    
    parser.add_argument('--count', type=int, default=1, 
                        help='number of devices to configure')
    
    parser.add_argument('--scalability-test', action='store_true', 
                        help='Configure master driver for a scalability test')
    
    parser.add_argument('--publish-only-depth-all', action='store_true', 
                        help='Configure drivers to only publish depth first all.')
    
    parser.add_argument('--stagger-driver-startup', type=float, 
                        help='Configure master driver to stagger driver startup over N seconds.')
    
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
    build_all_configs(args.agent_config, args.device_type, 
                      args.virtual_device_host, args.count, args.registry_config, 
                      args.config_dir, args.scalability_test, args.scalability_test_iterations,
                      args.stagger_driver_startup, args.publish_only_depth_all,
                      args.interval, args.campus, args.building)
    
    
    
