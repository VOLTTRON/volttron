"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import datetime
import grequests
import json
import logging
import os
import requests
import sys
from volttron.platform import jsonapi
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def httpproxy(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Httpproxy agent instance
    :rtype: Httpproxy agent
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    return HttpProxy(**kwargs)


class HttpProxy(Agent):
    """
    Document for retrieving remote API driver data and caching it during it's update period
    """

    def __init__(self, **kwargs):
        super(HttpProxy, self).__init__(**kwargs)
        self.default_config = {}
        # Set a default configuration to ensure that self.configure is called immediately to setup the agent.
        self.vip.config.set_default("config", self.default_config)
        # Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        Set agent configuration from config store
        :param config_name: Unused configuration name string
        :param action: Unused configuration action
        :param contents: Configuration store contents dictionary
        """
        config = self.default_config.copy()
        config.update(contents)

    @RPC.export
    def get_version(self):
        """
        :return: Agent version
        """
        return __version__


    @RPC.export
    def get_driver_data(self, driver_type, group_id, request_type, url, headers, params=None, body=None,
                        update_frequency=60, refresh=False):
        """
        Get the most up to date remote API driver data based on provided update frequency
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param request_type: HTTP request type for communicating with remote API
        :param driver_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param update_frequency: Frequency in seconds between remote API data updates, defaults to 60
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :param refresh: If true, HTTP Proxy agent will skip retrieving cached data
        :return: Remote API response data dictionary to be parsed by driver
        """
        # Input validation
        if not isinstance(driver_type, str):
            raise ValueError("Invalid driver type: {}, expected unique string".format(driver_type))
        if not isinstance(group_id, str):
            raise ValueError("Invalid driver group ID: {}, expected unique string".format(group_id))
        if not isinstance(update_frequency, int):
            raise ValueError("Invalid update frequency: {}, expected seconds".format(update_frequency))
        if not isinstance(headers, str):
            raise ValueError("Invalid request headers: {}, expected json string".format(headers))
        if headers and isinstance(headers, str):
            headers = json.loads(headers)
        if params and isinstance(params, str):
            params = json.loads(params)
        if body and isinstance(body, str):
            body = json.loads(body)
        # Override if "fresh" data requested by driver
        if refresh:
            request_data = self._get_json_request(
                driver_type, group_id, request_type, url, headers, params=params, body=body)
            return request_data
        else:
            # try to get recently cached data - will throw exception if the dat is out of date
            try:
                return self._get_json_cache(driver_type, group_id, request_type, update_frequency)
            # if no recently cached data is available, request data from remote API based on provided parameters
            except RuntimeError as re:
                request_data = self._get_json_request(
                    driver_type, group_id, request_type, url, headers, params=params, body=body)
                return request_data

    def _get_json_cache(self, driver_type, group_id, request_type, update_frequency):
        """

        :param driver_type: String representation of the type of driver
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param request_type: HTTP request type for communicating with remote API - used here for input validation
        :param update_frequency: Frequency in seconds between remote API data updates, defaults to 60
        :return: Remote API response data dictionary from cache to be parsed by driver
        """
        if request_type.upper() not in ["POST", "GET"]:
            raise ValueError("Unsupported request type for HTTP Proxy Agent: {}".format(request_type))
        data_path = "{}_{}.json".format(driver_type, group_id)
        update_delta = datetime.timedelta(seconds=update_frequency)
        if not os.path.isfile(data_path):
            raise RuntimeError("Data file for driver {}, id {} not found".format(driver_type, group_id))
        else:
            _log.debug("Checking cache at: {}".format(data_path))
            with open(data_path) as data_file:
                json_data = json.load(data_file)
                request_timestamp = utils.parse_timestamp_string(json_data.get("request_timestamp"))
                next_update_timestamp = request_timestamp + update_delta
                if next_update_timestamp < datetime.datetime.now():
                    raise RuntimeError("Request timestamp out of date, send new request")
                else:
                    return json_data

    def _get_json_request(self, driver_type, group_id, request_type, url, headers, params=None, body=None):
        """

        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param request_type: String representation of the type of driver
        :param driver_type: HTTP request type for communicating with remote API
        :param url: String url for communicating with remote API
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :return: Remote API response data dictionary from remote API to be parsed by driver
        """
        _log.debug("Getting driver response from remote.")
        if request_type.upper() not in ["POST", "GET"]:
            raise ValueError("Unsupported request type for HTTP Proxy Agent: {}".format(request_type))
        response = self.grequests_wrapper(request_type, url, headers, params=params, body=body)
        json_data = {
            "request_timestamp": utils.format_timestamp(datetime.datetime.now()),
            "request_response": response
        }
        with open("{}_{}.json".format(driver_type, group_id), "w") as data_file:
            jsonapi.dump(json_data, data_file)
        return json_data

    def grequests_wrapper(self, request_type, url, headers, params=None, body=None):
        """
        Wrapper around GRequests GET and POST methods with response handling for use with agent Mock tests
        :param request_type: HTTP request type for communicating with remote API
        :param url: String url for communicating with remote API
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :return: Remote API response body
        """
        # Handle based on appropriate request type, PUT not supported
        if request_type.upper() == "GET":
            request = grequests.get(url, verify=requests.certs.where(), params=params, headers=headers, timeout=3)
        elif request_type.upper() == "POST":
            request = grequests.post(url, verify=requests.certs.where(), data=params, headers=headers, json=body,
                                     timeout=3)
        else:
            raise ValueError("Unsupported request type {} for HTTPProxy agent.".format(request_type))
        # Send request and extract data from response
        response = grequests.map([request])[0]
        self.handle_response_code(response.status_code, response.text)
        headers = response.headers
        if "json" in headers.get("Content-Type"):
            return response.json()
        else:
            return response.content

    @staticmethod
    def handle_response_code(response_code, text):
        """
        Make sure response code from Ecobee indicates success
        :param response_code: HTTP response code
        :param text: HTTP request text mapped to response code
        """
        # 200 code indicates successful request
        if response_code == 200:
            return
        else:
            raise RuntimeError("Request to Ecobee failed with response code {}: {}.".format(response_code, text))


def main():
    """
    Main method called to start the agent.
    """
    utils.vip_main(httpproxy, identity="platform.httpproxy", version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
