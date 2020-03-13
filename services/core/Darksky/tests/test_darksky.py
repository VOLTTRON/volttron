# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import pytest
import os
import copy
import gevent
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from mock import MagicMock

from volttron.platform.agent.utils import get_aware_utc_now, format_timestamp
from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform import get_services_core
from volttron.platform.agent import utils

__version__ = "0.1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

API_KEY = os.environ.get('DARKSKY_KEY')

darksky_service = {
    'weather_service': get_services_core('Darksky'),
    'identity': 'platform.darksky',
    'max_size_gb': None,
    'api_key': API_KEY,
    'poll_locations': [],
    'poll_interval': 5,
    'performance_mode': False,
    'api_calls_limit': 100
}

darksky_perf = {
    'weather_service': get_services_core('Darksky'),
    'identity': 'platform.darksky_perf',
    'max_size_gb': None,
    'api_key': API_KEY,
    'poll_locations': [],
    'poll_interval': 5,
    'performance_mode': True,
    'api_calls_limit': 100
}

# TODO add test case for testing api_call_limit: -1

polling_service = {
    'weather_service': get_services_core('DarkskyAgent'),
    'max_size_gb': None,
    'api_key': '902a708bcc2c20fdcd91962640ef5d1b',
    'poll_interval': 5
}

# global variable. Set to skip the module
pytestmark = pytest.mark.skipif(not API_KEY, reason="No API key found. "
                                                    "Darksky weather API "
                                                    "key needs to be set in "
                                                    "the environment variable "
                                                    "DARKSKY_KEY")


@pytest.fixture(scope="function")
def cleanup_cache(volttron_instance, query_agent, weather):
    weather_uuid = weather[0]
    identity = weather[1]
    tables = ["get_current_weather", "get_hourly_forecast",
              "get_minutely_forecast", "get_daily_forecast"]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather_uuid, "darkskyagent-" +
                         version, "darkskyagent-" + version +
                         ".agent-data", "weather.sqlite"])
    _log.debug(database_file)
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()
    for table in tables:
        query = "DELETE FROM {};".format(table)
        _log.debug(query)
        cursor.execute(query)
    try:
        cursor.execute("DELETE FROM API_CALLS;")
    except Exception as e:
        print(e)
    sqlite_connection.commit()


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance2
    agent = volttron_instance.build_agent()
    agent.poll_callback = MagicMock(name="poll_callback")
    # subscribe to weather poll results
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix="weather/poll/current",
        callback=agent.poll_callback).get()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

@pytest.fixture(scope="module", params=[darksky_service, darksky_perf])
def weather(request, volttron_instance):
    print("** Setting up weather agent module **")
    print("request param", request.param)
    config = copy.copy(request.param)
    source = config.pop('weather_service')
    identity = config.pop('identity')

    agent = volttron_instance.install_agent(
        vip_identity=identity,
        agent_dir=source,
        start=False,
        config_file=config)

    volttron_instance.start_agent(agent)
    gevent.sleep(3)

    def stop_agent():
        print("stopping weather service")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent)

    request.addfinalizer(stop_agent)
    return agent, identity

