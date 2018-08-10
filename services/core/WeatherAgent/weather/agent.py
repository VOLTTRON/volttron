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

VALID_REQUEST_TYPES = ['forecast', 'current', 'historical']

class WeatherSchema:
    def __init__(self,
                 schema_mapping):
        self.base_schema = schema_mapping
        self.alternate_schema = {}

    def map_schema(self, mapping):
        for key, value in mapping:
            if key in self.base_schema:
                self.base_schema[key] = value
            else:
                self.alternate_schema[key] = value


class WeatherCache:
    """Caches data to create a local history, and to help reduce the
    number of requests to the API"""
    # TODO close the database connection onstop for the weather agent
    # TODO check that the appropriate tables exist, based
    # on the weather service
    def __init__(self,
                 db_name,
                 service_name,
                 request_types,
                 cache_period,
                 max_size,
                 trim_percent=70,
                 max_percent=90,
                 log_sql=True):
        """

        :param db_name:
        :param service_name: Name of the weather service (i.e. weather.gov)
        :param expected_tables: Names for tables, based on available request services
        (see VALID_REQUEST_TYPES)
        :param cache_period: Specifies time period for which we keep data
        :param cache_size: Specifies the size of cache to store data, in gb
        """
        self.db_name = db_name
        self.db_filepath = "" + db_name
        # TODO log sql statements
        self.log_sql = log_sql
        self.service_name = service_name
        self.tables = {}
        for request_type in request_types:
            if request_type in VALID_REQUEST_TYPES:
                self.tables[request_type] = service_name + "_" + request_type
            else:
                _log.debug("In WeatherCache: Invalid request type: ?", request_type)
                # TODO should we pass?
                pass
        self.trim_period = cache_period
        try:
            # Check if the database and tables exist, create them if they do not
            self.sqlite_conn = sqlite3.connect(self.db_filepath)
            self.current_size = os.path.getsize(self.db_filepath)
            _log.debug("connected to database ?, version: ?", self.db_name, sqlite3.version)
        except sqlite3.Error as err:
            _log.debug("Unable to open the sqlite database for caching: ?", err)
            # TODO should we pass?
            pass
        self.sqlite_cursor = self.sqlite_conn.cursor()
        try:
            for table in self.tables:
                if not self.sqlite_cursor.execute("SELECT 1 FROM ? WHERE TYPE = 'table' AND NAME='?'"
                                                   ,db_name, self.tables[table]):
                    self.sqlite_cursor.execute("CREATE TABLE ? (LOCATION TEXT, REQUEST_TIME TIMESTAMP, "
                                               "JSON_RESPONSE TEXT, PRIMARY KEY (LOCATION, REQUEST_TIME))",
                                               self.tables[table])
                    self.sqlite_conn.commit()
        except sqlite3.Error as err:
            _log.debug("Unable to access database tables: ?", err)
            # TODO should we pass?
            pass
        self.max_size = max_size
        self.trim_percent = trim_percent
        self.max_percent = max_percent

    def retrieve_cached_data_by_timestamp(self, request_type, start_timestamp, end_timestamp):
        """Returns all cached weather data based on the request type for
        the given time range"""
        return self.sqlite_conn.execute("SELECT * FROM ? WHERE REQUEST_TIME >= ? AND REQUEST_TIME <= ? ORDER BY"
                                        "REQUEST_TIME DESC",
                                        self.tables[request_type], start_timestamp, end_timestamp)

    def retrieve_most_recent_cached_data(self, request_type, location, number_of_records=1):
        return self.sqlite_cursor.execute("SELECT * FROM ? WHERE REQUEST_TIME = (SELECT MAX(REQUEST_TIME) FROM ?) AND"
                                          " Location = ? ORDER BY REQUEST_TIME DECS LIMIT ?",
                                          self.tables[request_type], self.tables[request_type], location,
                                          number_of_records)

    def trim_outdated_cached_data(self):
        """Regularly eliminates data cached from cache_period time before present,
        only if the cache is sufficiently full?"""
        # TODO this method should be run once per cache_period amount of time
        cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(self.cache_period)
        for table in self.tables:
            try:
                self.sqlite_cursor.execute("DELETE FROM ? WHERE REQUEST_TIME <= ?", table, cutoff_time)
                self.sqlite_conn.commit()
            except sqlite3.Error as err:
                _log.debug("Unable to remove old data from table ?: ?", table, err)
                # TODO should we pass?
                pass

    def trim_excess_cached_data(self, time_increment=datetime.timedelta(hours=1)):
        """Deletes oldest data in batches based on an arbitrary time increment until the database size is reasonable
        to prevent the cache from becoming too large."""
        # TODO this should occur every so often...maybe after n= some arbitrary number of writes
        try:
            self.current_size = os.path.getsize(self.db_filepath)
        except sqlite3.Error as err:
            _log.debug("Sqlite database unavailable: ?", err)
            # TODO should we pass?
            pass
            # don't allow unreasonable delta ranges
        if time_increment <= datetime.timedelta(minutes=30) or time_increment > datetime.timedelta(days=1):
            raise ValueError
        cutoff_time = datetime.datetime.utcnow() - time_increment
        while self.current_size / self.max_size > self.trim_percent:
            self.current_size = os.path.getsize(self.db_filepath)
            for table in self.tables:
                self.sqlite_cursor.execute("DELETE FROM ? WHERE REQUEST_TIME <= ?", table, cutoff_time)
                self.sqlite_conn.commit()


# class WeatherAgent():
class BaseWeatherAgent(Agent):
    """Creates weather services based on the json objects from the config,
    uses the services to collect and publish weather data"""

    # TODO set up defaults for a weather agent here
    def __init__(self,
                 api_key="",
                 base_url=None,
                 locations=[],
                 **kwargs):
        # TODO figure out if this is necessary
        super(BaseWeatherAgent, self).__init__(**kwargs)
        # TODO set protected variables
        self._api_key = api_key
        self._base_url = base_url
        self._locations = locations
        # TODO build from init parameters

        self._default_config = {"api_key": self._api_key}
        self.vip.config.set_default("config", self._default_config)

    @Core.receiver('onstart')
    def setup(self, config):
        try:
            self.configure(config)
            # TODO check this, might need to go in configure
            self.schema = WeatherSchema()
        except Exception as e:
            _log.error("Failed to load weather agent settings.")
        # TODO ?
        # self.vip.config.subscribe(self._configure, actions=["NEW", "UPDATE"], pattern="config")


    # TODO schema mapping should be contained in the config.config, no registry config necessary?
    @abstractmethod
    def configure(self, config):
        """Unimplemented method stub."""
        pass

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




