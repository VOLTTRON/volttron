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
import ujson
import copy
import pint
import pytest
import gevent
import logging
import sqlite3
import datetime
from volttron.utils.docs import doc_inherit
from volttron.platform.agent import utils
from volttron.platform.messaging.health import *
from volttron.platform.agent.base_weather import BaseWeatherAgent, WeatherCache

utils.setup_logging()
_log = logging.getLogger(__name__)

identity = 'platform.weather'

FAKE_LOCATION = {"location": "fake_location"}
FAKE_POINTS = {"fake": "fake_data"}

@pytest.fixture(scope="module")
def client_agent(request, volttron_instance):
    agent = volttron_instance.build_agent()
    yield agent
    agent.core.stop()

class BasicWeatherAgent(BaseWeatherAgent):
    """An implementation of the BaseWeatherAgent to test basic method functionality.
    Each RPC method will be tested by implementing them in a fashion that tests the expected behaviors, minus querying
    a particular api (essentially testing the cache functionality)."""
    def __init__(self, **kwargs):
        super(BasicWeatherAgent, self).__init__(**kwargs)

    def query_current_weather(self, location):
        current_time = datetime.datetime.utcnow()
        record = [
                  current_time,
                  {'points': FAKE_POINTS}
                 ]
        return record

    def query_hourly_forecast(self, location):
        records = []
        current_time = datetime.datetime.utcnow()
        for x in range(0, 3):
            record = [current_time + datetime.timedelta(hours=(x+1)),
                      {'points': FAKE_POINTS}
                     ]
            records.append(record)
        return current_time, records

    def query_hourly_historical(self, location, start_date, end_date):
        records = []
        for x in range(0, 3):
            current_time = datetime.datetime.combine(start_date, datetime.time())
            record = [location,
                      current_time + datetime.timedelta(hours=(x+1)),
                      {'points': FAKE_LOCATION}
                      ]
            records.append(record)
        return records

    def get_update_interval(self, service_name):
        if service_name == "get_current_weather":
            return datetime.timedelta(hours=1)
        elif service_name == "get_hourly_forecast":
            return datetime.timedelta(hours=1)

    def get_api_description(self, service_name):
        if service_name == "get_current_weather":
            return "returns fake current data"
        elif service_name == "get_hourly_forecast":
            return "returns fake hourly forecast data"
        elif service_name == "get_hourly_historical":
            return "returns fake hourly historical data"

    def validate_location(self, service_name, location):
        if service_name == "get_current_weather":
            return location.get("location")
        elif service_name == "get_hourly_forecast":
            if isinstance(location, dict) and "location" in location:
                return True
        else:
            return location.get("location") == "fake_location"

@pytest.fixture(scope="module")
def weather(request, volttron_instance):
    print("** Setting up weather agent module **")

    agent = volttron_instance.build_agent(
        agent_class=BasicWeatherAgent,
        identity=identity,
        service_name="BasicWeather"
    )

    yield agent
    agent.core.stop()

@pytest.mark.weather2
def test_create_tables(weather):
    connection = weather._cache._sqlite_conn
    cursor = connection.cursor()

    assert os.path.isfile("BasicWeather.sqlite")

    weather._cache.create_tables()

    for service_name in weather._api_services:
        query = "DROP TABLE IF EXISTS {};".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    for service_name in weather._api_services:
        query = "CREATE TABLE {} (TEST1 TEXT, TEST2 TEXT);".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    weather._cache.create_tables()

    for table in weather._api_services:
        info_query = "PRAGMA table_info({});".format(table)
        table_info = cursor.execute(info_query).fetchall()
        _log.debug(info_query)
        table_columns = []
        for row in table_info:
            table_columns.append(row[1])
        if weather._api_services[table]["type"] == "forecast":
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME", "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns

@pytest.mark.weather2
@pytest.mark.parametrize(
    "service_name, interval, service_type",
    [
        ("test_register_current", datetime.timedelta(hours=1), "current"),
        ("test_register_forecast", datetime.timedelta(hours=1), "forecast"),
        ("test_register_history", None, "history")
    ]
)
def test_register_service_success(weather, service_name, interval, service_type):
    weather.register_service(service_name, interval, service_type)
    assert weather._api_services.get(service_name)
    if service_type == "history":
        assert weather._api_services.get(service_name)["update_interval"] is None
    else:
        assert isinstance(weather._api_services.get(service_name)["update_interval"], datetime.timedelta)
    assert weather._api_services.get(service_name)["type"] == service_type
    assert weather._api_services.get(service_name)["description"] == None

