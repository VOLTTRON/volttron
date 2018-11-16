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

import datetime
import os
import ujson

import gevent
import pytest
from mock import MagicMock

from volttron.platform.agent import utils
from volttron.platform.agent.base_weather import BaseWeatherAgent
from volttron.platform.messaging.health import *

utils.setup_logging()
_log = logging.getLogger(__name__)

identity = 'platform.weather'

FAKE_LOCATION = {"location": "fake_location"}
FAKE_POINTS = {"fake1": 1,
               "fake2": 100,
               "fake3": 1}

EXPECTED_OUTPUT_VALUES = {"fake1": {"value": 2.54,
                                    "name": "FAKE1"},
                          "fake2": {"value": 212,
                                    "name": "FAKE2"},
                          "fake3": {"value": 473.176,
                                    "name": "FAKE3"}
                          }


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    agent = volttron_instance.build_agent()
    agent.poll_callback = MagicMock(name="poll_callback")
    # subscribe to weather poll results
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix="weather/poll/current",
        callback=agent.poll_callback).get()

    gevent.sleep(3)

    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


class BasicWeatherAgent(BaseWeatherAgent):
    """An implementation of the BaseWeatherAgent to test basic method
    functionality.
    Each RPC method will be tested by implementing them in a fashion that
    tests the expected behaviors, minus querying
    a particular api (essentially testing the cache functionality)."""

    def __init__(self, **kwargs):
        super(BasicWeatherAgent, self).__init__(**kwargs)

    # TODO create a file to use, a path, and stick the string here
    def get_point_name_defs_file(self):
        return "volttrontesting/services/weather/point_names_defs.csv"

    def query_current_weather(self, location):
        current_time = datetime.datetime.utcnow()
        record = [
            format_timestamp(current_time),
            {'points': FAKE_POINTS}
        ]
        return record

    def query_hourly_forecast(self, location):
        records = []
        current_time = datetime.datetime.utcnow()
        for x in range(0, 3):
            record = [format_timestamp(
                current_time + datetime.timedelta(hours=(x + 1))),
                      {'points': FAKE_POINTS}
                      ]
            records.append(record)
        return format_timestamp(current_time), records

    # TODO
    def query_hourly_historical(self, location, start_date, end_date):
        pass

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
        if service_name == "get_current_weather" or service_name == \
                "get_hourly_forecast":
            if isinstance(location, dict) and "location" in location \
                    and location["location"].startswith("fake_location"):
                return True
        else:
            return location.get("location") == "fake_location"


@pytest.fixture(scope="module")
def weather(volttron_instance):
    print("** Setting up weather agent module **")

    agent = volttron_instance.build_agent(
        agent_class=BasicWeatherAgent,
        identity=identity,
        service_name="BasicWeather"
    )
    gevent.sleep(2)

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
            for column in ["ID", "LOCATION", "GENERATION_TIME", "FORECAST_TIME",
                           "POINTS"]:
                assert column in table_columns
        else:
            for column in ["ID", "LOCATION", "OBSERVATION_TIME", "POINTS"]:
                assert column in table_columns


@pytest.mark.weather2
def test_manage_cache_size(volttron_instance):
    weather = volttron_instance.build_agent(
        agent_class=BasicWeatherAgent,
        identity="test_cache_basic_weather",
        service_name="BasicWeather",
        max_size_gb=0.00003
    )

    gevent.sleep(3)  # wait for agent to start and configure method to be called
    connection = weather._cache._sqlite_conn
    cursor = connection.cursor()

    assert os.path.isfile("BasicWeather.sqlite")

    weather._cache.create_tables()

    for service_name in weather._api_services:
        query = "DELETE FROM {};".format(service_name)
        cursor.execute(query)
        _log.debug(query)
        connection.commit()

    fake_locations = [{"location": "fake_location1"},
                      {"location": "fake_location2"},
                      {"location": "fake_location3"}
                      ]

    weather.get_hourly_forecast(fake_locations, hours=3)

    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_count")
    num_pages = cursor.fetchone()[0]
    total_size = page_size * num_pages
    assert total_size < 25000

    weather.get_hourly_forecast(fake_locations, hours=5)

    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    total_size = page_size * num_pages
    assert total_size < 25000

    weather.get_current_weather(fake_locations)

    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    total_size = page_size * num_pages
    assert total_size < 25000


