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
import sqlite3
import copy
import os
import gevent
import logging
from mock import MagicMock

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.messaging.health import STATUS_GOOD

__version__ = "5.0.1"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Ambient agent tests rely upon the configuration of devices operated
# by the owner/operater of Ambient devices - To run the Ambient tests
# the test_data/test_ambient_data.json file should be populated:
# api_key should be filled in with a valid Ambient API key, app_key
# with an Ambient application key, and locations with a list of device
# "locations" corresponding to devices owned/operated by the runner of
# the test suite.

# Replace get services core with something that will point us to our local directory
ambient_agent_path = get_services_core("Ambient")

API_KEY = os.environ.get('AMBIENT_API_KEY')
APP_KEY = os.environ.get('AMBIENT_APP_KEY')

# Locations should be a list of location objects with the value string matching the name of the location as configured
# in Ambient
LOCATIONS = [
        {"location": "<location a>"},
        {"location": "<location b>"}
    ]

# Poll test topics should be a list of weather topic strings with number of entries == length of locations
POLL_TEST_TOPICS = ['weather/poll/current/test_a', 'weather/poll/current/test_b']

ambient_service = {
    'weather_service': ambient_agent_path,
    'identity': 'platform.ambient',
    'max_size_gb': None,
    'api_key': API_KEY,
    'application_key': APP_KEY,
    'poll_locations': [],
    'poll_interval': 5,
}

ambient_polling_service = {
    'weather_service': ambient_agent_path,
    'identity': 'platform.ambient',
    'max_size_gb': None,
    'api_key': API_KEY,
    'application_key': APP_KEY,
    'poll_locations': LOCATIONS,
    'poll_interval': 5,
}

SKIP_LOCS = not len(LOCATIONS)
if not SKIP_LOCS:
    for location in LOCATIONS:
        if not isinstance(location, str) or not len(location):
            SKIP_LOCS = True

# global variable. Set to skip the module
pytestmark_api = pytest.mark.skipif(not API_KEY, reason="No API key found. "
                                                        "Ambient weather API "
                                                        "key needs to be set in "
                                                        "the test_ambient_data.json"
                                                        " variable api_key")
pytestmark_app = pytest.mark.skipif(not APP_KEY, reason="No APP key found. "
                                                        "Ambient weather application"
                                                        " key needs to be set in "
                                                        "the test_ambient_data.json"
                                                        " variable app_key")
pytestmark_locs = pytest.mark.skipif(SKIP_LOCS, reason="Invalid locations list for"
                                                       "Ambient agent. Ambient "
                                                       "agent requires a list of "
                                                       "location strings "
                                                       "corresponding to devices "
                                                       "owned/operated by the test"
                                                       "runner to be set in  the "
                                                       "test_ambient_data.json"
                                                       " variable app_key")


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


@pytest.fixture(scope="module", params=[ambient_service])
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


@pytest.fixture(scope="function")
def cleanup_cache(volttron_instance, query_agent, weather):
    """

    :return:
    """
    weather_uuid = weather[0]
    identity = weather[1]
    tables = ["get_current_weather"]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file = "/".join([cwd, "agents", weather_uuid, "ambientagent-" +
                              version, "ambientagent-" + version + ".agent-data",
                              "weather.sqlite"])
    _log.debug(database_file)
    sqlite_connection = sqlite3.connect(database_file)
    cursor = sqlite_connection.cursor()
    for table in tables:
        query = "DELETE FROM {};".format(table)
        _log.debug(query)
        cursor.execute(query)
    sqlite_connection.commit()


@pytest.fixture(scope="function")
def api_wait():
    """
    Wait 3 seconds to ensure no requests are sent before the 3 second timer
    for API calls has refreshed
    """
    gevent.sleep(3)


@pytest.mark.parametrize("locations", [
    LOCATIONS
])
def test_success_current(volttron_instance, cleanup_cache, weather,
                         query_agent, locations, api_wait):
    weather_uuid = weather[0]
    identity = weather[1]
    version = query_agent.vip.rpc.call(identity, 'get_version').get(timeout=3)
    cwd = volttron_instance.volttron_home
    database_file_path = os.path.join(cwd, "agents", weather_uuid, "ambientagent-" +
                                      version, "ambientagent-" + version +
                                      ".agent-data", "weather.sqlite")
    sqlite_connection = sqlite3.connect(database_file_path)
    cursor = sqlite_connection.cursor()

    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=33)

    if query_data[0].get("weather_error"):
        error = query_data[0].get("weather_error")

    print(query_data)

    assert len(query_data) == len(locations)
    for record in query_data:
        # check format here
        assert record.get("observation_time")
        assert (record.get("location"))
        results = record.get("weather_results")
        if results:
            assert isinstance(results, dict)
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

    cache_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=3)

    # check names returned are valid
    assert len(query_data) == len(cache_data)
    for x in range(0, len(cache_data)):
        assert len(cache_data[x]) == len(query_data[x])
        for key in query_data[x]:
            assert query_data[x].get(key) == cache_data[x].get(key)


@pytest.mark.parametrize("locations", [
    ["fail"],
    [{"location": 39.7555}],
    ()
])
def test_current_fail(weather, query_agent, locations, api_wait):
    """

    :param locations:
    :return:
    """
    identity = weather[1]
    query_data = query_agent.vip.rpc.call(identity, 'get_current_weather',
                                          locations).get(timeout=33)
    for record in query_data:
        error = record.get("weather_error")
        assert error.startswith("Invalid location format.") or error.startswith(
            "Invalid location")
        assert record.get("weather_results") is None


@pytest.mark.parametrize('config, result_topics', [
    ({'poll_locations': LOCATIONS,
      'poll_interval': 5,
      'api_key': API_KEY,
      'application_key': APP_KEY
      },
     ['weather/poll/current/all']),
    ({'poll_locations': LOCATIONS,
      'poll_interval': 5,
      'api_key': API_KEY,
      'application_key': APP_KEY,
      'poll_topic_suffixes': ['test_a', 'test_b']
      },
     POLL_TEST_TOPICS)
])
def test_polling_locations_valid_config(volttron_instance, query_agent, config,
                                        result_topics, api_wait):
    """

    :param volttron_instance:
    :param query_agent:
    :param config:
    :param result_topics:
    :return:
    """
    agent_uuid = None
    query_agent.poll_callback.reset_mock()
    try:
        agent_uuid = volttron_instance.install_agent(
            vip_identity="poll.weather",
            agent_dir=ambient_agent_path,
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
            "poll.weather", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


