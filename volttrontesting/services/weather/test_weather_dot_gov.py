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

import pytest
import gevent
from mock import MagicMock
import copy
import logging
from volttron.platform.agent import utils
from datetime import datetime, time, timedelta

from volttron.platform import get_services_core

__version__ = "0.1.0"
identity = 'platform.weather'

utils.setup_logging()
_log = logging.getLogger(__name__)

# how do we handle the registry config
weather_dot_gov_service = {
    'weather_service': get_services_core('WeatherDotGov'),
    # TODO change max size when memory error has been resolved
    # 'max_size_gb': 0.00002,
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

httpErrors = ["API request success, no data returned (code",
              "API redirected, but requests did not reach the intended location (code ",
              "Client's API request failed (code ",
              "API request to server failed (code ",
              "API request failed with unexpected response code (code "]

@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance2
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

# TODO params
@pytest.fixture(scope="module", params=[weather_dot_gov_service])
def weather(request, volttron_instance):
    print("** Setting up weather agent module **")
    print("request param", request.param)

    source = request.param.pop('weather_service')

    agent = volttron_instance.install_agent(
        vip_identity=identity,
        agent_dir=source,
        start=False,
        config_file=request.param)

    volttron_instance.start_agent(agent)

    def stop_agent():
        print("stopping weather service")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent)
        volttron_instance.remove_agent(agent)

    request.addfinalizer(stop_agent)
    return request.param


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"station": "KLAX"}],
    [{"station": "KLAX"}, {"station": "KBOI"}],
    []
])
def test_success_current(weather, query_agent, locations):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather', locations).get(timeout=30)
    assert len(query_data) == len(locations)
    for record in query_data:
        # check format here
        assert record.get("observation_time")
        assert record.get("station")
        # check weather error message
        results = record.get("weather_results")
        if results:
            assert isinstance(results, dict)
        else:
            results = record.get("weather_error")
            # The given http errors are valid responses.
            has_http_error = False
            for error in httpErrors:
                if results.startswith(error):
                    _log.debug(error)
                    has_http_error = True
            assert has_http_error

    cache_data = query_agent.vip.rpc.call(identity, 'get_current_weather', locations).get(timeout=30)

    # check names returned are valid
    assert len(cache_data) == len(cache_data)
    for x in range(0, len(cache_data)):
        assert len(cache_data[x]) == len(query_data[x])
        for key in query_data[x]:
            assert query_data[x].get(key) == cache_data[x].get(key)

@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}, "fail"]
])
def test_current_fail(weather, query_agent, locations):
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather', locations).get(timeout=30)
    for record in query_data:
        assert record.get("location_error")
        assert record.get("weather_results") is None


@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}],
    [{"wfo": 'BOU', 'x': 54, 'y': 62}],
    [{"wfo": 'BOU', 'x': 54, 'y': 62}, {"lat": 39.7555, "long": -105.2211}],
    []
])
def test_success_forecast(weather, query_agent, locations):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    locations = [{"lat": 39.7555, "long": -105.2211}]

    query_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
                                             locations).get(timeout=30)
    assert len(query_data) == len(locations)
    for x in range(0, len(query_data)):
        location_data = query_data[x]
        assert location_data.get("generation_time")
        assert (location_data.get("lat") and location_data.get("long")) or \
               (location_data.get("wfo") and location_data.get("x") and location_data.get("y"))
        results = location_data.get("weather_results")
        assert (results or location_data.get("weather_error"))
        if results:
            for record in results:
                forecast_time = utils.parse_timestamp_string(record[0])
                assert isinstance(forecast_time, datetime)

    cache_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
                                          locations).get(timeout=30)
    assert len(cache_data) == len(query_data)
    for x in range(0, len(cache_data)):
        query_location_data = query_data[x]
        cache_location_data = cache_data[x]
        assert cache_location_data.get("generation_time") == query_location_data.get("generation_time")
        if cache_location_data.get("lat") and cache_location_data.get("long"):
            assert cache_location_data.get("lat") == query_location_data.get("lat")
            assert cache_location_data.get("long") == query_location_data.get("long")
        elif cache_location_data.get("wfo") and cache_location_data.get("x") and cache_location_data.get("y"):
            assert cache_location_data.get("wfo") == query_location_data.get("wfo")
            assert cache_location_data.get("x") == query_location_data.get("x")
            assert cache_location_data.get("y") == query_location_data.get("y")
        else:
            assert False
        if cache_location_data.get("weather_results"):
            query_weather_results = query_location_data.get("weather_results")
            cache_weather_results = cache_location_data.get("weather_results")
            # TODO There is some condition which results in the timestamp format here being bad
            print query_weather_results
            print cache_weather_results
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
            has_http_error = False
            for error in httpErrors:
                if results.startswith(error):
                    _log.debug(error)
                    has_http_error = True
            assert has_http_error

# TODO compare failure condition messages
@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    ["fail"],
    [{"station": "KLAX"}],
    [{"station": "KLAX"}, "fail"]
])
def test_hourly_forecast_fail(weather, query_agent, locations):
    query_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast',
                                             locations).get(timeout=30)
    for record in query_data:
        assert record.get("location_error")
        assert record.get("weather_results") is None

@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"station": "KLAX"}, {"station": "KABQ"}]
])
def test_polling_locations_valid_locations(volttron_instance, weather, query_agent, locations):
    new_config = copy.copy(weather_dot_gov_service)
    source = get_services_core('WeatherDotGov')
    new_config["poll_locations"] = locations
    new_config["poll_interval"] = 5
    agent_uuid = None
    try:
        query_agent.callback = MagicMock(name="callback")
        query_agent.callback.reset_mock()
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=source,
            start=False,
            config_file=new_config)
        volttron_instance.start_agent(agent_uuid)
        query_agent.vip.pubsub.subscribe('pubsub', "weather/poll//all", query_agent.callback)
        gevent.sleep(5)
        assert query_agent.callback.call_count == len(locations)
        print query_agent.callback.call_args
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.weather2
@pytest.mark.parametrize("locations", [
    [{"lat": 39.7555, "long": -105.2211}],
    [{"lat": 39.7555}, {"long": -105.2211}],
    [{"wfo": 'BOU', 'x': 54, 'y': 62}],
    ["fail"]
])
def test_polling_locations_invalid_locations(volttron_instance, weather, query_agent, locations):
    new_config = copy.copy(polling_service)
    source = get_services_core('WeatherDotGov'),
    new_config["polling_locations"] = locations
    agent_uuid = None
    try:
        query_agent.callback = MagicMock(name="callback")
        query_agent.callback.reset_mock()
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=source,
            start=False,
            config_file=new_config)
        volttron_instance.start_agent(agent_uuid)
        query_agent.vip.pubsub.subscribe('pubsub', "weather/poll//all", query_agent.callback)
        gevent.sleep(5)
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)