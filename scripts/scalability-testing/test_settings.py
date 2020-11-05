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

#Change this to the IP of the machine that will host the virtual devices.
virtual_device_host = 'localhost'

#Device type to count and config map.
#Valid device type choices are "bacnet" and "modbus"
device_types = {'bacnet': (1, 'device-configs/bacnet_lab.csv'),
                'modbus': (1, 'device-configs/catalyst371.csv')}

#Output directory for configurations for the master driver agent 
# and individual drivers on the local host.
#Directory will be created if it does not exist.
config_dir = "configs"

#Volttron installation directory on virtua_device_host.
volttron_install = "~/volttron"

#Master driver config file name
master_driver_file = "master-driver.agent"

#Location of virtual device config files on virtual device host.
#Directory will be created if it does not exist and will
# have all config files removed prior to push out new configs.
host_config_location = "~/scalability-confgurations"

