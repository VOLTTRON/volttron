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

import gevent
import grequests
import json
import logging
import requests
from requests.packages.urllib3.connection import ConnectionError, NewConnectionError

from master_driver.interfaces import BaseInterface, BaseRegister, BasicRevert
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER

_log = logging.getLogger(__name__)
__version__ = "1.0"

THERMOSTAT_URL = 'https://api.ecobee.com/1/thermostat'
THERMOSTAT_HEADERS = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Authorization': 'Bearer {}'
}


class Interface(BasicRevert, BaseInterface):
    """
    Interface implementation for wrapping around the Ecobee thermostat API
    """

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        # Configuration value defaults
        self.config_dict = None
        self.cache_identity = None
        self.ecobee_id = None
        self.group_id = None
        self.api_key = None
        self.refresh_token = None
        self.access_token = None
        self.authorization_code = None
        self.pin = None
        self.authenticated = False
        # Config name for updating config during auth update
        self.config_name = None
        # Un-initialized data response from Driver Cache agent
        self.ecobee_data = None
        # Ecobee registers are of non-standard datatypes, so override existing register type dictionary
        self.registers = {
            ('hold', False): [],
            ('hold', True): [],
            ('setting', False): [],
            ('setting', True): [],
            ('status', True): [],
            ('vacation', False): [],
            ('programs', False): []
        }
        # Un-initialized greenlet for querying cache agent
        self.poll_greenlet = None

    def configure(self, config_dict, registry_config_str):
        """
        Configure agent with tokens and polling parameters
        :param config_dict: Device configuration dictionary from config store
        :param registry_config_str: registry configuration string from config store
        """
        # populate class values from configuration store
        _log.debug("Starting Ecobee driver configuration.")
        self.config_dict = config_dict
        self.cache_identity = config_dict.get("CACHE_IDENTITY")
        if not self.cache_identity:
            raise ValueError(
                "Ecobee configuration requires identity of Driver HTTP Cache Agent installed on the platform.")
        self.api_key = config_dict.get('API_KEY')
        self.refresh_token = config_dict.get('REFRESH_TOKEN')
        self.access_token = config_dict.get('ACCESS_TOKEN')
        self.authorization_code = config_dict.get('AUTHORIZATION_CODE')
        self.pin = config_dict.get("PIN")
        self.ecobee_id = config_dict.get('DEVICE_ID')
        self.group_id = config_dict.get("GROUP_ID", "default")
        self.config_name = config_dict.get("config_name")
        if not isinstance(self.config_name, str):
            raise ValueError("Ecobee driver requires config_name string in driver configuration for authentication "
                             "updates")
        if not isinstance(self.ecobee_id, int):
            try:
                self.ecobee_id = int(self.ecobee_id)
            except ValueError:
                raise ValueError(
                    "Ecobee driver requires Ecobee device identifier as int, got: {}".format(self.ecobee_id))
        # Update auth tokens as necessary using Ecobee API endpoints
        if self.authorization_code is not None:
            _log.info("Ecobee using existing Ecobee authorization code.")
            self.authenticated = True
            try:
                self.refresh_tokens()
            except Exception as rf:
                _log.debug("Failed to refresh tokens with existing auth key: {}.  refreshing auth code and trying again"
                           ".".format(rf))
                self.request_pin()
        else:
            _log.warning("Ecobee failed to authenicate, refreshing tokens...")
            self.authenticated = False
            self.access_token = ''
            self.authorization_code = ''
            self.refresh_token = ''
            self.request_pin()
        # then parse the driver's registry configuration
        self.parse_config(registry_config_str)
        # Spawn a periodic greenlet to make sure we're always updated with the most recent Ecobee API data
        if not self.poll_greenlet:
            self.poll_greenlet = self.core.periodic(180, self.get_ecobee_data)
        _log.debug("Ecobee configuration complete.")

    def refresh_tokens(self):
        """
        Refresh Ecobee API authentication tokens via API endpoint - asks Ecobee to reset tokens then updates config with
        new tokens from Ecobee
        """
        _log.debug('Refreshing Ecobee auth tokens.')
        url = 'https://api.ecobee.com/token'
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.api_key
        }
        if not self.pin:
            raise ValueError("Ecobee pin required for refreshing tokens.")
        # Generate auth request and extract returned value
        response = make_ecobee_request("POST", url, data=params)
        for token in 'access_token', 'refresh_token':
            if token not in response:
                raise RuntimeError("Ecobee response did not contain token{}:, response was {}".format(token, response))
        self.access_token = response['access_token']
        _log.debug("Ecobee access token: {}".format(self.access_token))
        self.refresh_token = response['refresh_token']
        _log.debug("Ecobee refresh token: {}".format(self.refresh_token))

    def request_pin(self):
        """
        Request new application pin from Ecobee API, then updates agent configuration via config store

        NOTE: This endpoint is currently broken based on information gathered from stack exchange!
        """
        # Generate auth request and return extracted values - let the user know the pin has to be updated manually using
        # the Ecobee Web UI
        _log.debug("Requesting new Ecobee pin.")
        url = 'https://api.ecobee.com/authorize'
        params = {
            'response_type': 'ecobeePin',
            'client_id': self.api_key,
            'scope': 'smartWrite'
        }
        try:
            response = make_ecobee_request("GET", url, params=params)
        except RuntimeError as re:
            _log.error(re)
            _log.warning("Error connecting to Ecobee. Possible connectivity outage. Could not request pin.")
            return
        for auth_item in ['code', 'ecobeePin']:
            if auth_item not in response:
                raise RuntimeError("Ecobee authorization response was missing required item: {}, response contained {]".
                                   format(auth_item, response))
        self.authorization_code = response.get('code')
        self.pin = response.get('ecobeePin')
        _log.warning("***********************************************************")
        _log.warning(
            'Please authorize your ecobee developer app with PIN code {}.\nGo to '
            'https://www.ecobee.com/consumerportal /index.html, click My Apps, Add application, Enter Pin and click '
            'Authorize.'.format(self.pin))
        _log.warning("***********************************************************")
        _log.info("New Ecobee authorization code: {}".format(self.authorization_code))

        # Allow the user some time to add the application pin through the Ecobee Web UI
        gevent.sleep(60)
        # Now that we have a new pin to use, refresh the auth tokens
        self.request_tokens()

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
        try:
            response = make_ecobee_request("POST", url, data=params)
        except RuntimeError as re:
            _log.error(re)
            _log.warning("Error connecting to Ecobee. Possible connectivity outage. Could not request tokens.")
            return
        self.authenticated = True
        for token in ["access_token", "refresh_token"]:
            if token not in response:
                raise RuntimeError("Request tokens response did  not contain {}, cannot connect to remote Ecobee API "
                                   "until tokens have been successfully obtained from remote")
        self.access_token = response.get('access_token')
        self.refresh_token = response.get('refresh_token')
        _log.info("New Ecobee access token: {}".format(self.access_token))
        _log.info("New Ecobee refresh token: {}".format(self.refresh_token))
        self.update_config()

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
            if not regDef.get("Point Name"):
                _log.warning("Registry configuration contained entry without a point name: {}".format(regDef))
                continue
            read_only = regDef.get('Writable', "").lower() != 'true'
            readable = regDef.get('Readable', "").lower() == 'true'
            point_name = regDef.get('Volttron Point Name')
            if not point_name:
                point_name = regDef.get("Point Name")
            if not point_name:
                # We require something we can use as a name for the register, so
                # don't try to create a register without the name
                raise ValueError(
                    "Registry config entry {} did not have a point name or VOLTTRON point name".format(index))
            description = regDef.get('Notes', '')
            units = regDef.get('Units', None)
            default_value = regDef.get("Default Value", "").strip()
            # Truncate empty string or 0 values to None
            if not default_value:
                default_value = None
            type_name = regDef.get("Type", 'string')
            # Create an instance of the register class based on the register type
            if type_name.lower().startswith("setting"):
                register = Setting(self.ecobee_id, self.access_token, read_only, readable, point_name, units,
                                   description=description)
            elif type_name.lower() == "hold":
                if first_hold:
                    _log.warning("Hold registers' set_point requires dictionary value, for best practices, visit "
                                 "https://www.ecobee.com/home/developer/api/documentation/v1/functions/SetHold.shtml")
                    first_hold = False
                register = Hold(self.ecobee_id, self.access_token, read_only, readable, point_name, units,
                                description=description)
            else:
                raise ValueError("Unsupported register type {} in Ecobee registry configuration".format(type_name))
            if default_value is not None:
                self.set_default(point_name, register.value)
            # Add the register instance to our list of registers
            self.insert_register(register)

        # Each Ecobee thermostat has one Status reporting "register", one programs register and one vacation "register

        # Status is a static point which reports a list of running HVAC systems reporting to the thermostat
        status_register = Status(self.ecobee_id, self.access_token)
        self.insert_register(status_register)

        # Vacation can be used to manage all Vacation programs for the thermostat
        vacation_register = Vacation(self.ecobee_id, self.access_token)
        self.insert_register(vacation_register)

        # Add a register for listing events and resuming programs
        program_register = Program(self.ecobee_id, self.access_token)
        self.insert_register(program_register)

    def update_config(self):
        """
        Update the master driver configuration for this device with new values from auth functions
        """
        _log.debug("Updating configuration with new Ecobee auth tokens.")
        self.config_dict["AUTHORIZATION_CODE"] = self.authorization_code
        self.config_dict["ACCESS_TOKEN"] = self.access_token
        self.config_dict["REFRESH_TOKEN"] = self.refresh_token
        self.config_dict["PIN"] = self.pin
        # Fetch existing driver configuration from config store
        driver_config = json.loads(
            self.vip.rpc.call(CONFIGURATION_STORE, "manage_get", PLATFORM_DRIVER, self.config_name).get())
        # update driver configuration with new values from Ecobee remote
        driver_config["driver_config"].update(self.config_dict)
        # Config store update RPC call to update device configuration
        self.vip.rpc.call(CONFIGURATION_STORE, "set_config", self.config_name, driver_config, trigger_callback=False,
                          send_update=True).get(timeout=3)

    def get_ecobee_data(self, refresh=False, retry=True):
        """
        Request most recent Ecobee data from Driver Cache agent - this prevents overwhelming remote API with data
        requests and or incurring excessive costs
        :param refresh: If true, the Driver HTTP Cache will skip cached data and try to query the API, may not return
        data if the remote rejects due to timing or cost constraints
        :param retry: If true try fetching data from cache agent again
        """
        # Generate request information to pass along to cache agent
        headers = json.dumps({
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': 'Bearer {}'.format(self.access_token)
        })
        params = json.dumps({
            'json': ('{"selection":{"selectionType":"registered",'
                     '"includeSensors":"true",'
                     '"includeRuntime":"true",'
                     '"includeEvents":"true",'
                     '"includeEquipmentStatus":"true",'
                     '"includeSettings":"true"}}')
        })
        # ask the cache for the most recent API data
        try:
            data = self.vip.rpc.call(
                self.cache_identity, "driver_data_get", "ecobee", self.group_id, THERMOSTAT_URL, headers,
                update_frequency=180, params=params, refresh=refresh).get()
            if data is None:
                self.ecobee_data = None
                raise RuntimeError("No Ecobee data available from Driver HTTP Cache Agent.")
            _log.info("Last Ecobee data update occurred: {}".format(data.get("request_timestamp")))
            self.ecobee_data = data.get("request_response")
        except RemoteError:
            if retry:
                _log.warning("Failed to get Ecobee data from Driver HTTP Cache Agent, refreshing tokens and trying "
                             "again.")
                self.refresh_tokens()
                self.get_ecobee_data(refresh=refresh, retry=False)
            else:
                raise RuntimeError("Failed to get Ecobee data from Driver Cache after refreshing tokens. May be "
                                   "experiencing connection issues or Ecobee API may be down.")

    def get_point(self, point_name, **kwargs):
        """
        Return a point's most recent stored value from remote API
        :param point_name:
        :return:
        """
        # Find the named register and get its current state from the periodic Ecobee API data
        register = self.get_register_by_name(point_name)
        try:
            return register.get_state(self.ecobee_data)
        except:
            self.refresh_tokens()
            return register.get_state(self.ecobee_data)

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
            raise IOError("Trying to write to a point configured read only: {}".format(point_name))
        if register.register_type not in ["setting", "hold", "vacation", "programs"]:
            raise RuntimeError("Register {} type {} does not support set_point".format(register.point_name,
                                                                                       register.register_type))
        try:
            if register.register_type == "setting" or register.register_type == "hold":
                register.set_state(value)
            elif register.register_type in ["vacation", "programs"]:
                register.set_state(value, **kwargs)
        except:
            self.refresh_tokens()
            if register.register_type == "setting" or register.register_type == "hold":
                register.set_state(value)
            elif register.register_type in ["vacation", "programs"]:
                register.set_state(value, **kwargs)
        if register.readable:
            return register.get_state(self.ecobee_data)

    def _scrape_all(self):
        """
        Fetch point data for all configured points
        :return: dictionary of most recent data for all points configured for the driver
        """
        result = {}
        # Get static registers
        programs_register = self.get_register_by_name("Programs")
        vacations_register = self.get_register_by_name("Vacations")
        status_register = self.get_register_by_name("Status")
        # Get all holds, filter holds that aren't readable points
        holds = self.get_registers_by_type("hold", True) + self.get_registers_by_type("hold", False)
        holds = [register for register in holds if register.readable]
        # Get all settings, filter settings that aren't readable points
        settings = self.get_registers_by_type("setting", True) + self.get_registers_by_type("setting", False)
        settings = [register for register in settings if register.readable]
        registers = holds + settings
        # Add data for all holds and settings to our results
        for register in registers:
            try:
                register_data = register.get_state(self.ecobee_data)
                if isinstance(register_data, dict):
                    result.update(register_data)
                else:
                    result[register.point_name] = register_data
            except RuntimeError as re:
                _log.warning(re)
        # include device status in the results
        try:
            result[status_register.point_name] = status_register.get_state()
        except RuntimeError as re:
            _log.warning(re)
        # include any vacations scheduled for the device
        try:
            result[vacations_register.point_name] = vacations_register.get_state(self.ecobee_data)
        except RuntimeError as re:
            _log.warning(re)
        # include any scheduled programs for the device
        try:
            result[programs_register.point_name] = programs_register.get_state(self.ecobee_data)
        except RuntimeError as re:
            _log.warning(re)
        return result


