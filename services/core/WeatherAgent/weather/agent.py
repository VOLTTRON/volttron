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
from abc import abstractmethod
from volttron.platform.agent import utils
from volttron.platform.vip.agent import *

_log = logging.getLogger(__name__)

# TODO testing
testing_config_path = os.path.dirname(os.path.realpath(__file__))
testing_config_path += "/config.config"


class WeatherCache:
    """Caches data to help reduce the number of requests to the API"""
    # TODO close the database connection onstop for the weather agent
    def __init__(self,
                 db_name,
                 service_name,
                 retain_records=0,
                 max_size_gb=1,
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
        self.db_filepath = "" + self.db_name
        self.log_sql = log_sql
        self.service_name = service_name
        self.tables = {}
        self.retain_records = retain_records
        self.max_size_gb = max_size_gb
        # Arbitrarily set values to ensure that the cache does not overflow
        self.trim_percent = 70
        self.max_percent = 90

    def setup_cache(self):
        """Check if the database exists, create it if it does not"""
        try:

            self.sqlite_conn = sqlite3.connect(self.db_filepath)
            self.current_size = os.path.getsize(self.db_filepath)
            _log.info("connected to database {} sqlite version: {}".format(self.db_name, sqlite3.version))
            self.sqlite_cursor = self.sqlite_conn.cursor()
        except sqlite3.Error as err:
            _log.error("Unable to open the sqlite database for caching: {}".format(err))

    def table_exists(self, request_type):
        table_name = self.service_name + "_" + request_type
        table_query = "SELECT 1 FROM {} WHERE TYPE = 'table' AND NAME='{}'"\
                    .format(self.db_name, table_name)
        if self.log_sql:
            _log.info(table_query)

    def create_table(self, request_type):
        """"""
        if not self.table_exists(request_type):
            create_table = "CREATE TABLE {} (LOCATION TEXT, REPORTED_TIME TIMESTAMP, JSON_RESPONSE TEXT, " \
                           "PRIMARY KEY (LOCATION, REQUEST_TIME))".format()
            if self.log_sql:
                _log.info(create_table)
            try:
                self.sqlite_cursor.execute(create_table)
                self.sqlite_conn.commit()
            except sqlite3.Error as err:
                _log.error("Unable to create database table: {}".format(err))

    # TODO
    def store_weather_data(self, request_type, location, timestamp, json_string):
        """Helper method to provide insert statement agnostic of record type (Records should be pre-formatted)."""
        table = self.tables[request_type]
        query = "INSERT INTO {} (LOCATION, REPORTED_TIME, JSON_RESPONSE) VALUES({}, {}, {})"\
            .format(table, location, timestamp, json_string)

    def data_has_gaps(self, start_timestamp, end_timestamp, interval):
        """Queries the table to check if there are any gaps in the records based on the expected interval between
        records. Expects start_timestamp and end_timestamp as datetime objects, interval as timedelta object."""
        if not (isinstance(start_timestamp, datetime.datetime) and isinstance(end_timestamp, datetime.datetime)
                and isinstance(interval, datetime.timedelta)):
            raise ValueError("expects two datetime.datetime objects, followed by datetime.timedelta object")
        period = datetime.timedelta(end_timestamp - start_timestamp).total_seconds()
        num_rows = math.floor(period / interval.total_seconds())
        # TODO generate query

    def retrieve_cached_data_by_timestamp(self, request_type, start_timestamp, end_timestamp):
        """Returns all cached weather data based on the request type for
        the given time range."""
        query = "SELECT * FROM {} WHERE REQUEST_TIME >= {} AND REPORTED_TIME <= {} ORDER BY REQUEST_TIME DESC"\
            .format(self.tables[request_type], start_timestamp, end_timestamp)
        if self.log_sql:
            _log.info(query)
        # TODO validate
        return self.sqlite_conn.execute(query)

    def retrieve_most_recent_cached_data(self, request_type, location, number_of_records=1):
        query = "SELECT * FROM {} WHERE REPORTED_TIME = (SELECT MAX(REPORTED_TIME) FROM {}) AND Location = {} " \
                "ORDER BY REQUEST_TIME DECS LIMIT {}"\
            .format(self.tables[request_type], self.tables[request_type], location, number_of_records)
        if self.log_sql:
            _log.info(query)
        # TODO validate
        return self.sqlite_cursor.execute(query)

    # TODO
    def cleanup_outdated_cached_data(self, request_type):
        """Removes outdated current and forecasted weather data. Retains an optional number of records."""

    # TODO
    # look at base historian caching
    def trim_cache(self, time_increment=datetime.timedelta(hours=1)):
        """Delete historical data when the cache starts to become full."""


#
class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    def __init__(self,
                 **kwargs):

        super(BaseWeatherAgent, self).__init__(**kwargs)
        # TODO set defaults, take a look at base historian

        # TODO create a default configuration
        self._default_config = {}
        self.vip.config.set_default("config", self._default_config)
        self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")

    @Core.receiver('onstart')
    def setup(self, config):
        # try:
        #     self.configure(config)
            # TODO check this, might need to go in configure
        # except Exception as e:
        #     _log.error("Failed to load weather agent settings.")
        # TODO do we need this?
        # self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")
        # self.cache = WeatherCache()



    # TODO
    @abstractmethod
    def _configure(self, contents):
        self.vip.heartbeat.start()
        _log.info("Configuring weather agent.")
        config = self._default_config.copy()
        config.update(contents)

        try:
            # TODO reset defaults from configuration
        except ValueError as e:
            _log.error("Failed to load base weather agent settings. Settings not applied!")
            return

        self.stop_process_thread()
        try:
            self.configure(config)
        except Exception as e:
            _log.error("Failed to load weather agent settings.")
        self.start_process_thread()

    # TODO
    @abstractmethod
    def get_current_weather(self, location):
        pass

    # TODO
    @abstractmethod
    def get_forecast(self, location):
        pass

    @abstractmethod
    def get_historical_weather(self, location, start_period, end_period):
        pass




