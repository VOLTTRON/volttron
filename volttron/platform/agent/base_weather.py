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
import json
import sqlite3
import datetime
from functools import wraps
from abc import abstractmethod
from gevent import get_hub
from volttron.platform.agent import utils
from utils import parse_timestamp_string
from volttron.platform.vip.agent import *
from volttron.platform.async import AsyncCall
from volttron.platform.messaging import headers
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_UNKNOWN,
                                                STATUS_GOOD,
                                                STATUS_STARTING,
                                                Status)

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

STATUS_KEY_PUBLISHING = "publishing"
STATUS_KEY_CACHE_FULL = "cache_full"


class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    def __init__(self,
                 service_name=None,
                 api_key=None,
                 max_size_gb=None,
                 polling_locations=None,
                 poll_interval=None,
                 **kwargs):

        super(BaseWeatherAgent, self).__init__(**kwargs)
        self._service_name = service_name
        self._async_call = AsyncCall()
        self._api_key = api_key
        self._max_size_gb = max_size_gb
        self.polling_locations = polling_locations
        self.poll_interval = poll_interval
        self._default_config = {
                                "service": self._service_name,
                                "api_key": self._api_key,
                                "max_size_gb": self._max_size_gb,
                                "polling_locations": self.polling_locations,
                                "poll_interval": self.poll_interval
                               }
        self.unit_registry = pint.UnitRegistry()
        self.point_name_mapping = {}
        self._api_services = \
            {"get_current_weather": {"type": "current",
                                     "update_interval": None,
                                     "description": "Params: locations ([{"
                                                    "type: "
                                                    "value},...])"
                                     },
             "get_hourly_forecast": {"type": "forecast",
                                     "update_interval": None,
                                     "description": "Params: locations "
                                                    "([{type: value},...])"
                                     },
             "get_hourly_historical": {"type": "history",
                                       "update_interval": None,
                                       "description": "Params: locations "
                                                      "([{type: value},...]), "
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

        # TODO finish status context
        self._current_status_context = {
            STATUS_KEY_CACHE_FULL: False
        }

        # TODO manage health with respect to these conditions
        self.successfully_publishing = None
        if self.polling_locations:
            self._current_status_context[STATUS_KEY_PUBLISHING] = True
            self.successfully_publishing = True

        self._cache = WeatherCache(service_name=self._service_name,
                                   api_services=self._api_services,
                                   max_size_gb=self._max_size_gb)

        self.vip.config.set_default("config", self._default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"],
                                  pattern="config")

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
            raise ValueError("service {} does not exist".format(service_function_name))

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
            raise ValueError("interval must be a valid datetime timedelta object.")
        if service_name in self._api_services:
            if self._api_services[service_name]["type"] == "history":
                raise ValueError("historical data does not utilize an update interval.")
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
            raise ValueError("{} not found in api features.".format(service_name))

    def update_default_config(self, config):
        """
        May be called by historians to add to the default configuration for its
        own use.
        :param config: configuration dictionary
        """
        self._default_config.update(config)
        self.vip.config.set_default("config", self._default_config)

    def parse_point_name_mapping(self, config_dict):
        """
        Parses the registry config, which should contain a mapping of service
        points to standardized points, with specified units.
        :param config_dict: registry configuration dictionary containing
                            mappings from points included in api, to points
                            included in the NOAA standard weather structure.
                            Points listed without a standard name will be
                            included without renaming or unit conversion.
        """
        for map_item in config_dict:
            service_point_name = map_item.get("Service_Point_Name")
            if service_point_name:
                standard_point_name = map_item.get("Standard_Point_Name")
                standardized_units = map_item.get("Standardized_Units")
                service_units = map_item.get("Service_Units")
                self.point_name_mapping[service_point_name] = \
                    {"Standard_Point_Name": standard_point_name,
                     "Standardized_Units": standardized_units,
                     "Service_units": service_units}

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
        try:
            api_key = config.get("api_key")
            max_size_gb = config.get("max_size_gb")
            polling_locations = config.get("poll_locations")
            poll_interval = config.get("poll_interval")
            if max_size_gb is not None:
                max_size_gb = float(max_size_gb)
            # TODO registry config
            # self.parse_point_name_mapping(registry_config)

        except ValueError:
            _log.error("""Failed to load base weather agent settings. 
                          Settings not applied!""")
            return
        self._api_key = api_key
        self._max_size_gb = max_size_gb
        self.polling_locations = polling_locations
        self.poll_interval = poll_interval
        try:
            self.configure(config)
        except:
            _log.error("Failed to load weather agent settings.")

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

    # TODO docs
    @abstractmethod
    def validate_location_for_current(self, location):
      pass

    # TODO docs
    @abstractmethod
    def validate_location_for_hourly_forecast(self, location):
      pass

    # TODO docs
    @abstractmethod
    def validate_location_for_hourly_history(self, location):
      pass

    # TODO add doc
    @RPC.export
    def get_current_weather(self, locations):
        result = []
        service_name = "get_current_weather"
        interval = self._api_services[service_name]["update_interval"]
        for location in locations:
            record_dict = location.copy()
            if not isinstance(location, dict):
                record_dict["location_error"] = "Invalid location format. " \
                                                "Location should be  " \
                                                "specified as a dictionary"
                result.append(record_dict)  # to next location
                continue
            elif not self.validate_location_for_current(location):
                record_dict["location_error"] = "Invalid location"
                result.append(record_dict)
                continue  # to next location

            observation_time, data = \
                self.get_cached_current_data(service_name, location)
            if observation_time and data:
                current_time = datetime.datetime.utcnow()
                update_window = current_time - interval
                # if observation time is within the update interval
                if observation_time > update_window:
                    record_dict["observation_time"] = observation_time
                    record_dict["weather_results"] = json.loads(data)

            # if there was no data in cache or if data is old query api
            if not record_dict.get("weather_results"):
                try:
                    observation_time, data = self.query_current_weather(
                        location)
                    # TODO unit conversions, properties name mapping
                    if observation_time is not None:
                        storage_record = [json.dumps(location),
                                          observation_time,
                                          json.dumps(data)]
                        self.store_weather_records(service_name, storage_record)
                        record_dict["observation_time"] = observation_time
                        record_dict["weather_results"] = data
                    else:
                        record_dict["weather_error"] = "Weather api did not " \
                                                       "return any records"
                except Exception as error:
                    _log.error(error)
                    record_dict["weather_error"] = error
            result.append(record_dict)
        return result

    @abstractmethod
    def query_current_weather(self, location):
        """

        :param location:
        :return: dictionary containing a single record of data
        """

    # TODO add docs
    @RPC.export
    def get_hourly_forecast(self, locations, hours=None):
        data = []
        service_name = "get_hourly_forecast"
        interval = self._api_services[service_name]["update_interval"]
        for location in locations:
            if not isinstance(location, dict):
                record_dict = {"bad_location": json.dumps(location)}
            else:
                record_dict = location.copy()
            try:
                if not self.validate_location_for_current(location):
                    raise ValueError("Invalid location: {}".format(location))
                most_recent_for_location = \
                    self.get_cached_forecast_data(service_name, location)
                location_data = []
                if most_recent_for_location:
                    current_time = datetime.datetime.utcnow()
                    update_window = current_time - interval
                    generation_time = most_recent_for_location[0][1]
                    if generation_time >= update_window:
                        for record in most_recent_for_location:
                            entry = [record[1], record[2],
                                     json.loads(record[3])]
                            location_data.append(entry)
                        record_dict["weather_results"] = location_data
                if not len(location_data) or (hours and len(location_data) < hours):
                    try:
                        response = self.query_hourly_forecast(location)
                        storage_records = []
                        if not len(response):
                            raise RuntimeError("No records were returned by the weather query")
                        for item in response:
                            if item[0] is not None and item[1] is not None:
                                storage_record = [json.dumps(location), item[0], item[1],
                                                  json.dumps(item[2])]
                                storage_records.append(storage_record)
                            location_data.append(item)
                        if len(storage_records):
                            self.store_weather_records(service_name, storage_records)
                        record_dict["weather_results"] = location_data
                    except Exception as error:
                        _log.error(error)
                        record_dict["weather_error"] = error
                data.append(record_dict)
            except ValueError as error:
                record_dict["location_error"] = error
                data.append(record_dict)
        return data

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
                       (datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1))
        # TODO
        for location in locations:
            if not self.validate_location_for_hourly_history(location):
                raise ValueError("Invalid Location:{}".format(location))
            current = start_datetime
            while current <= end_datetime:
                records = []
                cached_history = self.get_cached_historical_data(service_name, location, current)
                if cached_history:
                    for item in cached_history:
                        record = [location, item[0], json.loads(item[1])]
                        records.append(record)
                if not len(records):
                    response = self.query_hourly_historical(location, current)
                    storage_records = []
                    for item in response:
                        records.append(item)
                        record = [location, item[0], json.dumps(item[1])]
                        storage_records.append(record)
                    self.store_weather_records(service_name, storage_records)
                for record in records:
                    data.append(record)
                current = current + datetime.timedelta(days=1)
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
        topic = "weather/{}/current/{}/all"
        data = self.query_current_weather(self.polling_locations)
        for record in data:
            poll_topic = topic.format("poll", record["location"])
            self.publish_response(poll_topic, record)

    # TODO docs
    def publish_response(self, topic, publish_item):
        publish_headers = {HEADER_NAME_DATE: utils.format_timestamp(utils.get_aware_utc_now()),
                           HEADER_NAME_CONTENT_TYPE: headers.CONTENT_TYPE}
        self.vip.pubsub.publish(peer="pubsub", topic=topic, message=publish_item, headers=publish_headers)

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

    # TODO docs
    # methods to hide cache functionality from concrete weather agent implementations

    def get_cached_current_data(self, request_name, location):
        return self._cache.get_current_data(request_name, json.dumps(location))

    def get_cached_forecast_data(self, request_name, location):
        return self._cache.get_forecast_data(request_name, json.dumps(location))

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
        # TODO status alerts
        self._current_status_context[STATUS_KEY_CACHE_FULL] = cache_full
        return cache_full

    # TODO
    # Status management methods

    def _get_status_from_context(self, context):
        status = STATUS_GOOD
        if context.get("cache_full") or (not context.get("publishing") and len(self.polling_locations)):
            status = STATUS_BAD
        return status

    def _update_status_callback(self, status, context):
        self.vip.health.set_status(status, context)

    def _update_status(self, updates):
        context_copy, new_status = self._update_and_get_context_status(updates)
        self._async_call.send(None, self._update_status_callback, new_status, context_copy)

    def _send_alert_callback(self, status, context, key):
        self.vip.health.set_status(status, context)
        alert_status = Status()
        alert_status.update_status(status, context)
        self.vip.health.send_alert(key, alert_status)

    def _update_and_get_context_status(self, updates):
        self._current_status_context.update(updates)
        context_copy = self._current_status_context.copy()
        new_status = self._get_status_from_context(context_copy)
        return context_copy, new_status

    def _send_alert(self, updates, key):
        context_copy, new_status = self._update_and_get_context_status(updates)
        self._async_call.send(None, self._send_alert_callback, new_status, context_copy, key)

    # TODO docs
    # Agent lifecycle methods

    @Core.receiver("onstart")
    def setup(self, sender, **kwargs):
        if self.polling_locations:
            self.core.periodic(self.poll_interval, self.poll_for_locations)

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
            _log.error(self._max_size_gb)
            self.max_pages = max_storage_bytes / page_size
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

    # TODO return the json strings as dictionaries
    # cache data storage and retrieval methods
    # TODO look these over, remove request time
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

    def get_forecast_data(self, service_name, location):
        """
        Retrieves the most recent forecast record set (forecast should be a time-series) by location
        :param service_name:
        :param location:
        :return: list of forecast records
        """
        try:
            cursor = self._sqlite_conn.cursor()
            query = """SELECT LOCATION, GENERATION_TIME, FORECAST_TIME, POINTS 
                       FROM {table} 
                       WHERE LOCATION = ? 
                       AND FORECAST_TIME > ?
                       AND GENERATION_TIME =
                       (SELECT MAX(GENERATION_TIME) 
                        FROM {table}
                        WHERE LOCATION = ?) 
                       ORDER BY FORECAST_TIME ASC;""".format(table=service_name)
            _log.debug(query)
            cursor.execute(query, (location, datetime.datetime.utcnow(),
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
            query = """SELECT ID, LOCATION, OBSERVATION_TIME, POINTS 
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
        if self._max_size_gb is not None:
            self.manage_cache_size()
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
        if self._max_size_gb is not None:
            cache_full = self.page_count(cursor) >= self.max_pages
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
                                           (now-service["update_interval"]))
                elif attempt == 2:
                    for table_name, service in self._api_services.iteritems():
                        # Remove all data that is older than update interval
                        if service["type"] == "forecast":
                            query = """DELETE FROM {table} 
                                       WHERE GENERATION_TIME < ?""".format(
                                table=table_name)
                            cursor.execute(query,
                                           (now - service["update_interval"]))
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

