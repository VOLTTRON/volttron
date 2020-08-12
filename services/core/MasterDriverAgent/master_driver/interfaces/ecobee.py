# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import datetime
import gevent
import grequests
import logging
import requests
from requests.exceptions import HTTPError
from requests.packages.urllib3.connection import ConnectionError, NewConnectionError

from volttron.platform import jsonapi
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttron.utils.persistance import PersistentDict
from services.core.MasterDriverAgent.master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert

AUTH_CONFIG_PATH = "drivers/auth/ecobee_{}"
THERMOSTAT_URL = 'https://api.ecobee.com/1/thermostat'
THERMOSTAT_HEADERS = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Authorization': 'Bearer {}'
}

_log = logging.getLogger(__name__)
__version__ = "1.0"


class Interface(BasicRevert, BaseInterface):
    """
    Interface implementation for wrapping around the Ecobee thermostat API
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        # Configuration value defaults
        self.config_dict = {}
        self.api_key = ""
        self.ecobee_id = -1
        # which agent is being used as the caching agent
        self.cache = None
        # Authorization tokens
        self.refresh_token = None
        self.access_token = None
        self.authorization_code = None
        self.authorization_stage = "UNAUTHORIZED"
        # Config path for storing Ecobee auth information in config store, not user facing
        self.auth_config_path = ""
        # Un-initialized data response from Driver Cache agent
        self.thermostat_data = None
        # Un-initialized greenlet for querying cache agent
        self.poll_greenlet_thermostats = None

    def configure(self, config_dict, registry_config_str):
        """
        Interface configuration callback
        :param config_dict: Driver configuration dictionary
        :param registry_config_str: Driver registry configuration dictionary
        """
        self.config_dict.update(config_dict)
        self.api_key = self.config_dict.get("API_KEY")
        self.ecobee_id = self.config_dict.get('DEVICE_ID')
        if not isinstance(self.ecobee_id, int):
            try:
                self.ecobee_id = int(self.ecobee_id)
            except ValueError:
                raise ValueError(
                    f"Ecobee driver requires Ecobee device identifier as int, got: {self.ecobee_id}")
        self.cache = PersistentDict("ecobee_" + str(self.ecobee_id) + ".json", format='json')
        self.auth_config_path = AUTH_CONFIG_PATH.format(self.ecobee_id)
        self.parse_config(registry_config_str)

        # Fetch any stored configuration values to reuse
        self.authorization_stage = "UNAUTHORIZED"
        stored_auth_config = self.get_auth_config_from_store()
        # Do some minimal checks on auth
        if stored_auth_config:
            if stored_auth_config.get("AUTH_CODE"):
                self.authorization_code = stored_auth_config.get("AUTH_CODE")
                self.authorization_stage = "REQUEST_TOKENS"
                if stored_auth_config.get("ACCESS_TOKEN") and stored_auth_config.get("REFRESH_TOKEN"):
                    self.access_token = stored_auth_config.get("ACCESS_TOKEN")
                    self.refresh_token = stored_auth_config.get("REFRESH_TOKEN")
                    try:
                        self.get_thermostat_data()
                        self.authorization_stage = "AUTHORIZED"
                    except HTTPError:
                        _log.warning("Ecobee request response contained HTTP Error, authorization code may be expired. "
                                     "Requesting new authorization code from Ecobee api")
                        self.authorization_stage = "UNAUTHORIZED"
        if self.authorization_stage != "AUTHORIZED":
            # if this fails, our attempt to obtain new auth code and tokens was unsuccessful and the driver is in an
            # error state
            self.update_authorization()
            self.get_thermostat_data()

        if not self.poll_greenlet_thermostats:
            self.poll_greenlet_thermostats = self.core.periodic(180, self.get_thermostat_data)
        _log.debug("Ecobee configuration complete.")

    def parse_config(self, config_dict):
        """
        Parse driver registry configuration and create device registers
        :param config_dict: Registry configuration in dictionary representation
        """
        first_hold = True
        _log.debug("Parsing Ecobee registry configuration.")
        if not config_dict:
            return
        # Parse configuration file for registry parameters, then add new register to the interface
        for index, regDef in enumerate(config_dict):
            point_name = regDef.get("Point Name")
            if not point_name:
                _log.warning(f"Registry configuration contained entry without a point name: {regDef}")
                continue
            read_only = regDef.get('Writable', "").lower() != 'true'
            readable = regDef.get('Readable', "").lower() == 'true'
            volttron_point_name = regDef.get('Volttron Point Name')
            if not volttron_point_name:
                volttron_point_name = point_name
            description = regDef.get('Notes', '')
            units = regDef.get('Units', None)
            default_value = regDef.get("Default Value", "").strip()
            # Truncate empty string or 0 values to None
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            # Create an instance of the register class based on the register type
            if type_name.lower().startswith("setting"):
                register = Setting(self.ecobee_id, read_only, readable, volttron_point_name, point_name, units,
                                   description=description)
            elif type_name.lower() == "hold":
                if first_hold:
                    _log.warning("Hold registers' set_point requires dictionary value, for best practices, visit "
                                 "https://www.ecobee.com/home/developer/api/documentation/v1/functions/SetHold.shtml")
                    first_hold = False
                register = Hold(self.ecobee_id, read_only, readable, volttron_point_name, point_name, units,
                                description=description)
            else:
                _log.warning(f"Unsupported register type {type_name} in Ecobee registry configuration")
                continue
            if default_value is not None:
                self.set_default(point_name, default_value)
            # Add the register instance to our list of registers
            self.insert_register(register)

        # Each Ecobee thermostat has one Status reporting "register", one programs register and one vacation "register

        # Status is a static point which reports a list of running HVAC systems reporting to the thermostat
        status_register = Status(self.ecobee_id)
        self.insert_register(status_register)

        # Vacation can be used to manage all Vacation programs for the thermostat
        vacation_register = Vacation(self.ecobee_id)
        self.insert_register(vacation_register)

        # Add a register for listing events and resuming programs
        program_register = Program(self.ecobee_id)
        self.insert_register(program_register)

    def update_authorization(self):
        if self.authorization_stage == "UNAUTHORIZED":
            self.authorize_application()
        if self.authorization_stage == "REQUEST_TOKENS":
            self.request_tokens()
        if self.authorization_stage == "REFRESH_TOKENS":
            self.refresh_tokens()
        self.update_auth_config()

    def authorize_application(self):
        auth_url = "https://api.ecobee.com/authorize"
        params = {
            "response_type": "ecobeePin",
            "client_id": self.api_key,
            "scope": "smartWrite"
        }
        try:
            response = make_ecobee_request("GET", auth_url, params=params)
        except (ConnectionError, NewConnectionError) as re:
            _log.error(re)
            _log.warning("Error connecting to Ecobee, Could not request pin.")
            return
        for auth_item in ['code', 'ecobeePin']:
            if auth_item not in response:
                raise RuntimeError(f"Ecobee authorization response was missing required item: {auth_item}, response "
                                   "contained {response}")
        self.authorization_code = response.get('code')
        pin = response.get('ecobeePin')
        _log.warning("***********************************************************")
        _log.warning(
            f'Please authorize your Ecobee developer app with PIN code {pin}.\nGo to '
            'https://www.ecobee.com/consumerportal /index.html, click My Apps, Add application, Enter Pin and click '
            'Authorize.')
        _log.warning("***********************************************************")
        self.authorization_stage = "REQUEST_TOKENS"
        gevent.sleep(60)

    def request_tokens(self):
        """
        Request up to date Auth tokens from Ecobee using API key and authorization code
        """
        # Generate auth request and extract returned value
        _log.debug("Requesting new auth tokens from Ecobee.")
        url = 'https://api.ecobee.com/token'
        params = {
            'grant_type': 'ecobeePin',
            'code': self.authorization_code,
            'client_id': self.api_key
        }
        response = make_ecobee_request("POST", url, data=params)
        for token in ["access_token", "refresh_token"]:
            if token not in response:
                raise RuntimeError(f"Request tokens response did  not contain {token}: {response}")
        self.access_token = response.get('access_token')
        self.refresh_token = response.get('refresh_token')
        self.authorization_stage = "AUTHORIZED"

    def refresh_tokens(self):
        """
        Refresh Ecobee API authentication tokens via API endpoint - asks Ecobee to reset tokens then updates config with
        new tokens from Ecobee
        """
        _log.info('Refreshing Ecobee auth tokens.')
        url = 'https://api.ecobee.com/token'
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.api_key
        }
        # Generate auth request and extract returned value
        response = make_ecobee_request("POST", url, data=params)
        for token in 'access_token', 'refresh_token':
            if token not in response:
                raise RuntimeError(f"Ecobee response did not contain token {token}:, response was {response}")
        self.access_token = response['access_token']
        self.refresh_token = response['refresh_token']
        self.authorization_stage = "AUTHORIZED"

    def update_auth_config(self):
        """
        Update the master driver configuration for this device with new values from auth functions
        """
        auth_config = {"AUTH_CODE": self.authorization_code,
                       "ACCESS_TOKEN": self.access_token,
                       "REFRESH_TOKEN": self.refresh_token}
        _log.debug("Updating Ecobee auth configuration with new tokens.")
        self.vip.rpc.call(CONFIGURATION_STORE, "set_config", self.auth_config_path, auth_config, trigger_callback=False,
                          send_update=False).get(timeout=3)

    def get_auth_config_from_store(self):
        """
        :return: Fetch currently stored auth configuration info from config store, returns empty dict if none is
        present
        """
        configs = self.vip.rpc.call(CONFIGURATION_STORE, "manage_list_configs", PLATFORM_DRIVER).get(timeout=3)
        if self.auth_config_path in configs:
            return jsonapi.loads(self.vip.rpc.call(
                CONFIGURATION_STORE, "manage_get", PLATFORM_DRIVER, self.auth_config_path).get(timeout=3))
        else:
            _log.warning("No Ecobee auth file found in config store")
            return {}

    def get_thermostat_data(self, refresh=False):
        """
        Collects most up to date thermostat object data for the configured Ecobee thermostat ID
        :param refresh: whether or not to force obtaining new data from the remote Ecobee API
        """
        params = {
            "json": jsonapi.dumps({
                "selection": {
                    "selectionType": "thermostats",
                    "selectionMatch": self.ecobee_id,
                    "includeSensors": True,
                    "includeRuntime": True,
                    "includeEvents": True,
                    "includeEquipmentStatus": True,
                    "includeSettings": True
                }
            })
        }
        headers = populate_thermostat_headers(self.access_token)
        self.thermostat_data = self.get_ecobee_data("GET", THERMOSTAT_URL, 180, refresh=refresh, headers=headers,
                                                    params=params)

    def get_ecobee_data(self, request_type, url, update_frequency, refresh=False, **kwargs):
        """
        Checks cache for up to date Ecobee data. If none is available for the URL, makes a request to remote Ecobee API.
        :param refresh: force Ecobee data to be obtained from the remote API rather than cache
        :param request_type: HTTP request type for request sent to remote
        :param url: URL of remote Ecobee API endpoint
        :param update_frequency: period for which cached data is considered up to date
        :param kwargs: HTTP request arguments
        :return: Up to date Ecobee data for URL
        """
        cache_data = self.get_data_cache(url, update_frequency)
        if refresh or not (isinstance(cache_data, dict) and len(cache_data)):
            try:
                response = self.get_data_remote(request_type, url, **kwargs)
            except HTTPError as he:
                self.store_remote_data(url, None)
                raise he
            self.store_remote_data(url, response)
            return response
        else:
            return cache_data

    def get_data_remote(self, request_type, url, **kwargs):
        """
        Make request to Ecobee remote API for "register" data, updating authorization tokens as necessary
        :param request_type: HTTP request type for making request
        :param url: URL corresponding to "register" data
        :param kwargs: HTTP request arguments
        :return: remote API response body
        """
        try:
            response = make_ecobee_request(request_type, url, **kwargs)
            self.authorization_stage = "AUTHORIZED"
            return response
        except HTTPError:
            _log.warning(f"HTTPError occurred while fetching data from Ecobee API url: {url}")
            # The request to the remote failed, try refreshing the tokens and trying again using the refresh token
            self.authorization_stage = "REFRESH_TOKENS"
            try:
                self.update_authorization()
            except HTTPError:
                _log.warning("HTTPError occurred while refreshing Ecobee API tokens")
                # if tokens could not be refreshed, try obtaining new tokens using the existing authorization key
                self.authorization_stage = "REQUEST_TOKENS"
                # if we fail to request new tokens, the authorization key is no longer valid, the driver will need
                # to be restarted
                self.update_authorization()
            response = make_ecobee_request(request_type, url, **kwargs)
            self.authorization_stage = "AUTHORIZED"
            return response

    def get_data_cache(self, url, update_frequency):
        """
        Fetches data from cache dict if it is up to date
        :param url: URL to use to use as lookup value in cache dict
        :param update_frequency: duration in seconds for which data in cache is considered up to date
        :return: Data stored in cache if up to date, otherwise None
        """
        url_data = self.cache.get(url)
        if url_data:
            timestamp = utils.parse_timestamp_string(url_data.get("request_timestamp"))
            if (datetime.datetime.now() - timestamp).total_seconds() < update_frequency:
                return url_data.get("request_response")
            else:
                _log.info("Cached Ecobee data out of date.")
        return None

    def store_remote_data(self, url, response):
        """
        Store response body with a timestamp for a given URL
        :param url: url to use to use as lookup value in cache dict
        :param response: request response body to store in cache
        """
        timestamp = utils.format_timestamp(datetime.datetime.now())
        self.cache.update({
            url: {
                "request_timestamp": timestamp,
                "request_response": response
            }
        })
        _log.info(f"Last Ecobee update occurred at {timestamp}")
        self.cache.sync()

    def get_point(self, point_name, **kwargs):
        """
        Return a point's most recent stored value from remote API
        :param point_name: The name of the point corresponding to a register to get the state of
        :return: register's most recent state from remote API response
        """
        # Find the named register and get its current state from the periodic Ecobee API data
        register = self.get_register_by_name(point_name)
        try:
            return register.get_state(self.thermostat_data)
        except (ValueError, KeyError, TypeError):
            self.get_thermostat_data(refresh=True)
            return register.get_state(self.thermostat_data)

    def _set_point(self, point_name, value, **kwargs):
        """
        Send request to remote API to update a point based on provided parameters
        :param point_name: Name of the point to update
        :param value: Intended update value
        :return: Updated state from remote API
        """
        # Find the correct register by name, set its state, then fetch the new state based on the register's type
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError(f"Trying to write to a point configured read only: {point_name}")
        try:
            if isinstance(register, Setting) or isinstance(register, Hold):
                register.set_state(value, self.access_token)
            elif isinstance(register, Vacation) or isinstance(register, Program):
                register.set_state(value, self.access_token, **kwargs)
        except HTTPError:
            self.refresh_tokens()
            if isinstance(register, Setting) or isinstance(register, Hold):
                register.set_state(value, self.access_token)
            elif isinstance(register, Vacation) or isinstance(register, Program):
                register.set_state(value, self.access_token, **kwargs)
        self.get_thermostat_data(refresh=True)
        if register.readable:
            return register.get_state(self.thermostat_data)

    def _scrape_all(self):
        """
        Fetch point data for all configured points
        :return: dictionary of most recent data for all points configured for the driver
        """
        result = {}
        byte_registers = self.get_registers_by_type("byte", True) + self.get_registers_by_type("byte", False)
        registers = [register for register in byte_registers if register.readable]
        refresh = True
        # Add data for all holds and settings to our results
        for register in registers:
            try:
                register_data = register.get_state(self.thermostat_data)
                if isinstance(register_data, dict):
                    result.update(register_data)
                else:
                    result[register.point_name] = register_data
            except ValueError:
                if refresh is True:
                    # refresh data, but don't create a non-deterministic loop of refreshes
                    self.get_thermostat_data(refresh=refresh)
                    refresh = False
                    register_data = register.get_state(self.thermostat_data)
                    if isinstance(register_data, dict):
                        result.update(register_data)
                    else:
                        result[register.point_name] = register_data
        return result


class Setting(BaseRegister):
    """
    Register to wrap around points contained in setting field of Ecobee API's thermostat data response
    """

    def __init__(self, thermostat_identifier, read_only, readable, point_name, point_path, units,
                 description=''):
        super(Setting, self).__init__("byte", read_only, point_name, units, description=description)
        self.thermostat_id = thermostat_identifier
        self.readable = readable
        self.point_path = point_path

    def set_state(self, value, access_token):
        """
        Set Ecobee thermostat setting value by configured point name and provided value
        :param value: Arbitrarily specified value to request as set point
        :param access_token: Ecobee access token to provide as bearer auth in request
        :return: request response values from settings request
        """
        # Generate set state request content and send request
        params = {"format": "json"}
        thermostat_body = {
            "thermostat": {
                "settings": {
                    self.point_path: value
                }
            }
        }
        headers, body = populate_selection_objects(access_token, "thermostats", self.thermostat_id, thermostat_body)
        make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, params=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: Most recently available data for this setting register
        """
        if not self.readable:
            raise RuntimeError("Requested read of write-only point {}".format(self.point_name))
        if not ecobee_data:
            raise ValueError("No Ecobee data from cache available during point scrape.")
        # Parse the state out of the data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat["identifier"]) == self.thermostat_id:
                if self.point_path not in thermostat.get("settings") or \
                        thermostat["settings"].get(self.point_path) is None:
                    raise ValueError(f"Point name {self.point_name} could not be found in latest Ecobee data")
                else:
                    return thermostat["settings"].get(self.point_path)
        raise ValueError(
            f"Point {self.point_path} not available in Ecobee data (Volttron Point Name {self.point_name}).")


