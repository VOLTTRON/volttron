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

import logging
import requests

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

_log = logging.getLogger(__name__)

HTTP_STATUS_OK = 200


class Register(BaseRegister):
    def __init__(self, read_only, volttron_point_name, units, description, point_name):
        super(Register, self).__init__("byte",
                                       read_only,
                                       volttron_point_name,
                                       units,
                                       description=description)
        self.path = point_name


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)

    def configure(self, config_dict, registry_config_str):
        self.device_address = config_dict['device_address']
        self.parse_config(registry_config_str)

    def get_point(self, point_name, **kwargs):
        register = self.get_register_by_name(point_name)
        point_address = '/'.join([self.device_address, register.path])

        r = requests.get(point_address)
        if r.status_code != HTTP_STATUS_OK:
            _log.error('could not get point, device returned code {}'.format(r.status_code))

        return r.text

    def _set_point(self, point_name, value, **kwargs):
        register = self.get_register_by_name(point_name)
        point_address = '/'.join([self.device_address, register.path])

        if register.read_only:
            raise IOError("Trying to write to a point configured read only: " + point_name)

        r = requests.post(point_address, value)
        if r.status_code != HTTP_STATUS_OK:
            _log.error('could not set point, device returned code {}'.format(r.status_code))

        return r.text

    def _scrape_all(self):
        results = {}
        for point in self.point_map.keys():
            results[point] = self.get_point(point)
        return results

    def parse_config(self, configDict):
        if configDict is None:
            return

        for regDef in configDict:
            if not regDef['Point Name']:
                continue

            read_only = regDef['Writable'].lower() != 'true'
            volttron_point_name = regDef['Volttron Point Name']
            units = regDef['Units']
            description = regDef.get('Notes', '')
            point_name = regDef['Point Name']
            default = regDef.get('Default')
            if not read_only and default is not None:
                self.set_default(point_name, default)

            register = Register(
                read_only,
                volttron_point_name,
                units,
                description,
                point_name)

            self.insert_register(register)