@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}],
    [{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}]
])
@pytest.mark.darksky
def test_success_current(volttron_instance, cleanup_cache, weather,
                         query_agent,
                         locations):
    weather_uuid = weather[0]
    identity = weather[1]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather_uuid, "darkskyagent-" +
                              version, "darkskyagent-" + version +
                              ".agent-data", "weather.sqlite"])
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()

    api_calls_query = 'SELECT COUNT(*) FROM API_CALLS'
    cursor.execute(api_calls_query)
    current_api_calls = cursor.fetchone()[0]

    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)

    if query_data[0].get("weather_error"):
        error = query_data[0].get("weather_error")
        if error.endswith("Remote API returned Code 403"):
            pytest.skip("API key has exceeded daily call limit")

    print(query_data)

    cursor.execute(api_calls_query)
    new_api_calls = cursor.fetchone()[0]
    assert new_api_calls == current_api_calls + len(locations)
    current_api_calls = new_api_calls

    assert len(query_data) == len(locations)
    for record in query_data:
        # check format here
        assert record.get("observation_time")
        assert (record.get("lat") and record.get("long"))
        results = record.get("weather_results")
        if results:
            assert isinstance(results, dict)
            assert "data" not in results
            assert results["attribution"] == "Powered by Dark Sky"
        else:
            results = record.get("weather_error")
            if results.startswith("Remote API returned no data") or \
                    results.startswith("Remote API redirected request, "
                                       "but redirect failed") \
                    or results.startswith("Remote API returned invalid "
                                          "response") \
                    or results.startswith("API request failed with unexpected "
                                          "response"):
                assert True
            else:
                assert False
    services = {"get_minutely_forecast": 60,
                "get_hourly_forecast": 48,
                "get_daily_forecast":7}
    for service, records_amount in services.items():
        query = 'SELECT COUNT(*) FROM {service}'.format(service=service)
        cursor.execute(query)
        num_records = cursor.fetchone()[0]
        if identity == 'platform.darksky_perf':
            assert num_records is 0
        else:
            assert num_records is records_amount*len(locations)

    cache_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)

    cursor.execute(api_calls_query)
    new_api_calls = cursor.fetchone()[0]
    assert new_api_calls == current_api_calls

    # check names returned are valid
    assert len(query_data) == len(cache_data)
    for x in range(0, len(cache_data)):
        assert len(cache_data[x]) == len(query_data[x])
        for key in query_data[x]:
            assert query_data[x].get(key) == cache_data[x].get(key)

    for service, records_amount in services.items():
        query = 'SELECT COUNT(*) FROM {service}'.format(service=service)
        cursor.execute(query)
        num_records = cursor.fetchone()[0]
        if identity == 'platform.darksky_perf':
            assert num_records is 0
        else:
            assert num_records is records_amount*len(locations)


@pytest.mark.darksky
def test_calls_exceeded(volttron_instance, cleanup_cache, query_agent,
                                weather):
    weather_uuid = weather[0]
    identity = weather[1]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather_uuid, "darkskyagent-" +
                              version, "darkskyagent-" + version +
                              ".agent-data", "weather.sqlite"])
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()

    for i in range(0, 100):
        time = format_timestamp(get_aware_utc_now() + timedelta(seconds=i))
        insert_query = """INSERT INTO API_CALLS
                                         (CALL_TIME) VALUES (?);"""
        cursor.execute(insert_query, (time,))
    sqlite_connection.commit()

    locations = [{"lat": 39.7555, "long": -105.2211}]
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)

    assert query_data[0]['weather_error'] == 'No calls currently available ' \
                                               'for the configured API key'
    assert not query_data[0].get('weather_results')

    query_data = query_data = query_agent.vip.rpc.call(
        identity, 'get_hourly_forecast', locations).get(timeout=30)

    assert query_data[0]['weather_error'] == 'No calls currently available ' \
                                             'for the configured API key'
    assert not query_data[0].get('weather_results')

    delete_query = "DROP TABLE IF EXISTS API_CALLS;"
    cursor.execute(delete_query)

    create_query = """CREATE TABLE API_CALLS
                      (CALL_TIME TIMESTAMP NOT NULL);"""
    cursor.execute(create_query)
    sqlite_connection.commit()

@pytest.mark.parametrize("locations", [
    ["fail"],
    [{"lat": 39.7555}],
    ()
])
@pytest.mark.darksky
def test_current_fail(weather, query_agent, locations):
    identity = weather[1]
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)
    for record in query_data:
        error = record.get("weather_error")
        assert error.startswith("Invalid location format.") or error.startswith(
            "Invalid location")
        assert record.get("weather_results") is None


