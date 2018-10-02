# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import os
import sys
import pytest
import gevent
import logging
import sqlite3
import datetime
from volttron.platform.agent import utils
from volttron.platform.agent.base_weather import BaseWeatherAgent, WeatherCache

utils.setup_logging()
# setup_logging()
_log = logging.getLogger(__name__)

@pytest.mark.weather2
def test_cache_setup_no_size():
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=test_size)
    # does the file exist
    assert os.path.isfile("test.sqlite")
    # do the tables exist
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()
    for table in test_api_services:
        table_info = cursor.execute("PRAGMA table_info({});".format(table)).fetchall()
        table_columns = []
        for row in table_info:
            table_columns.append(row[1])
        if test_api_services[table]["type"] == "forecast":
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME", "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns
    cursor.close()
    connection.close()

# TODO
@pytest.mark.weather2
@pytest.mark.skip
def test_cache_setup_with_size():
    """tests the database's ability to use cache size to manage its size"""
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=0.00002)



@pytest.mark.weather2
def test_create_tables_dropped():
    """Create improper tables in the database, then call create_tables to see if the tables are overwritten.
    Note: tables which contain more than the necessary columns are acceptable."""
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=test_size)

    assert os.path.isfile("test.sqlite")

    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    # test if no tables exist
    for service_name in test_api_services:
        query = "DROP TABLE IF EXISTS {};".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    test_cache.create_tables()

    for table in test_api_services:
        table_info = cursor.execute("PRAGMA table_info({});".format(table)).fetchall()
        table_columns = []
        for row in table_info:
            table_columns.append(row[1])
        if test_api_services[table]["type"] == "forecast":
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME", "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns


@pytest.mark.weather2
def test_create_tables_bad_format():
    """test create tables if the current tables are of improper format"""
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=test_size)

    assert os.path.isfile("test.sqlite")

    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    for service_name in test_api_services:
        query = "DROP TABLE IF EXISTS {};".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    for service_name in test_api_services:
        query = "CREATE TABLE {} (TEST1 TEXT, TEST2 TEXT);".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    # TODO improper tables are created

    test_cache.create_tables()

    for table in test_api_services:
        info_query = "PRAGMA table_info({});".format(table)
        table_info = cursor.execute(info_query).fetchall()
        _log.debug(info_query)
        # TODO not table info -stuff may have not been created
        table_columns = []
        for row in table_info:
            table_columns.append(row[1])
        if test_api_services[table]["type"] == "forecast":
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME", "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns

    cursor.close()
    connection.close()


@pytest.mark.weather2
def test_store_weather_records_success():
    """"""
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=test_size)

    assert os.path.isfile("test.sqlite")

    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    location = "fake_location"
    time = datetime.datetime.utcnow()
    points = "fake points"

    for service_name in test_api_services:
        # make sure to reset tables to make sure the test doesn't get confused
        delete_query = "DELETE FROM {};".format(service_name)
        _log.debug(delete_query)
        cursor.execute(delete_query)
        connection.commit()

        if test_api_services[service_name]["type"] == "current":
            fake_data = [location, time, points]
        elif test_api_services[service_name]["type"] == "forecast":
            fake_data = [[location, time, time, points], [location, time, time, points], [location, time, time, points]]
        elif test_api_services[service_name]["type"] == "history":
            fake_data = [[location, time, points], [location, time, points], [location, time, points]]
        else:
            raise RuntimeError("Incompatible request {} of type {}".format(service_name, [service_name]["type"]))
        test_cache.store_weather_records(service_name, fake_data)

        count_query = "SELECT COUNT(*) FROM {};".format(service_name)
        _log.debug(count_query)

        if test_api_services[service_name]["type"] == "current":
            assert cursor.execute(count_query).fetchone()[0] == 1
        elif test_api_services[service_name]["type"] == "forecast" or \
                test_api_services[service_name]["type"] == "history":
            assert cursor.execute(count_query).fetchone()[0] == 3


@pytest.mark.weather2
def test_get_data_success():
    """ensure that under ideal conditions, all of the methods for fetching data work."""
    test_api_services = {"test_current": {"type": "current"},
                         "test_forecast": {"type": "forecast"},
                         "test_history": {"type": "history"}}
    # test setup without cache management
    test_size = None
    test_cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=test_size)

    assert os.path.isfile("test.sqlite")

    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    location = "fake_location"
    time = datetime.datetime.utcnow()
    points = "fake points"

    for service_name in test_api_services:

        delete_query = "DELETE FROM {};".format(service_name)
        _log.debug(delete_query)
        cursor.execute(delete_query)
        connection.commit()

        if test_api_services[service_name]["type"] == "current":
            fake_data = [location, time, points]
        elif test_api_services[service_name]["type"] == "forecast":
            fake_data = [[location, time, time, points], [location, time, time, points], [location, time, time, points]]
        elif test_api_services[service_name]["type"] == "history":
            fake_data = [[location, time, points], [location, time, points], [location, time, points]]
        else:
            raise RuntimeError("Incompatible request {} of type {}".format(service_name, [service_name]["type"]))
        test_cache.store_weather_records(service_name, fake_data)

    for service_name in test_api_services:
        if test_api_services[service_name]["type"] == "current":
            data = test_cache.get_current_data(service_name, location)
            assert len(data) == 4
        elif test_api_services[service_name]["type"] == "forecast":
            data = test_cache.get_forecast_data(service_name, location)
            assert len(data) == 3
            assert len(data[0]) == 5
        elif test_api_services[service_name]["type"] == "history":
            fake_end = datetime.datetime.utcnow()
            fake_start = fake_end - datetime.timedelta(days=7)
            data = test_cache.get_historical_data(service_name, location, fake_start)
            assert len(data) == 3
            assert len(data[0]) == 4


