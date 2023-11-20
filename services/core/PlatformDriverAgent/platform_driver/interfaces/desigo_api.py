# Copyright (c) 2023, ACE IoT Solutions LLC.
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

"""
The Desigo API driver is designed to perform point discovery
on a given desigo system and collect data from it.
"""

import http
import json
import logging
import requests
import urllib3

from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from urllib3.exceptions import InsecureRequestWarning

_log = logging.getLogger("desigo_api")

DESIGO_TYPE_MAPPING = {
    "BasicFloat": float,
    "BasicUint": int,
    "BasicInt": int,
}


class Register(BaseRegister):
    """
    Generic class for storing information about Desigo API points
    """
    def __init__(self, register_type, read_only, point_name, units, description=""):
        super().__init__("byte", read_only, point_name, units, description)
        self.python_type = DESIGO_TYPE_MAPPING.get(register_type, "string")


class Interface(BasicRevert, BaseInterface):
    """
    Create an interface to interact with Desigo API
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auth_token = None
        self.api_username = None
        self.api_password = None
        self.url = "https://18.223.129.4/API/api"
        self.system_id_list = []
        self.nodes = {}
        urllib3.disable_warnings(category=InsecureRequestWarning)

    def configure(self, config_dict, registry_config_str):
        """
        Initialize interface with necessary values
        """
        self.api_username = config_dict["api_username"]
        self.api_password = config_dict["api_password"]
        self.url = config_dict["api_url"]
        self.auth_token = self.get_token()
        # self.system_id_list = self.get_online_system_id_list()
        # self.get_all_nodes(self.system_id_list)
        # for node in self.nodes:
        #     value = self.get_resource(f"values/{node}")
        #     register = Register(
        #         register_type=value[0]["DataType"],
        #         read_only=True,
        #         point_name=node,
        #         units="",
        #     )
        #     self.insert_register(register)
        for point in registry_config_str:
            register = Register(
                register_type=point["collect_config"]["type"],
                read_only=True,
                point_name=point["name"],
                units=point["units"],
            )
            self.insert_register(register)

    def get_resource(self, resource="eventcounters"):
        """
        Retrieve resource from server
        """
        req = requests.get(
            f"{self.url}/{resource}",
            headers={"authorization": f"Bearer {self.auth_token}"},
            verify=False,
            timeout=300,
        )
        try:
            req.raise_for_status()
        except requests.HTTPError:
            # Token expired, get new token and try again
            if req.status_code == http.HTTPStatus.UNAUTHORIZED:
                self.auth_token = self.get_token()
                req = requests.get(
                    f"{self.url}/{resource}",
                    headers={"authorization": f"Bearer {self.auth_token}"},
                    verify=False,
                    timeout=300,
                )
        try:
            result = req.json()
        except json.decoder.JSONDecodeError as exc:
            _log.error(exc)
            result = req.text
        return result

    def get_online_system_id_list(self):
        """
        Return list of all online systems
        """
        id_list = []
        for system in self.get_resource("systems/local")["Systems"]:
            if system["IsOnline"]:
                id_list.append(system["Id"])
        return id_list

    def get_token(self):
        """
        Retrieve token from server
        """
        data = {
            "grant_type": "password",
            "username": self.api_username,
            "password": self.api_password,
        }
        req = requests.post(f"{self.url}/token", data=data, verify=False, timeout=300)
        req.raise_for_status()
        return req.json()["access_token"]

    def build_device_by_location(self):
        """
        Parse Nodes to find device location, name, etc.
        """
        location_data = {}
        for node in self.nodes:
            for entry in node["Location"].split("."):
                location_data[node["ObjectId"]] = entry

    def get_all_nodes(self, system_id_list):
        """
        Return list of all available nodes
        """
        for system in system_id_list:
            self.nodes = {
                item["ObjectId"]: item
                for item in self.get_resource(
                    f"systembrowser/{system}/?SearchString=*"
                )["Nodes"]
            }


    # def get_register_names(self):
    #     _log.debug(f"current nodes list is {self.nodes.keys()}")
    #     return self.nodes.keys()

    # def get_register_by_name(self, name):
    #     return self.nodes[name]

    def scrape_all(self):
        """
        Scrape all collect enabled points
        """
        self.get_all_nodes(self.system_id_list)
        nodes = {}
        metadata = {}
        for node in self.nodes:
            value = self.get_resource(f"values/{node}")
            # _log.debug(f"scraping {node}: {value[0]=}")
            nodes[node] = value[0]["Value"]["Value"]
            metadata[node] = {"type": value[0].get("DataType"), "tz": "", "units": ""}

        return nodes

    def _scrape_all(self):
        return self.scrape_all()

    def get_point(self, point_name, **kwargs):
        """
        Return point value and metadata
        """
        return self.get_resource(f"values/{point_name}")[0]["Value"]

    def _set_point(self, point_name, value):
        pass
