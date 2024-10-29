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
import gevent
import grequests
import traceback
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
        self.designation = None
        self.designation_map = defaultdict(list)
        self.desigo_registers = []
        self.scrape_interval = 900
        urllib3.disable_warnings(category=InsecureRequestWarning)

    def configure(self, config_dict, registry_config_str):
        """
        Initialize interface with necessary values
        """
        _log.debug("configuring desigo_api")
        self.api_username = config_dict["username"]
        self.api_password = config_dict["password"]
        self.url = config_dict["server_url"]
        self.designation = config_dict["designation"]
        self.auth_token = self.get_token()

        _log.debug(f"{registry_config_str=}")
        name = registry_config_str["name"]
        designation = registry_config_str["designation"]
        for prop in registry_config_str["properties"]:
            _log.debug(f"registering {name}")

            register = Register(
                register_type="desigo_p2",
                read_only=True,
                point_name=prop,
                designation=designation,
                property_name=prop,
                units="",
            )
            self.insert_register(register)
        self.desigo_registers = self.registers[("byte", True)]
        for register in self.desigo_registers:
            self.designation_map[register.designation].append(register)
        _log.info("finished configuration for desigo API interface")
        _log.info(f"registered {len(self.registers("byte", True))} points")

    def _grequests_exception_handler(self, request, exception):
        """
        Log exceptions from grequests
        """
        trace = traceback.format_exc()
        _log.error(f"grequests error: {exception} with {request}: {trace=}")

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
        if result.status_code == http.HTTPStatus.UNAUTHORIZED:
            # Token expired, get new token and try again
            before_request = datetime.utcnow()
            self.auth_token = self.get_token()
            req = grequests.get(
                f"{self.url}/{resource}",
                headers={"authorization": f"Bearer {self.get_token()}"},
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
                headers={"authorization": f"Bearer {self.get_token()}"},
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
                _log.info("token expired, getting new token")
                self.auth_token = self.get_token()
                before_request = datetime.utcnow()
                req = grequests.get(
                    f"{self.url}/{resource}",
                    headers={"authorization": f"Bearer {self.get_token()}"},
                    verify=False,
                    timeout=800,
                )
                after_request = datetime.utcnow()
                _log.debug(f"got resource in {after_request-before_request}")
                (result,) = grequests.map(
                    (req,), exception_handler=self._grequests_exception_handler
                )
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

    def get_token(self, **kwargs):
        """
        Retrieve token from server
        """
        _log.debug("trying to get token via RPC")
        try:
            self.auth_token = self.vip.rpc.call("platform.desigo_credential_handler", "get_token", self.url).get(timeout=30)
        except gevent.timeout.Timeout:
            _log.error("timed out getting token")
            return None
        if self.auth_token is None:
            _log.error("could not get token")
            return None
        _log.debug(f"found token: ...{self.auth_token[-4:]}")
        return self.auth_token

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


    def parse_to_forwarder(self, prop_values):
        """
        Parse propertyvalues JSON to send to forwarder agent
        """
        data = [{}, {}]
        for designation, properties in prop_values.items():
            for prop in properties:
                topic = f"{prop['PropertyName']}"
                value = self.ensure_no_string(prop['Value']['Value'])
                if value is None:
                    continue
                data[0][topic] = value
                data[1][topic] = ""
        return data[0]

    def scrape_all(self):
        """
        Scrape all collect enabled points
        """
        return self._scrape_all()


    def _scrape_all(self):
        # hit endpoint of designation
        api_values = {}
        prop_values = {}
        for designation, registers in self.designation_map.items():
            _log.debug(f"scraping {designation}")
            # check if point has property in designation
            if self.has_property_in_designation(designation):
                # read just the one property
                for register in registers:
                    properties_response = self.get_resource(
                        f"propertyvalues/{designation}", {"readAllProperties": True}
                    )
                    try:
                        value = properties_response.get('Properties', [{}])[0].get('Value', {})['Value']
                    except IndexError:
                        _log.warning(f"could not scrape value property {designation}")
                        continue
                    api_values[register.property_name] = value
                
            else:
                device_props = self.get_resource(f"propertyvalues/{designation}", {"readAllProperties": True})
                for register in registers:
                    api_values[register.property_name] = [x for x in device_props["Properties"] if x["PropertyName"] == register.property_name]
                    for prop in device_props["Properties"]:
                        if prop["PropertyName"] == register.property_name:
                            api_values[register.property_name] = prop["Value"]["Value"]


        # prop_values = self.parse_to_forwarder(prop_values)
        for prop, value in api_values.items():
            value = self.ensure_no_string(api_values[prop])
            if value is None or not isinstance(value, (int, float)):
                continue
            prop_values[prop] = value

        _log.debug(f"{prop_values=}")

        return prop_values

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

    def ensure_no_string(self, value):
        """
        Ensure strings are not returned to forwarder agent
        """
        try:
            return float(value)
        except ValueError:
            if value == "True":
                return 1
            elif value == "False":
                return 0
            else:
                print(f"cannot convert to float, int or bool: {value=}")
                return None
        except TypeError:
            if value == []: #don't debug empty lists
                return None
            _log.debug(f"could not convert to float: {value=}")
            return None

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

    def has_property_in_designation(self, designation):
        props = designation.split(".")
        if props[5] == "Points":
            return True
        else:
            return False