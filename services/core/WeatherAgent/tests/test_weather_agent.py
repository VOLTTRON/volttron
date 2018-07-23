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

from __future__ import print_function

from volttron.platform import get_services_core, get_examples

"""
Pytest test cases for testing weather agent both using pubsub request and 
regular polling. 
"""

from datetime import datetime, timedelta

import gevent
import pytest
from dateutil.tz import tzutc
from mock import MagicMock
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent
from volttrontesting.fixtures.volttron_platform_fixtures import *
from dateutil import parser

FAILURE = 'FAILURE'
SUCCESS = 'SUCCESS'
PLATFORM_ACTUATOR = 'platform.actuator'
TEST_AGENT = 'test-agent'
actuator_uuid = None
REQUEST_CANCEL_SCHEDULE = 'request_cancel_schedule'
REQUEST_NEW_SCHEDULE = 'request_new_schedule'
publish_agent_v2 = None
API_KEY=os.environ.get('WU_KEY')

pytestmark = pytest.mark.skipif(not API_KEY, reason="No API key found. "
                                                    "Weather Undergroup API "
                                                    "key need to be set in "
                                                    "the environment variable "
                                                    "WU_KEY")

@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    print("**In setup of publish_agent volttron is_running {}".format(
        volttron_instance.is_running))

    fake_publish_agent = volttron_instance.build_agent()
    # Mock callback methods attach actuate method to fake_publish_agent as
    # it needs to be a class method for the call back to work
    # fake_publish_agent.callback =
    #                types.MethodType(callback, fake_publish_agent)
    fake_publish_agent.process_poll_result = \
        MagicMock(name="process_poll_result")
    fake_publish_agent.process_response = MagicMock(name="process_response")
    fake_publish_agent.process_poll_result = MagicMock(
        name="process_poll_result")
    fake_publish_agent.process_error = MagicMock(name="process_error")

    fake_publish_agent.process_poll_result.reset_mock()
    fake_publish_agent.process_response.reset_mock()
    fake_publish_agent.process_error.reset_mock()

    # subscribe to polled weather data
    fake_publish_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=topics.WEATHER2_POLL,
        callback=fake_publish_agent.process_poll_result).get()

    # subscribe to weather response topic
    fake_publish_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=topics.WEATHER2_RESPONSE,
        callback=fake_publish_agent.process_response).get()

    # subscribe to weather error topic
    fake_publish_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=topics.WEATHER2_ERROR,
        callback=fake_publish_agent.process_error).get()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(fake_publish_agent, Agent):
            fake_publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return fake_publish_agent

@pytest.fixture(scope="module")
def weather_agent(request, volttron_instance):
    global API_KEY

    config = {
        "operation_mode": 1,
        "wu_api_key": API_KEY
    }
    weather_uuid = volttron_instance.install_agent(
        vip_identity='weather_agent',
        agent_dir=get_services_core("WeatherAgent"),
        config_file=config,
        start=False)

    volttron_instance.start_agent(weather_uuid)

    def stop_agent():
        if volttron_instance.is_running():
            volttron_instance.stop_agent(weather_uuid)
        volttron_instance.remove_agent(weather_uuid)

    request.addfinalizer(stop_agent)

def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)



def assert_weather_response(args):
    response_header = args[4]
    assert 'Date' in response_header
    assert len(args[5]) == 1
    response_msg = args[5][0]
    assert 'feelslike_c' in response_msg
    assert isinstance(float(response_msg['feelslike_c']), float)


