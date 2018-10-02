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
    'polling_locations': [],
    'poll_interval': None
}

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

    agent_uuid = volttron_instance.install_agent(
        vip_identity=identity,
        agent_dir=source,
        start=False,
        config_file=request.param)
    volttron_instance.start_agent(agent_uuid)

    def stop_agent():
        print("stopping weather service")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)

    request.addfinalizer(stop_agent)
    return request.param

@pytest.mark.dev
def test_success_current(weather, query_agent):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    locations = [{"station": "KLAX"}, {"wfo": 'PDT', "x": 120, "y": 130}]

    current_data = query_agent.vip.rpc.call(identity, 'get_current_weather', locations).get(timeout=10)
    # TODO deal with current data parsing
    for record in current_data:
        if len(record) == 3:
            assert isinstance(record[0], str)
            assert isinstance(record[1], datetime.datetime)
            assert isinstance(record[2], dict)
        else:
            _log.debug("response sanity checking: ")
            _log.debug(current_data)
            assert len(record) == 0

@pytest.mark.dev
def test_success_forecast(weather, query_agent):
    """
    Tests the basic functionality of a weather agent under optimal conditions.
    :param weather: instance of weather service to be tested
    :param query_agent: agent to leverage to use RPC calls
    """
    locations = [{"wfo": 'PDT', "x": 120, "y": 130}]

    forecast_data = query_agent.vip.rpc.call(identity, 'get_hourly_forecast', locations).get(timeout=10)

    for record in forecast_data:
        if len(record) == 4:
            assert isinstance(record[0], str)
            assert isinstance(record[1], datetime.datetime)
            assert isinstance(record[2], datetime.datetime)
            assert isinstance(record[3], dict)
        else:
            assert len(record) == 0