@pytest.mark.weather2
@pytest.mark.parametrize("service_name, interval, service_type, description", [
    ("test_register_current", None, "current", None),
    ("test_register_current", datetime.timedelta(hours=1), "bad_service_type", None),
    ("test_register_history", datetime.timedelta(hours=1), "history", None),
    ("test_register_history", datetime.timedelta(hours=1), "history", 1)
])
def test_register_service_fail(weather, service_name, interval, service_type, description):
    passed = False
    try:
        weather.register_service(service_name, interval, service_type, description)
        passed = True
    except ValueError as error:
        if interval is None and service_type is not "history":
            assert str(error) == "Interval must be a valid datetime timedelta object."
        elif service_type == "bad_service_type":
            assert str(error) == "Invalid service type. It should be history, current, " \
                            "or forecast"
        elif service_type == "history" and interval is not None:
            assert str(error) == "History object does not utilize an interval."
        elif description:
            assert str(error) == "description is expected as a string describing the " \
                            "service function's usage."
    assert not passed

@pytest.mark.weather2
def test_remove_service_success(weather):
    initial_length = len(weather._api_services)
    weather.register_service("test", datetime.timedelta(hours=1), "current", None)
    weather.remove_service("test")
    assert len(weather._api_services) == initial_length
    weather.remove_service("get_current_weather")
    assert len(weather._api_services) == initial_length-1

@pytest.mark.weather2
@pytest.mark.parametrize("service_name", ["fake_service", False])
def test_remove_service_fail(weather, service_name):
    passed = False
    try:
        weather.remove_service(service_name)
        passed = True
    except ValueError as error:
        assert str(error).startswith("service ") and str(error).endswith(" does not exist")
    assert not passed

@pytest.mark.weather2
def test_set_api_description_success(weather):
    weather.set_api_description("get_current_weather", "kittens")
    assert weather._api_services["get_current_weather"]["description"] is "kittens"
    weather.set_api_description("get_current_weather", weather.get_api_description("get_current_weather"))
    assert weather._api_services["get_current_weather"]["description"] is "returns fake current data"

@pytest.mark.weather2
@pytest.mark.parametrize("service_name, description", [("fake_service", "fake"), ("get_current_weather", None)])
def test_set_api_description_fail(weather, service_name, description):
    passed = False
    try:
        weather.set_api_description(service_name, description)
        passed = True
    except ValueError as error:
        if service_name not in weather._api_services:
            assert str(error).endswith(" not found in api features.")
        if not isinstance(description, str):
            assert str(error) == "description expected as string"
    assert not passed

@pytest.mark.weather2
def test_set_update_interval_success(weather):
    weather.set_update_interval("get_current_weather", datetime.timedelta(days=1))
    assert weather._api_services["get_current_weather"]["update_interval"].total_seconds() == \
           datetime.timedelta(days=1).total_seconds()

@pytest.mark.weather2
@pytest.mark.parametrize("service_name, interval", [
    ("get_hourly_historical", datetime.timedelta(hours=1)),
    ("fake_service", datetime.timedelta(hours=1)),
    ("get_current_weather", None)
])
def test_set_update_interval_fail(weather, service_name, interval):
    passed = False
    try:
        weather.set_update_interval(service_name, interval)
        passed = True
    except ValueError as error:
        if service_name not in weather._api_services:
            assert str(error).endswith(" not found in api features.")
        elif weather._api_services[service_name]["type"] == "history":
            assert str(error) == "historical data does not utilize an update interval."
        if not isinstance(interval, datetime.timedelta):
            assert str(error) == "interval must be a valid datetime timedelta object."
    assert not passed

@pytest.mark.weather2
@pytest.mark.parametrize("from_units, start, to_units, end", [
    ("inch", 1, "cm", 2.54),
    ("fahrenheit", 32, "celsius", 0),
    ("celsius", 100, "fahrenheit", 212),
    ("pint", 1, "milliliter", 473.176)
])
def test_manage_unit_conversion_success(weather, from_units, start, to_units, end):
    output = weather.manage_unit_conversion(from_units, start, to_units)
    assert str(output).startswith(str(end))

@pytest.mark.weather2
@pytest.mark.parametrize("from_units, start, to_units", [
    ("inch", 1, "celsius"),
    ("kittens", 1, "millimeter"),
    ("pint", 1, "puppies")
])
def test_manage_unit_conversion_fail(weather, from_units, start, to_units):
    try:
        weather.manage_unit_conversion(from_units, start, to_units)
    except pint.DimensionalityError as error:
        assert str(error).startswith("Cannot convert from ")
    except pint.UndefinedUnitError as error:
        assert str(error).endswith(" is not defined in the unit registry")