@pytest.mark.weather2
@pytest.mark.parametrize("service_name, interval, service_type", [
    ("test_register_current", datetime.timedelta(hours=1), "current"),
    ("test_register_forecast", datetime.timedelta(hours=1), "forecast"),
    ("test_register_history", None, "history"),
])
def test_register_service_success(weather, service_name, interval,
                                  service_type):
    weather.register_service(service_name, interval, service_type)
    assert weather._api_services.get(service_name)
    if service_type == "history":
        assert weather._api_services.get(service_name)[
                   "update_interval"] is None
    else:
        assert isinstance(
            weather._api_services.get(service_name)["update_interval"],
            datetime.timedelta)
    assert weather._api_services.get(service_name)["type"] == service_type
    assert weather._api_services.get(service_name)["description"] is None


@pytest.mark.weather2
@pytest.mark.parametrize(
    "service_name, interval, service_type, description, failure_string", [
        ("test_register_current", None, "current", None,
         "Interval must be a valid datetime timedelta object."),
        ("test_register_current", datetime.timedelta(hours=1),
         "bad_service_type", None,
         "Invalid service type. It should be history, current, or forecast"),
        ("test_register_history", datetime.timedelta(hours=1), "history", None,
         "History object does not utilize an interval."),
        ("test_register", datetime.timedelta(hours=1), "current", 1,
         "description is expected as a string describing the service "
         "function's usage.")
    ])
def test_register_service_fail(weather, service_name, interval, service_type,
                               description, failure_string):
    passed = False
    try:
        weather.register_service(service_name, interval, service_type,
                                 description)
        passed = True
    except ValueError as error:
        error_string = str(error)
        assert failure_string == error_string
    assert not passed


@pytest.mark.weather2
def test_remove_service_success(weather):
    initial_length = len(weather._api_services)
    weather.register_service("test", datetime.timedelta(hours=1), "current",
                             None)
    weather.remove_service("test")
    assert len(weather._api_services) == initial_length
    weather.remove_service("get_current_weather")
    assert len(weather._api_services) == initial_length - 1
    weather.register_service("get_current_weather", datetime.timedelta(hours=1),
                             "current", None)


@pytest.mark.weather2
@pytest.mark.parametrize("service_name", ["fake_service", False])
def test_remove_service_fail(weather, service_name):
    passed = False
    try:
        weather.remove_service(service_name)
        passed = True
    except ValueError as error:
        assert str(error).startswith("service ") and str(error).endswith(
            " does not exist")
    assert not passed


@pytest.mark.weather2
def test_set_api_description_success(weather):
    default_description = weather.get_api_description("get_hourly_historical")
    weather.set_api_description("get_hourly_historical", "test_description")
    assert weather._api_services["get_hourly_historical"][
               "description"] is "test_description"
    weather.set_api_description("get_hourly_historical", default_description)
    assert weather._api_services["get_hourly_historical"][
               "description"] is default_description


@pytest.mark.weather2
@pytest.mark.parametrize("service_name, description", [
    ("fake_service", "fake"), ("get_hourly_historical", None)
])
def test_set_api_description_fail(weather, service_name, description):
    passed = False

    try:
        weather.set_api_description(service_name, description)
        passed = True
    except ValueError as error:
        if service_name not in weather._api_services:
            error_message = str(error)
            assert error_message.endswith(" not found in api features.")
        elif not isinstance(description, str):
            error_message = str(error)
            assert error_message == "description expected as string"

    assert not passed


@pytest.mark.weather2
def test_set_update_interval_success(weather):
    weather.set_update_interval("get_hourly_forecast",
                                datetime.timedelta(days=1))
    assert weather._api_services["get_hourly_forecast"][
               "update_interval"].total_seconds() == \
        datetime.timedelta(days=1).total_seconds()
    weather.set_update_interval("get_hourly_forecast",
                                datetime.timedelta(hours=1))


