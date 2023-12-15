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
import grequests
import urllib3

from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict
from datetime import datetime

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

    def __init__(
        self,
        register_type,
        read_only,
        point_name,
        designation,
        property_name,
        units,
        description="",
    ):
        super().__init__("byte", read_only, point_name, units, description)
        self.python_type = DESIGO_TYPE_MAPPING.get(register_type, float)
        self.designation = designation
        self.property_name = property_name


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
        self.designation_map = defaultdict(list)
        self.desigo_registers = []
        self.points = []
        self.scrape_interval = 900
        urllib3.disable_warnings(category=InsecureRequestWarning)

    def configure(self, config_dict, registry_config_str):
        """
        Initialize interface with necessary values
        """
        _log.debug(f"configuring desigo_api with {config_dict}")
        self.api_username = config_dict["username"]
        self.api_password = config_dict["password"]
        self.url = config_dict["server_url"]
        self.auth_token = self.get_token()

        for point in registry_config_str:

            register = Register(
                register_type="desigo_p2",
                read_only=True,
                point_name=point["name"],
                designation=point["designation"],
                property_name=point["property"],
                units="",
            )
            self.insert_register(register)
            self.points.append(point)
        self.desigo_registers = self.registers[("byte", True)]
        for register in self.desigo_registers:
            self.designation_map[register.designation].append(register)
        _log.info("finished configuration for desigo API interface")
        _log.info(f"registered {len(self.points)} points")

    def _grequests_exception_handler(self, request, exception):
        """
        Log exceptions from grequests
        """
        _log.error(f"grequests error: {exception} with {request}")

    def post_to_resource(self, resource=None, post_data=None, parameters=None):
        """
        Post data to server
        """
        before_request = datetime.utcnow()
        req = grequests.post(
            f"{self.url}/{resource}",
            headers={"authorization": f"Bearer {self.auth_token}"},
            json=post_data,
            params=parameters,
            verify=False,
            timeout=300,
        )
        (result,) = grequests.map(
            (req,), exception_handler=self._grequests_exception_handler
        )
        after_request = datetime.utcnow()
        _log.debug(f"got data in {(after_request-before_request)}")
        # print(result)
        if result.status_code == http.HTTPStatus.UNAUTHORIZED:
            # Token expired, get new token and try again
            before_request = datetime.utcnow()
            self.auth_token = self.get_token()
            req = grequests.get(
                f"{self.url}/{resource}",
                headers={"authorization": f"Bearer {self.auth_token}"},
                verify=False,
                timeout=300,
            )
            (result,) = grequests.map(
                (req,), exception_handler=self._grequests_exception_handler
            )
            after_request = datetime.utcnow()
            _log.debug(f"got data in {(after_request-before_request)}")
        return result.json()

    def get_resource(self, resource="eventcounters", parameters=None):
        """
        Retrieve resource from server
        """
        before_request = datetime.utcnow()
        try:
            req = grequests.get(
                f"{self.url}/{resource}",
                headers={"authorization": f"Bearer {self.auth_token}"},
                params=parameters,
                verify=False,
                timeout=300,
            )
            after_request = datetime.utcnow()
            (result,) = grequests.map(
                (req,), exception_handler=self._grequests_exception_handler
            )
            _log.debug(result.url)
            _log.debug(f"got resource in {after_request-before_request}")
            if result.status_code == http.HTTPStatus.UNAUTHORIZED:
                # Token expired, get new token and try again
                self.auth_token = self.get_token()
                before_request = datetime.utcnow()
                req = grequests.get(
                    f"{self.url}/{resource}",
                    headers={"authorization": f"Bearer {self.auth_token}"},
                    verify=False,
                    timeout=300,
                )
                after_request = datetime.utcnow()
                _log.debug(f"got resource in {after_request-before_request}")
                (result,) = grequests.map(
                    (req,), exception_handler=self._grequests_exception_handler
                )
            # try:
            #     result = req.json()
            # except json.decoder.JSONDecodeError as exc:
            #     print(exc)
            #     result = req.text
            # print(f"{result=}")
            # print(result.json())
            return result.json()
        except ConnectionError:
            print(
                "Could not resolve domain name. Restart systemd-networkd to reset DNS server priority"
            )

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
        req = grequests.post(f"{self.url}/token", data=data, verify=False, timeout=300)
        (result,) = grequests.map(
            (req,), exception_handler=self._grequests_exception_handler
        )
        _log.info(f"acquired access_token: ...{result.json()['access_token'][-5:]}")
        return result.json()["access_token"]

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


    def scrape_all(self):
        """
        Scrape all collect enabled points
        """
        return self._scrape_all()


    def _scrape_all(self):
        # hit endpoint of designation
        post_data = []
        # _log.debug(f"scraping {self.designation_properties}")
        for designation, registers in self.designation_map.items():
            for register in registers:
                post_data.append(f"{designation}.{register.property_name}")

        result = self.post_to_resource(
            "values", post_data, {"readMaxAge": self.scrape_interval * 1000}
        )
        values = self.ensure_no_string(result)
        values = self.normalize_topic_names(values)
        values = {list(x.keys())[0]: list(x.values())[0] for x in values}


        return values

    def get_point(self, point_name, **kwargs):
        """
        Return point value and metadata
        """
        designation = point_name.get("collect_config", {}).get("designation")
        property_name = point_name.get("collect_config", {}).get("property_name")
        if not designation or not property_name:
            _log.error(f"point {designation=} has incomplete collect_config")
            return
        value = [
            x["Value"]["Value"]
            for x in self.get_resource(
                f"propertyvalues/{designation}", {"readAllProperties": True}
            )["Properties"]
            if x["PropertyName"] == property_name
        ]
        return value

    def _set_point(self, point_name, value):
        pass
    def ensure_no_string(self, data):
        """
        Ensure there are no strings in the data
        Data types must only be float or int
        """
        valid_data_types = ["BasicFloat", "BasicUint", "BasicInt", "BasicBit32"]
        values = []
        for entry in data:
            if entry["DataType"] in valid_data_types:
                values.append(
                    {
                        entry["OriginalObjectOrPropertyId"]: float(
                            entry["Value"]["Value"]
                        )
                    }
                )
            elif entry["DataType"] == "BasicBool":
                if entry["Value"]["Value"] == "True":
                    values.append({entry["OriginalObjectOrPropertyId"]: 1})
                elif entry["Value"]["Value"] == "False":
                    values.append({entry["OriginalObjectOrPropertyId"]: 0})
                else:
                    values.append(
                        {
                            entry["OriginalObjectOrPropertyId"]: int(
                                bool(entry["Value"]["Value"])
                            )
                        }
                    )
            else:
                try:
                    values.append(
                        {
                            entry["OriginalObjectOrPropertyId"]: float(
                                entry["Value"]["Value"]
                            )
                        }
                    )
                except ValueError:
                    _log.warning(
                        f"could not convert {entry['Value']['Value']} to float"
                    )
                    continue

        # perform redundancy check
        for entry in values:
            for _, value in entry.items():
                if isinstance(value, str):
                    _log.warning(f"found string {value} in {entry}")
                    values.remove(entry)  # pylint: disable=modified-iterating-list

        return values

    def normalize_topic_names(self, data):
        """
        Ensure value name lines up with ace topic
        """
        normalized_data = []
        for entry in data:
            for key, value in entry.items():
                normalized_data.append(
                    {
                        key.replace(";.", "/").replace(
                            ".ManagementView:ManagementView.FieldNetworks.", "/"
                        ): value
                    }
                )
        return normalized_data
