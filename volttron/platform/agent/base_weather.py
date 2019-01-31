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

import logging
import pint
import json
import csv
import sqlite3
import datetime
from functools import wraps
from abc import abstractmethod
from gevent import get_hub
from volttron.platform.agent.utils import fix_sqlite3_datetime, \
    get_aware_utc_now, format_timestamp, process_timestamp, \
    parse_timestamp_string
from volttron.platform.vip.agent import *
from volttron.platform.async import AsyncCall
from volttron.platform.messaging import headers
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_GOOD,
                                                Status)

POLL_TOPIC = "weather/poll/current/{}"

SERVICE_HOURLY_FORECAST = "get_hourly_forecast"

SERVICE_CURRENT_WEATHER = "get_current_weather"

SERVICE_HOURLY_HISTORICAL = "get_hourly_historical"

CREATE_STMT_CURRENT = """CREATE TABLE {table}
                        (ID INTEGER PRIMARY KEY ASC,
                         LOCATION TEXT NOT NULL,
                         OBSERVATION_TIME TIMESTAMP NOT NULL, 
                         POINTS TEXT NOT NULL);"""

CREATE_STMT_FORECAST = """CREATE TABLE {table}
                        (ID INTEGER PRIMARY KEY ASC,
                         LOCATION TEXT NOT NULL,
                         GENERATION_TIME TIMESTAMP NOT NULL,
                         FORECAST_TIME TIMESTAMP NOT NULL,
                         POINTS TEXT NOT NULL);"""

CACHE_READ_ERROR = "Cache read failed"
CACHE_WRITE_ERROR = "Cache write failed"
CACHE_FULL = "cache_full"
WEATHER_WARN = "weather_warnings"
WEATHER_RESULTS = "weather_results"
WEATHER_ERROR = "weather_error"
__version__ = "2.0.0"

_log = logging.getLogger(__name__)

HEADER_NAME_DATE = headers.DATE
HEADER_NAME_CONTENT_TYPE = headers.CONTENT_TYPE

# Register a better datetime parser in sqlite3.
fix_sqlite3_datetime()