@pytest.mark.weather2
@pytest.mark.parametrize("service_name, interval", [
    ("get_hourly_historical", datetime.timedelta(hours=1)),
    ("fake_service", datetime.timedelta(hours=1)),
    ("get_hourly_forecast", None)
])
def test_set_update_interval_fail(weather, service_name, interval):
    passed = False
    try:
        weather.set_update_interval(service_name, interval)
        passed = True
    except ValueError as error:
        if service_name not in weather._api_services:
            error_message = str(error)
            assert error_message.endswith(" not found in api features.")
        elif not isinstance(interval, datetime.timedelta):
            assert str(
                error) == "interval must be a valid datetime timedelta object."
        elif weather._api_services[service_name]["type"] == "history":
            assert str(
                error) == "historical data does not utilize an update interval."
    assert not passed


@pytest.mark.weather2
@pytest.mark.parametrize("from_units, start, to_units, end", [
    ("inch", 1, "cm", 2.54),
    ("celsius", 100, "fahrenheit", 212),
    ("pint", 1, "milliliter", 473.176)
])
def test_manage_unit_conversion_success(weather, from_units, start, to_units,
                                        end):
    output = weather.manage_unit_conversion(from_units, start, to_units)
    assert str(output).startswith(str(end))


@pytest.mark.weather2
@pytest.mark.parametrize("from_units, start, to_units, error_string", [
    ("inch", 1, "celsius", "Cannot convert from "),
    ("kittens", 1, "millimeter", " is not defined in the unit registry"),
    ("pint", 1, "puppies", " is not defined in the unit registry"),
    (None, 1, "millimeter", "Cannot convert from 'dimensionless"),
    ("inch", None, "millimeter", "Invalid magnitude for Quantity: "),
    ("inch", 1, None, "NoneType' object has no attribute 'items'")
])
def test_manage_unit_conversion_fail(weather, from_units, start, to_units,
                                     error_string):
    try:
        weather.manage_unit_conversion(from_units, start, to_units)
    except Exception as error:
        actual_error = str(error)
        assert actual_error.startswith(error_string) or actual_error.endswith(
            error_string)


@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations", [
    [],
    [{"location": "fake_location"}],
    [{"location": "fake_location1"}, {"location": "fake_location2"}]
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
    assert len(results1) == len(fake_locations)
    if not len(results1):
        assert not len(fake_locations)
    else:
        assert results1[0]["observation_time"]
        test_points = results1[0]["weather_results"]["points"]
        assert test_points
        for initial_point in FAKE_POINTS:
            fake_point = EXPECTED_OUTPUT_VALUES[initial_point]
            test_value = test_points[fake_point["name"]]
            assert test_value
            if test_value:
                assert str(test_value).startswith(str(fake_point["value"]))
        assert results1[0]["location"].startswith("fake_location")

        # Check data got cached
        query = "SELECT * FROM 'get_current_weather';"
        cache_results = cursor.execute(query).fetchall()
        assert ujson.loads(cache_results[0][1]) == fake_locations[0]
        time_in_cache = False
        for x in range(0, len(cache_results)):
            for result in results1:
                if result["observation_time"] == format_timestamp(
                        cache_results[x][2]):
                    time_in_cache = True
            assert time_in_cache
        # assert results1 and cached data are same
        assert ujson.loads(cache_results[0][3]) == results1[0][
            "weather_results"]

        # update cache before querying again
        cursor.execute("UPDATE get_current_weather SET POINTS = ?",
                       (ujson.dumps({"points": {"fake": "updated cache"}}),))
        conn.commit()

        # second query - results should be from cache
        results2 = weather.get_current_weather(fake_locations)
        assert len(results2) == len(fake_locations)
        assert results2[0]["observation_time"] == results1[0][
            "observation_time"]
        assert results2[0]["weather_results"]["points"] == {
            'fake': 'updated cache'}
        assert results2[0]["location"] == results1[0]["location"]

        # third query  - set update interval so that cache would be marked old
        weather.set_update_interval("get_current_weather",
                                    datetime.timedelta(seconds=1))
        gevent.sleep(1)
        results3 = weather.get_current_weather(fake_locations)
        assert len(results3) == len(fake_locations)
        assert results3[0]["observation_time"] != results1[0][
            "observation_time"]
        for point in results3[0]["weather_results"]["points"]:
            valid_point = False
            for name, map_dict in EXPECTED_OUTPUT_VALUES.iteritems():
                if point == map_dict["name"]:
                    valid_point = True
            assert valid_point
        assert results3[0]["location"].startswith("fake_location")

        # check data got cached again
        query = "SELECT * FROM get_current_weather ORDER BY ID;"
        cache_results = cursor.execute(query).fetchall()
        print cache_results
        assert len(cache_results) == 2 * len(fake_locations)
        assert ujson.loads(cache_results[1][1]) in fake_locations
        for result in results3:
            time_in_cache = False
            for x in range(0, len(cache_results)):
                if result["observation_time"] == format_timestamp(
                        cache_results[x][2]):
                    # assert results1 and cached data are same
                    assert ujson.loads(cache_results[x][3]) == result[
                        "weather_results"]
                    time_in_cache = True
            assert time_in_cache

    cursor.close()


