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
import datetime
import pytz
import sys
import re

import grequests
# requests should be imported after grequests as
# requests imports ssl and grequests patches ssl
import requests

import pkg_resources
from volttron.platform.agent import utils
from volttron.platform.vip.agent import RPC
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.agent.base_weather import BaseWeatherAgent
from volttron.platform.agent.base_weather import get_forecast_start_stop
from volttron.platform import jsonapi

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

WEATHER_WARN = "weather_warnings"
WEATHER_ERROR = "weather_error"
WEATHER_RESULTS = "weather_results"

SERVICES_MAPPING = {
 'get_hourly_forecast': {'json_name': 'hourly', 'type': 'forecast'},
 'get_daily_forecast': {'json_name':  'daily', 'type': 'forecast'},
 'get_current_weather': {'json_name': 'currently', 'type': 'current'},
 'get_minutely_forecast': {'json_name': 'minutely', 'type': 'forecast'}
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
    except Exception:
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

    def __init__(self, performance_mode=True, **kwargs):
        super(Darksky, self).__init__(**kwargs)
        self.performance_mode = performance_mode
        if self.performance_mode:
            _log.info("Darksky agent staring in performance mode")
        _log.debug("vip_identity: " + self.core.identity)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        self.register_service('get_minutely_forecast',
                              self.get_update_interval('get_minutely_forecast'),
                              'forecast', description=
                              "Params: locations ([{'lat': <value>, 'long': <value>},...])")
        self.register_service('get_daily_forecast',
                              self.get_update_interval('get_daily_forecast'),
                              'forecast', description=
                              "Params: locations ([{'lat': <value>, 'long': <value>},...])")
        self.remove_service("get_hourly_historical")

    @RPC.export
    def get_version(self):
        """
        Provides the current version of the agent.
        :return: current version number in string format.
        """
        return __version__

    def get_api_calls_interval(self):
        """
        :return: Returns a datetime object representing the time period for API
        calls to expire as well as a number representing the number of API calls
        alloted during the period
        """
        return datetime.timedelta(days=1)

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
        # returning resource file instead of stream, as csv.DictReader require file path or file like object opened in
        # text mode.
        return pkg_resources.resource_filename(__name__, "data/name_mapping.csv")

    def get_darksky_data(self, service, location, timestamp=None):
        """
        Generic method called by the current and forecast service endpoint
        methods to fetch a forecast request from the Darksky API. If
        performance mode is set to True, the url adds exclusions for the
        services provided by the API that were not requested.
        :param service: requested service endpoint
        :param location: location dictionary for building url
        :param timestamp: timestamp of a record if this request is for the
        Time Machine end point
        :return: Darksky forecast request response
        """
        service_json_name = ''
        if service in SERVICES_MAPPING:
            service_json_name = SERVICES_MAPPING[service]['json_name']
        if "lat" in location and 'long' in location:
            if timestamp:
                timestamp = int((timestamp.replace(tzinfo=None) -
                                 datetime.datetime.utcfromtimestamp(0)).
                                total_seconds())
                url = "https://api.darksky.net/forecast/{key}/{lat}," \
                           "{long},{timestamp}?units=us".format(
                    key=self._api_key, lat=location['lat'],
                    long=location['long'], timestamp=timestamp)
            else:
                url = "https://api.darksky.net/forecast/{key}/{lat}," \
                "{long}?units=us".format(
                    key=self._api_key, lat=location['lat'],
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
        _log.info("requesting url: {}".format(url))
        grequest = [grequests.get(url, verify=requests.certs.where(),
                                  headers=self.headers, timeout=3)]
        gresponse = grequests.map(grequest)[0]
        self.add_api_call()
        if gresponse is None:
            raise RuntimeError("get request did not return any "
                               "response")
        try:
            response = jsonapi.loads(gresponse.content)
            return response
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)

    def format_multientry_response(self, location, response, service, timezone):
        """
        Used to extract the data not used by the RPC method, and store it in
        the cache, helping to limit the number of API calls used to obtain data
        :param location: location dictionary to include with cached data
        :param response: Darksky forecast response
        :param service:
        :param timezone: timezone string extracted from Darksky response
        :return: formatted response data by service
        """
        data = []
        generation_time = self.get_generation_time_for_service(service)
        for entry in response['data']:
            entry_time = datetime.datetime.fromtimestamp(
                entry['time'], pytz.timezone(timezone))
            entry_time = entry_time.astimezone(pytz.utc)
            if entry_time > utils.get_aware_utc_now():
                if SERVICES_MAPPING[service]['type'] is 'forecast':
                    data.append([jsonapi.dumps(location), generation_time, entry_time,
                                 jsonapi.dumps(entry)])
                else:
                    data.append([jsonapi.dumps(location), entry_time, jsonapi.dumps(
                        entry)])
        return data

    def query_current_weather(self, location):
        """
        Retrieve data from the Darksky API, return formatted current data and
        store forecast data in cache
        :param location: location dictionary requested by the user
        :return: Timestamp and data for current data from the Darksky API
        """
        darksky_response = self.get_darksky_data(
            'get_current_weather', location)
        if 'currently' not in darksky_response:
            _log.error("Current data not found in Dark Sky response: {}".format(darksky_response))
        current_response = darksky_response.pop('currently')
        # Darksky required attribution
        current_response["attribution"] = "Powered by Dark Sky"
        current_time = datetime.datetime.fromtimestamp(
            current_response['time'],
            pytz.timezone(darksky_response['timezone']))
        current_time = current_time.astimezone(pytz.utc)
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service in SERVICES_MAPPING:
                if service is not 'get_current_weather' and \
                        SERVICES_MAPPING[service]['json_name'] in \
                        darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service]['json_name'])
                    service_data = self.format_multientry_response(
                        location, service_response, service,
                        darksky_response['timezone'])
                    self.store_weather_records(service, service_data)
        return format_timestamp(current_time), current_response

    def get_generation_time_for_service(self, service):
        """
        Calculates generation time of forecast request response. "Next-hour
        minutely forecast data is updated every five minutes. Hourly and daily
        forecast data are updated every hour."
        (https://darksky.net/dev/docs/faq#data-update)
        :param service: requested weather agent service endpoint
        :return: Datetime object representing the timestamp when the weather was
        forecasted
        """
        generation_time = get_aware_utc_now().replace(microsecond=0, second=0)
        # if the update interval for the service is a minute
        if self.get_update_interval(service).total_seconds() / 60 == 1:
            gen_minutes = generation_time.minute / 5 * 5
            generation_time = generation_time.replace(minute=gen_minutes)
        # if the update interval for the service is an hour or greater
        elif self.get_update_interval(service).total_seconds() / 3600 >= 1:
            generation_time = generation_time.replace(minute=0)
        return format_timestamp(generation_time)

    def create_forecast_entry(self, service, location, timestamp, forecast_start):
        """
        Helper method used for removing extraneous data from a forecast request
        response based on request time
        :param service: weather agent service endpoint
        :param location: request location dictionary
        :param timestamp: timestamp for the forecast request. If None, the default forecast result of
         are returned - a minute-by-minute forecast for the next hour (where available), or
         an hour-by-hour forecast for the next 48 hours, or a day-by-day forecast for the next week
        :return: (the last time stamp for which forecast is returned, filtered Dark Sky forecast response)
        """
        darksky_response = self.get_darksky_data(service, location, timestamp)
        forecast_response = darksky_response.pop(
            SERVICES_MAPPING[service]['json_name'])
        forecast_data = []
        last_entry_time = None
        for entry in forecast_response['data']:
            entry_time = datetime.datetime.fromtimestamp(
                entry['time'], pytz.timezone(darksky_response['timezone']))
            entry_time = entry_time.astimezone(pytz.utc)
            if entry_time < forecast_start:
                continue
            if timestamp and entry_time < timestamp:
                continue
            else:
                # Darksky required attribution
                entry["attribution"] = "Powered by Dark Sky"
                forecast_data.append([format_timestamp(entry_time), entry])
                last_entry_time = entry_time
        if not self.performance_mode:
            # if performance mode isn't running we'll be receiving extra data
            # that we can store to help with conserving daily api calls
            for service_code in SERVICES_MAPPING:
                if service_code is not service and \
                        SERVICES_MAPPING[service_code]['json_name'] in \
                        darksky_response:
                    service_response = darksky_response.pop(
                        SERVICES_MAPPING[service_code]['json_name'])
                    if SERVICES_MAPPING[service_code][
                        'type'] is not 'current':
                        service_data = self.format_multientry_response(
                            location, service_response,
                            service_code,
                            darksky_response['timezone'])
                    else:
                        service_data = \
                            [jsonapi.dumps(location),
                             datetime.datetime.fromtimestamp(
                                 service_response['time'],
                                 pytz.timezone(
                                     darksky_response['timezone'])),
                             jsonapi.dumps(service_response)]
                    self.store_weather_records(service_code, service_data)
        return last_entry_time, forecast_data

    def query_forecast_service(self, service, location, quantity, forecast_start):
        """
        Generic method for requesting forecast data from the various RPC
        forecast methods. If the user requests a number of records to return
        greater than the default for the forecast request(7 daily records)
        additional API calls will be made to the Dark Sky Time Machine endpoint.
        If the number of API calls required to fulfill the additional records is
        greater than the amount of available API calls, the user will receive
        only the records returned by the forecast request.
        :param service: forecast service type of weather data to return
        :param location: location dictionary requested during the RPC call
        :param quantity: number of records to return, used to generate
        Time Machine requests after the forecast request
        :param forecast_start: forecast results that are prior to this
         timestamp will be filtered by base weather agent
        :return: Timestamp and data returned by the Darksky weather API response
        """
        # Get as much as we can from the forecast endpoint
        if service not in SERVICES_MAPPING:
            raise RuntimeError("{} is not a service provided by "
                               "Darksky".format(service))
        forecast_data = []
        forecast_time = None
        # get the generation time of the requested forecast service
        generation_time = self.get_generation_time_for_service(service)
        last_available_time, forecast_entry = self.create_forecast_entry(
            service, location, forecast_time, forecast_start)
        forecast_data.extend(forecast_entry)
        remaining_records = quantity - len(forecast_data)
        if remaining_records > 0:
            if self.api_calls_available(remaining_records):
                # Darksky will return 'valid' prediction data AT LEAST 6 months
                # following the current date
                while remaining_records > 0:
                    # Get the next forecast time based on the forecast service. i.e. +1 minute or +1 hour or +1 day
                    _log.debug("last available : Before call {}".format(last_available_time))
                    if service == "get_daily_forecast":
                        # time machine request with 12AM for a date return the previous day.
                        # Simply adding 1 day to last available forecast time gets the right result
                        forecast_time = last_available_time + datetime.timedelta(days=1)
                    else:
                        forecast_time, _ = get_forecast_start_stop(last_available_time, 1, service)

                    last_available_time, forecast_entry = self.create_forecast_entry(
                        service, location, forecast_time, forecast_start)
                    forecast_data.extend(forecast_entry)
                    remaining_records -= len(forecast_entry)
            else:
                raise RuntimeError('Insufficient calls available for additional'
                                   'data requests')
        return generation_time, forecast_data

    @RPC.export
    def get_minutely_forecast(self, locations, minutes=60):
        """
        RPC method for getting time series forecast weather data minute by
        minute. Dark Sky does not provide more than 1 hour into the future of
        minutely forecast data.
        :param locations: list of location dictionaries from the RPC call
        :param minutes: Number of minutes of weather data to be returned
        :return: List of minutely forecast weather dictionaries
        """
        if minutes > 60:
            minutes = 60
        return self.get_forecast_by_service(
            locations, 'get_minutely_forecast', 'minute', minutes)

    @RPC.export
    def get_hourly_forecast(self, locations, hours=48):
        """
        Overload of get_hourly_forecast method of base weather agent - sets
        default hours to 48 as this is the quantity provided by a Dark Sky
        forecast request
        :param locations: ist of location dictionaries from the RPC call
        :param hours: Number of hours of weather data to be returned
        :return: Dark Sky forecast data by the hour
        """
        return self.get_forecast_by_service(locations, 'get_hourly_forecast',
                                            'hour', hours)

    @RPC.export
    def get_daily_forecast(self, locations, days=7):
        """
        RPC method for getting time series forecast weather data by full day.
        :param locations: list of location dictionaries from the RPC call
        :param days: Number of minutes of weather data to be returned
        :return: List of daily forecast weather dictionaries
        """
        return self.get_forecast_by_service(
            locations, 'get_daily_forecast', 'day', days)

    def generate_response_error(self, url, response_code):
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
                "Request ({}) rejected by remote API: Remote API returned "
                "Code {}".format(url, response_code))
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