class Hold(BaseRegister):
    """
    Register to wrap around points contained in hold field of Ecobee API's thermostat data response
    """

    def __init__(self, thermostat_identifier, read_only, readable, point_name, point_path, units, description=''):
        super(Hold, self).__init__("byte", read_only, point_name, units, description=description)
        self.thermostat_id = thermostat_identifier
        self.readable = readable
        self.python_type = int
        self.point_path = point_path

    def set_state(self, value, access_token):
        """
        Set Ecobee thermostat hold by configured point name and provided value dictionary
        :param value: Arbitrarily specified value dictionary. Ecobee API documentation provides best practice
        information for each hold.
        :param access_token: Ecobee access token to provide as bearer auth in request
        :return: request response values from settings request
        """
        if not isinstance(value, dict):
            raise ValueError(f"Hold register set_state expects dict, received {type(value)}")
        if "holdType" not in value:
            raise ValueError('Hold register requires "holdType" in value dict')
        if self.point_path not in value:
            raise ValueError(f"Point name {self.point_name} not found in Hold set_state value dict")
        # Generate set state request content and send request
        params = {"format": "json"}
        function_body = {
            "functions": [
                {
                    "type": "setHold",
                    "params": value
                }
            ]
        }
        headers, body = populate_selection_objects(access_token, "thermostats", self.thermostat_id, function_body)
        make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, params=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: Most recently available data for this setting register
        """
        if not self.readable:
            raise RuntimeError(f"Requested read of write-only point {self.point_name}")
        if not ecobee_data:
            raise ValueError("No Ecobee data from cache available during point scrape.")
        # Parse the value from the data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                runtime_data = thermostat.get("runtime")
                if not runtime_data or runtime_data.get(self.point_path) is None:
                    raise ValueError(f"Point name {self.point_name} could not be found in latest Ecobee data")
                return runtime_data.get(self.point_path)
        raise ValueError(
            f"Point {self.point_path} not available in Ecobee data (Volttron Point Name {self.point_name}).")


# TODO deleting a vacation is currently broken
class Vacation(BaseRegister):
    """
    Wrapper register for adding and deleting vacations, and getting vacation status
    Note: Since vacations are transient, only 1 vacation register will be
    created per driver. The driver can be used to add, delete, or get the status
    of all vacations for the device
    """

    def __init__(self, thermostat_identifier):
        vacation_description = "Add, remove and fetch Vacations on this Ecobee device."
        super(Vacation, self).__init__("byte", False, "Vacations", "", description=vacation_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.python_type = str

    def set_state(self, vacation, access_token, delete=False):
        """
        Send delete or create vacation request to Ecobee API for the configured thermostat
        :param vacation: Vacation name for delete, or vacation object dictionary for create
        :param access_token: Ecobee access token to provide as bearer auth in request
        :param delete: Whether to delete the named vacation
        """
        if delete:
            if isinstance(vacation, dict):
                vacation = vacation.get("name")
            if not vacation:
                raise ValueError('Deleting vacation on Ecobee thermostat requires either vacation name string or '
                                 'dict with "name" string')
            _log.debug("Creating Ecobee vacation deletion request")
            # Generate and send delete vacation request to remote API
            params = {"format": "json"}
            function_body = {
                "functions": [
                    {
                        "type": "deleteVacation",
                        "params": {
                            "name": vacation
                        }
                    }
                ]
            }
            headers, body = populate_selection_objects(access_token, "registered", self.thermostat_id, function_body)
            make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, params=params, json=body)
        else:
            # Do some basic format validation for vacation dict, but user is ultimately responsible for formatting
            # Ecobee API docs describe expected format, link provided below
            valid_vacation = True
            required_items = ["name", "coolHoldTemp", "heatHoldTemp", "startDate", "startTime", "endDate", "endTime"]
            if not isinstance(vacation, dict):
                valid_vacation = False
            else:
                for item in required_items:
                    if item not in vacation:
                        valid_vacation = False
                        break
            if not valid_vacation:
                raise ValueError('Creating vacation on Ecobee thermostat requires dict: {"name": <name string>, '
                                 '"coolHoldTemp": <temp>, "heatHoldTemp": <temp>, "startDate": <date string>, '
                                 '"startTime": <time string>, "endDate": <date string>, "endTime": <time string>}. '
                                 'Date format required is "YYYY-mm-dd", time format is "HH:MM:SS". See '
                                 'https://www.ecobee.com/home/developer/api/examples/ex9.shtml for more information')
            # Generate create vacation request and send
            params = {"format": "json"}
            function_body = {
                "functions": [
                    {
                        "type": "createVacation",
                        "params": vacation
                    }
                ]
            }
            headers, body = populate_selection_objects(access_token, "registered", self.thermostat_id, function_body)
            make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, params=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: List of vacation dictionaries returned by Ecobee remote API
        """
        if not ecobee_data:
            raise ValueError("No Ecobee data from cache available during point scrape.")
        # Parse out vacations from Ecobee API data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                events_data = thermostat.get("events")
                if not isinstance(events_data, list):
                    raise ValueError(f"Point name {self.point_name} could not be found in latest Ecobee data")
                return [event for event in events_data if event.get("type") == "vacation"]
        raise ValueError(f"Point {self.point_name} not available in Ecobee data.")


