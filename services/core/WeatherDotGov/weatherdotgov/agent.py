# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

__docformat__ = 'reStructuredText'

import logging
import re
import sys
import grequests
import datetime
from importlib.resources import files as get_resource_files
from volttron.platform.agent.base_weather import BaseWeatherAgent
from volttron.platform.agent import utils
from volttron.utils.docs import doc_inherit
from volttron.platform import jsonapi


# requests should be imported after grequests
# as grequests monkey patches ssl and requests imports ssl
import requests

__version__ = "2.0.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

SERVICE_HOURLY_FORECAST = "get_hourly_forecast"

LAT_LONG_REGEX = re.compile(
    r"^-?[0-9]{1,3}(\.[0-9]{1,4})?,( |t?)-?[0-9]{1,3}(\.[0-9]{1,4})?$")
STATION_REGEX = re.compile("^[Kk][a-zA-Z]{3}$")
WFO_REGEX = re.compile("^[A-Z]{3}$")


def weather_agent(config_path, **kwargs):
    """
    Used for instantiating the WeatherDotGov agent.
    :param config_path: string formatted file path to use for configuring the
    agent.
    :param kwargs: keyword arguments passed during instantiation.
    :return: an instance of the WeatherDotGov Agent
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)
    _log.debug("config_dict before init: {}".format(config_dict))
    utils.update_kwargs_with_config(kwargs, config_dict)
    return WeatherDotGovAgent(**kwargs)


class WeatherDotGovAgent(BaseWeatherAgent):
    """
    Concrete implementation of the base weather agent for querying the
    NOAA/weather.gov weather api.
    """

    def __init__(self, **kwargs):
        super(WeatherDotGovAgent, self).__init__(**kwargs)
        self.headers = {"Accept": "application/json",
                        "Accept-Language": "en-US"
                        }
        self.remove_service("get_hourly_historical")

    def get_update_interval(self, service_name):
        """
        Get the timedelta between api service updates.
        :param service_name: name of service stored in api_services
        :return: datetime.timedelta object representing the time between
        the api's service updates
        """
        if service_name == "get_current_weather":
            return datetime.timedelta(hours=1)
        elif service_name == "get_hourly_forecast":
            return datetime.timedelta(hours=1)
        else:
            return None

    def get_point_name_defs_file(self):
        """
        Constructs the point name mapping dict from the
        mapping csv.
        :return: dictionary containing a mapping of service point
        names to standard point names with optional
        """
        # returning resource file instead of stream, as csv.DictReader require file path or file like object opened in
        # text mode.
        return str(get_resource_files("weatherdotgov").joinpath("data/name_mapping.csv"))

    def get_location_string(self, location):
        """
        Generic conversion of location dictionary into corresponding string
        format for request url.
        :param location: location dictionary formatted as for a specific
        request.
        :return: string representation of location dictionary for request url.
        """
        if location.get('lat') and location.get('long'):
            formatted_location = self.get_lat_long_str(location)
            return formatted_location
        if location.get('station'):
            formatted_location = self.get_station_str(location)
            return formatted_location
        elif location.get("wfo") and location.get("x") and location.get("y"):
            formatted_location = self.get_gridpoints_str(location)
            return formatted_location
        else:
            raise ValueError("Invalid location {}".format(location))

    def get_api_description(self, service_name):
        """
        Provides the api description string for a given api service.
        Primarily used during concrete agent startup.
        :param service_name: name of the api service
        :return: string describing the function of the api endpoint, along with
        rpc call usage for the weather agent.
        """
        if service_name == "get_current_weather":
            return "Provides current weather observations by station via RPC " \
                   "(Requires {'station': <station id>}"
        elif service_name == "get_hourly_forecast":
            return "Provides <hours> (optional) hours of forecast " \
                   "predictions by lat/long or gridpoint location " \
                   "via RPC (Requires {'wfo': <wfo string>, 'x': <x " \
                   "coordinate>, 'y': <y coordinate>} or" \
                   "{'lat': <latitude>, 'long': <longitude>}"
        else:
            raise RuntimeError(
                "Service {} is not implemented by weather.gov.".format(
                    service_name))

    @staticmethod
    def get_lat_long_str(location_dict):
        """
        Converts a location dictionary using lat/long format into string
        format to be used in a request url.
        :param location_dict: location dictionary for the upcoming request.
        Expects lat/long
        :return: url formatted location string
        """
        return "{},{}".format(location_dict.get("lat"),
                              location_dict.get("long"))

    @staticmethod
    def get_station_str(location_dict):
        """
        Converts a location dictionary using station format into string
        format to be used in a request url.
        :param location_dict: location dictionary for the upcoming request.
        Expects station id
        :return: url formatted location string
        """
        return location_dict.get("station")

    @staticmethod
    def get_gridpoints_str(location_dict):
        """
        Converts a location dictionary using gridpoints format into string
        format to be used in a request url.
        :param location_dict: location dictionary for the upcoming request.
        Expects gridpoint format
        :return: url formatted location string
        """
        return "{}/{},{}".format(location_dict.get("wfo"),
                                 location_dict.get("x"), location_dict.get("y"))

    def validate_location(self, service_name, location):
        """
        Intermediate method for validating location dicts passed by rpc
        calls. Validity depends on the service being
        requested.
        :param service_name: name of the api service which the location
        dictionary is intended to be used for.
        :param location: location dictionary to validate for the api service
        :return: boolean indicating whether the location/service combination
        is valid for the weather api.
        """
        if service_name == "get_current_weather":
            return self.validate_location_formats(("station",), location)
        else:
            return self.validate_location_formats(("gridpoints", "lat/long", "station"),
                                                  location)

    def validate_location_formats(self, accepted_formats, location):
        """
        Regular expression comparision to validate the various location
        dictionary formats
        :param accepted_formats: string representations of the acceptable
        location formats for an api service
        :param location: location dictionary to validate for the api service
        :return: boolean representing the validity of the location
        """
        if ("lat/long" in accepted_formats) and (
                location.get('lat') and location.get('long')):
            location_string = self.get_lat_long_str(location)
            if LAT_LONG_REGEX.match(location_string):
                return True
        elif ("station" in accepted_formats) and (location.get('station')):
            location_string = self.get_station_str(location)
            if STATION_REGEX.match(location_string):
                return True
            else:
                _log.debug("station did not match regex")
                return False

        elif ("gridpoints" in accepted_formats) and (
                location.get("wfo") and location.get("x") and location.get(
                "y")):
            if WFO_REGEX.match(location.get("wfo")) and (
                    1 <= len(str(location.get("x"))) <= 3) and \
                    (1 <= len(str(location.get("y"))) <= 3):
                return True
        else:
            return False

    @staticmethod
    def generate_response_error(url, response_code):
        """
        raises a descriptive runtime error based on the response code
        returned by a service.
        :param url: actual url used for requesting data from weather.gov
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

    @doc_inherit
    def query_current_weather(self, location):
        """
        Returns current hourly weather data provided by the api via an http
        request.
        :param location: currently accepts station id (K followed by 3
        letters, case insensitive) or
        lat/long (up to 4 decimals) location dictionary formats
        :return: time of data observation as a timestamp string,
        data dictionary containing weather data points
        """
        if location.get('station'):
            formatted_location = self.get_location_string(location)
            url = "https://api.weather.gov/stations/{}/" \
                  "observations/latest".format(formatted_location)
        else:
            raise ValueError('Invalid location. Expected format is:'
                             '{"station":"station_id_value"}')
        gresponse = self.make_web_request(url)
        try:
            response = jsonapi.loads(gresponse.content)
            properties = response["properties"]
            observation_time = properties["timestamp"]
            return observation_time, properties
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)

    @doc_inherit
    def query_forecast_service(self, service, location, quantity, forecast_start):
        """
        Returns forecast weather from Weather.gov for requested forecast service
        :param service: forecast service to query, Weather.gov provides only
        hourly
        :param location: currently accepts lat/long
        :param quantity: As Weather.gov offers only a set quantity of data, this
         is ignored
        :param forecast_start: forecast results that are prior to this
         timestamp will be filtered by base weather agent
        :return: generation time, forecast records
        """
        if service is SERVICE_HOURLY_FORECAST:
            generation_time, data = self.query_hourly_forecast(location)
            return generation_time, data
        else:
            raise RuntimeError("Weather.Gov supports hourly forecast requests "
                               "only")

    @doc_inherit
    def query_hourly_forecast(self, location):
        """
        Returns hourly forecast weather data provided by the api via an http
        request.
        :param location: currently accepts lat/long location dictionary
        format only
        :return: time of forecast prediction as a timestamp string,
        and a list of
        """

        # TODO: cache mapping between station id - lat/long - wfo,x,y to improve performance
        if location.get('station'):
            # Two step process.
            # 1. get lat,long for station id
            url = "https://api.weather.gov/stations/{}".format(
                location.get('station').strip())
            _log.info(f"STATIONS url:{url}")
            gresponse = self.make_web_request(url)
            try:
                _log.info(f"{gresponse.content}")
                response = jsonapi.loads(gresponse.content)
                long_lat_list = response["geometry"]["coordinates"]
                # . get the url to query hourly forecast data -i.e. get wfo,x, y based on  lat, long
                url = self.get_forecast_url({"lat": long_lat_list[1], 'long': long_lat_list[0]})
            except ValueError:
                self.generate_response_error(url, gresponse.status_code)
        elif location.get('lat') and location.get('long'):
            #  get the url to query hourly forecast data -i.e. get wfo,x, y for give lat, long
            url = self.get_forecast_url(location)
        elif location.get("wfo") and location.get("x") and location.get("y"):
            formatted_location = self.get_gridpoints_str(location)
            url = "https://api.weather.gov/" \
                  "gridpoints/{}/forecast/hourly".format(formatted_location)
        else:
            raise ValueError("Improperly formatted station ID was passed.")
        _log.debug("Request Url: {}".format(url))
        gresponse = self.make_web_request(url)
        return self.extract_forecast_data(url, gresponse)

    def get_forecast_url(self, location):
        formatted_location = self.get_location_string(location)
        url = "https://api.weather.gov/points/{}".format(
            formatted_location)
        gresponse = self.make_web_request(url)
        try:
            _log.info(f" after get forecast url for lat lon: response is{gresponse.content}")
            response = jsonapi.loads(gresponse.content)
            url = response["properties"]["forecastHourly"]
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)
        return url

    def make_web_request(self, url):
        response = requests.get(url, headers=self.headers, verify=requests.certs.where())
        if response is None:
            raise RuntimeError("get request did not return any "
                               "response")
        return response

    def extract_forecast_data(self, url, gresponse):
        try:
            response = jsonapi.loads(gresponse.content)
            data = []
            properties = response["properties"]
            generation_time = properties["generatedAt"]
            periods = properties["periods"]
            for period in periods:
                forecast_time = period["startTime"]
                record = [forecast_time, period]
                data.append(record)
            return generation_time, data
        except ValueError:
            self.generate_response_error(url, gresponse.status_code)

    def query_hourly_historical(self, location, start_date, end_date):
        """
        Unimplemented method stub
        :param location: no format currently determined for history.
        :param start_date: Starting date for historical weather period.
        :param end_date: Ending date for historical weather period.
        :return: NotImplementedError
        """
        raise NotImplementedError


def main():
    """" Main entry point for the agent."""
    try:
        utils.vip_main(weather_agent, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    """Entry point for script"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
