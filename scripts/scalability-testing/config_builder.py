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

class DeviceConfig(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, host_address, instance_number, registry_config, interval=60):
        self.configuration = {"registry_config": registry_config,
                              "interval": interval,
                              "driver_type": self.device_type(),
                              "unit": self.device_type() + str(instance_number)}
        
        self.configuration["driver_config"] = self.get_driver_config(host_address, instance_number)
        
    def __str__(self):
        return json.dumps(self.configuration,
                          indent=4, separators=(',', ': '))
    
    @abc.abstractmethod
    def device_type(self):
        pass

    @abc.abstractmethod
    @staticmethod
    def get_driver_config(host_address, instance_number):
        pass
    
    @abc.abstractmethod
    @staticmethod
    def get_virtual_driver_commandline(host_address, instance_number, config):
        pass

class BACnetConfig(DeviceConfig):
    starting_port = 47808
    def __init__(self, host_address, instance_number, registry_config, interval=60):
        super(BACnetConfig, self).__init__(host_address, instance_number, registry_config, interval=interval)
        
    @abc.abstractmethod
    def device_type(self):
        "bacnet"
        
    @staticmethod
    def get_driver_config(host_address, instance_number):
        return {"device_address": host_address + ":" + str(BACnetConfig.starting_port + instance_number)}
    
    @staticmethod
    def get_virtual_driver_commandline(host_address, instance_number, config):
        pass

class ModbusConfig(DeviceConfig):
    starting_port = 5020
    def __init__(self, host_address, instance_number, registry_config, interval=60):
        super(BACnetConfig, self).__init__(instance_number, registry_config, interval=interval)
        
    @abc.abstractmethod
    def device_type(self):
        "modbus"
        
    @staticmethod
    def get_driver_config(host_address, instance_number):
        return {"device_address": host_address,
                "port": ModbusConfig.starting_port + instance_number}
    
    @staticmethod
    def get_virtual_driver_commandline(host_address, instance_number):
        pass

device_config_classes = {"bacnet":BACnetConfig,
                         "modbus":ModbusConfig}

def build_device_configs(device_type, host_address, count, reg_config, config_dir):    
    config_paths = []
    
    klass = device_config_classes[device_type]
    for i in range(count):
        config_instance = klass(host_address, i, reg_config)
        
        file_name = device_type + str(i)
        file_path = os.path.join(config_dir, file_name)
        
        with(file_path, 'w') as f:
            f.write(config_instance)
            
        config_paths.append(file_path)
        
    return config_paths

def build_all_configs(agent_config, device_type, host_address, count, reg_config, config_dir):
    try:
        os.makedirs(config_dir)
    except os.error:
        pass
    
    config_dir = os.path.abspath(config_dir)
    
    config_list = build_device_configs(device_type, host_address, count, reg_config, config_dir)
    
    configuration = {"driver_config_list": config_list}
    
    config_str = json.dumps(self.configuration, indent=4, separators=(',', ': '))
    
    with(agent_config, 'w') as f:
        f.write(config_str)
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create driver configuration files for scalability test.")
    parser.add_argument('--agent-config', metavar='CONFIG_NAME', help='name of the master driver config file',
                        default='master-driver.agent')
    
    parser.add_argument('--count', type=int, default=1, help='number of devices to configure')
    
    parser.add_argument('device-type', choices=['bacnet', 'modbus'], 
                        help='type of device to use for testing')
    
    parser.add_argument('host-address', help='host of the test devices')
    
    parser.add_argument('registry-config', help='registry configuration to use for test devices')
    
    parser.add_argument('config-dir', help='output directory for configurations')
    
    
    