# TODO deleting a program currently broken
class Program(BaseRegister):
    """
    Wrapper register for managing Ecobee thermostat programs, and getting program status
    """

    def __init__(self, thermostat_identifier):
        program_description = "List or resume non-vacation programs stored on Ecobee thermostat"
        super(Program, self).__init__("byte", False, "Programs", "", description=program_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.python_type = str

    def set_state(self, program, access_token, resume_all=False):
        """
        Set a new program, resume the next program on the programs stack, or "resume all"
        :param program: Program dictionary as specified by Ecobee API docs if setting a new program, else None
        :param access_token: Ecobee access token to provide as bearer auth in request
        :param resume_all: Whether or not to "resume all" if using the resume program function
        """
        params = {"format": "json"}
        if not isinstance(program, dict) and not len(program):
            if not resume_all:
                _log.warning("No program specified, resuming next event on Ecobee event stack. To learn how to create "
                             "an Ecobee program, Visit "
                             "https://www.ecobee.com/home/developer/api/examples/ex11.shtml for more information")
            else:
                _log.info("No program specified and resume all is set to true, resuming all stored programs.")
            _log.debug("Resuming scheduled Ecobee program(s)")
            function_body = {
                "functions": [
                    {
                        "type": "resumeProgram",
                        "params": {
                            "resumeAll": resume_all
                        }
                    }
                ]
            }
            headers, body = populate_selection_objects(access_token, "thermostats", self.thermostat_id, function_body)
        else:
            program_body = {
                "thermostat": {
                    "program": program
                }
            }
            headers, body = populate_selection_objects(access_token, "registered", self.thermostat_id, program_body)

        make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, params=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: List of Ecobee event objects minus vacation events
        """
        if not ecobee_data:
            raise ValueError("No Ecobee data from cache available during point scrape.")
        # Parse out event objects from Ecobee API data
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                events_data = thermostat.get("events")
                if not isinstance(events_data, list):
                    raise ValueError(f"Point name {self.point_name} could not be found in latest Ecobee data")
                return [event for event in events_data if event.get("type") != "vacation"]
        raise ValueError(f"Point {self.point_name} not available in Ecobee data.")


class Status(BaseRegister):
    """
    Status request wrapper register for Ecobee thermostats.
    Note: There is a single status point for each thermostat, which is set by the device.
    """

    def __init__(self, thermostat_identifier):
        status_description = "Reports device status as a list of running HVAC devices interfacing with this thermostat."
        super(Status, self).__init__("byte", True, "Status", "", description=status_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.python_type = int

    def set_state(self, value, access_token):
        """
        Set state is not supported for the static Status register.
        """
        raise NotImplementedError("Setting thermostat status is not supported.")

    def get_state(self, ecobee_data):
        """
        :return: List of currently running equipment connected to Ecobee thermostat
        """
        if not ecobee_data:
            raise ValueError("No Ecobee data from cache available during point scrape.")
        # Parse out event objects from Ecobee API data
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                status_string = thermostat.get("equipmentStatus")
                if not isinstance(status_string, str):
                    raise ValueError(f"Point name {self.point_name} could not be found in latest Ecobee data")
                return [status for status in status_string.split(",") if len(status)]
        raise ValueError(f"Point {self.point_name} not available in Ecobee data.")


def populate_thermostat_headers(access_token):
    """
    Create populated header json as dictionary
    :param access_token: Ecobee "bearer" access token
    :return: header json as dictionary
    """
    headers = THERMOSTAT_HEADERS.copy()
    headers['Authorization'] = headers['Authorization'].format(access_token)
    return headers


def populate_selection_objects(access_token, selection_type, selection_match, specification):
    """
    Utility method for generating set point request bodies for Ecobee remote api
    :param access_token: Ecobee access token from auth steps/configuration (bearer in request header)
    :param selection_type: Ecobee identity selection type
    :param selection_match: Ecobee identity selection match id
    :param specification: dictionary specifying the Ecobee object for updating the point on the remote API
    :return: request body JSON as dictionary
    """
    body = {
        "selection": {
            "selectionType": selection_type,
            "selectionMatch": selection_match
        },
    }
    body.update(specification)
    return populate_thermostat_headers(access_token), body


def call_grequest(method_name, url, **kwargs):
    """
    Make grequest calls to remote api
    :param method_name: method type - put/get/delete
    :param url: http URL suffix
    :param kwargs: Additional arguments for http request
    :return: grequest response
    """
    try:
        fn = getattr(grequests, method_name)
        request = fn(url, **kwargs)
        response = grequests.map([request])[0]
        if response and isinstance(response, list):
            response = response[0]
        response.raise_for_status()
        return response
    except (ConnectionError, NewConnectionError) as e:
        _log.error(f"Error connecting to {url} with args {kwargs}: {e}")
        raise e


def make_ecobee_request(request_type, url, **kwargs):
    """
    Wrapper around making arbitrary GET and POST requests to remote Ecobee API
    :return: Ecobee API response using provided request content
    """
    # Generate appropriate grequests object
    if request_type.lower() in ["get", "post"]:
        response = call_grequest(request_type.lower(), url, verify=requests.certs.where(), timeout=30, **kwargs)
    else:
        raise ValueError(f"Unsupported request type {request_type} for Ecobee driver.")
    # Send request and extract data from response
    headers = response.headers
    if "json" in headers.get("Content-Type"):
        return response.json()
    else:
        content = response.content
        if isinstance(content, bytes):
            content = jsonapi.loads(response.decode("UTF-8"))
        return content

