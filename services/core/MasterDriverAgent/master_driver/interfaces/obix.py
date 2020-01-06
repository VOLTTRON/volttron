# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

__docformat__ = 'reStructuredText'

import logging
import grequests
from xml.dom.minidom import parseString

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

#Logging is completely configured by now.
_log = logging.getLogger(__name__)

TOPIC_DELIM ='/'

class Register(BaseRegister):
    obix_types = {'int': int,
                  'bool': lambda x: x.lower() == "true",
                  'real': float}

    def __init__(self, url, point_name, obix_point_name, obix_type_str, read_only, units, description=''):
        super(Register, self).__init__("byte",
                                       read_only,
                                       point_name,
                                       units,
                                       description=description)

        interface_point_name = obix_point_name.replace(" ", "$20").replace("-", "$2d")
        if not url.endswith("/"):
            url += "/"

        if not interface_point_name.endswith("/"):
            interface_point_name += "/"

        self.url = url + interface_point_name

        self.obix_type_str = obix_type_str
        self.obix_type = Register.obix_types[obix_type_str]

    def get_value_async_result(self, username=None, password=None):
        return grequests.get(self.url, auth=(username, password))

    def parse_result(self, xml_tree):
        document = parseString(xml_tree)
        root = document.documentElement
        value = self.obix_type(root.getAttribute("val"))
        return value

    def set_value_async_result(self, value, username=None, password=None):
        data = '<{type} val="{value}" />'.format(type=self.obix_type_str, value=str(value).lower())
        return grequests.post(self.url, data=data, auth=(username, password))


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.username = None
        self.password = None

    def configure(self, config_dict, registry_config):
        self.username = config_dict.get("username")
        self.password = config_dict.get("password")
        self.parse_config(registry_config, config_dict.get("url", ""))

    def _process_request(self, async_request, register):
        async_result = grequests.map([async_request])
        async_result = async_result[0]
        async_result.raise_for_status()
        result = register.parse_result(async_result.text)
        return result

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        async_request = register.get_value_async_result(username=self.username,
                                                        password=self.password)
        return self._process_request(async_request, register)

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)

        async_request = register.set_value_async_result(value,
                                                        username=self.username,
                                                        password=self.password)
        return self._process_request(async_request, register)

    def _scrape_all(self):
        results = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        async_requests = []

        all_registers = read_registers + write_registers

        for register in all_registers:
            async_requests.append(register.get_value_async_result(username=self.username,
                                                                 password=self.password))

        async_results = grequests.map(async_requests)

        for register, result in zip(all_registers, async_results):
            try:
                result.raise_for_status()
                results[register.point_name] = register.parse_result(result.text)
            except Exception as e:
                _log.error("Error reading point: {}".format(repr(e)))

        return results


    def parse_config(self, configDict, url):
        if configDict is None:
            return


        for regDef in configDict:

            obix_type = regDef.get('Obix Type', 'bool')
            read_only = regDef.get('Writable').lower() != 'true'


            obix_point_name = regDef['Obix Point Name']

            point_name = regDef.get('Volttron Point Name', obix_point_name)

            description = regDef.get('Notes', '')

            units = regDef.get('Units')

            register = Register(url, point_name,
                                obix_point_name,
                                obix_type, read_only,
                                units, description)

            self.insert_register(register)