class BaseWeatherAgent(Agent):
    """
    Base class for building concrete weather agents
    """

    def __init__(self,
                 database_file="weather.sqlite",
                 api_key=None,
                 max_size_gb=None,
                 poll_locations=None,
                 poll_interval=None,
                 poll_topic_suffixes=None,
                 **kwargs):
        # Initial agent configuration
        try:
            super(BaseWeatherAgent, self).__init__(**kwargs)
            self._database_file = database_file
            self._async_call = AsyncCall()
            self._api_key = api_key
            self._max_size_gb = max_size_gb
            self.poll_locations = poll_locations
            self.poll_interval = poll_interval
            self.poll_topic_suffixes = poll_topic_suffixes
            self.do_polling = False
            self.poll_greenlet = None
            self._cache = None
            self.cache_read_error = False
            self.cache_write_error = False

            self._default_config = \
                {
                    "database_file": "weather.sqlite",
                    "api_key": self._api_key,
                    "max_size_gb": self._max_size_gb,
                    "poll_locations": self.poll_locations,
                    "poll_interval": self.poll_interval,
                    "poll_topic_suffixes": self.poll_topic_suffixes
                }
            self.unit_registry = pint.UnitRegistry()
            self.point_name_mapping = self.parse_point_name_mapping()
            self._api_services = {
                SERVICE_CURRENT_WEATHER:
                    {"type": "current",
                     "update_interval": None,
                     "description": "Params: locations ([{type: value},...])"
                     },
                SERVICE_HOURLY_FORECAST:
                    {"type": "forecast",
                     "update_interval": None,
                     "description": "Params: locations ([{type: value},...])"
                     },
                SERVICE_HOURLY_HISTORICAL:
                    {"type": "history",
                     "update_interval": None,
                     "description": "Params: locations "
                                    "([{type: value},..]), "
                                    "start_date (date), end_date(date)"
                     }
            }

            self.vip.config.set_default("config", self._default_config)
            self.vip.config.subscribe(self._configure,
                                      actions=["NEW", "UPDATE"],
                                      pattern="config")
        except Exception as e:
            _log.error("Failed to load weather agent settings.")
            self.vip.health.set_status(STATUS_BAD,
                                       "Failed to load weather agent settings."
                                       "Error: {}".format(e.message))

    # Configuration methods

    def register_service(self, service_function_name, interval, service_type,
                         description=None):
        """Called in a weather agent's __init__ function to add api services
        to the api services dictionary.
        :param service_function_name: function call name for an api feature
        :param interval: datetime timedelta object describing the length of
        time between api updates.
        :param service_type: the string "history", "current", or "forecast".
        This
                     determines the structure of the cached data.
        :param description: optional description string describing the method's
        usage.
        """
        if service_type == "history":
            if interval:
                raise ValueError("History object does not utilize an interval.")
        elif not isinstance(interval, datetime.timedelta):
            raise ValueError("Interval must be a valid datetime "
                             "timedelta object.")
        if service_type not in ("history", "current", "forecast"):
            raise ValueError("Invalid service type. It should be history, "
                             "current, or forecast")
        if description and not isinstance(description, str):
            raise ValueError("description is expected as a string describing "
                             "the service function's usage.")
        self._api_services[service_function_name] = \
            {"update_interval": interval,
             "type": service_type,
             "description": description}

    def remove_service(self, service_function_name):
        """
        Used to remove services from the api_services dictionary which aren't
        implemented in a concrete instance.
        :param service_function_name: a function call name for an api feature
        to be removed.
        """
        if service_function_name in self._api_services:
            self._api_services.pop(service_function_name)
        else:
            raise ValueError("service {} does not exist".format(
                service_function_name))

    def validate_location_dict(self, service_name, location):
        """
        Error checking and format validation for a location dictionary
        corresponding to an api service call.
        :param service_name: name of the api service the dictionary is
        intended to be used for.
        :param location: location dictionary to be validated
        :return: location dictionary, includes "weather_error" if the
        location is invalid.
        """
        record_dict = None
        if not isinstance(location, dict):
            record_dict = {"location": location,
                           WEATHER_ERROR: "Invalid location format. "
                                             "Location should be  "
                                             "specified as a dictionary"}

        elif not self.validate_location(service_name, location):
            record_dict = location.copy()
            record_dict[WEATHER_ERROR] = "Invalid location"
        return record_dict

    @abstractmethod
    def validate_location(self, service_name, location):
        """
        Abstract method for generic location validation
        :param service_name: name of service the location dictionary is
        intended for.
        :param location: location dictionary to be validated for a service.
        :return: boolean representing whether the location is in fact valid.
        """
        pass

    @abstractmethod
    def get_update_interval(self, service_name):
        """
        Abstract method used by concrete agents to set the update intervals
        for the various api services.
        :param service_name: name of service to retrieve the update interval for
        :return: datetime.timestamp object representing the time between
        weather data updates from the weather api.
        """
        pass

    @abstractmethod
    def get_api_description(self, service_name):
        """
        Abstract method used by concrete agents to set the description for
        the various api services.
        :param service_name:service_name: name of service to retrieve the
        description for
        :return: string description of the api service usage
        """
        pass

    def set_update_interval(self, service_name, interval):
        """
        Updates the api service dictionary with the datetime.timedelta
        specifying the length of time between api updates
        :param service_name: a function call name for an api feature to be
        updated
        :param interval: datetime timedelta object specifying the length of
        time between api updates
        """
        if not isinstance(interval, datetime.timedelta):
            raise ValueError(
                "interval must be a valid datetime timedelta object.")
        if service_name in self._api_services:
            if self._api_services[service_name]["type"] == "history":
                raise ValueError(
                    "historical data does not utilize an update interval.")
            self._api_services[service_name]["update_interval"] = interval
        else:
            raise ValueError(
                "{} not found in api features.".format(service_name))

    def set_api_description(self, service_name, description):
        """
        Updates the api service dictionary with the api feature's string
        description
        :param service_name: a function call name for an api feature to be
        updated
        :param description: string description describing purpose and usage
        of an api feature
        """
        if not isinstance(description, str):
            raise ValueError("description expected as string")
        if service_name in self._api_services:
            self._api_services[service_name]["description"] = description
        else:
            raise ValueError(
                "{} not found in api features.".format(service_name))

    def update_default_config(self, config):
        """
        May be called by implementing classes to add to the default
        configuration for its own use.
        :param config: configuration dictionary
        """
        self._default_config.update(config)
        self.vip.config.set_default("config", self._default_config)

    @abstractmethod
    def get_point_name_defs_file(self):
        """
        :return: file path of a csv containing a mapping of
        Service_Point_Name to an optional Standard_Point_Name.
        May also optionally provide Service_Units (a Pint-parsable unit name
        for a point, provided by the service) to
        Standardized_Units (units specified for the Standard_Point_Name by
        the CF standards). Should return None if
        the concrete agent does not require point name mapping and/or unit
        conversion.
        """

    def parse_point_name_mapping(self):
        """
        Parses point name mapping, which should contain a mapping of service
        points to standardized points, with specified units.
        """
        point_name_mapping = {}
        try:
            mapping_file = self.get_point_name_defs_file()
        except Exception as e:
            _log.warn("Error loading mapping file ({})".format(e))
            return None
        if mapping_file:
            try:
                if isinstance(mapping_file, str):
                    mapping_file = open(mapping_file)
                    # else assume it is a file like object
                config_dict = csv.DictReader(mapping_file)
                for map_item in config_dict:
                    service_point_name = map_item.get("Service_Point_Name")
                    if service_point_name:
                        standard_point_name = map_item.get(
                            "Standard_Point_Name")
                        standardized_units = map_item.get("Standardized_Units")
                        service_units = map_item.get("Service_Units")
                        point_name_mapping[service_point_name] = \
                            {"Standard_Point_Name": standard_point_name,
                             "Standardized_Units": standardized_units,
                             "Service_Units": service_units}
            except IOError as error:
                _log.error("Error parsing standard point name mapping: "
                           "{}".format(error))
                raise ValueError("Error parsing point name mapping from file "
                                 "{}".format(error))
            finally:
                mapping_file.close()
        return point_name_mapping

    def _configure(self, config_name, actions, contents):
        """
        Handles most of the configuration of weather agent implementations
        :param config_name: unused parameter, required by config store
        :param actions: unused parameter, required by config store
        :param contents: Configuration dictionary used to specify operational
        parameters for the agent.
        """
        self.vip.heartbeat.start()
        _log.info("Configuring weather agent.")
        config = self._default_config.copy()
        config.update(contents)

        max_size_gb = config.get("max_size_gb")
        try:
            if max_size_gb is not None:
                self._max_size_gb = float(max_size_gb)
        except ValueError:
            _log.warn("Invalid value for max_size_gb: {} "
                      "defaulting to 1GB".format(max_size_gb))
            self._max_size_gb = 1

        self._api_key = config.get("api_key")
        self.poll_locations = config.get("poll_locations")
        self.poll_interval = config.get("poll_interval")
        self.poll_topic_suffixes = config.get("poll_topic_suffixes")
        try:
            self.validate_poll_config()
            self.configure(config)
        except Exception as e:
            _log.error("Failed to load weather agent settings with error:"
                       "{}".format(e.message))
            self.vip.health.set_status(STATUS_BAD,
                                       "Configuration of weather agent failed "
                                       "with error: {}".format(e.message))
        else:
            _log.debug("Configuration successful")
            try:
                self._cache = WeatherCache(self._database_file,
                                           api_services=self._api_services,
                                           max_size_gb=self._max_size_gb)
                self.vip.health.set_status(STATUS_GOOD,
                                           "Configuration of weather agent "
                                           "successful")
            except sqlite3.OperationalError as error:
                _log.error(error.message)
                self.vip.health.set_status(STATUS_BAD, "Cache failed to start "
                                                       "during configuration")

            if self.do_polling:
                if self.poll_greenlet:
                    self.poll_greenlet.kill()
                self.poll_greenlet = self.core.periodic(self.poll_interval,
                                                        self.poll_for_locations)

    def validate_poll_config(self):
        """
        Ensures that polling settings have been properly configured.
        :return: boolean indicating whether the polling options provided were
        properly formatted.
        """
        if self.poll_locations:
            if not self.poll_interval:
                err_msg = "poll_interval is mandatory configuration when " \
                          "poll_locations are specified"
                raise ValueError(err_msg)
            if (self.poll_topic_suffixes is not None and
                    (not isinstance(self.poll_topic_suffixes, list) or
                     len(self.poll_topic_suffixes) < len(self.poll_locations))):
                err_msg = "poll_topic_suffixes, if set, should be a list of " \
                          "string with the same length as poll_locations. If " \
                          "it is not set results for all locations will be " \
                          "published to a single topic(" \
                          "weather/poll/current/all). If it is a list, " \
                          "each location's result will be published to the " \
                          "corresponding topic (" \
                          "weather/poll/current/<topic_suffix>)"
                raise ValueError(err_msg)
            self.do_polling = True

    def configure(self, configuration):
        """Optional, may be implemented by a concrete implementation to add
        support for the configuration store.
        Values should be stored in this function only.

        The process thread is stopped before this is called if it is running.
        It is started afterwards.
        :param configuration:
        """
        pass

    # RPC, helper and abstract methods to be used by concrete
    # implementations of the weather agent

    @RPC.export
    def get_version(self):
        """
        Provides the current version of the agent.
        :return: current version number in string format.
        """
        return __version__

    @RPC.export
    def get_api_features(self):
        """
        Provides api features and corresponding descriptions for users of the
        weather agent.
        :return: dictionary formatted as {function call: description string}
        """
        features = {}
        for service_name in self._api_services:
            features[service_name] = \
                self._api_services[service_name]["description"]
        return features

    @RPC.export
    def get_current_weather(self, locations):
        """
        RPC method returning current weather data for each location provided.
        Will provide cached data for efficiency if
        available.
        :param locations: List of location dictionary objects.
        :return: list of dictionaries containing weather data for each location.
                 result dictionary would contain all location details passed
                 as input. Weather data results  will be returned in the key
                 'weather_results'. In case of errors, error message will be
                 in the key 'weather_error'.

                 For example:
                 Input: [{"zipcode":"99353"}, {"zipcode":"invalid zipcode"},
                         {"zipcode":"99354"}]
                 Output:
                 [{'observation_time': '2018-11-15T20:53:00.000000+00:00',
                   'zipcode': '99353',
                   'weather_results':
                       { 'dew_point_temperature': -6.099999999999966,
                         'wind_speed_of_gust': {'qualityControl': 'qc:Z',
                                              'unitCode': 'unit:m_s-1',
                                              'value': None
                                              },
                         'textDescription': 'Mostly Cloudy',
                         'timestamp': '2018-11-15T20:53:00+00:00'
                         }
                   },
                  {'zipcode': 'invalid zipcode',
                    'weather_error': "Invalid location"
                   },
                  {'zipcode': '99354',
                   'weather_error': 'Remote API returned
                                     invalid response (code 500)'
                   }
                 ]

        """
        result = []
        for location in locations:
            record_dict = self.validate_location_dict(SERVICE_CURRENT_WEATHER,
                                                      location)
            if record_dict:
                result.append(record_dict)
                continue
            # Attempt getting from cache
            record_dict = self.get_cached_current_data(location)
            cache_warning = record_dict.get(WEATHER_WARN)
            # if there was no data in cache or if data is old, query api
            if not record_dict.get(WEATHER_RESULTS):
                _log.debug("Current weather data from api")
                record_dict = self.get_current_weather_remote(location)
                if cache_warning:
                    warnings = record_dict.get(WEATHER_WARN, [])
                    warnings.extend(cache_warning)
                    record_dict[WEATHER_WARN] = warnings

            result.append(record_dict)
        return result

    def get_cached_current_data(self, location):
        """
        Retrieves current weather data stored in cache if it exists and is
        current (the timestamp is within the update
        interval) for the location
        :param location: location to retrieve current stored data for.
        :return: current weather data dictionary
        """
        result = location.copy()
        try:
            observation_time, data = \
                self._cache.get_current_data(SERVICE_CURRENT_WEATHER,
                                             json.dumps(location))
            if observation_time and data:
                interval = self._api_services[SERVICE_CURRENT_WEATHER][
                    "update_interval"]
                _log.debug("update interval is {}".format(interval))
                # ts in cache is tz aware utc
                current_time = get_aware_utc_now()
                next_update_at = observation_time + interval
                # if observation time is within the update interval
                if current_time < next_update_at:
                    result["observation_time"] = \
                        format_timestamp(observation_time)
                    result[WEATHER_RESULTS] = json.loads(data)
        except Exception as error:
            bad_cache_message = "Weather agent failed to read from " \
                                "cache"
            self.vip.health.set_status(STATUS_BAD,
                                       bad_cache_message)
            status = Status.from_json(self.vip.health.get_status_json())
            self.vip.health.send_alert(CACHE_READ_ERROR, status)
            _log.error("{}. Exception:{}".format(bad_cache_message,
                                                 error.message))
            self.cache_read_error = True
            result[WEATHER_WARN] = [bad_cache_message]
        else:
            if self.cache_read_error:
                self.vip.health.set_status(STATUS_GOOD)
                self.cache_read_error = False
        return result

    def get_current_weather_remote(self, location):
        """
        Retrieves current weather data for a location from the remote api
        service provider
        :param location: location for which to retrieve current weather data
        from the api
        :return: dictionary of weather data, or containing an error message
        if the api call failed. Example - input: output:
        """
        result = location.copy()
        try:
            observation_time, data = self.query_current_weather(
                location)
            observation_time, oldtz = process_timestamp(
                observation_time)
            if self.point_name_mapping:
                _log.debug("Got point name mapping")
                data = self.apply_mapping(data)
            if observation_time is not None:
                storage_record = [json.dumps(location),
                                  observation_time,
                                  json.dumps(data)]
                try:
                    self.store_weather_records(SERVICE_CURRENT_WEATHER,
                                               storage_record)
                except Exception:
                    bad_cache_message = "Weather agent failed to write to " \
                                        "cache"
                    result[WEATHER_WARN] = [bad_cache_message]
                result["observation_time"] = \
                    format_timestamp(observation_time)
                result[WEATHER_RESULTS] = data
            else:
                result[WEATHER_ERROR] = "Weather api did not " \
                                          "return any records"
        except Exception as error:
            _log.error(error)
            result[WEATHER_ERROR] = error.message
        return result

    @abstractmethod
    def query_current_weather(self, location):
        """
        Abstract method for sending/receiving requests for current weather
        data from an api service
        :param location: location for which to query the remote api
        :return: dictionary containing a single record of current weather data
        """

    @RPC.export
    def get_hourly_forecast(self, locations, hours=24):
        """
        RPC method returning hourly forecast weather data for each location
        provided. Will provide cached data for
        efficiency if available.
        :param locations: list of location dictionaries for which to return
        weather data
        :param hours: number of hours worth of weather data to return for the
        request
        :return: list of dictionaries containing weather data for each location.
                 result dictionary would contain all location details passed
                 as input in addition to results. Weather data results  will be
                 returned in the key  'weather_results'. value of
                 'weather_results' will be in the format
                 [[<forecast time>, <dictionary of data returned for
                 that forecast time>], [<forecast time>, <dictionary of data
                 returned for that forecast time],...]
                 If the weather api did not return the requested number of
                 records, in addition to 'weather_results' there will also be a
                 'weather_warn' key.
                 In case of errors, error message will be in the key
                 'weather_error'.


                 For example:
                 Input: [{'lat': 39.0693, 'long': -94.6716},
                         {"zipcode":"invalid location. say only lat/long
                         allowed for forecast"}]
                 Output:

                 [
                     #Result for first location
                     {'lat': 39.0693,
                       'generation_time': '2018-11-15T22:00:38.000000+00:00',
                      'weather_results':
                           [
                               [ '2018-11-15T17:00:00-06:00',
                                 {u'': None, 'wind_speed':'6 mph', 'name': u'',
                                  'temperatureUnit': 'F', 'number': 2,
                                  'detailedForecast': u'', 'isDaytime': True,
                                  'air_temperature': 44,
                                  'startTime': '2018-11-15T17:00:00-06:00',
                                  'wind_from_direction': 'SW',
                                  'endTime': '2018-11-15T18:00:00-06:00',
                                  'shortForecast': 'Sunny',...
                                  }
                               ],
                               ['2018-11-15T18:00:00-06:00',
                                 {u'': None, 'wind_speed': '6 mph', 'name': u'',
                                 'temperatureUnit': 'F', 'number': 3,
                                 'detailedForecast': u'',
                                 'startTime': '2018-11-15T18:00:00-06:00',
                                 'endTime': '2018-11-15T19:00:00-06:00',..
                                 }
                               ], ... total = number of hours requested or
                               defaults to 24 hours.
                           ],
                      'long': -94.6716
                     },
                     #Result for second location
                     {"zipcode":"invalid location. say only lat/long
                         allowed for forecast",
                      WEATHER_ERROR: "Invalid location"
                     }
                  ]

        """
        request_time = get_aware_utc_now()
        result = []
        for location in locations:
            record_dict = self.validate_location_dict(SERVICE_HOURLY_FORECAST,
                                                      location)
            if record_dict:
                result.append(record_dict)
                continue

            # check if we have enough recent data in cache
            record_dict = self.get_cached_hourly_forecast(location, hours,
                                                          request_time)
            cache_warning = record_dict.get(WEATHER_WARN)
            # if cache didn't work out query remote api
            if not record_dict.get(WEATHER_RESULTS):
                _log.debug("forecast weather from api")
                record_dict = self.get_remote_hourly_forecast(location,
                                                              hours,
                                                              request_time)
                if cache_warning:
                    warnings = record_dict.get(WEATHER_WARN, [])
                    warnings.extend(cache_warning)
                    record_dict[WEATHER_WARN] = warnings
                _log.debug("record_dict from remote : {}".format(record_dict))
            result.append(record_dict)

        return result

    def get_cached_hourly_forecast(self, location, hours, request_time):
        """
        Retrieves forecast weather data stored in cache if it exists and is
        current (the generation timestamp is
        within the update interval) for the location
        :param location: location for which to retrieve forecast weather records
        :param hours: number of hours worth of data to include with each
        location's records
        :param request_time: time at which the request for data was made,
        used for checking if the data is current.
        :return: dictionary of forecast weather data for the location
        """
        record_dict = location.copy()
        interval = \
            self._api_services[SERVICE_HOURLY_FORECAST]["update_interval"]
        # format [(generation_time, forecast_time, points), ...]
        try:
            most_recent_for_location = \
                self._cache.get_forecast_data(SERVICE_HOURLY_FORECAST,
                                              json.dumps(location),
                                              hours, request_time)
            location_data = []
            if most_recent_for_location:
                _log.debug(" from cache")

                generation_time = most_recent_for_location[0][0]
                next_update_at = generation_time + interval
                _log.debug("request_time {}".format(request_time))
                _log.debug("next_update_at {}".format(next_update_at))
                _log.debug("generation_time time {}".format(generation_time))

                if request_time < next_update_at and \
                        len(most_recent_for_location) >= hours:
                    # Enough to just check for length since cache is querying
                    # records between expected forecast start and end time
                    i = 0
                    while i < hours:
                        record = most_recent_for_location[i]
                        # record = (forecast time, points)
                        entry = [format_timestamp(record[1]),
                                 json.loads(record[2])]
                        location_data.append(entry)
                        i = i + 1
                    record_dict["generation_time"] = format_timestamp(
                        generation_time)
                    record_dict[WEATHER_RESULTS] = location_data
        except Exception as error:
            bad_read_message = "Weather agent failed to read from cache"
            self.vip.health.set_status(STATUS_BAD,
                                       bad_read_message)
            status = Status.from_json(self.vip.health.get_status_json())
            self.vip.health.send_alert(CACHE_READ_ERROR, status)
            _log.error("{}. Exception:{}".format(bad_read_message,
                                                 error.message))
            record_dict[WEATHER_WARN] = [bad_read_message]
            self.cache_read_error = True
        else:
            if self.cache_read_error:
                self.vip.health.set_status(STATUS_GOOD)
                self.cache_read_error = False
                
        return record_dict

    def get_remote_hourly_forecast(self, location, hours, request_time):
        """
        Retrieves forecast weather data for a location from the remote api
        service provider
        :param location: location for which to retrieve forecast weather records
        :param hours: number of hours worth of data to include with each
        location's records
        :param request_time: time at which the request for data was made,
        used for checking if the data is current.
        :return: dictionary containing forecast weather data, or an error
        message if the request failed.
        """
        result = location.copy()
        try:
            # query for maximum number of hours so that we can cache it
            # also makes retrieval from cache simpler
            generation_time, response = self.query_hourly_forecast(
                location)
            _log.debug("Current time {}".format(datetime.datetime.utcnow()))
            _log.debug(" response from forecast generation_time : {}".format(
                generation_time))
            _log.debug(" response from forecast : {}".format(response[0]))
            if not generation_time:
                # in case api does not return details on when this
                # forecast data was generated
                generation_time = datetime.datetime.utcnow()
            else:
                generation_time, oldtz = process_timestamp(
                    generation_time)
            _log.debug(" generation time after process : {}".format(
                generation_time))
            if self.point_name_mapping:
                response = [[item[0],
                             self.apply_mapping(item[1])] for item in response]

            storage_records = []
            location_data = []

            i = 0
            for item in response:
                # item contains (forecast time, points)
                if item[0] is not None and item[1] is not None:
                    forecast_time, tz = process_timestamp(item[0])
                    storage_record = [json.dumps(location),
                                      generation_time,
                                      forecast_time,
                                      json.dumps(item[1])]
                    storage_records.append(storage_record)
                    if len(location_data) < hours and \
                            forecast_time > request_time:
                        # checking time because weather.gov returns fixed set
                        # of data and some of the records might be older than
                        # current time
                        location_data.append(item)
                i = i + 1
            if location_data:
                try:
                    self.store_weather_records(SERVICE_HOURLY_FORECAST,
                                               storage_records)
                except Exception:
                    err_message = "Weather agent failed to write to cache"
                    result[WEATHER_WARN] = [err_message]
                result["generation_time"] = \
                    format_timestamp(generation_time)
                _log.debug(
                    " generation_time in result obj : {}".format(
                        result["generation_time"]))
                result[WEATHER_RESULTS] = location_data
            else:
                result[WEATHER_ERROR] = \
                    "No records were returned by the weather query"

            if location_data and len(location_data) < hours:
                warnings = result.get(WEATHER_WARN, [])
                warnings.append("Weather provider returned less than requested "
                                "amount of data")
                result[WEATHER_WARN] = warnings
        except Exception as error:
            _log.error(error)
            result[WEATHER_ERROR] = error.message
        return result

    def apply_mapping(self, record_dict):
        """
        Alters the weather dictionary returned by a provider to use
        standardized point names specified in the agent's
        registry configuration file.
        (see http://cfconventions.org/Data/cf-standard-names/57/build/cf
        -standard-name-table.html for standardized
        weather terminology)
        :param record_dict: dictionary of weather points
        :return: dictionary of weather points containing names updated to
        match the standard point names provided.
        """
        mapped_data = {}
        for point, value in record_dict.iteritems():
            if isinstance(value, dict):
                value = self.apply_mapping(value)
            if point in self.point_name_mapping:
                point_name = self.point_name_mapping[point][
                    "Standard_Point_Name"]
                mapped_data[point_name] = value
                if (self.point_name_mapping[point]["Service_Units"] and
                        self.point_name_mapping[point]["Standardized_Units"]):
                    mapped_data[point_name] = self.manage_unit_conversion(
                        self.point_name_mapping[point]["Service_Units"],
                        value,
                        self.point_name_mapping[point][
                            "Standardized_Units"])
            else:
                mapped_data[point] = value
        return mapped_data

    @abstractmethod
    def query_hourly_forecast(self, location):
        """
        Abstract method for sending/receiving requests for forecast weather
        data from an api service
        :param location: location for which to query the remote api
        :return: list of dictionaries containing weather data corresponding
        to forecast timestamp
        """

    # @RPC.export
    # def get_hourly_historical(self, locations, start_date, end_date):
    #     data = []
    #     service_name = "get_hourly_historical"
    #     start_datetime = datetime.datetime.combine(start_date,
    # datetime.time())
    #     end_datetime = datetime.datetime.combine(end_date, datetime.time())
    #  + \
    #                    (datetime.timedelta(days=1))
    #     for location in locations:
    #         if not self.validate_location(service_name, location):
    #             raise ValueError("Invalid Location:{}".format(location))
    #         current = start_datetime
    #         while current <= end_datetime:
    #             records = []
    #             cached_history = self.get_cached_historical_data(
    # service_name, location, current)
    #             if cached_history:
    #                 for item in cached_history:
    #                     observation_time = format_timestamp(item[0])
    #                     record = [location, observation_time,
    #                               json.loads(item[1])]
    #                     records.append(record)
    #             if not len(records):
    #                 response = self.query_hourly_historical(location, current)
    #                 storage_records = []
    #                 for item in response:
    #                     records.append(item)
    #                     observation_time = parse_timestamp_string(item[0])
    #                     s_record = [location, observation_time,
    #                                 json.dumps(item[1])]
    #                     storage_records.append(s_record)
    #                     record = [location,
    #                               format_timestamp(observation_time),
    #                               json.dumps(item[1])]
    #                 self.store_weather_records(service_name, storage_records)
    #             for record in records:
    #                 data.append(record)
    #             current = current + datetime.timedelta(hours=1)
    #     return data

    @abstractmethod
    def query_hourly_historical(self, location, start_date, end_date):
        """
        Abstract method for sending/receiving requests for forecast weather
        data from an api service
        :param location: location for which to query the remote api
        :param start_date: timestamp indicating the start of a historical
        period for which to query the api
        :param end_date: timestamp indicating the end of a historical period
        for which to query the api
        :return: list of dictionaries containing historical weather data
        corresponding to a historical timestamp
        """

    def poll_for_locations(self):
        """
        Called periodically by core.period to get_current_weather with the
        agent's polling_locations list as a
        parameter. Publishes to the corresponding entry in the agent's
        poll_topic_suffixes, or to /all if none
        are specified.
        """
        _log.debug("polling for locations")
        results = self.get_current_weather(self.poll_locations)
        if self.poll_topic_suffixes is None:
            _log.debug("publishing results to single topic")
            self.publish_response(POLL_TOPIC.format("all"), results)
        else:
            for i in range(0, len(results)):
                _log.debug("publishing results to location specific topic")
                poll_topic = POLL_TOPIC.format(self.poll_topic_suffixes[i])
                self.publish_response(poll_topic, results[i])

    def publish_response(self, topic, publish_item):
        """
        Publishes a response with the correct headers and topic to the
        Volttron message bus.
        :param topic: topic string to send with the message bus publish for
        the message
        :param publish_item: message contents to be sent in the message bus
        publish.
        """
        publish_headers = {
            HEADER_NAME_DATE: format_timestamp(get_aware_utc_now()),
            HEADER_NAME_CONTENT_TYPE: headers.CONTENT_TYPE}
        self.vip.pubsub.publish(peer="pubsub", topic=topic,
                                message=publish_item,
                                headers=publish_headers)

    def manage_unit_conversion(self, from_units, value, to_units):
        """
        Used to convert units from a query response to the expected
        standardized units
        :param from_units: pint formatted unit string for the current value
        :param value: magnitude of a measurement prior to conversion
        :param to_units: pint formatted unit string for the output value
        :return: magnitude of measurement in the desired units
        """
        if self.unit_registry.parse_expression(
                from_units) == self.unit_registry.parse_expression(to_units):
            return value
        else:
            starting_quantity = self.unit_registry.Quantity(value, from_units)
            updated_value = starting_quantity.to(to_units).magnitude
            return updated_value

    def get_cached_historical_data(self, request_name, location,
                                   date_timestamp):
        """
        Utility method to retrieve cached historical data without direct
        interface with the cache.
        :param request_name: name of the api service function for which to
        retrieve cached data.
        :param location: location of the weather data to return
        :param date_timestamp: date for which to retrieve cached data.
        :return: list of dictionaries of historical weather data for the date
        and location.
        """
        return self._cache.get_historical_data(request_name,
                                               json.dumps(location),
                                               date_timestamp)

    def store_weather_records(self, service_name, records):
        """
        Generically stores weather records returned from the api into the
        corresponding service table in the cache
        database.
        :param service_name: name of the api service function, for which
        records will be put into the corresponding
        table.
        :param records: list of records to put into the insert query.
        """
        try:
            cache_full = self._cache.store_weather_records(service_name,
                                                           records)
            if cache_full:
                self.vip.health.set_status(STATUS_BAD,
                                           "Weather agent cache is full")
                status = Status.from_json(self.vip.health.get_status_json())
                self.vip.health.send_alert(CACHE_FULL, status)
        except Exception as error:
            err_msg = "Weather agent failed to write to cache"
            _log.error("{}. Exception:{}".format(err_msg, error))
            self.vip.health.set_status(STATUS_BAD, err_msg)
            status = Status.from_json(self.vip.health.get_status_json())
            self.vip.health.send_alert(CACHE_WRITE_ERROR, status)
            self.cache_write_error = True
            raise error
        else:
            if self.cache_write_error:
                self.vip.health.set_status(STATUS_GOOD)
                self.cache_write_error = False


    @Core.receiver("onstart")
    def starting(self, sender, **kwargs):
        for service_name in self._api_services:
            if not self._api_services[service_name]["type"] == "history":
                interval = self.get_update_interval(service_name)
                if interval:
                    self.set_update_interval(service_name, interval)
            description = self.get_api_description(service_name)
            if description:
                self.set_api_description(service_name, description)

    @Core.receiver("onstop")
    def stopping(self, sender, **kwargs):
        self._cache.close()