@pytest.mark.weather
@pytest.mark.parametrize(("locations", "result_topics"), [
    # single zip code location
    ([{"zip": "99353"}],
     ['{}/current/ZIP/99353/all'.format(topics.WEATHER2_POLL)]),

    # Multiple zip code locations
    ([{"zip": "99353"}, {"zip": "99354"}],
     ['{}/current/ZIP/99353/all'.format(topics.WEATHER2_POLL),
      '{}/current/ZIP/99354/all'.format(topics.WEATHER2_POLL)]),

    # Single city and state
    ([{"city": "Richland", "region": "WA"}],
     ['{}/current/WA/Richland/all'.format(topics.WEATHER2_POLL)]),

    # Multiple cities and states
    ([{"city": "Richland", "region": "Washington"},
      {"city": "Kennewick", "region": "Washington"}],
     ['{}/current/Washington/Richland/all'.format(topics.WEATHER2_POLL),
      '{}/current/Washington/Kennewick/all'.format(topics.WEATHER2_POLL)])
])
def test_poll_valid(volttron_instance, publish_agent, locations, result_topics):
    global publish_agent_v2, API_KEY
    uuid = None
    try:
        config = {
            "operation_mode": 2,
            "wu_api_key": API_KEY,
            "locations": locations,
            "poll_time": 20
        }
        uuid = volttron_instance.install_agent(
            vip_identity='weather_agent',
            agent_dir=get_services_core("WeatherAgent"),
            config_file=config,
            start=False)

        # reset mock to ignore any previous callback
        publish_agent.process_poll_result.reset_mock()
        publish_agent.process_error.reset_mock()
        volttron_instance.start_agent(uuid)
        gevent.sleep(10)
        assert publish_agent.process_poll_result.call_count == len(locations)
        assert publish_agent.process_error.call_count == 0
        call_args_list = publish_agent.process_poll_result.call_args_list

        i = 0
        for args in call_args_list:
            assert args[0][3] == result_topics[i]
            assert_weather_response(args[0])
            i += 1
    finally:
        if uuid:
            volttron_instance.remove_agent(uuid)


@pytest.mark.weather
@pytest.mark.parametrize(
    ("locations","result_topic", "result_error"),
    [
        ([{"zip": "6000652"}],
         '{}/current/ZIP/6000652/all'.format(topics.WEATHER2_ERROR),
         'querynotfound:No cities match your search query'),

        ([{"city": "Richland2", "region": "Washington"}],
         '{}/current/Washington/Richland2/all'.format(topics.WEATHER2_ERROR),
         'querynotfound:No cities match your search query'),

    ])
def test_poll_invalid(volttron_instance, publish_agent, locations,
                      result_topic, result_error):
    global publish_agent_v2, API_KEY
    uuid = None
    try:
        config = {
            "operation_mode": 2,
            "wu_api_key": API_KEY,
            "locations": locations,
            "poll_time": 20
        }
        uuid = volttron_instance.install_agent(
            vip_identity='weather_agent',
            agent_dir=get_services_core("WeatherAgent"),
            config_file=config,
            start=False)

        # reset mock to ignore any previous callback
        publish_agent.process_poll_result.reset_mock()
        publish_agent.process_error.reset_mock()
        volttron_instance.start_agent(uuid)
        gevent.sleep(10)
        assert publish_agent.process_error.call_count == len(locations)
        assert publish_agent.process_poll_result.call_count == 0
        call_args_list = publish_agent.process_error.call_args_list
        i = 0
        for args in call_args_list:
            assert args[0][3] == result_topic
            assert isinstance(args[0][5], dict)
            assert args[0][5]['type'] == "WeatherUndergroundError"
            assert args[0][5]['description'] == result_error
            i += 1

    finally:
        if uuid:
            volttron_instance.remove_agent(uuid)


