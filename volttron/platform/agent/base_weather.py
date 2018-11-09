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
import pytz
import copy
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
                                                STATUS_UNKNOWN,
                                                STATUS_GOOD,
                                                STATUS_STARTING,
                                                 Status)

POLL_TOPIC = "weather/poll/current/{}"

SERVICE_HOURLY_FORECAST = "get_hourly_forecast"

SERVICE_CURRENT_WEATHER = "get_current_weather"

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

__version__ = "0.1.0"

_log = logging.getLogger(__name__)

HEADER_NAME_DATE = headers.DATE
HEADER_NAME_CONTENT_TYPE = headers.CONTENT_TYPE

# Register a better datetime parser in sqlite3.
fix_sqlite3_datetime()

class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    def __init__(self,
                 service_name=None,
                 api_key=None,
                 max_size_gb=None,
                 poll_locations=None,
                 poll_interval=None,
                 poll_topic_suffixes=None,
                 **kwargs):
        try:
            super(BaseWeatherAgent, self).__init__(**kwargs)
            self._service_name = service_name
            self._async_call = AsyncCall()
            self._api_key = api_key
            self._max_size_gb = max_size_gb
            self.poll_locations = poll_locations
            self.poll_interval = poll_interval
            self.poll_topic_suffixes = poll_topic_suffixes
            self.do_polling = False
            self.poll_greenlet = None
            self._cache = None

            self._default_config = \
                {
                    "service": self._service_name,
                    "api_key": self._api_key,
                    "max_size_gb": self._max_size_gb,
                    "poll_locations": self.poll_locations,
                    "poll_interval": self.poll_interval,
                    "poll_topic_suffixes": self.poll_topic_suffixes
                }
            self.unit_registry = pint.UnitRegistry()
            self.point_name_mapping = self.parse_point_name_mapping()
            self._api_services = {SERVICE_CURRENT_WEATHER:{"type": "current",
                                           "update_interval": None,
                                           "description": "Params: locations "
                                                          "([{"
                                                          "type: "
                                                          "value},...])"
                                         },
                 SERVICE_HOURLY_FORECAST: {"type": "forecast",
                                           "update_interval": None,
                                           "description": "Params: locations "
                                                          "([{type: value},"
                                                          "...])"
                                         },
                 "get_hourly_historical":{"type": "history",
                                           "update_interval": None,
                                           "description": "Params: locations "
                                                          "([{"
                                                          "type: value},..]), "
                                                          "start_date (date), "
                                                          "end_date(date)"
                                           }
                 }

            for service_name in self._api_services:
                if not self._api_services[service_name]["type"] == "history":
                    interval = self.get_update_interval(service_name)
                    if interval:
                        self.set_update_interval(service_name, interval)
                description = self.get_api_description(service_name)
                if description:
                    self.set_api_description(service_name, description)

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
    # TODO update documentation
    def register_service(self, service_function_name, interval, service_type,
                         description=None):
        """Called in a weather agent's __init__ function to add api services
        to the api services dictionary.
        :param service_function_name: function call name for an api feature
        :param interval: datetime timedelta object describing the length of
        time between api updates.
        :param service_type: the string "history", "current", or "forecast". This
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

    # TODO docs
    def remove_service(self, service_function_name):
        """

        :param service_function_name: a function call name for an api feature
        to be removed.
        """
        if service_function_name in self._api_services:
            self._api_services.pop(service_function_name)
        else:
            raise ValueError("service {} does not exist".format(
                service_function_name))

    def validate_location_dict(self, service_name, location):
        record_dict = None
        if not isinstance(location, dict):
            record_dict = {"location": location,
                           "location_error": "Invalid location format. "
                                             "Location should be  "
                                             "specified as a dictionary"}

        elif not self.validate_location(service_name, location):
            record_dict = location.copy()
            record_dict["location_error"] = "Invalid location"
        return record_dict

    @abstractmethod
    def validate_location(self, service_name, location):
        pass

    @abstractmethod
    def get_update_interval(self, service_name):
        pass

    @abstractmethod
    def get_api_description(self, service_name):
        pass

    # TODO update documentation
    def set_update_interval(self, service_name, interval):
        """

        :param service_name: a function call name for an api feature to be updated
        :param interval: datetime timedelta object specifying the length of time between api updates
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
            raise ValueError("{} not found in api features.".format(service_name))

    def set_api_description(self, service_name, description):
        """

        :param service_name:
        :param description:
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
        :return: file path of a csv containing a mapping of Service_Point_Name to an optional Standard_Point_Name.
        May also optionally provide Service_Units (a Pint-parsable unit name for a point, provided by the service) to
        Standardized_Units (units specified for the Standard_Point_Name by the CF standards). Should return None if
        the concrete agent does not require point name mapping and/or unit conversion.
        """

    def parse_point_name_mapping(self):
        """
        Parses point name mapping, which should contain a mapping of service
        points to standardized points, with specified units.
        """
        point_name_mapping = {}
        mapping_file = self.get_point_name_defs_file()
        if mapping_file:
            try:
                if isinstance(mapping_file, str):
                    mapping_file = open(mapping_file)
                    #else assume it is a file like object
                config_dict = csv.DictReader(mapping_file)
                for map_item in config_dict:
                    service_point_name = map_item.get("Service_Point_Name")
                    if service_point_name:
                        standard_point_name = map_item.get("Standard_Point_Name")
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

    # TODO copy documentation?
    def _configure(self, config_name, actions, contents):
        """

        :param config_name:
        :param actions:
        :param contents:
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
            _log.error("Failed to load weather agent settings.")
            self.vip.health.set_status(STATUS_BAD,
                                       "Configuration of weather agent failed "
                                       "with error: {}".format(e.message))
        else:
            _log.debug("Configuration successful")
            self._cache = WeatherCache(service_name=self._service_name,
                                       api_services=self._api_services,
                                       max_size_gb=self._max_size_gb)
            self.vip.health.set_status(STATUS_GOOD,
                                       "Configuration of weather agent "
                                       "successful")
            if self.do_polling:
                if self.poll_greenlet:
                    self.poll_greenlet.kill()
                self.poll_greenlet = self.core.periodic(self.poll_interval,
                                                        self.poll_for_locations)

    def validate_poll_config(self):
        if self.poll_locations:
            if not self.poll_interval:
                err_msg = "poll_interval is mandatory configuration when " \
                          "poll_locations are specified"
                raise ValueError(err_msg)
            if (self.poll_topic_suffixes is not None and
                    (not isinstance(self.poll_locations, list) or
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
        return __version__

    # TODO update spec to match name
    # Add doc string
    @RPC.export
    def get_api_features(self):
        """

        :return: {function call: description string}
        """
        features = {}
        for service_name in self._api_services:
            features[service_name] = \
                self._api_services[service_name]["description"]
        return features

    # TODO add doc
    @RPC.export
    def get_current_weather(self, locations):
        result = []
        for location in locations:
            record_dict = self.validate_location_dict(SERVICE_CURRENT_WEATHER,
                                                      location)
            if record_dict:
                result.append(record_dict)
                continue

            # Attempt getting from cache
            record_dict = self.get_cached_current_data(location)

            # if there was no data in cache or if data is old, query api
            if not record_dict.get("weather_results"):
                _log.debug("Current weather data from api")
                record_dict = self.get_current_weather_remote(location)

            result.append(record_dict)
        return result

    def get_cached_current_data(self, location):

        observation_time, data = \
            self._cache.get_current_data(SERVICE_CURRENT_WEATHER,
                                         json.dumps(location))
        result = location.copy()
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
                result["weather_results"] = json.loads(data)
        return result

    def get_current_weather_remote(self, location):
        result = location.copy()
        try:
            observation_time, data = self.query_current_weather(
                location)
            _log.debug("Got data from remote as {}".format(data))
            observation_time, oldtz = process_timestamp(
                observation_time)
            if self.point_name_mapping:
                _log.debug("Got point name mapping")
                data = self.apply_mapping(data)
            _log.debug("data from api after mapping {}".format(data))
            if observation_time is not None:
                storage_record = [json.dumps(location),
                                  observation_time,
                                  json.dumps(data)]
                self.store_weather_records(SERVICE_CURRENT_WEATHER,
                                           storage_record)
                result["observation_time"] = \
                    format_timestamp(observation_time)
                result["weather_results"] = data
            else:
                result["weather_error"] = "Weather api did not " \
                                               "return any records"
        except Exception as error:
            _log.error(error)
            result["weather_error"] = error
        return result

    @abstractmethod
    def query_current_weather(self, location):
        """

        :param location:
        :return: dictionary containing a single record of data
        """

    # TODO add docs
    @RPC.export
    def get_hourly_forecast(self, locations, hours=24):
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

            # if cache didn't work out query remote api
            if not record_dict.get("weather_results"):
                _log.debug("forecast weather from api")
                record_dict = self.get_remote_hourly_forecast(location,
                                                              hours,
                                                              request_time)
                _log.debug("record_dict from remote : {}".format(record_dict))
            result.append(record_dict)

        return result

    def get_cached_hourly_forecast(self, location, hours, request_time):
        interval = \
            self._api_services[SERVICE_HOURLY_FORECAST]["update_interval"]
        # format [(generation_time, forecast_time, points), ...]
        most_recent_for_location = \
            self._cache.get_forecast_data(SERVICE_HOURLY_FORECAST,
                                          json.dumps(location),
                                          hours, request_time)
        record_dict = location.copy()
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
                record_dict["weather_results"] = location_data
        return record_dict

    def get_remote_hourly_forecast(self, location, hours, request_time):
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
                self.store_weather_records(SERVICE_HOURLY_FORECAST,
                                           storage_records)
                result["generation_time"] = \
                    format_timestamp(generation_time)
                _log.debug(
                    " generation_time in result obj : {}".format(
                        result["generation_time"]))
                result["weather_results"] = location_data
            else:
                result["weather_error"] = \
                    "No records were returned by the weather query"

            if location_data and len(location_data) < hours:
                result["weather_warn"] = \
                    "Weather provider returned less than requested " \
                    "amount of data"
        except Exception as error:
            _log.error(error)
            result["weather_error"] = error
        return result

    def apply_mapping(self, record_dict):
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

    # TODO docs
    @abstractmethod
    def query_hourly_forecast(self, location):
        """

        :param location:
        :return: list containing 1 dictionary per data record in the forecast set
        """

    # TODO do by date, add docs
    @RPC.export
    def get_hourly_historical(self, locations, start_date, end_date):
        data = []
        service_name = "get_hourly_historical"
        start_datetime = datetime.datetime.combine(start_date, datetime.time())
        end_datetime = datetime.datetime.combine(end_date, datetime.time()) + \
                       (datetime.timedelta(days=1))
        # TODO
        for location in locations:
            if not self.validate_location(service_name, location):
                raise ValueError("Invalid Location:{}".format(location))
            current = start_datetime
            while current <= end_datetime:
                records = []
                cached_history = self.get_cached_historical_data(service_name, location, current)
                if cached_history:
                    for item in cached_history:
                        observation_time = format_timestamp(item[0])
                        record = [location, observation_time,
                                  json.loads(item[1])]
                        records.append(record)
                if not len(records):
                    response = self.query_hourly_historical(location, current)
                    storage_records = []
                    for item in response:
                        records.append(item)
                        observation_time = parse_timestamp_string(item[0])
                        s_record = [location, observation_time,
                                    json.dumps(item[1])]
                        storage_records.append(s_record)
                        record = [location,
                                  format_timestamp(observation_time),
                                  json.dumps(item[1])]
                    self.store_weather_records(service_name, storage_records)
                for record in records:
                    data.append(record)
                current = current + datetime.timedelta(hours=1)
        return data

    @abstractmethod
    def query_hourly_historical(self, location, start_date, end_date):
        """

        :param location:
        :param start_date:
        :param end_date:
        :return: list containing 1 dictionary per data record in the history set
        """

    # TODO docs
    def poll_for_locations(self):
        _log.debug("polling for locations")
        results = self.get_current_weather(self.poll_locations)
        if self.poll_topic_suffixes is None:
            _log.debug("publishing results to single topic")
            self.publish_response(POLL_TOPIC.format("all"), results)
        else:
            for i in range(0,len(results)):
                _log.debug("publishing results to location specific topic")
                poll_topic = POLL_TOPIC.format(self.poll_topic_suffixes[i])
                self.publish_response(poll_topic, results[i])
                i = i + 1

    # TODO docs
    def publish_response(self, topic, publish_item):
        publish_headers = {
            HEADER_NAME_DATE: format_timestamp(get_aware_utc_now()),
            HEADER_NAME_CONTENT_TYPE: headers.CONTENT_TYPE}
        self.vip.pubsub.publish(peer="pubsub", topic=topic,
                                message=publish_item,
                                headers=publish_headers)

    def manage_unit_conversion(self, from_units, value, to_units):
        """
        Used to convert units from a query response to the expected standardized units
        :param from_units: pint formatted unit string for the current value
        :param value: magnitude of a measurement
        :param to_units: pint formatted unit string for the output value
        :return: magnitude of measurement in the desired units
        """
        if self.unit_registry.parse_expression(from_units) == self.unit_registry.parse_expression(to_units):
            return value
        else:
            starting_quantity = self.unit_registry.Quantity(value, from_units)
            updated_value = starting_quantity.to(to_units).magnitude
            return updated_value

    def get_cached_historical_data(self, request_name, location,
                                   date_timestamp):
        return self._cache.get_historical_data(request_name, json.dumps(location),
                                               date_timestamp)

    def store_weather_records(self, service_name, records):
        """
        :param service_name:
        :param records:
        """
        cache_full = self._cache.store_weather_records(service_name, records)
        if cache_full:
            self.vip.health.set_status(STATUS_BAD, "Weather agent cache is full")
            status = Status.from_json(self.vip.health.get_status_json())
            self.vip.health.send_alert("cache_full", status)

    @Core.receiver("onstop")
    def stopping(self, sender, **kwargs):
        self._cache.close()

# TODO docs
class WeatherCache:
    """Caches data to help reduce the number of requests to the API"""
    def __init__(self,
                 service_name="default",
                 api_services=None,
                 max_size_gb=1,
                 check_same_thread=True):
        """

        :param service_name: Name of the weather service (i.e. weather.gov)
        :param api_services: dictionary from BaseAgent, used to determine table names
        :param max_size_gb: maximum size in gigabytes of the sqlite database file, useful for deployments with limited
        storage capacity
        :param check_same_thread:
        """
        self._service_name = service_name
        # TODO need to alter the file path for the database
        self._db_file_path = self._service_name + ".sqlite"
        self._api_services = api_services
        self._max_size_gb = max_size_gb
        self._sqlite_conn = None
        self.max_pages = None
        self._setup_cache(check_same_thread)

    # cache setup methods

    # TODO calculating max_storage_bytes has memory error?
    def _setup_cache(self, check_same_thread):
        """
        prepare the cache to begin processing weather data
        :param check_same_thread:
        """
        _log.debug("Setting up backup DB.")
        _log.debug(self._db_file_path)
        self._sqlite_conn = sqlite3.connect(
            self._db_file_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=check_same_thread)
        _log.info("connected to database {} sqlite version: {}".format(self._service_name, sqlite3.version))
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
        Checks to see if the proper tables and table columns are in the database, creates them if they are not.
        """
        cursor = self._sqlite_conn.cursor()
        for service_name in self._api_services:
            table_exists = False
            table_type = None
            try:
                table_type = self._api_services[service_name]["type"]
                if table_type == "forecast":
                    create_table = CREATE_STMT_FORECAST.format(table=service_name)
                elif table_type == "current" or table_type == "history":
                    create_table = CREATE_STMT_CURRENT.format(table=service_name)
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
                if table_type == "forecast":
                    create_table = CREATE_STMT_FORECAST.format(table=service_name)
                elif table_type == "current" or table_type == "history":
                    create_table = CREATE_STMT_CURRENT.format(table=service_name)
                _log.debug(create_table)
                cursor.execute(create_table)
                self._sqlite_conn.commit()
                break


    def get_current_data(self, service_name, location):
        """
        Retrieves the most recent current data by location
        :param service_name:
        :param location:
        :return: a single current weather observation record
        """
        try:
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
        except sqlite3.Error as e:
            _log.error("Error fetching current data from cache: {}".format(e))
            return None

    def get_forecast_data(self, service_name, location, hours, request_time):
        """
        Retrieves the most recent forecast record set (forecast should be a time-series) by location
        :param service_name:
        :param location:
        :param hours:
        :param request_time:
        :return: list of forecast records
        """
        try:
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
        except sqlite3.Error as e:
            _log.error("Error fetching forecast data from cache: {}".format(e))

    def get_historical_data(self, service_name, location, date_timestamp):
        """
        Retrieves historical data over the the given time period by location
        :param service_name:
        :param location:
        :param date_timestamp:
        :return: list of historical records
        """
        start_timestamp = date_timestamp
        end_timestamp = date_timestamp + (datetime.timedelta(days=1)-datetime.timedelta(milliseconds=1))
        if service_name not in self._api_services:
            raise ValueError("service {} does not exist in the agent's services.".format(service_name))
        try:
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
        except sqlite3.Error as e:
            _log.error("Error fetching historical data from cache: {}".format(e))

    def store_weather_records(self, service_name, records):
        """
        Request agnostic method to store weather records in the cache.
        :param service_name:
        :param records: expects a list of records (as lists) formatted to match tables
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
        try:
            if request_type == "current":
                cursor.execute(query, records)
            else:
                cursor.executemany(query, records)
            self._sqlite_conn.commit()
        except sqlite3.Error as e:
            _log.info(query)
            _log.error("Failed to store data in the cache: {}".format(e))
        cache_full = False
        if self._max_size_gb is not None and \
                self.page_count(cursor) >= self.max_pages:
            cache_full = True
            self.manage_cache_size()
        cursor.close()
        return cache_full

    # cache management/ lifecycle methods

    def page_count(self, cursor):
        cursor.execute("PRAGMA page_count")
        return cursor.fetchone()[0]

    # TODO This needs extensive testing
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
                                       WHERE OBSERVATION_TIME < ?;"""\
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
    @wraps(method, ['__name__', '__doc__'])
    def apply(*args, **kwargs):
        return get_hub().threadpool.apply(method, args, kwargs)
    return apply


class AsyncWeatherCache(WeatherCache):
    """Asynchronous weather cache wrapper for use with gevent"""
    def __init__(self, **kwargs):
        kwargs["check_same_thread"] = False
        super(AsyncWeatherCache, self).__init__(**kwargs)


# TODO documentation
for method in [WeatherCache.get_current_data,
               WeatherCache.get_forecast_data,
               WeatherCache.get_historical_data,
               WeatherCache._setup_cache,
               WeatherCache.store_weather_records]:
    setattr(AsyncWeatherCache, method.__name__, _using_threadpool(method))