class Setting(BaseRegister):
    """
    Register to wrap around points contained in setting field of Ecobee API's thermostat data response
    """

    def __init__(self, thermostat_identifier, access_token, read_only, readable, point_name, units, description=''):
        super(Setting, self).__init__("setting", read_only, point_name, units, description=description)
        self.thermostat_id = thermostat_identifier
        self.access_token = access_token
        self.readable = readable

    def set_state(self, value):
        """
        Set Ecobee thermostat setting value by configured point name and provided value
        :param value: Arbitrarily specified value to request as set point
        :return: request response values from settings request
        """
        if self.read_only:
            raise RuntimeError("Attempted write of read-only register {}".format(self.point_name))
        # Generate set state request content and send request
        params = {"format": "json"}
        thermostat_body = {
            "thermostat": {
                "settings": {
                    self.point_name: value
                }
            }
        }
        headers, body = generate_set_point_request_objects(self.access_token, "thermostats", self.thermostat_id,
                                                           thermostat_body)
        return make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, data=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: Most recently available data for this setting register
        """
        if not self.readable:
            raise RuntimeError("Requested read of write-only point {}".format(self.point_name))
        if not ecobee_data:
            raise RuntimeError("No Ecobee data from cache available during point scrape.")
        # Parse the state out of the data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat["identifier"]) == self.thermostat_id:
                if self.point_name not in thermostat["settings"]:
                    raise RuntimeError("Register name {} could not be found in latest Ecobee data".format(
                        self.point_name))
                else:
                    return thermostat["settings"].get(self.point_name)
        raise RuntimeError("Point {} not available in Ecobee data.".format(self.point_name))


class Hold(BaseRegister):
    """
    Register to wrap around points contained in hold field of Ecobee API's thermostat data response
    """

    def __init__(self, thermostat_identifier, access_token, read_only, readable, point_name, units, description=''):
        super(Hold, self).__init__("hold", read_only, point_name, units, description=description)
        self.thermostat_id = thermostat_identifier
        self.access_token = access_token
        self.readable = readable
        self.python_type = int

    def set_state(self, value):
        """
        Set Ecobee thermostat hold by configured point name and provided value dictionary
        :param value: Arbitrarily specified value dictionary. Ecobee API documentation provides best practice
        information for each hold.
        :return: request response values from settings request
        """
        if not isinstance(value, dict):
            raise ValueError("Hold register set_state expects dict, received {}".format(type(value)))
        if "holdType" not in value:
            raise ValueError('Hold register requires "holdType" in value dict')
        if self.point_name not in value:
            raise ValueError("Point name {} not found in Hold set_state value dict")
        # Generate set state request content and send reques
        params = {"format": "json"}
        function_body = {
            "functions": [
                {
                    "type": "setHold",
                    "params": value
                }
            ]
        }
        headers, body = generate_set_point_request_objects(self.access_token, "thermostats", self.thermostat_id,
                                                           function_body)
        return make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, data=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: Most recently available data for this setting register
        """
        if not self.readable:
            raise RuntimeError("Requested read of write-only point {}".format(self.point_name))
        if not ecobee_data:
            raise RuntimeError("No Ecobee data from cache available during point scrape.")
        # Parse the value from the data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                runtime_data = thermostat.get("runtime")
                if not runtime_data:
                    raise RuntimeError("No runtime data included in Ecobee response")
                return runtime_data.get(self.point_name)
        raise RuntimeError("Point {} not available in Ecobee data.".format(self.point_name))


