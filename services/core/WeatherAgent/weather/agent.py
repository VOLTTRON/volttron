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
import os
import sys
import math
import requests
import sqlite3
import datetime
import threading
from functools import wraps
from abc import abstractmethod
import gevent
from gevent import get_hub
from volttron.platform.agent import utils
from volttron.platform.vip.agent import *

_log = logging.getLogger(__name__)

# TODO testing
testing_config_path = os.path.dirname(os.path.realpath(__file__))
testing_config_path += "/config.config"

class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    def __init__(self,
                 db_name="weather_cache",
                 max_size_gb=None,
                 log_sql=False,
                 **kwargs):

        super(BaseWeatherAgent, self).__init__(**kwargs)
        self._db_name = db_name
        self._max_size_gb = max_size_gb
        self._log_sql = log_sql
        self._default_config = {
                                "db_name": self._db_name,
                                "max_size_gb": self._max_size_gb,
                                "log_sql": self._log_sql
                               }
        self.vip.config.set_default("config", self._default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")

    def update_default_config(self, config):
        """
        May be called by historians to add to the default configuration for its
        own use.
        """
        self._default_config.update(config)
        self.vip.config.set_default("config", self._default_config)

    # TODO check with Kyle
    def start_process_thread(self):
        if self._process_loop_in_greenlet:
            self._process_thread = self.core.spawn(self._process_loop)
            self._process_thread.start()
            _log.debug("Process greenlet started.")
        else:
            self._process_thread = threading.Thread(target=self._process_loop)
            self._process_thread.daemon = True  # Don't wait on thread to exit.
            self._process_thread.start()
            _log.debug("Process thread started.")

    # TODO documentation (look at baseHistorian)
    def manage_cache_size(self, historical_limit_timestamp, storage_limit_gb):
        """

        :param historical_limit_timestamp: remove all data older than this timestamp from historical data
        :param storage_limit_gb: remove oldest historical data until database is smaller than this value
        """
        pass

    # TODO ask Kyle
    def stop_process_thread(self):
        _log.debug("Stopping the process loop.")
        if self._process_thread is None:
            return

        # Tell the loop it needs to die.
        self._stop_process_loop = True
        # Wake the loop.
        self._event_queue.put(None)

        # 9 seconds as configuration timeout is 10 seconds.
        self._process_thread.join(9.0)
        # Greenlets have slightly different API than threads in this case.
        if self._process_loop_in_greenlet:
            if not self._process_thread.ready():
                _log.error("Failed to stop process greenlet during reconfiguration!")
        elif self._process_thread.is_alive():
            _log.error("Failed to stop process thread during reconfiguration!")

        self._process_thread = None
        _log.debug("Process loop stopped.")

    # TODO take a look at basehistorian
    def _configure(self, contents):
        self.vip.heartbeat.start()
        _log.info("Configuring weather agent.")
        config = self._default_config.copy()
        config.update(contents)

        self.cache = WeatherCache()

        try:
            # TODO reset defaults from configuration
        except ValueError as err:
            _log.error("Failed to load base weather agent settings. Settings not applied!")
            return

        self.stop_process_thread()
        try:
            self.configure(config)
        except Exception as err:
            _log.error("Failed to load weather agent settings.")
        self.start_process_thread()

    def configure(self, configuration):
        """Optional, may be implemented by a concrete implementation to add support for the configuration store.
        Values should be stored in this function only.

        The process thread is stopped before this is called if it is running. It is started afterwards."""
        pass

    # TODO do we need this?

    def get_data(self, method, request, cache_callback, location, **kwargs):
        # TODO get data from cache via callback
        data = self.cache.cache_callback(location, **kwargs)
        if not data:
            data = requests.request(method, request)
        return data

    @abstractmethod
    def resolve_location(self, location):

    @RPC.export
    def get_current_weather(self, location):
        return self.query_current_weather(location)

    @abstractmethod
    def query_current_weather(self, location):


    @RPC.export
    def get_hourly_forecast(self, location):
        return self.query_hourly_forecast(location)

    @abstractmethod
    def query_hourly_forecast(self):

    @RPC.export
    def get_daily_historical_weather(self, location, start_period, end_period):
        return self.query_daily_historical_weather(location, start_period, end_period)

    @abstractmethod
    def query_daily_historical_weather(self, location, start_period, end_period):

    @staticmethod
    def _get_status_from_context(context):
        status = STATUS_GOOD
        if (context.get("backlogged") or
                context.get("cache_full") or
                not context.get("publishing")):
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

    # TODO check base historian
    def _process_loop(self):
        _log.debug("Starting process loop.")

# TODO: define columns, implement other caching features
class WeatherCache:
    """Caches data to help reduce the number of requests to the API"""

    # TODO close the database connection onstop for the weather agent
    def __init__(self,
                 db_name,
                 service_name,
                 max_size_gb=1,
                 request_types=[],
                 log_sql=False):
        """

        :param db_name: file name of mysql database file, should be specified in agent
         configuration
        :param service_name: Name of the weather service (i.e. weather.gov)
        :param cache_period: Specifies time period for which we keep data
        :param cache_size: Specifies the size of cache to store data, in gb
        """
        self.db_name = db_name
        # TODO check from base historian
        self.db_filepath = self.db_name + ".sqlite"
        self.log_sql = log_sql
        self.service_name = service_name
        for request in request_types:
            self.tables[request] = service_name + "_" + request
        self._default_columns = {"CURRENT": ["LOCATION", "REQUEST_TIME", "OBS_TIME", "JSON_STRING"],
                                 "FORECAST_HOURLY": ["LOCATION", "REQUEST_TIME", "PREDICTION_TIME",
                                                     "JSON_STRING"],
                                 "HISTORICAL_DAILY": ["LOCATION", "REQUEST_TIME", "", "JSON_STRING"]}
        self._max_size_gb = max_size_gb
        # Arbitrarily set values to ensure that the cache does not overflow
        self.trim_percent = 70
        self.max_percent = 90

        self.setup_cache()

    def setup_cache(self, check_same_thread):
        # Check if the database exists, create it if it does not
        try:
            # TODO
            self._sqlite_conn = sqlite3.connect(
                self.db_filepath,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=check_same_thread)
            self.current_size = os.path.getsize(self.db_filepath)
            _log.info("connected to database {} sqlite version: {}".format(self.db_name, sqlite3.version))

            cursor = self.sqlite_conn.cursor()

            if self._max_size_gb is not None:
                cursor.execute('''PRAGMA page_size''')
                page_size = cursor.fetchone()[0]
                max_storage_bytes = self._max_size_gb * 1024 ** 3
                self.max_pages = max_storage_bytes / page_size
        except sqlite3.Error as err:
            _log.error("Unable to open the sqlite database for caching: {}".format(err))
        # create tables if they don't exist
        for request in self.tables:
            self.create_table(self.tables[request], cursor)

    def table_exists(self, request_type, cursor):
        table_query = "SELECT 1 FROM {} WHERE TYPE = 'table' AND NAME='{}'" \
            .format(self.db_name, request_type)
        if self.log_sql:
            _log.info(table_query)
        return bool(cursor.execute(table_query))

    def create_table(self, request_type, columns):
        """Populate the database with the given table"""
        cursor = self._sqlite_conn.cursor()
        if not self.table_exists(request_type):
            create_table = "CREATE TABLE {} (LOCATION TEXT, REQUEST_TIME TIMESTAMP, JSON_RESPONSE TEXT, " \
                           "PRIMARY KEY (LOCATION, REQUEST_TIME))".format(request_type)
            if self.log_sql:
                _log.info(create_table)
            try:
                cursor.execute(create_table)
                self._sqlite_conn.commit()
            except sqlite3.Error as err:
                _log.error("Unable to create database table: {}".format(err))
        # check that the table columns are correct
        else:
            cursor.execute("pragma table_info({});".format(request_type))
            name_index = 0
            for description in cursor.description:
                if description[0] == "name":
                    break
                name_index += 1

    def close(self):
        self._sqlite_conn.close()
        self._sqlite_conn = None


def _using_threadpool(method):
    @wraps(method, ['__name__', '__doc__'])
    def apply(*args, **kwargs):
        return get_hub().threadpool.apply(method, args, kwargs)
    return apply


# TODO checkout base historian
class AsyncWeatherCache(WeatherCache):
    def __init__(self, **kwargs):
        kwargs["check_same_thread"] = False
        super(AsyncWeatherCache, self).__init__(**kwargs)

# TODO fill with methods, check base historian
for method in []:
    setattr(AsyncWeatherCache, method.__name__, _using_threadpool(method))


class BaseWeather(BaseWeatherAgent):
    def __init__(self, **kwargs):
        _log.debug('Constructor of BaseWeather thread: {}'.format(
            threading.currentThread().getName()
        ))
        super(BaseWeather, self).__init__(**kwargs)