@pytest.mark.parametrize(("request_topic", "response_topic"), [
    # zip
    ("{}/current/ZIP/99353/all".format(topics.WEATHER2_REQUEST),
     "{}/current/ZIP/99353/all".format(topics.WEATHER2_RESPONSE)),
    #region, city
    ("{}/current/WA/Richland/all".format(topics.WEATHER2_REQUEST),
     "{}/current/WA/Richland/all".format(topics.WEATHER2_RESPONSE))
    # TODO add point instead of all once code is added for it. for now code only
    # returns all

])
@pytest.mark.weather
def test_request_current(weather_agent, publish_agent, request_topic,
                         response_topic):
    # reset mock to ignore any previous callback
    publish_agent.process_response.reset_mock()
    publish_agent.process_error.reset_mock()

    # publish request
    publish(publish_agent,
            request_topic,
            {},
            None)
    gevent.sleep(2)

    # assert result
    assert publish_agent.process_response.call_count == 1
    assert publish_agent.process_error.call_count == 0
    assert publish_agent.process_response.call_args[0][3] == response_topic
    response_header = publish_agent.process_response.call_args[0][4]
    assert 'Date' in response_header
    assert len(publish_agent.process_response.call_args[0][5]) == 1
    response_msg = publish_agent.process_response.call_args[0][5][0]
    assert 'solarradiation' in response_msg
    assert response_msg['temp_c']
    assert response_msg['temp_f']


@pytest.mark.weather
@pytest.mark.parametrize(("request_topic", "response_topic"), [
    # zip - end date default to start +1 day
    ("{}/history/ZIP/99353/all/2018-06-26".format(topics.WEATHER2_REQUEST),
     "{}/history/ZIP/99353/all/2018-06-26".format(topics.WEATHER2_RESPONSE)),

    # region, city - end date defaults to start +1 day
    ("{}/history/WA/Richland/all/2018-06-26".format(
        topics.WEATHER2_REQUEST),
     "{}/history/WA/Richland/all/2018-06-26".format(
         topics.WEATHER2_RESPONSE)),

    # zip - explicit start and end date
    ("{}/history/ZIP/99353/all/2018-06-24/2018-06-26".format(
        topics.WEATHER2_REQUEST),
     "{}/history/ZIP/99353/all/2018-06-24/2018-06-26".format(
         topics.WEATHER2_RESPONSE)),

    # TODO add point instead of all once code is added for it. for now code only
    # returns all

])
def test_request_history(weather_agent, publish_agent, request_topic,
                         response_topic):
    # reset mock to ignore any previous callback
    publish_agent.process_response.reset_mock()
    publish_agent.process_error.reset_mock()

    # publish request
    publish(publish_agent,
            request_topic,
            {},
            None)
    gevent.sleep(2)  # wait

    # assert
    assert publish_agent.process_response.call_count == 1
    assert publish_agent.process_error.call_count == 0
    assert publish_agent.process_response.call_args[0][3] == response_topic
    response_header = publish_agent.process_response.call_args[0][4]
    assert 'Date' in response_header
    history_result = publish_agent.process_response.call_args[0][5]
    assert len(history_result) > 1
    # result list
    parts = request_topic.split('/')
    expected_start_date = parser.parse(parts[6]).date()
    start_epoch = float(history_result[0]['observation_epoch'])
    end_epoch = float(history_result[-1]['observation_epoch'])
    if len(parts) == 8:
        expected_end_date = parser.parse(parts[7]).date()
    else:
        expected_end_date = expected_start_date + timedelta(days=1)

    assert expected_start_date == datetime.fromtimestamp(start_epoch).date()
    assert expected_end_date == datetime.fromtimestamp(end_epoch).date()