@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations", [
    [{"location": "bad_string"}],
    [{"fail": "fail"}],
    ["bad_format"],
    [{"fail": "fail"}, {"location": "bad_string"}, "bad_format"]
])
def test_get_current_invalid_locations(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()

    query = "DELETE FROM 'get_current_weather';"
    cursor.execute(query)
    conn.commit()

    fake_results = weather.get_current_weather(fake_locations)
    for record_set in fake_results:
        assert record_set.get("weather_error")
    size_query = "SELECT COUNT(*) FROM 'get_current_weather';"
    size = cursor.execute(size_query).fetchone()[0]
    assert size == 0


@pytest.mark.weather2
@pytest.mark.parametrize("locations, expected_passing, expected_errors", [
    ([{"location": "fake_location"}], 1, 0),
    ([{"location": "fake_location"}, {"fail": "fail"}], 1, 1,),
    ([{"location": "fake_location1"}, {"location": "fake_location2"}], 2, 0,),
    ([{"loc": "thing"}, "string"], 0, 2)
])
def test_get_current_mixed_locations(weather, locations, expected_passing,
                                     expected_errors):
    results = weather.get_current_weather(locations)
    actual_passing = 0
    actual_failing = 0
    for record in results:
        if record.get("weather_error") and \
                record["weather_error"].startswith("Invalid location"):
            actual_failing += 1
        elif record.get("weather_results") or record.get("weather_error"):
            actual_passing += 1
    assert actual_failing == expected_errors
    assert actual_passing == expected_passing


@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations", [
    [],
    [{"location": "fake_location"}],
    [{"location": "fake_location1"}, {"location": "fake_location2"}]
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
    if not len(fake_locations):
        assert len(result1) == 0
    else:
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

        # 2. second query - results should still be got from api since not
        # enough
        # rows are in cache
        result2 = weather.get_hourly_forecast(fake_locations)
        print result2
        validate_basic_weather_forecast(fake_locations, result2)

        # assert result2 and cached data are same
        query = "SELECT * FROM 'get_hourly_forecast' " \
                "ORDER BY GENERATION_TIME DESC;"
        cache_result = cursor.execute(query).fetchall()
        print cache_result
        validate_cache_result_forecast(fake_locations, result2, cache_result)

        # 3. third query - results should be from cache. update cache so we know
        # we are getting from cache
        cursor.execute("UPDATE get_hourly_forecast "
                       "SET POINTS = ? "
                       "WHERE GENERATION_TIME= ?",
                       (ujson.dumps({"points": {"fake": "updated cache"}}),
                        result2[0]["generation_time"]))
        conn.commit()
        # set hours to 2 so cached data is sufficient
        result3 = weather.get_hourly_forecast(fake_locations, hours=2)
        print result3
        validate_basic_weather_forecast(fake_locations, result3, warn=False,
                                        hours=2)

        # 4. fourth query  - set update interval so that cache would be
        # marked old
        # and
        # set hours to 2 so cache has enough number of records but is out of
        # date

        weather.set_update_interval("get_hourly_forecast",
                                    datetime.timedelta(seconds=1))
        gevent.sleep(1)
        result4 = weather.get_hourly_forecast(fake_locations, hours=2)
        validate_basic_weather_forecast(fake_locations, result4, warn=False,
                                        hours=2)
        # check data got cached again
        query = "SELECT * FROM 'get_hourly_forecast' " \
                "ORDER BY GENERATION_TIME DESC;"
        cache_result = cursor.execute(query).fetchall()
        print cache_result
        validate_cache_result_forecast(fake_locations, result4, cache_result)


def validate_cache_result_forecast(locations, api_result, cache_result):
    for result in api_result:
        time_in_results = False
        for cr in cache_result:
            if utils.format_timestamp(cr[2]) == result["generation_time"]:
                for record in result["weather_results"]:
                    if utils.format_timestamp(cr[3]).startswith(record[0]):
                        time_in_results = True
                        assert ujson.loads(cr[1]) in locations
                        assert record[1] == ujson.loads(cr[4])
                        break
        assert time_in_results


def validate_basic_weather_forecast(locations, result, warn=True, hours=3):
    assert len(result) == len(locations)
    i = 0
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
            assert isinstance(wr[0], str)
            assert isinstance(wr[1], dict)
            assert wr[1] == weather_result2[0][1]
        i += 1


@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations", [
    [{"location": "bad_string"}],
    [{"fail": "fail"}],
    ["bad_format"],
    [{"location": "bad_string"}, {"fail": "fail"}, "bad_format"]
])
def test_get_forecast_fail(weather, fake_locations):
    conn = weather._cache._sqlite_conn
    cursor = conn.cursor()

    query = "DELETE FROM 'get_hourly_forecast';"
    cursor.execute(query)
    conn.commit()

    fake_results = weather.get_hourly_forecast(fake_locations)
    assert len(fake_results) == len(fake_locations)
    for record_set in fake_results:
        assert record_set.get("weather_error")
    size_query = "SELECT COUNT(*) FROM 'get_hourly_forecast';"
    size = cursor.execute(size_query).fetchone()[0]
    assert size == 0


