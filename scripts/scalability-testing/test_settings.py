# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

#Change this to the IP of the machine that will host the virtual devices.
virtual_device_host = 'localhost'

#Device type to count and config map.
#Valid device type choices are "bacnet" and "modbus"
device_types = {'bacnet': (1, 'device-configs/bacnet_lab.csv'),
                'modbus': (1, 'device-configs/catalyst371.csv')}

#Output directory for configurations for the platform driver agent
# and individual drivers on the local host.
#Directory will be created if it does not exist.
config_dir = "configs"

#Volttron installation directory on virtua_device_host.
volttron_install = "~/volttron"

#platform driver config file name
platform_driver_file = "platform-driver.agent"

#Location of virtual device config files on virtual device host.
#Directory will be created if it does not exist and will
# have all config files removed prior to push out new configs.
host_config_location = "~/scalability-confgurations"
