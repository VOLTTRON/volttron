# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
#  FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official,
# policies either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

__docformat__ = 'reStructuredText'

import logging
import datetime
import pytz
import sys

import grequests
# requests should be imported after grequests as requests imports ssl and grequests patches ssl
import requests

import pkg_resources
from volttron.platform.agent import utils
from volttron.platform.vip.agent import RPC
from volttron.platform.agent.utils import format_timestamp
from volttron.platform.agent.base_weather import BaseWeatherAgent
from volttron.platform import jsonapi

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def ambient(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: Ambient
    :rtype: Ambient
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    if not config:
        _log.error("Ambient agent configuration: ".format(config))
    api_key = config.get("api_key")
    if not api_key or isinstance(api_key, str):
        raise RuntimeError("Ambient agent must be configured with an api key.")
    if "application_key" not in config:
        raise RuntimeError("Ambient agent must be configured with an application key.")
    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)

    return Ambient(**kwargs)


class Ambient(BaseWeatherAgent):
    """
    The Ambient agent requires having an API key to interact with the remote API. The agent offers a performance_mode
    configuration option which allows users to limit the amount of data returned by the API.
    """

    def __init__(self, application_key="", **kwargs):
        super(Ambient, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        self.remove_service("get_hourly_historical")
        self.remove_service("get_hourly_forecast")

        self.app_key = application_key

        self.last_service_call_timestamp = None

    @RPC.export
    def get_version(self):
        """
        Provides the current version of the agent.
        :return: current version number in string format.
        """
        return __version__

    def validate_location(self, service_name, location):
        """
        Indicates whether the location dictionary provided matches the format required by the remote weather API
        :param service_name: name of the remote API service
        :param location: location dictionary to provide in the remote API url
        :return: True if the location matches the required format else False
        """
        return isinstance(location.get("location", None), str)

    def get_update_interval(self, service_name):
        """
        Indicates the interval between remote API updates
        :param service_name: requested service endpoint
        :return: datetime timedelta representing the time interval
        """
        if service_name == "get_current_weather":
            return datetime.timedelta(minutes=5)
        else:
            return None

    def get_api_description(self, service_name):
        """
        Provides a human-readable description of the various endpoints provided by the agent
        :param service_name: requested service endpoint
        :return: Human-readable description string
        """
        if service_name is "get_current_weather":
            "Provides current weather observations for locations by their corresponding Ambient weather station name " \
                "via RPC (Requires {'location': <station location string>})"
        else:
            raise RuntimeError(
                "Service {} is not implemented by Ambient.".format(service_name))

    def get_point_name_defs_file(self):
        """
        Constructs the point name mapping dict from the mapping csv.
        :return: dictionary containing a mapping of service point names to standard point names with optional
        """
        # returning resource file instead of stream, as csv.DictReader require file path or file like object opened in
        # text mode.
        return pkg_resources.resource_filename(__name__, "data/name_mapping.csv")

    def query_current_weather(self, location):
        """
        Retrieve data from the Ambient API, return formatted current data and store forecast data in cache
        :param location: location dictionary requested by the user
        :return: Timestamp and data for current data from the Ambient API
        """
        ambient_response = self.make_request()
        location_response = None
        current_time = None
        for record in ambient_response:
            record_location = None
            record_info = record.pop("info")
            if record_info:
                record_location = record_info.get("location", "")
            if record_location:
                weather_data = record.get("lastData", {})
                weather_data["macAddress"] = record.pop("macAddress", "")
                weather_data["name"] = record_info.get("name", "")
                # "date": "2019-04-25T17:09:00.000Z"
                weather_tz_string = weather_data.get('tz', None)
                if weather_tz_string:
                    weather_tz = pytz.timezone(weather_tz_string)
                else:
                    weather_tz = pytz.utc
                weather_date = datetime.datetime.strptime(
                    weather_data.pop("date"), "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(weather_tz)
                if location["location"] == record_location:
                    current_time = format_timestamp(weather_date)
                    location_response = weather_data
                else:
                    weather_data = self.apply_mapping(weather_data)
                    self.store_weather_records("get_current_weather",
                                               [jsonapi.dumps({"location": record_location}),
                                                weather_date,
                                                jsonapi.dumps(weather_data)])
            else:
                raise RuntimeError("API record contained improper 'info' format")
        return current_time, location_response

    def query_forecast_service(self, service, location, quantity, forecast_start):
        """
        Unimplemented method stub
        :param service: forecast service type of weather data to return
        :param location: location dictionary requested during the RPC call
        :param quantity: number of records to return, used to generate Time Machine requests after the forecast request
        :param forecast_start: forecast results that are prior to this timestamp will be filtered by base weather agent
        :return: Timestamp and data returned by the Ambient weather API response
        """
        raise NotImplementedError

    def make_request(self):
        """
        Request data from the Ambient Weather API
        An example of the return value is as follows

        [
            {
                "macAddress": "18:93:D7:3B:89:0C",
                "lastData": {
                    "dateutc": 1556212140000,
                    "tempinf": 71.9,
                    "humidityin": 31,
                    "battout": "1",
                    "temp1f": 68.7,
                    "humidity1": 36,
                    "batt1": "1",
                    "date": "2019-04-25T17:09:00.000Z"
                },
                "info": {
                    "name": "Home B WS",
                    "location": "Lab Home B"
                }
            },
            {
                "macAddress": "50:F1:4A:F7:3C:C4",
                "lastData": {
                    "dateutc": 1556211960000,
                    "tempinf": 82.5,
                    "humidityin": 27,
                    "battout": "1",
                    "temp1f": 68.5,
                    "humidity1": 42,
                    "batt1": "1",
                    "date": "2019-04-25T17:06:00.000Z"
                },
                "info": {
                    "name": "Home A WS",
                    "location": "Lab Home A"
                }
            }
        ]
        :return:
        """

        # AuthenticationTwo API Keys are required for all REST API requests:applicationKey - identifies the
        #   developer / application. To request an application key please email support@ambient.comapiKey -
        #   grants access to past/present data for a given user's devices. A typical consumer-facing application will
        #   initially ask the user to create an apiKey on their Ambient.net account page
        #   (https://dashboard.ambientweather.net/account) and paste it into the app. Developers for personal or
        #   in-house apps will also need to create an apiKey on their own account page.
        # Rate LimitingAPI requests are capped at 1 request/second for each user's apiKey and 3 requests/second
        #   per applicationKey. When this limit is exceeded, the API will return a 429 response code.
        #   Please be kind to our servers :)

        # If the previous call to the API was at least 3 seconds ago - this is a constraint set by Ambient
        if not self.last_service_call_timestamp or (
                datetime.datetime.now() - self.last_service_call_timestamp).total_seconds() > 3:

            url = 'https://api.ambientweather.net/v1/devices?applicationKey=' + self.app_key + '&apiKey=' + \
                  self._api_key

            _log.info("requesting url: {}".format(url))
            grequest = [grequests.get(url, verify=requests.certs.where(), headers=self.headers, timeout=3)]
            gresponse = grequests.map(grequest)[0]
            if gresponse is None:
                raise RuntimeError("get request did not return any response")
            try:
                response = jsonapi.loads(gresponse.content)
                self.last_service_call_timestamp = datetime.datetime.now()
                return response
            except ValueError:
                self.last_service_call_timestamp = datetime.datetime.now()
                self.generate_response_error(url, gresponse.status_code)
        else:
            raise RuntimeError("Previous API call to Ambient service is too recent, please wait at least 3 seconds "
                               "between API calls.")

    def query_hourly_forecast(self, location):
        """
        Unimplemented method stub
        :param location: currently accepts lat/long location dictionary format only
        :return: time of forecast prediction as a timestamp string, and a list of
        """
        raise NotImplementedError

    def query_hourly_historical(self, location, start_date, end_date):
        """
        Unimplemented method stub
        :param location: no format currently determined for history.
        :param start_date: Starting date for historical weather period.
        :param end_date: Ending date for historical weather period.
        :return: NotImplementedError
        """
        raise NotImplementedError

    def generate_response_error(self, url, response_code):
        """
        Raises a descriptive runtime error based on the response code returned by a service.
        :param url: actual url used for requesting data from Ambient
        :param response_code: Http response code returned by a service following a request
        """
        code_x100 = int(response_code / 100)
        if code_x100 == 2:
            raise RuntimeError("Remote API returned no data(code:{}, url:{})".format(response_code, url))
        elif code_x100 == 3:
            raise RuntimeError(
                "Remote API redirected request, but redirect failed (code:{}, url:{})".format(response_code, url))
        elif code_x100 == 4:
            raise RuntimeError(
                "Request ({}) rejected by remote API: Remote API returned Code {}".format(url, response_code))
        elif code_x100 == 5:
            raise RuntimeError(
                "Remote API returned invalid response (code:{}, url:{})".format(response_code, url))
        else:
            raise RuntimeError(
                "API request failed with unexpected response code (code:{}, url:{})".format(response_code, url))


def main():
    """Main method called to start the agent."""
    utils.vip_main(ambient,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
