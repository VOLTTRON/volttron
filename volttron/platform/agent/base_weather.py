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
import sqlite3
import datetime
import threading
import requests
from functools import wraps
from abc import abstractmethod
from Queue import Queue, Empty
import gevent
from gevent import get_hub
from volttron.platform.agent import utils
from volttron.platform.vip.agent import *
from volttron.platform.async import AsyncCall
from volttron.platform.messaging import headers
from volttron.platform.messaging.health import (STATUS_BAD,
                                                STATUS_UNKNOWN,
                                                STATUS_GOOD,
                                                STATUS_STARTING,
                                                Status)

_log = logging.getLogger(__name__)

HEADER_NAME_DATE = headers.DATE
HEADER_NAME_CONTENT_TYPE = headers.CONTENT_TYPE

STATUS_KEY_PUBLISHING = "publishing"
STATUS_KEY_CACHE_FULL = "cache_full"


# TODO process loop/ agent lifecycle
class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    def __init__(self,
                 service=None,
                 **kwargs):

        super(BaseWeatherAgent, self).__init__(**kwargs)
        self._async_call = AsyncCall()
        self._service = service
        self._api_key = None
        self._max_size_gb = None
        self._log_sql = False
        self._polling_locations = []
        self._current_status_context = {}
        self._default_config = {
                                "api_key": self._api_key,
                                "max_size_gb": self._max_size_gb,
                                "log_sql": self._log_sql
                               }
        self.unit_registry = pint.UnitRegistry()
        self.weather_mapping = {}
        self._api_features = {}
        self._update_intervals = {}
        self._tables = {}
        self._cache = None
        self._current_status_context = {
            STATUS_KEY_PUBLISHING: True,
            STATUS_KEY_CACHE_FULL: False
        }
        # TODO successfully publishing should not affect the status if polling is not being used
        self.succesfully_publishing = True
        self.reverse_map = self.get_reverse_mapping()
        self.vip.config.set_default("config", self._default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")

    # Configuration methods

    def get_reverse_mapping(self):
        """Helper method for fetching the standardized_point_name based on a service_point_name"""
        reverse_mappings = {}
        for key in self.weather_mapping:
            value = self.weather_mapping[key]["Service_Point_Name"]
            reverse_mappings[value] = key
        return reverse_mappings

    def update_default_config(self, config):
        """
        May be called by historians to add to the default configuration for its
        own use.
        """
        self._default_config.update(config)
        self.vip.config.set_default("config", self._default_config)

    def parse_weather_mapping(self, config_dict):
        """
        Parses the registry config, which should contain a mapping of service points to standardized points, with
        specified unit
        :param config_dict:
        """
        for map_item in config_dict:
            standard_point_name = map_item.get("Standard_Point_Name")
            service_point_name = map_item.get("Service_Point_Name")
            standardized_units = map_item.get("Standardized_Units")
            service_units = map_item.get("Service_Units")
            self.weather_mapping[standard_point_name] = {"Service_Point_Name": service_point_name,
                                                         "Standardized_Units": standardized_units,
                                                         "Service_units": service_units}

    # TODO copy documentation?
    def _configure(self, config_dict, registry_config):
        self.vip.heartbeat.start()
        _log.info("Configuring weather agent.")
        config = self._default_config.copy()
        config.update(config_dict)
        try:
            api_key = config.get("api_key")
            max_size_gb = config.get("max_size_gb")
            log_sql = config.get("log_sql", False)
            polling_locations = config.get("poll_locations")
            if max_size_gb is not None:
                max_size_gb = float(max_size_gb)
            self.parse_weather_mapping(registry_config)
        except ValueError:
            _log.error("Failed to load base weather agent settings. Settings not applied!")
            return
        self._api_key = api_key
        self._max_size_gb = max_size_gb
        self._log_sql = log_sql
        self._polling_locations = polling_locations
        try:
            self.configure(config)
        except:
            _log.error("Failed to load weather agent settings.")

    def configure(self, configuration):
        """Optional, may be implemented by a concrete implementation to add support for the configuration store.
        Values should be stored in this function only.

        The process thread is stopped before this is called if it is running. It is started afterwards."""
        pass

    # RPC, helper and abstract methods to be used by concrete implementations of the weather agent

    @RPC.export
    def get_api_features(self):
        return self._api_features

    @RPC.export
    def get_version(self):
        return self.version()

    @abstractmethod
    def version(self):
        """"""

    @RPC.export
    def get_current_weather(self, location):
        return self.query_current_weather(location)

    @abstractmethod
    def query_current_weather(self, location):
        """"""

    @RPC.export
    def get_hourly_forecast(self, location):
        return self.query_hourly_forecast(location)

    @abstractmethod
    def query_hourly_forecast(self, location):
        """"""

    @RPC.export
    def get_hourly_historical_weather(self, location, start_period, end_period):
        return self.query_hourly_historical_weather(location, start_period, end_period)

    @abstractmethod
    def query_hourly_historical_weather(self, location, start_period, end_period):
        """"""

    def poll_for_locations(self):
        topic = "weather/{}/current/{}/all"
        for location in self._polling_locations:
            if len(location):
                try:
                    data_point = self.query_current_weather(location)
                    poll_topic = topic.format("poll", location)
                    self.publish_response(poll_topic, data_point)
                except ValueError:
                    self.successfully_publishing = False
                    # TODO alerts/ status update
                    raise
                except RuntimeError as error:
                    # TODO alerts/status update
                    error_topic = topic.format("error", location)
                    self.publish_error(error_topic, error)

    def publish_error(self, topic, error):
        _log.error(error)
        self.publish_response(topic, error)

    def publish_response(self, topic, publish_items):
        publish_headers = {HEADER_NAME_DATE: utils.format_timestamp(utils.get_aware_utc_now()),
                           HEADER_NAME_CONTENT_TYPE: headers.CONTENT_TYPE}
        self.vip.pubsub.publish(peer="pubsub", topic=topic, message=publish_items, headers=publish_headers)

    def manage_unit_conversion(self, from_units, value, to_units):
        """
        Used to convert units from a query response to the expected standardized units
        :param from_units: pint formatted unit string for the current value
        :param value: magnitude of a measurement
        :param to_units: pint formatted unit string for the output value
        :return: magnitude of measurement in the desired units
        """
        if ((1 * self.unit_registry.parse_expression(from_units)) ==
                (1 * self.unit_registry.parse_expression(to_units))):
            return value
        else:
            updated_value = (value * self.unit_registry(from_units)).to(self.unit_registry(to_units)).magnitude
            return updated_value

    # methods to hide cache functionality from concrete weather agent implementations

    def get_cached_current_data(self, request_name, location):
        self._cache.get_current_data(request_name, location)

    def get_cached_forecast_data(self, request_name, location):
        self._cache.get_forecast_data(request_name, location)

    def get_cached_historical_data(self, request_type, location, start_timestamp, end_timestamp):
        self._cache.get_historical_data(request_type, location, start_timestamp, end_timestamp)

    def store_weather_records(self, request_name, request_type, records):
        """

        :param request_name:
        :param request_type:
        :param records:
        """
        self._cache.manage_cache_size()
        # TODO update status?
        self._current_status_context[STATUS_KEY_CACHE_FULL] = \
            self._cache.store_weather_records(request_name, request_type, records)
        # TODO alerts?

    # Status management methods

    @staticmethod
    def _get_status_from_context(context):
        status = STATUS_GOOD
        if context.get("cache_full") or not context.get("publishing"):
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

    # Agent lifecycle methods

    @Core.receiver("onstart")
    def onstart(self):
        if self._polling_locations:
            self.core.periodic(self._update_intervals["current"], self.poll_for_locations)

    @Core.receiver("onstop")
    def onstop(self):
        self._cache.close()


# TODO tables may be being used improperly
class WeatherCache:
    """Caches data to help reduce the number of requests to the API"""

    def __init__(self,
                 service_name,
                 tables=None,
                 max_size_gb=1,
                 log_sql=False,
                 check_same_thread=True):
        """

        :param service_name: Name of the weather service (i.e. weather.gov)
        :param tables: dict formatted as {key: table_name, value: request_type} where request type is  one of
        ['current', 'forecast', 'historical']
        :param max_size_gb: maximum size in gigabytes of the sqlite database file, useful for deployments with limited
        storage capacity
        :param log_sql: if True, all sql statements executed will be written to log.info
        """
        self._service_name = service_name
        self._db_file_path = self._service_name + ".sqlite"
        self._log_sql = log_sql
        self._tables = tables
        self._max_size_gb = max_size_gb
        self._sqlite_conn = None
        self._setup_cache(check_same_thread)

    # cache setup methods

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
        for request_name in self._tables:
            self.create_table(request_name)
        cursor = self._sqlite_conn.cursor()
        if self._max_size_gb is not None:
            cursor.execute('''PRAGMA page_size''')
            page_size = cursor.fetchone()[0]
            max_storage_bytes = self._max_size_gb * 1024 ** 3
            self.max_pages = max_storage_bytes / page_size
        cursor.close()

    def table_exists(self, request_name, cursor):
        """
        Checks if a table can be found in the database, for use during database initialization
        :param request_name: name of the table to check for
        :param cursor: cursor object, avoids redundant cursor objects
        :return: True if the table is in the database, else False
        """
        table_query = "SELECT 1 FROM {} WHERE TYPE = 'table' AND NAME='{}'".format(self._service_name, request_name)
        if self._log_sql:
            _log.info(table_query)
        return bool(cursor.execute(table_query))

    def create_table(self, request_name):
        """Populates the database with the given table, and checks that all of the requisite columns exist
        :param request_name: the name of the request for which we want to store data
        """
        cursor = self._sqlite_conn.cursor()
        if not self.table_exists(request_name, cursor):
            table_type = self._tables[request_name]
            if table_type == "forecast":
                create_table = """CREATE TABLE {}
                                                (LOCATION TEXT NOT NULL,
                                                 REQUEST_TIME TIMESTAMP NOT NULL,
                                                 DATA_TIME TIMESTAMP NOT NULL,
                                                 FORECAST_TIME TIMESTAMP NOT NULL,
                                                 JSON_RESPONSE TEXT NOT NULL) 
                                                 PRIMARY KEY (LOCATION, REQUEST_TIME))""".format(request_name)
            else:
                create_table ="""CREATE TABLE {}
                                (LOCATION TEXT NOT NULL,
                                 REQUEST_TIME TIMESTAMP NOT NULL,
                                 DATA_TIME TIMESTAMP NOT NULL, 
                                 JSON_RESPONSE TEXT NOT NULL) 
                                 PRIMARY KEY (LOCATION, REQUEST_TIME))""".format(request_name)
            if self._log_sql:
                _log.info(create_table)
            try:
                cursor.execute(create_table)
                self._sqlite_conn.commit()
            except sqlite3.Error as err:
                _log.error("Unable to create database table: {}".format(err))
        else:
            cursor.execute("pragma table_info({});".format(request_name))
            name_index = 0
            for description in cursor.description:
                if description[0] == "name":
                    break
                name_index += 1
            columns = {"LOCATION": False, "REQUEST_TIME": False, "DATA_TIME": False, "JSON_RESPONSE": False}
            for row in cursor:
                if row[name_index] in columns:
                    columns[row[name_index]] = True
            for column in columns:
                if not columns[column]:
                    _log.error("The Database is missing column {}.".format(columns[column]))
        cursor.close()

    # cache data storage and retrieval methods

    def get_current_data(self, request_name, location):
        """
        Retrieves the most recent current data by location
        :param request_name:
        :param location:
        :return: a single current weather observation record
        """
        try:
            cursor = self._sqlite_conn.cursor()
            query = """SELECT * FROM (SELECT * FROM {} WHERE LOCATION = {} ORDER BY DATA_TIME DESC) LIMIT 1"""\
                .format(request_name, location)
            if self._log_sql:
                _log.info(query)
            cursor.execute(query)
            data = cursor.fetchone()
            cursor.close()
            return data
        except sqlite3.Error as e:
            _log.error("Error fetching current data from cache: {}".format(e))
            return None

    def get_forecast_data(self, request_name, location):
        """
        Retrieves the most recent forecast record set (forecast should be a time-series) by location
        :param request_name:
        :param location:
        :return: list of forecast records
        """
        try:
            cursor = self._sqlite_conn.cursor()
            query = """SELECT * FROM {} WHERE LOCATION = {} AND DATA_TIME = 
                    (SELECT MAX(DATA_TIME) FROM {} WHERE LOCATION = {}})""".format(request_name, request_name, location)
            if self._log_sql:
                _log.info(query)
            cursor.execute(query)
            data = cursor.fetchall()
            cursor.close()
            return data
        except sqlite3.Error as e:
            _log.error("Error fetching forecast data from cache: {}".format(e))

    def get_historical_data(self, request_type, location, start_timestamp, end_timestamp):
        """
        Retrieves historical data over the the given time period by location
        :param request_type:
        :param location:
        :param start_timestamp:
        :param end_timestamp:
        :return: list of historical records
        """
        try:
            cursor = self._sqlite_conn.cursor()
            query = """SELECT * FROM {} WHERE LOCATION = {} AND DATA_TIME >= {} AND DATA_TIME <= {} 
                    ORDER BY DATA_TIME ASC""".format(request_type, location, start_timestamp, end_timestamp)
            if self._log_sql:
                _log.info(query)
            cursor.execute(query)
            data = cursor.fetchall()
            cursor.close()
            return data
        except sqlite3.Error as e:
            _log.error("Error fetching historical data from cache: {}".format(e))

    def store_weather_records(self, request_name, request_type, records):
        """
        Request agnostic method to store weather records in the cache.
        :param request_name:
        :param request_type:
        :param records: expects a list of records (as lists) formatted to match tables
        """
        cursor = self._sqlite_conn.cursor()
        if request_type == "current":
            query = "INSERT INTO {} (LOCATION, REQUEST_TIME, DATA_TIME, FORECAST_TIME, JSON_RESPONSE)" \
                    "VALUES (?, ?, ?, ?, ?)".format(request_name)
        else:
            query = "INSERT INTO {} (LOCATION, REQUEST_TIME, DATA_TIME, JSON_RESPONSE) VALUES (?, ?, ?, ?)"\
                .format(request_name)
        if self._log_sql:
            _log.info(query)
        try:
            cursor.executemany(query, records)
            self._sqlite_conn.commit()
        except sqlite3.Error as e:
            _log.info(query)
            _log.error("Failed to store data in the cache: {}".format(e))
        cache_full = self.page_count(cursor) >= self.max_pages
        cursor.close()
        return cache_full

    # cache management/ lifecycle methods

    def page_count(self, cursor):
        cursor.execute("PRAGMA page_count")
        return cursor.fetchone()[0]

    def manage_cache_size(self):
        """
        Removes data from the weather cache until the cache is a safe size. prioritizes removal from current, then
        forecast, then historical request types
        """
        cursor = self._sqlite_conn.cursor()
        if self._max_size_gb is not None:
            row_counts = {}
            for table in self._tables:
                query = "SELECT COUNT(*) FROM {}".format(table)
                row_counts[table] = (int(cursor.execute(query).fetchone()[0]), self._tables[table])
            priority = 1
            while self.page_count(cursor) > self.max_pages:
                for table in row_counts:
                    if priority == 1:
                        # Remove all but the most recent 'current' records
                        if row_counts[table][1] == "current" and row_counts[table][0] > 1:
                            query = "SELECT MAX(DATA_TIME) FROM {}".format(table)
                            most_recent = cursor.execute(query).fetchone()[0]
                            query = "DELETE FROM {} WHERE DATA_TIME < {}".format(table, most_recent)
                            cursor.execute(query)
                            self._sqlite_conn.commit()
                    elif priority == 2:
                        # Remove all but the most recent 'forecast' records
                        if row_counts[table][1] == "forecast" and row_counts[table][0] > 1:
                            query = "SELECT MAX(DATA_TIME) FROM {}".format(table)
                            most_recent = cursor.execute(query).fetchone()[0]
                            query = "DELETE FROM {} WHERE DATA_TIME < {}".format(table, most_recent)
                            cursor.execute(query)
                    elif priority == 3:
                        # Remove historical records in batches of 100 until the table is of appropriate size
                        if row_counts[table][1] == "historical" and row_counts[table][0] >= 1:
                            query = "DELETE FROM {} ORDER BY REQUEST_TIME ASC LIMIT 100".format(table)
                            cursor.execute(query)
                    self._sqlite_conn.commit()
                    priority += 1

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


# TODO documentation
class BaseWeather(BaseWeatherAgent):
    def __init__(self, service):
        _log.debug('Constructor of BaseWeather thread: {}'.format(
            threading.currentThread().getName()
        ))
        super(BaseWeather, self).__init__(service)