@pytest.mark.parametrize("locations, service", [
    ([{"lat": 39.7555, "long": -105.2211}], 'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_hourly_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_hourly_forecast'),
])
@pytest.mark.darksky
def test_success_forecast(volttron_instance, cleanup_cache, weather,
                          query_agent, locations, service):
    weather_uuid = weather[0]
    identity = weather[1]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather_uuid, "darkskyagent-" +
                              version, "darkskyagent-" + version +
                              ".agent-data", "weather.sqlite"])
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()

    api_calls_query = 'SELECT COUNT(*) FROM API_CALLS'
    cursor.execute(api_calls_query)
    current_api_calls = cursor.fetchone()[0]

    query_data = []

    if service == "get_minutely_forecast":
        query_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)
    if service == "get_hourly_forecast":
        query_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)
    if service == "get_daily_forecast":
        query_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)

    if query_data[0].get("weather_error"):
        error = query_data[0].get("weather_error")
        if error.endswith("Remote API returned Code 403"):
            pytest.skip("API key has exceeded daily call limit")

    cursor.execute(api_calls_query)
    new_api_calls = cursor.fetchone()[0]
    # For daily forecast, when request time is on the same day but earlier hour as first forecast, the agent discards
    # the forecast entry of current day and makes a second call for the 8th day forecast.
    if service == "get_daily_forecast":
        number = current_api_calls + len(locations)
        assert new_api_calls == number or new_api_calls == number + 1
    else:
        assert new_api_calls == current_api_calls + len(locations)
    current_api_calls = new_api_calls

    services = {
                "get_minutely_forecast": 60,
                "get_hourly_forecast": 48,
                "get_current_weather": 1,
                "get_daily_forecast": 7}

    for service_name, records_amount in services.items():
        query = 'SELECT COUNT(*) FROM {service}'.format(service=service_name)
        print(query)
        cursor.execute(query)
        num_records = cursor.fetchone()[0]
        if service_name == service:
            assert num_records is records_amount * len(locations)
        else:
            if identity == 'platform.darksky_perf':
                assert num_records is 0
            else:
                assert num_records is records_amount * len(locations)

    assert len(query_data) == len(locations)

    for x in range(0, len(query_data)):
        location_data = query_data[x]
        assert location_data.get("lat") and location_data.get("long")
        results = location_data.get("weather_results")
        error = location_data.get("weather_error")
        if error and not results:
            if error.startswith("Remote API returned no data") \
                    or error.startswith("Remote API redirected request, but "
                                        "redirect failed") \
                    or error.startswith("Remote API returned invalid "
                                        "response") \
                    or error.startswith("API request failed with "
                                        "unexpected response"):
                assert True
            else:
                assert False
        if results:
            assert location_data.get("generation_time")
            for record in results:
                forecast_time = utils.parse_timestamp_string(record[0])
                assert isinstance(forecast_time, datetime)
                if not service == "get_minutely_forecast":
                    assert 'summary' in record[1]
                else:
                    assert 'summary' not in record[1]
                assert record[1]["attribution"] == "Powered by Dark Sky"

    cache_data = []

    # default quantity

    if service == 'get_minutely_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)
    if service == 'get_hourly_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)
    if service == 'get_daily_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations).get(timeout=30)

    cursor.execute(api_calls_query)
    new_api_calls = cursor.fetchone()[0]
    assert new_api_calls == current_api_calls

    assert len(cache_data) == len(query_data)
    for x in range(0, len(cache_data)):
        query_location_data = query_data[x]
        print(query_location_data)
        cache_location_data = cache_data[x]
        print(cache_location_data)
        assert cache_location_data.get(
            "generation_time") == query_location_data.get("generation_time")
        assert cache_location_data.get("lat") == query_location_data.get(
            "lat")
        assert cache_location_data.get("long") == query_location_data.get(
            "long")
        if cache_location_data.get("weather_results"):

            query_weather_results = query_location_data.get("weather_results")
            cache_weather_results = cache_location_data.get("weather_results")
            for y in range(0, len(query_weather_results)):
                result = query_weather_results[y]
                cache_result = cache_weather_results[y]
                query_time, oldtz = utils.process_timestamp(result[0])
                query_time = utils.format_timestamp(query_time)
                assert query_time == cache_result[0]
                for key in cache_result[1]:
                    assert cache_result[1][key] == result[1][key]
        else:
            results = cache_location_data.get("weather_error")
            if results.startswith("Remote API returned no data") \
                    or results.startswith("Remote API redirected request, but "
                                          "redirect failed") \
                    or results.startswith("Remote API returned invalid "
                                          "response") \
                    or results.startswith("API request failed with unexpected "
                                          "response"):
                assert True
            else:
                assert False

    for service_name, records_amount in services.items():
        if not service_name == service:
            query = 'SELECT COUNT(*) FROM {service}'.format(
                service=service_name)
            cursor.execute(query)
            num_records = cursor.fetchone()[0]
            if identity == 'platform.darksky_perf':
                assert num_records is 0
            else:
                assert num_records is records_amount*len(locations)