@pytest.mark.weather
@pytest.mark.parametrize(("request_topic", "response_topic"), [
    # zip - forecast 3
    ("{}/hourly/ZIP/99353/all".format(topics.WEATHER2_REQUEST),
     "{}/hourly/ZIP/99353/all".format(topics.WEATHER2_RESPONSE)),

    # region, city
    ("{}/hourly/WA/Richland/all".format(topics.WEATHER2_REQUEST),
     "{}/hourly/WA/Richland/all".format(
         topics.WEATHER2_RESPONSE)),

    #zip - forecast 10
    ("{}/hourly10days/ZIP/99353/all".format(topics.WEATHER2_REQUEST),
     "{}/hourly10days/ZIP/99353/all".format(topics.WEATHER2_RESPONSE)),

    # region, city
    ("{}/hourly10days/WA/Richland/all".format(topics.WEATHER2_REQUEST),
     "{}/hourly10days/WA/Richland/all".format(
         topics.WEATHER2_RESPONSE)),

    # TODO add point instead of all once code is added for it. for now code only
    # returns all

])
def test_request_forecast(weather_agent, publish_agent, request_topic,
                         response_topic):
    # reset mock to ignore any previous callback
    publish_agent.process_response.reset_mock()
    publish_agent.process_error.reset_mock()

    # publish request
    publish(publish_agent,
            request_topic,
            {},
            None)
    gevent.sleep(2)  # wait

    # assert
    assert publish_agent.process_response.call_count == 1
    assert publish_agent.process_error.call_count == 0
    assert publish_agent.process_response.call_args[0][3] == response_topic
    response_header = publish_agent.process_response.call_args[0][4]
    assert 'Date' in response_header
    result = publish_agent.process_response.call_args[0][5]
    parts = request_topic.split('/')
    days = 0
    if parts[2] == 'hourly':
        # wu doesn't seem to reliably provide certain number of days for hourly
        # forecast. so skip end date check
        days = 0
    elif parts[2] == 'hourly10days':
        days = 10
    else:
        pytest.fail("Invalid request_topic in test case parameter")
    expected_start = datetime.today().date()
    start_epoch = float(result[0]['observation_epoch'])
    assert expected_start == datetime.fromtimestamp(start_epoch).date()

    if days > 0:
        end_epoch = float(result[-1]['observation_epoch'])
        expected_end = expected_start + timedelta(days=days)
        assert expected_end == datetime.fromtimestamp(end_epoch).date()


@pytest.mark.weather
@pytest.mark.parametrize(
    ("request_topic", "result_topic", "err_type", "err_msg"),
    [
        ("{}/current/ZIP/99353".format(topics.WEATHER2_REQUEST),
         '{}/current/ZIP/99353'.format(topics.WEATHER2_ERROR),
         'ValueError',
         'Invalid request format. Request is missing required information'),

        ("{}/current/wash/Richland/all".format(topics.WEATHER2_REQUEST),
         '{}/current/wash/Richland/all'.format(topics.WEATHER2_ERROR),
         'WeatherUndergroundError',
         'Ambiguous location information'),

        ("{}/current/xyz/abc/all".format(topics.WEATHER2_REQUEST),
         '{}/current/xyz/abc/all'.format(topics.WEATHER2_ERROR),
         'WeatherUndergroundError',
         'querynotfound:No cities match your search query'),

        ("{}/history/Richland/Washington/all".format(
            topics.WEATHER2_REQUEST),
         '{}/history/Richland/Washington/all'.format(topics.WEATHER2_ERROR),
         'ValueError',
         'Missing start date. history requests should be of the format:'
         ' {}/history/<region>/<city>/all/start/end'.format(
             topics.WEATHER2_REQUEST)),

        ("{}/hourly/xyz/abc/all".format(topics.WEATHER2_REQUEST),
         '{}/hourly/xyz/abc/all'.format(topics.WEATHER2_ERROR),
         'WeatherUndergroundError',
         'querynotfound:No cities match your search query'),

        ("{}/hourly10days/xyz/abc/all".format(topics.WEATHER2_REQUEST),
         '{}/hourly10days/xyz/abc/all'.format(topics.WEATHER2_ERROR),
         'WeatherUndergroundError',
         'querynotfound:No cities match your search query'),

    ])
def test_invalid_request(weather_agent, publish_agent, request_topic,
                         result_topic, err_type, err_msg):

    # reset mock to ignore any previous callback
    publish_agent.process_response.reset_mock()
    publish_agent.process_error.reset_mock()

    # publish request
    publish(publish_agent,
            request_topic,
            {},
            None)
    gevent.sleep(2)  # wait

    # assert
    assert publish_agent.process_response.call_count == 0
    assert publish_agent.process_error.call_count == 1
    assert publish_agent.process_error.call_args[0][3] == result_topic
    response_msg = publish_agent.process_error.call_args[0][5]
    assert response_msg['type'] == err_type
    assert response_msg['description'].startswith(err_msg)
