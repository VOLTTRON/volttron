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
import re
import json
import grequests
import pkg_resources
from volttron.platform.agent import utils
from volttron.platform.vip.agent import RPC
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.agent.base_weather import BaseWeatherAgent

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

WEATHER_WARN = "weather_warnings"
WEATHER_ERROR = "weather_error"
WEATHER_RESULTS = "weather_results"

SERVICES_MAPPING = {
 'SERVICE_HOURLY_FORECAST':
     {'service': 'get_hourly_forecast', 'json_name': 'hourly', 'type':
         'forecast'},
 'SERVICE_DAILY_FORECAST':
     {'service': 'get_daily_forecast', 'json_name':  'daily', 'type':
         'forecast'},
 'SERVICE_CURRENT_WEATHER':
     {'service': 'get_current_weather', 'json_name': 'currently', 'type':
         'current'},
 'SERVICE_MINUTELY_FORECAST':
     {'service': 'get_minutely_forecast', 'json_name': 'minutely', 'type':
         'forecast'}
}

LAT_LONG_REGEX = re.compile("^-?[0-9]{1,3}(\.[0-9]{1,4})?$")


def darksky(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Darksky
    :rtype: Darksky
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}
    if not config:
        _log.error("Darksky agent configuration: ".format(config))
    if "api_key" not in config:
        raise RuntimeError("Darksky agent must be configured with an api key.")
    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)

    return Darksky(**kwargs)