class BasicWeatherAgent(BaseWeatherAgent):
    """An implementation of the BaseWeatherAgent to test basic method functionality.
    Each RPC method will be tested by implementing them in a fashion that tests the expected behaviors, minus querying
    a particular api (essentially testing the cache functionality)."""
    def __init__(self, **kwargs):
        super(BasicWeatherAgent, self).__init__(**kwargs)
        for service_name in self._api_services:
            self.set_update_interval(service_name, datetime.timedelta(seconds=1))
        self.conn = self._cache._sqlite_conn
        self.cursor = self.conn.cursor()

    def query_current_weather(self, location):
        current_time = datetime.datetime.utcnow()
        record = ["fake_location", current_time, "{'points': {'fake_data': 'fake'}}"]
        return record

    def query_hourly_forecast(self, location):
        records = []
        current_time = datetime.datetime.utcnow()
        for x in range(0, 10):
            record = ["fake_location", current_time, current_time + datetime.timedelta(hours=(x+1)),
                      "{'points': {'fake_data': 'fake'}}"]
            records.append(record)
        return records

    def query_hourly_historical(self, location, date):
        records = []
        location_name = self.get_location_string(location)
        for x in range(0, 3):
            current_time = datetime.datetime.combine(date, datetime.time())
            record = [location_name, current_time + datetime.timedelta(hours=(x+1)), {'points': {'fake_data': 'fake'}}]
            records.append(record)
        return records

    def get_location_string(self, location):
        if "location" in location:
            return location["location"]
        else:
            raise ValueError("bad location")

    def validate_location(self, accepted_formats, location):
        return True

@pytest.mark.weather2
def test_success_current(volttron_instance):
    """
    Tests some basic functionality of get success, including fetching from database, and querying for data
    :param volttron_instance:
    """
    v1 = volttron_instance
    assert v1.is_running()
    weather_agent = BasicWeatherAgent(service_name="test",
                                      api_key=None,
                                      max_size_gb=None,
                                      polling_locations=[],
                                      poll_interval=None
                                      )
    gevent.spawn(weather_agent.core.run).join(0)
    agent = v1.build_agent()

    for service in weather_agent._api_services:
        delete_query = "DELETE FROM {};".format(service)
        _log.debug(delete_query)
        weather_agent.cursor.execute(delete_query)

    # should call query_current_weather, then get from cache, then query again

    fake_locations = [{"location": "fake_location"}, {"location": "fake_location"}, {"location": "fake_location2"}]
    data = weather_agent.get_current_weather(fake_locations)
    assert len(data) == 3
    for record in data:
        assert len(record) == 3

@pytest.mark.weather2
def test_success_hourly_forecast(volttron_instance):
    """
    Tests some basic functionality of get success, including fetching from database, and querying for data
    :param volttron_instance:
    """
    v1 = volttron_instance
    assert v1.is_running()
    weather_agent = BasicWeatherAgent(service_name="test",
                                      api_key=None,
                                      max_size_gb=None,
                                      polling_locations=[],
                                      poll_interval=None
                                      )
    gevent.spawn(weather_agent.core.run).join(0)
    agent = v1.build_agent()

    for service in weather_agent._api_services:
        delete_query = "DELETE FROM {};".format(service)
        _log.debug(delete_query)
        weather_agent.cursor.execute(delete_query)

    # should call query_current_weather, then get from cache, then query again

    fake_locations = [{"location": "fake_location"}, {"location": "fake_location"}, {"location": "fake_location2"}]
    data = weather_agent.get_hourly_forecast(fake_locations)
    assert len(data) == 30
    for record in data:
        assert len(record) == 4

@pytest.mark.weather2
@pytest.mark.skip
def test_success_hourly_historical(volttron_instance):
    """
    Tests some basic functionality of get success, including fetching from database, and querying for data
    :param volttron_instance:
    """
    v1 = volttron_instance
    assert v1.is_running()
    weather_agent = BasicWeatherAgent(service_name="test",
                                      api_key=None,
                                      max_size_gb=None,
                                      polling_locations=[],
                                      poll_interval=None
                                      )
    gevent.spawn(weather_agent.core.run).join(0)
    agent = v1.build_agent()

    for service in weather_agent._api_services:
        delete_query = "DELETE FROM {};".format(service)
        _log.debug(delete_query)
        weather_agent.cursor.execute(delete_query)

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1)

    fake_locations = [{"location": "fake_location"}, {"location": "fake_location"}, {"location": "fake_location2"}]
    data = weather_agent.get_hourly_historical(fake_locations, start_date, end_date)
    assert(len(data) == 18)
    for record in data:
        assert len(record) == 3