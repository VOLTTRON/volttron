"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import datetime
import grequests
import json
import logging
import requests
from volttron.platform import jsonapi
from volttron.platform.agent import utils
from volttron.utils.persistance import PersistentDict

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class DriverHTTPCache(object):
    """
    Document for retrieving remote API driver data and caching it during it's update period
    """

    def __init__(self, driver_name):
        super(DriverHTTPCache, self).__init__()
        store_path = "driver_cache.json"
        self.driver_name = driver_name
        self.cache = PersistentDict(filename=store_path, format='json')

    def driver_data_get(self, group_id, url, headers, params=None, body=None,
                        update_frequency=60, refresh=False):
        """
        Get the most up to date remote API driver data based on provided update frequency
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param driver_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param update_frequency: Frequency in seconds between remote API data updates, defaults to 60
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :param refresh: If true, Driver HTTP Cache agent will skip retrieving cached data
        :return: Remote API response data dictionary to be parsed by driver
        """
        return self.get_driver_data(group_id, "GET", url, headers, params=params, body=body,
                                    update_frequency=update_frequency, refresh=refresh)

    def driver_data_post(self, group_id, url, headers, params=None, body=None,
                         update_frequency=60, refresh=False):
        """
        Post the updated data using remote API
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param driver_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param update_frequency: Frequency in seconds between remote API data updates, defaults to 60
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :param refresh: If true, Driver HTTP Cache agent will skip retrieving cached data
        :return: Remote API response data dictionary to be parsed by driver
        """
        return self.get_driver_data(group_id, "POST", url, headers, params=params, body=body,
                                    update_frequency=update_frequency, refresh=refresh)

    def get_driver_data(self, group_id, request_type, url, headers, params=None, body=None,
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
        :param refresh: If true, Driver HTTP Cache agent will skip retrieving cached data
        :return: Remote API response data dictionary to be parsed by driver
        """
        # Input validation
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
            request_data = self._get_json_request(group_id, request_type, url, headers, params=params, body=body)
            return request_data
        else:
            # try to get recently cached data - will throw exception if the data is out of date
            try:
                return self._get_json_cache(group_id, url, update_frequency)
            # if no recently cached data is available, request data from remote API based on provided parameters
            except (RuntimeError, ValueError, KeyError):
                request_data = self._get_json_request(group_id, request_type, url, headers, params=params, body=body)
                return request_data

    # TODO rework storage to use shared persistent dict
    def _get_json_cache(self, group_id, request_url, update_frequency):
        """
        Fetch data from cache file corresponding to the driver type/group id based on request's url
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param request_url: HTTP request URL used to differentiate request endpoints (allows caching of multiple
        endpoints per driver)
        :param update_frequency: Frequency in seconds between remote API data updates, defaults to 60
        :return: Remote API response data dictionary from cache to be parsed by driver
        """
        update_delta = datetime.timedelta(seconds=update_frequency)
        # If there is a group entry containing data for the given URL in the cache
        if self.cache.get(self.driver_name):
            driver_data = self.cache.get(self.driver_name)
            if driver_data.get(group_id):
                url_data = driver_data.get(group_id).get(request_url)
                if not url_data or not isinstance(url_data, dict):
                    raise ValueError("No valid data stored for group {} url {}".format(group_id, request_url))
                # Determine if the cached data is out of date
                request_timestamp = utils.parse_timestamp_string(url_data.get("request_timestamp"))
                next_update_timestamp = request_timestamp + update_delta
                if next_update_timestamp < datetime.datetime.now():
                    raise RuntimeError("Request timestamp out of date, send new request")
                else:
                    return url_data
            else:
                raise KeyError("No {} data for url found in driver cache: {}".format(group_id, request_url))
        else:
            raise KeyError("No data found for {} driver in driver cache".format(self.driver_name))

    def _get_json_request(self, group_id, request_type, url, headers, params=None, body=None):
        """
        Fetch data from remote API using grequests wrapper method then store the data in the cache for later retrieval
        :param group_id: arbitrary identifier to separate driver data between collections of devices
        :param request_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param headers: HTTP request headers dictionary for remote API specified by driver
        :param params: HTTP request parameters dictionary for remote API specified by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :return: Remote API response data dictionary from remote API to be parsed by driver
        """
        _log.debug("Getting driver response from remote.")
        if request_type.upper() not in ["POST", "GET"]:
            raise ValueError("Unsupported request type for Driver HTTP Cache Agent: {}".format(request_type))
        response = self.grequests_wrapper(request_type, url, headers, params=params, body=body)
        url_data = {
            "request_timestamp": utils.format_timestamp(datetime.datetime.now()),
            "request_response": response
        }
        json_data = {
            url: url_data
        }
        if self.driver_name not in self.cache:
            self.cache[self.driver_name] = {}
        if group_id not in self.cache[self.driver_name]:
            self.cache[self.driver_name][group_id] = json_data
        else:
            self.cache[self.driver_name][group_id].update(json_data)
        return url_data

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
            raise ValueError("Unsupported request type {} for DriverHTTPCache agent.".format(request_type))
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