class WeatherCache:
    """Caches data to help reduce the number of requests to the API"""

    def __init__(self,
                 database_file,
                 api_services=None,
                 max_size_gb=1,
                 check_same_thread=True):
        """

        :param database_file: path sqlite file to use for cache
        :param api_services: dictionary from BaseAgent, used to determine
        table names
        :param max_size_gb: maximum size in gigabytes of the sqlite database
        file, useful for deployments with limited
        storage capacity
        :param check_same_thread: True to allow multiple threads to connect
        to the sqlite object, else false (see
        https://docs.python.org/3/library/sqlite3.html)
        """
        self._db_file_path = database_file
        self._api_services = api_services
        self._max_size_gb = max_size_gb
        self._sqlite_conn = None
        self.max_pages = None
        self._setup_cache(check_same_thread)

    # cache setup methods

    def _setup_cache(self, check_same_thread):
        """
        Prepares the cache to begin processing weather data
        :param check_same_thread: True to allow multiple threads to connect
        to the sqlite object, else false (see
        https://docs.python.org/3/library/sqlite3.html)
        """
        _log.debug("Setting up backup DB.")
        _log.debug(self._db_file_path)
        self._sqlite_conn = sqlite3.connect(
            self._db_file_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=check_same_thread)
        _log.info("connected to database, sqlite version: {}".format(
            sqlite3.version))
        self.create_tables()
        cursor = self._sqlite_conn.cursor()
        if self._max_size_gb is not None:
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            max_storage_bytes = self._max_size_gb * 1024 ** 3
            self.max_pages = int(max_storage_bytes / page_size)
            self.manage_cache_size()
        cursor.close()

    def create_tables(self):
        """
        Creates the necessary tables for the weather agent's services and
        ensures proper structure.
        """
        cursor = self._sqlite_conn.cursor()
        for service_name in self._api_services:
            table_exists = False
            table_type = None
            try:
                table_type = self._api_services[service_name]["type"]
                if table_type == "forecast":
                    create_table = CREATE_STMT_FORECAST.format(
                        table=service_name)
                elif table_type == "current" or table_type == "history":
                    create_table = CREATE_STMT_CURRENT.format(
                        table=service_name)
                else:
                    raise ValueError("Invalid table type {} "
                                     "for table {}.".format(table_type,
                                                            service_name))
                _log.debug(create_table)
                cursor.execute(create_table)
                self._sqlite_conn.commit()
            except sqlite3.OperationalError as o:
                if str(o).startswith("table") and str(o).endswith("already "
                                                                  "exists"):
                    table_exists = True
            except sqlite3.Error as err:
                _log.error("Unable to create database table: {}".format(err))
            if table_exists:
                self.validate_and_fix_cache_tables(service_name, table_type)
        cursor.close()

    def validate_and_fix_cache_tables(self, service_name, table_type):
        """
        Ensures that the proper columns are in the service's table.
        :param service_name: api service function name to be used as the
        table name
        :param table_type: indicates the expected columns for the service (
        must be forecast, history, or current)
        """
        if table_type == "forecast":
            expected_columns = ["ID", "LOCATION", "GENERATION_TIME",
                                "FORECAST_TIME", "POINTS"]
        else:
            expected_columns = ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]
        column_names = []
        cursor = self._sqlite_conn.cursor()
        table_info = cursor.execute(
            "PRAGMA table_info({})".format(service_name)).fetchall()
        for row in table_info:
            column_names.append(row[1])
        for column_name in expected_columns:
            if column_name not in column_names:
                delete_query = "DROP TABLE {};".format(service_name)
                cursor.execute(delete_query)
                self._sqlite_conn.commit()
                _log.debug(delete_query)
                create_table = ""
                if table_type == "forecast":
                    create_table = CREATE_STMT_FORECAST.format(
                        table=service_name)
                elif table_type == "current" or table_type == "history":
                    create_table = CREATE_STMT_CURRENT.format(
                        table=service_name)
                if len(create_table):
                    _log.debug(create_table)
                    cursor.execute(create_table)
                    self._sqlite_conn.commit()
                    break

    def get_current_data(self, service_name, location):
        """
        Retrieves the most recent current data by location from cache
        :param service_name: name of the api service for table lookup
        :param location: location to query by
        :return: a single current weather observation record
        """
        query = ""

        cursor = self._sqlite_conn.cursor()
        query = """SELECT max(OBSERVATION_TIME), POINTS 
                   FROM {table}
                   WHERE LOCATION = ?;""".format(table=service_name)
        _log.debug(query)
        cursor.execute(query, (location,))
        data = cursor.fetchone()
        cursor.close()
        if data and data[0]:
            return parse_timestamp_string(data[0]), data[1]
        else:
            return None, None

    def get_forecast_data(self, service_name, location, hours, request_time):
        """
        Retrieves the most recent forecast record set (forecast should be a
        time-series) by location
        :param service_name: name of the api service for table lookup
        :param location: location to query by
        :param hours: number of hours (records) to query for
        :param request_time: time at which the data was requested, used to
        compare with generation time.
        :return: list of up-to-date forecast records for the location
        """
        query = ""

        # get records that have forecast time between the hour immediately
        # after when user requested the data and endtime < start+hours
        # do this to avoid returning data for hours 4 to 10 instead of
        # 2-8 when the request time is hour 1.
        forecast_start = request_time + datetime.timedelta(hours=1)
        forecast_start = forecast_start.replace(minute=0, second=0,
                                                microsecond=0)
        forecast_end = forecast_start + datetime.timedelta(hours=hours)

        cursor = self._sqlite_conn.cursor()
        query = """SELECT GENERATION_TIME, FORECAST_TIME, POINTS 
                   FROM {table} 
                   WHERE LOCATION = ? 
                   AND FORECAST_TIME >= ? 
                   AND FORECAST_TIME < ? 
                   AND GENERATION_TIME = 
                   (SELECT MAX(GENERATION_TIME) 
                    FROM {table}
                    WHERE LOCATION = ?) 
                   ORDER BY FORECAST_TIME ASC;""".format(table=service_name)
        _log.debug(query)
        cursor.execute(query, (location, forecast_start, forecast_end,
                               location))
        data = cursor.fetchall()
        cursor.close()
        return data

    def get_historical_data(self, service_name, location, date_timestamp):
        """
        Retrieves historical data over the the given time period by location
        :param service_name: name of the api service for table lookup
        :param location: location to query by
        :param date_timestamp: date for which to return a record set
        :return: list of historical records for the provided date/location
        """
        start_timestamp = date_timestamp
        end_timestamp = date_timestamp + (
                    datetime.timedelta(days=1) - datetime.timedelta(
                        milliseconds=1))
        if service_name not in self._api_services:
            raise ValueError(
                "service {} does not exist in the agent's services.".format(
                    service_name))

        cursor = self._sqlite_conn.cursor()
        query = """SELECT OBSERVATION_TIME, POINTS 
                   FROM {table} WHERE LOCATION = ? 
                   AND OBSERVATION_TIME BETWEEN ? AND ? 
                   ORDER BY OBSERVATION_TIME ASC;""".format(
            table=service_name)
        _log.debug(query)
        cursor.execute(query, (location, start_timestamp, end_timestamp))
        data = cursor.fetchall()
        cursor.close()
        return data

    def store_weather_records(self, service_name, records):
        """
        Request agnostic method to store weather records in the cache.
        :param service_name: name of the api service to use as a table name
        for record storage
        :param records: expects a list of records (as lists) formatted to
        match tables
        :return: boolean value representing whether or not the cache is full
        """
        cursor = self._sqlite_conn.cursor()
        request_type = self._api_services[service_name]["type"]
        if request_type == "forecast":
            query = """INSERT INTO {} 
                       (LOCATION, GENERATION_TIME, FORECAST_TIME, POINTS) 
                       VALUES (?, ?, ?, ?)""".format(service_name)
        else:
            query = """INSERT INTO {} 
                       (LOCATION, OBSERVATION_TIME, POINTS) 
                       VALUES (?, ?, ?)""".format(service_name)
        _log.debug(query)

        if request_type == "current":
            cursor.execute(query, records)
        else:
            cursor.executemany(query, records)
        self._sqlite_conn.commit()

        cache_full = False
        if self._max_size_gb is not None and \
                self.page_count(cursor) >= self.max_pages:
            cache_full = True
            self.manage_cache_size()
        cursor.close()
        return cache_full

    # cache management/ lifecycle methods

    @staticmethod
    def page_count(cursor):
        """
        Gets the number of pages written to in the database for memory
        management purposes.
        :param cursor: Cache's cursor object used for querying
        :return: number of pages currently written to in the cache database
        """
        cursor.execute("PRAGMA page_count")
        return cursor.fetchone()[0]

    def manage_cache_size(self):
        """
        Removes data from the weather cache until the cache is a safe size.
        Prioritizes removal from current, then forecast, then historical
        request types
        """
        if self._max_size_gb:

            cursor = self._sqlite_conn.cursor()
            page_count = self.page_count(cursor)
            if page_count < self.max_pages:
                return

            attempt = 1
            records_deleted = 0
            now = datetime.datetime.utcnow()
            while page_count >= self.max_pages:
                if attempt == 1:
                    for table_name, service in self._api_services.iteritems():
                        # Remove all data that is older than update interval
                        if service["type"] == "current":
                            query = """DELETE FROM {table} 
                                       WHERE OBSERVATION_TIME < ?;""" \
                                .format(table=table_name)
                            cursor.execute(query,
                                           (now - service["update_interval"],))
                elif attempt == 2:
                    for table_name, service in self._api_services.iteritems():
                        # Remove all data that is older than update interval
                        if service["type"] == "forecast":
                            query = """DELETE FROM {table} 
                                       WHERE GENERATION_TIME < ?""".format(
                                table=table_name)
                            cursor.execute(query,
                                           (now - service["update_interval"],))
                elif attempt > 2:
                    records_deleted = 0
                    for table_name, service in self._api_services.iteritems():
                        if service["type"] == "history":
                            query = "DELETE FROM {table} WHERE ID IN " \
                                    "(SELECT ID FROM {table} " \
                                    "ORDER BY ID ASC LIMIT 100)".format(
                                        table=table_name)
                            cursor.execute(query)
                            records_deleted += cursor.rowcount
                if attempt > 2 and records_deleted == 0:
                    # all history records removed
                    break
                attempt += 1
                page_count = self.page_count(cursor)

            # if we still don't have space in cache
            while page_count >= self.max_pages:
                for table_name in self._api_services:
                    query = """DELETE FROM {table} WHERE ID IN 
                               (SELECT ID FROM {table} 
                                ORDER BY ID ASC LIMIT 100)""".format(
                        table=table_name)
                    cursor.execute(query)
                    page_count = self.page_count(cursor)

    def close(self):
        """Close the sqlite database connection when the agent stops"""
        self._sqlite_conn.close()
        self._sqlite_conn = None


# Code reimplemented from https://github.com/gilesbrown/gsqlite3
def _using_threadpool(method):
    """Used by agents for threading."""

    @wraps(method, ['__name__', '__doc__'])
    def apply(*args, **kwargs):
        return get_hub().threadpool.apply(method, args, kwargs)

    return apply


class AsyncWeatherCache(WeatherCache):
    """Asynchronous weather cache wrapper for use with gevent"""

    def __init__(self, **kwargs):
        kwargs["check_same_thread"] = False
        super(AsyncWeatherCache, self).__init__(**kwargs)


# Cache methods to make available for threading.
for method in [WeatherCache.get_current_data,
               WeatherCache.get_forecast_data,
               WeatherCache.get_historical_data,
               WeatherCache._setup_cache,
               WeatherCache.store_weather_records]:
    setattr(AsyncWeatherCache, method.__name__, _using_threadpool(method))