@pytest.mark.dev
@pytest.mark.parametrize("fake_locations", [
    [{"location": "fake_location"}]
])
def test_get_current_valid_locations(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()
    weather.set_update_interval("get_current_weather",
                                datetime.timedelta(days=1))
    query = "DELETE FROM 'get_current_weather';"
    cursor.execute(query)
    conn.commit()

    # results1 should look like:
    # [{location, "weather_results": []}]

    # initial run. cache is empty should return from BasicWeatherAgent's
    # query_current
    results1 = weather.get_current_weather(fake_locations)
    assert len(results1) == 1
    assert results1[0]["observation_time"]
    assert results1[0]["weather_results"]["points"]["fake"] == "fake_data"
    assert results1[0]["location"] == "fake_location"

    # Check data got cached
    query = "SELECT * FROM 'get_current_weather';"
    cache_results = cursor.execute(query).fetchall()
    print cache_results
    assert len(cache_results) == 1
    assert ujson.loads(cache_results[0][1]) == fake_locations[0]
    assert cache_results[0][2] == results1[0]["observation_time"]
    # assert results1 and cached data are same
    assert ujson.loads(cache_results[0][3]) == results1[0]["weather_results"]

    #update cache before querying again
    cursor.execute("UPDATE get_current_weather SET POINTS = ?",
                   (ujson.dumps({"points": {"fake": "updated cache"}}),))
    conn.commit()

    # second query - results should be from cache
    results2 = weather.get_current_weather(fake_locations)
    assert len(results2) == 1
    assert results2[0]["observation_time"] == results1[0]["observation_time"]
    assert results2[0]["weather_results"]["points"]["fake"] == "updated cache"
    assert results2[0]["location"] == results1[0]["location"]

    # third query  - set update interval so that cache would be marked old
    weather.set_update_interval("get_current_weather",
                                datetime.timedelta(seconds=1))
    gevent.sleep(1)
    results3 = weather.get_current_weather(fake_locations)
    assert len(results3) == 1
    assert results3[0]["observation_time"]
    assert results3[0]["observation_time"] != results1[0]["observation_time"]
    assert results3[0]["weather_results"]["points"]["fake"] == "fake_data"
    assert results3[0]["location"] == "fake_location"

    # check data got cached again
    query = "SELECT * FROM get_current_weather ORDER BY ID;"
    cache_results = cursor.execute(query).fetchall()
    print cache_results
    assert len(cache_results) == 2
    assert ujson.loads(cache_results[1][1]) == fake_locations[0]
    assert cache_results[1][2] == results3[0]["observation_time"]
    # assert results1 and cached data are same
    assert ujson.loads(cache_results[1][3]) == results3[0]["weather_results"]

    cursor.close()

@pytest.mark.dev
@pytest.mark.parametrize("fake_locations", [
    [{"location": "bad_string"}, {"fail": "fail"},
     "bad_format"]
])
def test_get_current_fail(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()

    query = "DELETE FROM 'get_current_weather';"
    cursor.execute(query)
    conn.commit()

    # results should look like:
    # [{location, "location_error": []}]

    fake_results = weather.get_current_weather(fake_locations)
    assert len(fake_results) == 3
    for record_set in fake_results:
        assert record_set.get("location_error")
    size_query = "SELECT COUNT(*) FROM 'get_current_weather';"
    size = cursor.execute(size_query).fetchone()[0]
    assert size == 0

@pytest.mark.dev
@pytest.mark.parametrize("fake_locations", [
    [{"location": "fake_location1"}]
])
def test_get_forecast_valid_locations(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()
    weather.set_update_interval("get_hourly_forecast",
                                datetime.timedelta(days=1))
    query = "DELETE FROM 'get_hourly_forecast';"
    cursor.execute(query)
    conn.commit()

    # 1. initial run. cache is empty should return from BasicWeatherAgent's
    # query_current
    result1 = weather.get_hourly_forecast(fake_locations)
    print result1
    validate_basic_weather_forecast(fake_locations, result1)

    # Check data got cached
    query = "SELECT * FROM 'get_hourly_forecast';"
    cache_result = cursor.execute(query).fetchall()
    print cache_result

    # assert result1 and cached data are same
    validate_cache_result_forecast(fake_locations, result1, cache_result)

    # update cache before querying again.
    cursor.execute("UPDATE get_hourly_forecast SET POINTS = ?",
                   (ujson.dumps({"points": {"fake": "updated cache"}}),))
    conn.commit()

    # 2. second query - results should still be got from api since not enough
    # rows are in cache
    result2 = weather.get_hourly_forecast(fake_locations)
    print result2
    validate_basic_weather_forecast(fake_locations, result2)

    # assert result2 and cached data are same
    query = "SELECT * FROM 'get_hourly_forecast' ORDER BY GENERATION_TIME DESC;"
    cache_result = cursor.execute(query).fetchall()
    print cache_result
    validate_cache_result_forecast(fake_locations, result2, cache_result)

    # 3. third query - results should be from cache. update cache so we know
    # we are getting from cache
    cursor.execute("UPDATE get_hourly_forecast SET POINTS = ? WHERE "
                   "GENERATION_TIME= ?",
                   (ujson.dumps({"points": {"fake": "updated cache"}}),
                    result2[0]["generation_time"]))
    conn.commit()
    # set hours to 2 so cached data is sufficient
    result3 = weather.get_hourly_forecast(fake_locations, hours=2)
    print result3
    validate_basic_weather_forecast(fake_locations, result3, warn=False,
                                    point_data={"fake": "updated cache"},
                                    hours=2)

    # 4. fourth query  - set update interval so that cache would be marked old
    # and
    # set hours to 2 so cache has enough number of records but is out of date

    weather.set_update_interval("get_hourly_forecast",
                                datetime.timedelta(seconds=1))
    gevent.sleep(1)
    result4 = weather.get_hourly_forecast(fake_locations, hours=2)
    validate_basic_weather_forecast(fake_locations, result4, warn=False,
                                    hours=2)
    # check data got cached again
    query = "SELECT * FROM 'get_hourly_forecast' ORDER BY GENERATION_TIME DESC;"
    cache_result = cursor.execute(query).fetchall()
    print cache_result
    validate_cache_result_forecast(fake_locations, result4, cache_result,
                                   hours=2)


def validate_cache_result_forecast(locations, api_result, cache_result,
                                   hours=3):
    j = 0
    for location in locations:
        assert len(cache_result) >= len(api_result[j]["weather_results"])
        assert ujson.loads(cache_result[j][1]) == location
        assert cache_result[j][2] == api_result[j]["generation_time"]
        i = 0
        while i < hours:
            cr = cache_result[i]
            assert ujson.loads(cr[1]) == locations[0]
            assert cr[2] == api_result[j]["generation_time"]
            api_weather_result = api_result[j]["weather_results"]
            assert cr[3] == api_weather_result[i][0]
            i = i + 1
        j = j + 1


def validate_basic_weather_forecast(locations, result, warn=True,
                                    point_data=FAKE_POINTS, hours=3):
    assert len(result) == len(locations)
    i= 0
    for location in locations:
        assert result[i]["generation_time"]
        if warn:
            assert result[i]["weather_warn"] == \
                   "Weather provider returned less than requested amount " \
                   "of data"
        else:
            assert result[i].get("weather_warn") is None

        assert result[i]["location"] == location["location"]
        weather_result2 = result[i]["weather_results"]
        assert len(weather_result2) == hours
        assert len(weather_result2[0]) == 2
        for wr in weather_result2:
            assert isinstance(wr[0], datetime.datetime)
            assert isinstance(wr[1], dict)
            assert wr[1]["points"] == point_data


@pytest.mark.dev
@pytest.mark.parametrize("fake_locations", [
    [{"location": "bad_string"}, {"fail": "fail"}, "bad_format"],
    [{"location": "fake_location"}, "fail"]
])
def test_get_forecast_fail(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()

    query = "DELETE FROM 'get_hourly_forecast';"
    cursor.execute(query)
    conn.commit()

    # results should look like:
    # [{location, "location_error": []}]

    fake_results = weather.get_hourly_forecast(fake_locations)
    assert len(fake_results) == 3
    for record_set in fake_results:
        if "location" in record_set:
            assert record_set.get("weather_results")
        else:
            assert record_set.get("location_error")
    size_query = "SELECT COUNT(*) FROM 'get_hourly_forecast';"
    size = cursor.execute(size_query).fetchone()[0]
    assert size == 0

@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations, start_date, end_date", [])
def test_hourly_historical_success(weather, fake_locations, start_date, end_date):
    pass

@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations, start_date, end_date", [])
def test_hourly_historical_fail(weather, fake_locations, start_date, end_date):
    pass

# TODO
@pytest.mark.weather2
def test_polling_locations(volttron_instance, weather, query_agent):
    new_config = copy.copy(weather)
    source = new_config.pop("weather_service")
    new_config["polling_locations"] = [{"station": "KLAX"}, {"station": "KABQ"}]
    new_config["poll_interval"] = 5
    agent_uuid = None
    try:
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=source,
            start=False,
            config_file=new_config)
        volttron_instance.start_agent(agent_uuid)
        gevent.sleep(5)
        assert query_agent.vip.rpc.call(identity, "health.get_status").get(timeout=10) == STATUS_GOOD
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.weather2
def test_update_and_get_status(volttron_instance, weather, query_agent):
    assert query_agent.vip.rpc.call(identity, "health.get_status").get(timeout=10) == STATUS_GOOD
    weather._update_status({"publishing": False})
    assert query_agent.vip.rpc.call(identity, "health.get_status").get(timeout=10) == STATUS_BAD
    weather.polling_locations = []
    weather.poll_for_locations()
    assert query_agent.vip.rpc.call(identity, "health.get_status").get(timeout=10) == STATUS_GOOD