class Status(BaseRegister):
    """
    Status request wrapper register for Ecobee thermostats.
    Note: There is a single status point for each thermostat, which is set by the device.
    """

    def __init__(self, thermostat_identifier, access_token):
        status_description = "Reports device status as a list of running HVAC devices interfacing with this thermostat."
        super(Status, self).__init__("status", True, "Status", None, description=status_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.access_token = access_token
        self.python_type = int

    def set_state(self, value):
        """
        Set state is not supported for the static Status register.
        """
        raise NotImplementedError("Setting thermostat status is not supported.")

    def get_state(self):
        """
        :return: List of currently running equipment connected to Ecobee thermostat
        """
        # Generate set state request content and send request
        status_url = "https://api.ecobee.com/1/thermostatSummary"
        headers = generate_thermostat_headers(self.access_token)
        params = {
            'json': json.dumps({
                "selection": {
                    "selectionType": "registered",
                    "selectionMatch": "",
                    "includeEquipmentStatus": True
                }
            })
        }
        status_message = make_ecobee_request("GET", status_url, headers=headers, params=params)
        # Parse the status from the request response
        if not status_message:
            raise RuntimeError(
                "No response data from Ecobee thermostat summary endpoint, could not get thermostat status")
        for status_line in status_message["statusList"]:
            thermostat, running_equipment = status_line.split(":")
            if int(thermostat) == self.thermostat_id:
                return running_equipment.split(",")
        raise RuntimeError("Could not find status for Ecobee device {} in thermostat summary".format(
            self.thermostat_id))


# TODO deleting a vacation is currently broken
class Vacation(BaseRegister):
    """
    Wrapper register for adding and deleting vacations, and getting vacation status
    Note: Since vacations are transient, only 1 vacation register will be
    created per driver. The driver can be used to add, delete, or get the status
    of all vacations for the device
    """

    def __init__(self, thermostat_identifier, access_token):
        vacation_description = "Add, remove and fetch Vacations on this Ecobee device."
        super(Vacation, self).__init__("vacation", False, "Vacations", None, description=vacation_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.access_token = access_token
        self.python_type = str

    def set_state(self, vacation, delete=False):
        """
        Send delete or create vacation request to Ecobee API for the configured thermostat
        :param vacation: Vacation name for delete, or vacation object dictionary for create
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
            headers, body = generate_set_point_request_objects(self.access_token, "registered", "", function_body)
            make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, data=params, json=body)
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
            _log.debug("Creating Ecobee vacation creation request")
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
            headers, body = generate_set_point_request_objects(self.access_token, "registered", self.thermostat_id,
                                                               function_body)
            make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, data=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: List of vacation dictionaries returned by Ecobee remote API
        """
        if not ecobee_data:
            raise RuntimeError("No Ecobee data from cache available during point scrape.")
        # Parse out vacations from Ecobee API data dictionary
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                events_data = thermostat.get("events")
                return [event for event in events_data if event.get("type") == "vacation"]
        raise RuntimeError("Point {} not available in Ecobee data.".format(self.point_name))


# TODO deleting a program currently broken
class Program(BaseRegister):
    """
    Wrapper register for managing Ecobee thermostat programs, and getting program status
    """

    def __init__(self, thermostat_identifier, access_token):
        program_description = "List or resume non-vacation programs stored on Ecobee thermostat"
        super(Program, self).__init__("programs", False, "Programs", None, description=program_description)
        self.thermostat_id = thermostat_identifier
        self.readable = True
        self.access_token = access_token
        self.python_type = str

    def set_state(self, program, resume_all=False):
        """
        Set a new program, resume the next program on the programs stack, or "resume all"
        :param program: Program dictionary as specified by Ecobee API docs if setting a new program, else None
        :param resume_all: Whether or not to "resume all" if using the resume program function
        """
        params = {"format": "json"}
        if not program:
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
            headers, body = generate_set_point_request_objects(self.access_token, "thermostats", self.thermostat_id,
                                                               function_body)
        else:
            _log.debug("Creating new Ecobee thermostat program")
            program_body = {
                "thermostat": {
                    "program": program
                }
            }
            headers, body = generate_set_point_request_objects(self.access_token, "registered", self.thermostat_id,
                                                               program_body)

        make_ecobee_request("POST", THERMOSTAT_URL, headers=headers, data=params, json=body)

    def get_state(self, ecobee_data):
        """
        :param ecobee_data: Ecobee data dictionary obtained from Driver HTTP Cache agent
        :return: List of Ecobee event objects minus vacation events
        """
        if not ecobee_data:
            raise RuntimeError("No Ecobee data from cache available during point scrape.")
        # Parse out event objects from Ecobee API data
        for thermostat in ecobee_data.get("thermostatList"):
            if int(thermostat.get("identifier")) == self.thermostat_id:
                events_data = thermostat.get("events")
                return [event for event in events_data if event.get("type") != "vacation"]
        raise RuntimeError("Point {} not available in Ecobee data.".format(self.point_name))


def generate_thermostat_headers(access_token):
    """
    Create populated header json as dictionary
    :param access_token: Ecobee "bearer" access token
    :return: header json as dictionary
    """
    headers = THERMOSTAT_HEADERS
    headers['Authorization'] = headers['Authorization'].format(access_token)
    return headers


def generate_set_point_request_objects(access_token, selection_type, selection_match, point_specification):
    """
    Utility method for generating set point request bodies for Ecobee remote api
    :param access_token: Ecobee access token from auth steps/configuration (bearer in request header)
    :param selection_type: Ecobee identity selection type
    :param selection_match: Ecobee identity selection match id
    :param point_specification: dictionary specifying the Ecobee object for updating the point on the remote API
    :return: request body JSON as dictionary
    """
    body = {
        "selection": {
            "selectionType": selection_type,
            "selectionMatch": selection_match
        },
    }
    body.update(point_specification)
    return generate_thermostat_headers(access_token), body


def call_grequest(method_name, url, **kwargs):
    """
    Make grequest calls to remote api
    :param method_name: method type - put/get/delete
    :param url: http URL suffix
    :param kwargs: Additional arguments for http request
    :return:
    """
    try:
        fn = getattr(grequests, method_name)
        request = fn(url, **kwargs)
        response = grequests.map([request])

        if response and isinstance(response, list):
            response[0].raise_for_status()
    except (ConnectionError, NewConnectionError) as e:
        _log.debug("Error connecting to {} with args {}: {}".format(url, kwargs, e))
        raise e
    except requests.exceptions.HTTPError as e:
        _log.debug("Exception when trying to make HTTP request to {} with args {} : {}".format(url, kwargs, e))
        raise e
    except AttributeError as e:
        _log.debug("Exception when trying to make HTTP request to {} wit args {} : {}".format(url, kwargs, e))
        raise e
    return response


def make_ecobee_request(request_type, url, **kwargs):
    """
    Wrapper around making arbitrary GET and POST requests to remote Ecobee API
    :return: Ecobee API response using provided request content
    """
    # Generate appropriate grequests object
    if request_type.lower() in ["get", "post"]:
        response = call_grequest(request_type.lower(), url, verify=requests.certs.where(), timeout=30, **kwargs)[0]
    else:
        raise ValueError("Unsupported request type {} for Ecobee driver.".format(request_type))
    # Send request and extract data from response
    headers = response.headers
    if "json" in headers.get("Content-Type"):
        return response.json()
    else:
        return response.content