@pytest.mark.weather2
@pytest.mark.parametrize("locations, expected_passing, expected_errors", [
    ([{"location": "fake_location"}], 1, 0),
    ([{"fail": "fail"}], 0, 1),
    ([{"location": "fake_location"}, {"fail": "fail"}], 1, 1),
    ([{"location": "fake_location1"}, {"location": "fake_location2"}], 2, 0),
    ([{"fail": "fail"}, {"fail": "fail2"}], 0, 2)
])
def test_hourly_forecast_mixed_locations(weather, locations, expected_passing,
                                         expected_errors):
    results = weather.get_current_weather(locations)
    actual_passing = 0
    actual_failing = 0
    for record in results:
        if record.get("weather_error") and \
                record["weather_error"].startswith("Invalid location"):
            actual_failing += 1
        elif record.get("weather_results") or record.get("weather_error"):
            actual_passing += 1
    assert actual_failing == expected_errors
    assert actual_passing == expected_passing


@pytest.mark.xfail
@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations, start_date, end_date", [])
def test_hourly_historical_success(weather, fake_locations, start_date,
                                   end_date):
    assert False


@pytest.mark.xfail
@pytest.mark.weather2
@pytest.mark.parametrize("fake_locations, start_date, end_date", [])
def test_hourly_historical_fail(weather, fake_locations, start_date, end_date):
    assert False