class Darksky(BaseWeatherAgent):
    """
    The Darksky agent requires having an API key to interact with the remote
    API. The agent offers a performance_mode configuration option which
    allows users to limit the amount of data returned by the API.

    ***Powered by Dark Sky***
    """

    def __init__(self, performance_mode=False, **kwargs):
        super(Darksky, self).__init__(**kwargs)
        self.performance_mode = performance_mode
        if self.performance_mode:
            _log.info("Darksky agent staring in performance mode")
        _log.debug("vip_identity: " + self.core.identity)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        minutely_service = SERVICES_MAPPING['SERVICE_MINUTELY_FORECAST'][
                                  'service']
        self.register_service(minutely_service,
                              self.get_update_interval(minutely_service),
                              'forecast', description=
                              "Params: locations ([{type: value},...])")
        daily_service = SERVICES_MAPPING['SERVICE_DAILY_FORECAST']['service']
        self.register_service(daily_service,
                              self.get_update_interval(daily_service),
                              'forecast', description=
                              "Params: locations ([{type: value},...])")
        self.remove_service("get_hourly_historical")

    @RPC.export
    def get_version(self):
        """
        Provides the current version of the agent.
        :return: current version number in string format.
        """
        return __version__

    def get_api_calls_settings(self):
        """
        :return: Returns a datetime object representing the time period for API
        calls to expire as well as a number representing the number of API calls
        alloted during the period
        """
        return datetime.timedelta(days=1), 1000

    def validate_location(self, service_name, location):
        """
        Indicates whether the location dictionary provided matches the format
        required by the remote weather API
        :param service_name: name of the remote API service
        :param location: location dictionary to provide in the remote API url
        :return: True if the location matches the required format else False
        """
        if 'lat' in location and 'long' in location:
            if LAT_LONG_REGEX.match(str(location['lat'])) and \
                    LAT_LONG_REGEX.match(str(location['long'])):
                return True
        else:
            return False

    def get_update_interval(self, service_name):
        """
        Indicates the interval between remote API updates
        :param service_name: requested service endpoint
        :return: datetime timedelta representing the time interval
        """
        if service_name == "get_current_weather":
            return datetime.timedelta(hours=1)
        elif service_name == "get_hourly_forecast":
            return datetime.timedelta(hours=1)
        elif service_name == "get_minutely_forecast":
            return datetime.timedelta(minutes=5)
        elif service_name == 'get_daily_forecast':
            return datetime.timedelta(hours=1)
        else:
            return None

    def get_api_description(self, service_name):
        """
        Provides a human-readable description of the various endpoints provided
        by the agent
        :param service_name: requested service endpoint
        :return: Human-readable description string
        """
        if service_name is "get_current_weather":
            return "Provides current weather observations by lat/long via RPC "\
                   "(Requires {'lat': <latitude>, 'long': <longitude>}"
        elif service_name is "get_hourly_forecast":
            return "Provides <hours> (optional) hours of forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        elif service_name is "get_minutely_forecast":
            return "Provides 60 minutes of forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        elif service_name is "get_daily_forecast":
            return "Provides 1 week of daily forecast predictions "\
                   "by lat/long via RPC (Requires {'lat': <latitude>, 'long': "\
                   "<longitude>}"
        else:
            raise RuntimeError(
                "Service {} is not implemented by Darksky.".format(
                    service_name))

    def get_point_name_defs_file(self):
        """
        Constructs the point name mapping dict from the
        mapping csv.
        :return: dictionary containing a mapping of service point
        names to standard point names with optional
        """
        return pkg_resources.resource_stream(__name__, "data/name_mapping.csv")

    def get_darksky_forecast(self, service, location):
        """
        Generic method called by the current and forecast service endpoint
        methods to fetch a forecast request from the Darksky API. If
        performance mode is set to True, the url adds exclusions for the
        services provided by the API that were not requested.
        :param service: requested service endpoint
        :param location: location dictionary for building url
        :return: Darksky forecast request response
        """
        service_json_name = ''
        for service_code in SERVICES_MAPPING:
            if SERVICES_MAPPING[service_code]['service'] is service:
                service_json_name = SERVICES_MAPPING[service_code]['json_name']
        if "lat" in location and 'long' in location:
            url = "https://api.darksky.net/forecast/{key}/{lat}," \
               "{long}?units=si".format(key=self._api_key, lat=location['lat'],
                               long=location['long'])
            if self.performance_mode:
                services = ["currently", "hourly", "minutely", "daily"]
                if service_json_name and service_json_name in services:
                    services.remove(service_json_name)
                    url += "&exclude=" + ",".join(services)
                else:
                    raise RuntimeError("Requested service {} is not provided"
                                       " by the Darksky API".format(service))
        else:
            raise ValueError('Invalid location. Expected format is: '
                             '"{"lat": "xxx.xxxx", "long": "xxx.xxxx"}"')
        grequest = [grequests.get(url, headers=self.headers, timeout=3)]
        gresponse = grequests.map(grequest)[0]
        if gresponse is None:
            raise RuntimeError("get request did not return any "
                               "response")
        response = json.loads(gresponse.content)
        if gresponse.status_code != 200:
            self.generate_response_error(url, gresponse.status_code)
        return response

    @staticmethod
    def format_multientry_response(location, response, request_type):
        """
        Used to extract the data not used by the RPC method, and store it in
        the cache, helping to limit the number of API calls used to obtain data
        :param location: location dictionary to include with cached data
        :param response: Darksky forecast response
        :param request_type: The type service data to extract and format
        :param timezone: Timezone of the timestamps in the forecast response
        data
        :return: formatted response data by service
        """
        data = []
        generation_time = get_aware_utc_now()\
            .replace(microsecond=0, second=0, minute=0)
        for entry in response['data']:
            entry_time = datetime.datetime.fromtimestamp(entry['time'],
                                                         pytz.utc)
            if request_type is 'forecast':
                data.append([json.dumps(location), generation_time, entry_time,
                             json.dumps(entry)])
            else:
                data.append([json.dumps(location), entry_time, json.dumps(
                    entry)])
        return data

    def query_current_weather(self, location):
        """
        Retrieve data from the Darksky API, return formatted current data and
        store forecast data in cache
        :param location: location dictionary requested by the user
        :return: Timestamp and data for current data from the Darksky API
        """
        darksky_response = self.get_darksky_forecast(
            SERVICES_MAPPING['SERVICE_CURRENT_WEATHER']['service'], location)
        current_response = darksky_response.pop('currently')
        # Darksky required attribution
        current_response["attribution"] = "Powered by Dark Sky"
        current_time = datetime.datetime.fromtimestamp(
            current_response['time'], pytz.utc)
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service in SERVICES_MAPPING:
                if service is not 'SERVICE_CURRENT_WEATHER' and \
                        SERVICES_MAPPING[service]['json_name'] in \
                        darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service]['json_name'])
                    service_data = self.format_multientry_response(
                        location, service_response, SERVICES_MAPPING[
                            service]['type'])
                    self.store_weather_records(SERVICES_MAPPING[service][
                                                   'service'], service_data)
        return format_timestamp(current_time), current_response

    def query_forecast_service(self, service, location):
        """
        Generic method for requesting forecast data from the various RPC
        forecast methods
        :param service: forecast service type of weather data to return
        :param location: location dictionary requested during the RPC call
        :return: Timestamp and data returned by the Darksky weather API response
        """
        service_name = ''
        for service_code in SERVICES_MAPPING:
            if SERVICES_MAPPING[service_code]['service'] is service:
                service_name = service_code
                break
        if not len(service_name):
            raise RuntimeError("{} is not a service provided by "
                               "Darksky".format(service))
        darksky_response = self.get_darksky_forecast(
            SERVICES_MAPPING[service_name]['service'], location)
        forecast_response = darksky_response.pop(SERVICES_MAPPING[service_name]
                                                 ['json_name'])
        forecast_data = []
        for entry in forecast_response['data']:
            entry_time = datetime.datetime.fromtimestamp(entry['time'],
                                                         pytz.utc)
            # Darksky required attribution
            entry["attribution"] = "Powered by Dark Sky"
            forecast_data.append([format_timestamp(entry_time), entry])
        if service == "get_minutely_weather":
            now = get_aware_utc_now()
            gen_minutes = now.minute / 5 * 5
            generation_time = now.replace(microsecond=0, second=0,
                                          minute=gen_minutes)
        else:
            generation_time = format_timestamp(get_aware_utc_now()
                                               .replace(microsecond=0, second=0,
                                                        minute=0))
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service_code in SERVICES_MAPPING:
                if service_code is not service_name and \
                        SERVICES_MAPPING[service_code]['json_name'] in \
                        darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service_code]['json_name'])
                    if SERVICES_MAPPING[service_code]['type'] is not 'current':
                        service_data = self.format_multientry_response(
                            location, service_response, SERVICES_MAPPING[
                                service_code]['type'])
                    else:
                        service_data = \
                            [json.dumps(location), datetime.datetime.
                                fromtimestamp(service_response['time']),
                             json.dumps(service_response)]
                    self.store_weather_records(SERVICES_MAPPING[service_code][
                                                   'service'], service_data)
        return generation_time, forecast_data

    @RPC.export
    def get_minutely_forecast(self, locations, minutes=60):
        """
        RPC method for getting timeseries forecast weather data minute by minute
        :param locations: list of location dictionaries from the RPC call
        :param minutes: Number of minutes of weather data to be returned
        :return: List of minutely forecast weather dictionaries
        """
        # maximum of 60 minutes plus the current minute of forecast available
        # TODO check that this is the desired behavior
        if minutes > 60:
            minutes = 60
        return self.get_forecast_by_service(locations, SERVICES_MAPPING[
                                                'SERVICE_MINUTELY_FORECAST'][
                                                'service'], 'minute',
                                            minutes)

    @RPC.export
    def get_daily_forecast(self, locations, days=7):
        """
        RPC method for getting timeseries forecast weather data by full day
        :param locations: list of location dictionaries from the RPC call
        :param days: Number of minutes of weather data to be returned
        :return: List of daily forecast weather dictionaries
        """
        # maximum of 8 days including the current day provided by the API
        if days > 7:
            days = 7
        return self.get_forecast_by_service(locations,
                                            SERVICES_MAPPING[
                                                'SERVICE_DAILY_FORECAST'][
                                                'service'], 'day',
                                            days)

    @staticmethod
    def generate_response_error(url, response_code):
        """
        raises a descriptive runtime error based on the response code
        returned by a service.
        :param url: actual url used for requesting data from Darksky
        :param response_code: Http response code returned by a service
        following a request
        """
        code_x100 = int(response_code / 100)
        if code_x100 == 2:
            raise RuntimeError(
                "Remote API returned no data(code:{}, url:{})".format(
                    response_code, url))
        elif code_x100 == 3:
            raise RuntimeError(
                "Remote API redirected request, "
                "but redirect failed (code:{}, url:{})".format(response_code,
                                                               url))
        elif code_x100 == 4:
            raise RuntimeError(
                "Invalid request ({}) Remote API returned "
                " Code {}".format(url, response_code))
        elif code_x100 == 5:
            raise RuntimeError(
                "Remote API returned invalid response "
                "(code:{}, url:{})".format(response_code, url))
        else:
            raise RuntimeError(
                "API request failed with unexpected response "
                "code (code:{}, url:{})".format(response_code, url))


def main():
    """Main method called to start the agent."""
    utils.vip_main(darksky, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