@pytest.mark.parametrize("locations, service", [
    ([{"lat": 39.7555, "long": -105.2211}], 'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_hourly_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_hourly_forecast'),
])
@pytest.mark.darksky
def test_less_than_default_forecast(volttron_instance, cleanup_cache, weather,
                                    query_agent, locations, service):
    query_data = []
    cache_data = []
    identity = weather[1]
    if service == 'get_minutely_forecast':
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, minutes=2).get(timeout=30)
    elif service == 'get_hourly_forecast':
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, hours=2).get(timeout=30)
    elif service == 'get_daily_forecast':
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, days=2).get(timeout=30)
    else:
        pytest.fail('invalid request type')
    if query_data[0].get("weather_error"):
        error = query_data[0].get("weather_error")
        if error.endswith("Remote API returned Code 403"):
            pytest.skip("API key has exceeded daily call limit")

    assert len(query_data) == len(locations)

    for record in query_data:
        assert len(record['weather_results']) == 2

    if service == 'get_minutely_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, minutes=2).get(timeout=30)
    elif service == 'get_hourly_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, hours=2).get(timeout=30)
    elif service == 'get_daily_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, days=2).get(timeout=30)

    assert len(cache_data) == len(query_data)
    for x in range(0, len(cache_data)):
        query_location_data = query_data[x]
        print(query_location_data)
        cache_location_data = cache_data[x]
        print(cache_location_data)
        assert cache_location_data.get(
            "generation_time") == query_location_data.get("generation_time")
        assert cache_location_data.get("lat") == query_location_data.get(
            "lat")
        assert cache_location_data.get("long") == query_location_data.get(
            "long")
        if cache_location_data.get("weather_results"):

            query_weather_results = query_location_data.get("weather_results")
            cache_weather_results = cache_location_data.get("weather_results")
            for y in range(0, len(query_weather_results)):
                result = query_weather_results[y]
                cache_result = cache_weather_results[y]
                query_time, oldtz = utils.process_timestamp(result[0])
                query_time = utils.format_timestamp(query_time)
                assert query_time == cache_result[0]
                for key in cache_result[1]:
                    assert cache_result[1][key] == result[1][key]

