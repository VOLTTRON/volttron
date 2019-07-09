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
import copy

import pytest
import gevent
from mock import MagicMock
import sqlite3
import logging
from volttron.platform.agent import utils
from datetime import datetime
from volttron.platform.messaging.health import STATUS_GOOD

from volttron.platform import get_services_core

__version__ = "0.1.0"
identity = 'platform.weather'

utils.setup_logging()
_log = logging.getLogger(__name__)

# how do we handle the registry config
weather_dot_gov_service = {
    'weather_service': get_services_core('WeatherDotGov'),
    'max_size_gb': None,
    'api_key': None,
    'poll_locations': [],
    'poll_interval': 5
}

polling_service = {
    'weather_service': get_services_core('WeatherDotGov'),
    'max_size_gb': None,
    'api_key': None,
    'poll_interval': 5
}


@pytest.fixture(scope="function")
def cleanup_cache(volttron_instance, query_agent, weather):
    tables = ["get_current_weather", "get_hourly_forecast"]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather, "weatherdotgovagent-" +
                         version, "weatherdotgovagent-" + version +
                         ".agent-data", "weather.sqlite"])
    _log.debug(database_file)
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()
    for table in tables:
        query = "DELETE FROM {};".format(table)
        _log.debug(query)
        cursor.execute(query)
        sqlite_connection.commit()


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance
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


@pytest.fixture(scope="module", params=[weather_dot_gov_service])
def weather(request, volttron_instance):
    print("** Setting up weather agent module **")
    print("request param", request.param)
    config = copy.copy(request.param)
    source = config.pop('weather_service')

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
    return agent


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"station": "KLAX"}],
    [{"station": "KLAX"}, {"station": "KBOI"}]
])
def test_success_current(cleanup_cache, weather, query_agent, locations):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)
    print(query_data)
    assert len(query_data) == len(locations)
    for record in query_data:
        # check format here
        assert record.get("observation_time")
        assert record.get("station")
        # check weather error message
        results = record.get("weather_results")
        if results:
            assert isinstance(results, dict)
            assert "summary" not in results
        else:
            results = record.get("weather_error")
            if results.startswith("Remote API returned no data") or \
                    results.startswith("Remote API redirected request, "
                                       "but redirect failed") \
                    or results.startswith("Remote API returned invalid "
                                          "response")\
                    or results.startswith("API request failed with unexpected "
                                          "response"):
                assert True
            else:
                assert False

    cache_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)

    # check names returned are valid
    assert len(cache_data) == len(cache_data)
    for x in range(0, len(cache_data)):
        assert len(cache_data[x]) == len(query_data[x])
        for key in query_data[x]:
            assert query_data[x].get(key) == cache_data[x].get(key)


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}, "fail"],
    ()
])
def test_current_fail(weather, query_agent, locations):
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=30)
    for record in query_data:
        error = record.get("weather_error")
        assert error.startswith("Invalid location format.") or error.startswith(
            "Invalid location")
        assert record.get("weather_results") is None


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}],
    [{"lat": 39.0693, "long": -94.6716}],
    [{"wfo": 'BOU', 'x': 54, 'y': 62}],
    [{"wfo": 'BOU', 'x': 54, 'y': 62}, {"lat": 39.7555, "long": -105.2211}],
    []
])
def test_success_forecast(cleanup_cache, weather, query_agent, locations):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    query_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
                                          locations, hours=2).get(timeout=30)
    # print(query_data)
    assert len(query_data) == len(locations)
    for x in range(0, len(query_data)):
        location_data = query_data[x]
        assert (location_data.get("lat") and location_data.get("long")) or \
               (location_data.get("wfo") and location_data.get(
                   "x") and location_data.get("y"))
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

    cache_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
                                          locations,
                                          hours=2).get(timeout=30)
    assert len(cache_data) == len(query_data)
    for x in range(0, len(cache_data)):
        query_location_data = query_data[x]
        cache_location_data = cache_data[x]
        assert cache_location_data.get(
            "generation_time") == query_location_data.get("generation_time")
        if cache_location_data.get("lat") and cache_location_data.get("long"):
            assert cache_location_data.get("lat") == query_location_data.get(
                "lat")
            assert cache_location_data.get("long") == query_location_data.get(
                "long")
        elif cache_location_data.get("wfo") and cache_location_data.get(
                "x") and cache_location_data.get("y"):
            assert cache_location_data.get("wfo") == query_location_data.get(
                "wfo")
            assert cache_location_data.get("x") == query_location_data.get("x")
            assert cache_location_data.get("y") == query_location_data.get("y")
        else:
            assert False
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


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    ["fail"],
    [{"station": "KLAX"}],
    [{"station": "KLAX"}, "fail"],
    [{"lat": 39.0693}],

])
def test_hourly_forecast_fail(weather, query_agent, locations):
    query_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
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


@pytest.mark.weather2
@pytest.mark.parametrize('config, result_topics', [
    ({'poll_locations': [{"station": "KLAX"}, {"station": "KABQ"}],
      'poll_interval': 5,
      },
     ['weather/poll/current/all']),
    ({'poll_locations': [{"station": "KLAX"}, {"station": "KABQ"}],
      'poll_interval': 5,
      'poll_topic_suffixes': ["KLAX", "KABQ"]},
     ['weather/poll/current/KLAX', 'weather/poll/current/KABQ']),

])
def test_polling_locations_valid_config(volttron_instance, query_agent, config,
                                        result_topics):
    agent_uuid = None
    query_agent.poll_callback.reset_mock()
    try:
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=get_services_core("WeatherDotGov"),
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
