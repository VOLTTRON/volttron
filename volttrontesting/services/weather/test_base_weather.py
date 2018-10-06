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
_log = logging.getLogger(__name__)

identity = 'platform.weather'


test_api_services = {"test_current": {"type": "current"},
                     "test_forecast": {"type": "forecast"},
                     "test_history": {"type": "history"}}

fake_location = "fake_location"
fake_time = datetime.datetime.utcnow()
fake_points = {"fake_data", "fake_data"}

# TODO validate
@pytest.fixture(scope="module")
def test_cache():
    cache = WeatherCache(service_name="test", api_services=test_api_services, max_size_gb=0.00002)
    return cache

# Test table creation

@pytest.mark.weather2
def test_create_tables(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    assert os.path.isfile("test.sqlite")

    test_cache.create_tables()

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

    test_cache.create_tables()

    for table in test_api_services:
        info_query = "PRAGMA table_info({});".format(table)
        table_info = cursor.execute(info_query).fetchall()
        _log.debug(info_query)
        table_columns = []
        for row in table_info:
            table_columns.append(row[1])
        if test_api_services[table]["type"] == "forecast":
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME", "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns

def test_store_current_success(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    service_name = "test_current"
    fake_data = [fake_location, fake_time, fake_points]

    delete_query = "DELETE FROM {};".format(service_name)
    _log.debug(delete_query)
    cursor.execute(delete_query)
    connection.commit()

    test_cache.store_weather_records(service_name, fake_data)

    count_query = "SELECT COUNT(*) FROM {};".format(service_name)
    _log.debug(count_query)

    assert cursor.execute(count_query).fetchone()[0] == 1

def test_store_forecast_success(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    service_name = "test_forecast"
    fake_data = [[fake_location, fake_time, fake_time, fake_points],
                 [fake_location, fake_time, fake_time, fake_points],
                 [fake_location, fake_time, fake_time, fake_points]
                 ]

    delete_query = "DELETE FROM {};".format(service_name)
    _log.debug(delete_query)
    cursor.execute(delete_query)
    connection.commit()

    test_cache.store_weather_records(service_name, fake_data)

    count_query = "SELECT COUNT(*) FROM {};".format(service_name)
    _log.debug(count_query)

    assert cursor.execute(count_query).fetchone()[0] == 3

def test_store_history_success(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    service_name = "test_history"
    fake_data = [[fake_location, fake_time, fake_points],
                 [fake_location, fake_time, fake_points],
                 [fake_location, fake_time, fake_points]
                 ]

    delete_query = "DELETE FROM {};".format(service_name)
    _log.debug(delete_query)
    cursor.execute(delete_query)
    connection.commit()

    test_cache.store_weather_records(service_name, fake_data)

    count_query = "SELECT COUNT(*) FROM {};".format(service_name)
    _log.debug(count_query)

    assert cursor.execute(count_query).fetchone()[0] == 3

@pytest.mark.weather2
@pytest.mark.parametrize('service_name', 'records', 'exception', [
    (None, ["fake_location", datetime.datetime.now(), {"fake_data", "fake_data"}], ValueError),
    ("test_current", [None, datetime.datetime.now(), {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_current", ["fake_location", None, {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_current", ["fake_location", datetime.datetime.now(), None], sqlite3.Error),
    ("test_current", [], sqlite3.Error),
])
def test_store_current_fail(test_cache, service_name, records, exception):
    with pytest.raises(exception):
        test_cache.store_weather_records(service_name, records)

@pytest.mark.weather2
@pytest.mark.parametrize('service_name', 'records', 'exception', [
    (None, ["fake_location", datetime.datetime.now(), datetime.datetime.now(), {"fake_data", "fake_data"}], ValueError),
    ("test_forecast", [None, datetime.datetime.now(), datetime.datetime.now(), {"fake_data", "fake_data"}],
     sqlite3.Error),
    ("test_forecast", ["fake_location", None, datetime.datetime.now(), {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_forecast", ["fake_location", datetime.datetime.now(), {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_forecast", ["fake_location", datetime.datetime.now(), None], sqlite3.Error),
    ("test_forecast", [], sqlite3.Error),
])
def test_store_forecast_fail(test_cache, service_name, records, exception):
    with pytest.raises(exception):
        test_cache.store_weather_records(service_name, records)

@pytest.mark.weather2
@pytest.mark.parametrize('service_name', 'records', 'exception', [
    (None, ["fake_location", datetime.datetime.now(), {"fake_data", "fake_data"}], ValueError),
    ("test_history", [None, datetime.datetime.now(), {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_history", ["fake_location", None, {"fake_data", "fake_data"}], sqlite3.Error),
    ("test_history", ["fake_location", datetime.datetime.now(), None], sqlite3.Error),
    ("test_history", [], sqlite3.Error),
])
def test_store_history_fail(test_cache, service_name, records, exception):
    with pytest.raises(exception):
        test_cache.store_weather_records(service_name, records)

# test getters

@pytest.mark.weather2
def test_get_current_success(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    service_name = "test_current"
    delete_query = "DELETE FROM {};".format(service_name)
    _log.debug(delete_query)
    cursor.execute(delete_query)
    connection.commit()

    fake_data = [fake_location, fake_time, fake_points]
    test_cache.store_weather_records(service_name, fake_data)

    data = test_cache.get_current_data(service_name, fake_location)
    assert len(data) == 4
    # TODO make instanceof asserts

# TODO parametrize
# @pytest.mark.weather2
# @pytest.mark.parametrize('service_name', 'location', 'exception', [])
# def test_get_current_fail(test_cache, service_name, location, exception):
#     with pytest.raises(exception):
#             test_cache.get_current_data(service_name, location)

@pytest.mark.weather2
def test_get_forecast_success(test_cache):
    connection = test_cache._sqlite_conn
    cursor = connection.cursor()

    service_name = "test_forecast"
    delete_query = "DELETE FROM {};".format(service_name)
    _log.debug(delete_query)
    cursor.execute(delete_query)
    connection.commit()

    fake_data = [[fake_location, fake_time, fake_time, fake_points],
                 [fake_location, fake_time, fake_time, fake_points],
                 [fake_location, fake_time, fake_time, fake_points]
                 ]
    test_cache.store_weather_records(service_name, fake_data)
    data = test_cache.get_forecast_data(service_name, fake_location)
    assert len(data) == 3
    assert len(data[0]) == 5
    # TODO make instanceof asserts

# TODO parametrize
# @pytest.mark.weather2
# @pytest.mark.parametrize('service_name', 'location', 'exception', [])
# def test_get_forecast_fail(test_cache, service_name, location, exception):
#     with pytest.raises(exception):
#             test_cache.get_forecast_data(service_name, location)

# TODO
# @pytest.mark.weather2
# def test_get_history_success(test_cache):
#     connection = test_cache._sqlite_conn
#     cursor = connection.cursor()
#
#     service_name = "test_history"
#     delete_query = "DELETE FROM {};".format(service_name)
#     _log.debug(delete_query)
#     cursor.execute(delete_query)
#     connection.commit()
#
#     location = "fake_location"
#     time = datetime.datetime.utcnow()
#     fake_data = [[fake_location, time, fake_points],
#                  [location, time, fake_points],
#                  [location, time, fake_points]
#                  ]
#     test_cache.store_weather_records(service_name, fake_data)
#
#     fake_end = datetime.datetime.utcnow()
#     fake_start = fake_end - datetime.timedelta(days=7)
#     data = test_cache.get_historical_data(service_name, location, fake_start)
#     assert len(data) == 3
#     assert len(data[0]) == 4
#     # TODO make instanceof asserts
#
# TODO
# TODO parametrize
# @pytest.mark.weather2
# @pytest.mark.parametrize()
# def test_get_history_fail(test_cache, service_name, location, start_time, exception):
#     with pytest.raises(exception):
#         test_cache.get_historical_data(service_name, location, start_time)

# TODO
# def test_manage_size(test_cache):


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
        record = ["fake_location",
                  current_time,
                  {'points': fake_points}
                  ]
        return record

    def query_hourly_forecast(self, location):
        records = []
        current_time = datetime.datetime.utcnow()
        for x in range(0, 10):
            record = ["fake_location",
                      current_time,
                      current_time + datetime.timedelta(hours=(x+1)),
                      {'points': fake_points}
                      ]
            records.append(record)
        return records

    # TODO
    def query_hourly_historical(self, location, date):
        records = []
        location_name = self.get_location_string(location)
        for x in range(0, 3):
            current_time = datetime.datetime.combine(date, datetime.time())
            record = [location_name,
                      current_time + datetime.timedelta(hours=(x+1)),
                      {'points': fake_points}
                      ]
            records.append(record)
        return records

    def get_location_string(self, location):
        if "location" in location:
            return location["location"]
        else:
            raise ValueError("bad location")

    # TODO
    def validate_location(self, location):
        return True

# TODO validate
@pytest.fixture(scope="module")
def weather(request, volttron_instance):
    print("** Setting up weather agent module **")

    agent_uuid = volttron_instance.build_agent(
        identity=identity,
        service_name="BasicWeather"
    )

    volttron_instance.start_agent(agent_uuid)

    def stop_agent():
        print("stopping weather service")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)

    request.addfinalizer(stop_agent)
    return request.param

# TODO ALL

# @pytest.mark.weather2
# def test_register_service_success():
#     """"""
#
# @pytest.mark.weather2
# def test_register_service_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_remove_service():
#     """"""
#
# @pytest.mark.weather2
# def test_set_update_interval_success():
#     """"""
#
# @pytest.mark.weather2
# def test_set_update_interval_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_update_default_config_success():
#     """"""
#
# @pytest.mark.weather2
# def test_update_default_config_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_parse_weather_mapping_success():
#     """"""
#
# @pytest.mark.weather2
# def test_parse_weather_mapping_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_configure_success():
#     """"""
#
# @pytest.mark.weather2
# def test_configure_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_get_api_features():
#     """"""

# TODO
@pytest.mark.weather2
def test_get_current_success(volttron_instance):
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

# TODO
# @pytest.mark.weather2
# def test_get_current_fail():
#     """"""

# TODO
# TODO use hours
@pytest.mark.weather2
def test_get_hourly_forecast_success(volttron_instance):
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
# TODO
# @pytest.mark.weather2
# def test_get_hourly_forecast_fail():
#     """"""

# TODO
# @pytest.mark.weather2
# def test_get_hourly_historical_success(volttron_instance):
    # v1 = volttron_instance
    # assert v1.is_running()
    # weather_agent = BasicWeatherAgent(service_name="test",
    #                                   api_key=None,
    #                                   max_size_gb=None,
    #                                   polling_locations=[],
    #                                   poll_interval=None
    #                                   )
    # gevent.spawn(weather_agent.core.run).join(0)
    # agent = v1.build_agent()
    #
    # for service in weather_agent._api_services:
    #     delete_query = "DELETE FROM {};".format(service)
    #     _log.debug(delete_query)
    #     weather_agent.cursor.execute(delete_query)
    #
    # end_date = datetime.date.today()
    # start_date = end_date - datetime.timedelta(days=1)
    #
    # fake_locations = [{"location": "fake_location"}, {"location": "fake_location"}, {"location": "fake_location2"}]
    # data = weather_agent.get_hourly_historical(fake_locations, start_date, end_date)
    # assert(len(data) == 18)
    # for record in data:
    #     assert len(record) == 3

# TODO ALL

# @pytest.mark.weather2
# def test_get_hourly_historical_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_poll_for_locations():
#     """"""
#
# @pytest.mark.weather2
# def test_publish_response_success():
#     """"""
#
# @pytest.mark.weather2
# def test_publish_response_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_manage_unit_conversion_success():
#     """"""
#
# @pytest.mark.weather2
# def test_manage_unit_conversion_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_get_cached_current_success():
#     """"""
#
# @pytest.mark.weather2
# def test_get_cached_current_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_get_cached_forecast_success():
#     """"""
#
# @pytest.mark.weather2
# def test_get_cached_forecast_fail():
#     """"""
#
#
# # TODO get_cached_historical_tests
#
# @pytest.mark.weather2
# def test_store_weather_records_success():
#     """"""
#
# @pytest.mark.weather2
# def test_store_weather_records_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_get_status_from_context_success():
#     """"""
#
# @pytest.mark.weather2
# def test_get_status_from_context_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_update_status_callback_success():
#     """"""
#
# @pytest.mark.weather2
# def test_update_status_callback_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_update_status_success():
#     """"""
#
# @pytest.mark.weather2
# def test_update_status_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_send_alert_callback_sucess():
#     """"""
#
# @pytest.mark.weather2
# def test_send_alert_callback_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_update_and_get_context_status_success():
#     """"""
#
# @pytest.mark.weather2
# def test_update_and_get_context_status_fail():
#     """"""
#
# @pytest.mark.weather2
# def test_send_alert_success():
#     """"""
#
# @pytest.mark.weather2
# def test_send_alert_fail():
#     """"""