@pytest.mark.parametrize("locations, service", [
    ([{"lat": 39.7555, "long": -105.2211}], 'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_minutely_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_daily_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}], 'get_hourly_forecast'),
    ([{"lat": 39.7555, "long": -105.2211}, {"lat": 46.2804, "long": -119.2752}],
     'get_hourly_forecast'),
])
@pytest.mark.darksky
def test_more_than_default_forecast(volttron_instance, cleanup_cache, weather,
                                    query_agent, locations, service):
    identity = weather[1]
    big_request = 0
    query_data = []
    cache_data = []
    if service == 'get_minutely_forecast':
        big_request = 61
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, minutes=big_request).get(timeout=30)
        if big_request > 60:
            big_request = 60  # dark sky provides 60 minutes max.
    elif service == 'get_hourly_forecast':
        big_request = 50
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, hours=big_request).get(timeout=30)
    elif service == 'get_daily_forecast':
        big_request = 9
        query_data = query_agent.vip.rpc.call(
            identity, service, locations, days=big_request).get(timeout=30)
    else:
        pytest.fail('invalid request type')
    if query_data[0].get("weather_error"):
        error = query_data[0].get("weather_error")
        if error.endswith("Remote API returned Code 403"):
            pytest.skip("API key has exceeded daily call limit")
    assert len(query_data) == len(locations)
    for record in query_data:
        assert len(record['weather_results']) == big_request

    if service == 'get_minutely_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, minutes=big_request).get(timeout=30)
    elif service == 'get_hourly_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, hours=big_request).get(timeout=30)
    elif service == 'get_daily_forecast':
        cache_data = query_agent.vip.rpc.call(
            identity, service, locations, days=big_request).get(timeout=30)

    assert len(cache_data) == len(query_data)
    print("Query data: \n {}".format(query_data))
    print("Cache data: \n {}".format(cache_data))

    # TODO: verify that we get the right forecast times

    for x in range(0, len(cache_data)):
        query_location_data = query_data[x]
        cache_location_data = cache_data[x]
        assert cache_location_data.get(
            "generation_time") == query_location_data.get("generation_time")
        assert cache_location_data.get("lat") == query_location_data.get(
            "lat")
        assert cache_location_data.get("long") == query_location_data.get(
            "long")
        if cache_location_data.get("weather_results"):

            query_weather_results = query_location_data.get("weather_results")
            cache_weather_results = cache_location_data.get("weather_results")
            for y in range(0, len(query_weather_results)):
                result = query_weather_results[y]
                cache_result = cache_weather_results[y]
                query_time, oldtz = utils.process_timestamp(result[0])
                query_time = utils.format_timestamp(query_time)
                assert query_time == cache_result[0]
                for key in cache_result[1]:
                    assert cache_result[1][key] == result[1][key]


@pytest.mark.parametrize("locations, service", [
    (["fail"], 'get_minutely_forecast'),
    ([{"lat": 39.7555}], 'get_minutely_forecast'),
    ([], 'get_minutely_forecast'),
    (["fail"], 'get_hourly_forecast'),
    ([{"lat": 39.7555}], 'get_hourly_forecast'),
    ([], 'get_hourly_forecast'),
    (["fail"], 'get_daily_forecast'),
    ([{"lat": 39.7555}], 'get_daily_forecast'),
    ([], 'get_daily_forecast')
])
@pytest.mark.darksky
def test_forecast_fail(weather, query_agent, locations, service):
    identity = weather[1]
    query_data = query_agent.vip.rpc.call(identity, service,
                                          locations).get(timeout=30)
    for record in query_data:
        error = record.get("weather_error")
        if error.startswith("Invalid location format."):
            assert error.startswith("Invalid location format.")
        elif error.startswith("Invalid location"):
            assert error.startswith("Invalid location")
        else:
            assert False
        assert record.get("weather_results") is None


@pytest.mark.darksky
@pytest.mark.parametrize('config, result_topics', [
    ({'poll_locations': [{"lat": 39.7555, "long": -105.2211},
                         {"lat": 46.2804, "long": 119.2752}],
      'poll_interval': 5,
      'api_key': API_KEY
      },
     ['weather/poll/current/all']),
    ({'poll_locations': [{"lat": 39.7555, "long": -105.2211},
                         {"lat": 46.2804, "long": 119.2752}],
      'poll_interval': 5,
      'api_key': API_KEY,
      'poll_topic_suffixes': ['test1', 'test2']
      },
     ['weather/poll/current/test1', 'weather/poll/current/test2'])
])
def test_polling_locations_valid_config(volttron_instance, query_agent, config,
                                        result_topics):
    agent_uuid = None
    query_agent.poll_callback.reset_mock()
    try:
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=get_services_core("Darksky"),
            start=False,
            config_file=config)
        volttron_instance.start_agent(agent_uuid)
        gevent.sleep(3)
        print(query_agent.poll_callback.call_args_list)
        assert len(result_topics) == query_agent.poll_callback.call_count
        assert "poll.weather" == query_agent.poll_callback.call_args[0][1]
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
            "poll.weather", "health.get_status").get(timeout=10).get(
            'status') == STATUS_GOOD
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.darksky
def test_default_config(volttron_instance):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = volttron_instance.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_services_core("Darksky"), "config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)
    volttron_instance.install_agent(
        agent_dir=get_services_core("Darksky"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")
    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