@pytest.mark.weather2
def test_poll_location(volttron_instance, query_agent):
    agent = None
    query_agent.poll_callback.reset_mock()
    try:
        agent = volttron_instance.build_agent(
            agent_class=BasicWeatherAgent,
            identity="test_poll_basic",
            service_name="BasicWeather",
            poll_locations=[{"location": "fake_location"}],
            poll_interval=5,
            should_spawn=True
        )
        gevent.sleep(3)
        assert 1 == query_agent.poll_callback.call_count
        assert "test_poll_basic" == query_agent.poll_callback.call_args[0][1]
        assert "weather/poll/current/all" == \
               query_agent.poll_callback.call_args[0][3]
        # header
        header = query_agent.poll_callback.call_args[0][4]
        assert isinstance(header, dict)
        results1 = query_agent.poll_callback.call_args[0][5]
        assert isinstance(results1, list)
        assert len(results1) == 1
        assert results1[0]["observation_time"]
        test_points = results1[0]["weather_results"]["points"]
        assert test_points
        for initial_point in FAKE_POINTS:
            fake_point = EXPECTED_OUTPUT_VALUES[initial_point]
            test_value = test_points[fake_point["name"]]
            assert test_value
            if test_value:
                assert str(test_value).startswith(str(fake_point["value"]))
        assert results1[0]["location"].startswith("fake_location")

        assert query_agent.vip.rpc.call(
            "test_poll_basic", "health.get_status").get(timeout=10).get(
            'status') == STATUS_GOOD
    finally:
        if agent:
            agent.core.stop()


@pytest.mark.weather2
@pytest.mark.parametrize('config, result_topics', [
    ({'poll_locations': [{"location": "fake_location"},
                         {"location": "fake_location2"}],
      'poll_interval': 5,
      },
     ['weather/poll/current/all']),
    ({'poll_locations': [{"location": "fake_location"},
                         {"location": "fake_location2"}],
      'poll_interval': 10,
      'poll_topic_suffixes': ["1", "2"]},
     ['weather/poll/current/1', 'weather/poll/current/2']),

])
def test_poll_multiple_locations(volttron_instance, query_agent, config,
                                 result_topics):
    agent = None
    query_agent.poll_callback.reset_mock()
    try:
        agent = volttron_instance.build_agent(
            agent_class=BasicWeatherAgent,
            identity="test_poll_basic2",
            service_name="BasicWeather",
            should_spawn=True,
            **config
        )
        gevent.sleep(3)
        print(query_agent.poll_callback.call_args_list)
        assert len(result_topics) == query_agent.poll_callback.call_count
        assert "test_poll_basic2" == query_agent.poll_callback.call_args[0][1]
        i = 0
        for topic in result_topics:
            arguments = query_agent.poll_callback.call_args_list[i][0]
            assert topic == arguments[3]
            # header
            assert isinstance(arguments[4], dict)
            results1 = arguments[5]
            if len(result_topics) > 1:
                assert isinstance(results1, dict)
                assert results1['observation_time']
                assert results1['weather_results']
            else:
                assert isinstance(results1, list)
                assert len(results1) == len(config["poll_locations"])
            i = i + 1
        assert query_agent.vip.rpc.call(
            "test_poll_basic2", "health.get_status").get(timeout=10).get(
            'status') == STATUS_GOOD
    finally:
        if agent:
            agent.core.stop()


@pytest.mark.weather2
@pytest.mark.parametrize('config, err_message', [
    ({'poll_locations': [{"location": "fake_location"},
                         {"location": "fake_location2"}],
      'poll_interval': 5,
      'poll_topic_suffixes': ["1"]
      },
     "poll_topic_suffixes, if set, should be a list of string with the "
     "same length as poll_locations"),
    ({'poll_locations': [{"location": "fake_location"},
                         {"location": "fake_location2"}]
      },
     "poll_interval is mandatory configuration when poll_locations are "
     "specified")
])
def test_poll_errors(volttron_instance, query_agent, config,
                     err_message):
    agent = None
    query_agent.poll_callback.reset_mock()
    try:

        agent = volttron_instance.build_agent(
            agent_class=BasicWeatherAgent,
            identity="test_poll_errors",
            service_name="BasicWeather",
            should_spawn=True,
            **config
        )
        gevent.sleep(10)
        assert query_agent.poll_callback.call_count == 0
        status_result = query_agent.vip.rpc.call(
            "test_poll_errors", "health.get_status").get(timeout=10)
        assert status_result['status'] == STATUS_BAD
        assert err_message in status_result['context']

    finally:
        if agent:
            agent.core.stop()
