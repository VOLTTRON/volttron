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

import datetime
import json
import logging
import mock
import os
import pytest
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttrontesting.utils.utils import AgentMock
from services.core.DriverHTTPCache.driver_http_cache.agent import DriverHTTPCache

__version__ = "0.1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

DriverHTTPCache.__bases__ = (AgentMock.imitate(Agent, Agent()),)
agent = DriverHTTPCache()

HEADERS = json.dumps(
    {
        "Accept": "application/json",
        "Accept-Language": "en-US"
    }
)
TEST_URL1 = "http://localhost:443/"
TEST_URL2 = "http://127.0.0.1:80/"


def get_mock_response(obj, request_type, url, headers, params=None, body=None):
    """

    :param obj:
    :param request_type:
    :param url:
    :param headers:
    :param params:
    :param body:
    :return:
    """
    return {
        "content": {
            "request_type": request_type.upper(),
            "test": "test"
        }
    }


@mock.patch.object(DriverHTTPCache, 'grequests_wrapper', get_mock_response)
@pytest.mark.driver
def test_get_json_request():
    """
    """
    # set up group and driver ids for test
    group_id = "testid"
    driver_type = "testdriver"
    # filepath to validate later
    data_path = "{}_{}.json".format(driver_type, group_id)

    # Pre-Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)

    # Check typical get request
    response = agent._get_json_request(driver_type, group_id, "GET", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('test') == "test"

    # compare stored data
    assert os.path.isfile(data_path)
    with open(data_path, "r") as data_file:
        saved_data = json.load(data_file)
        test_data = saved_data.get(TEST_URL1)
        request_timestring = test_data.get("request_timestamp")
        get_request_timestamp = utils.parse_timestamp_string(request_timestring)
        assert get_request_timestamp < datetime.datetime.now()
        request_response = test_data.get("request_response")
        content = request_response.get('content')
        assert content.get('request_type') == "GET"
        assert content.get('test') == "test"

    # Check get request bad capitals - should still work
    response = agent._get_json_request(driver_type, group_id, "get", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('test') == "test"

    # Check POST with same rules as GET
    response = agent._get_json_request(driver_type, group_id, "POST", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "POST"
    assert content.get('test') == "test"

    assert os.path.isfile(data_path)
    with open(data_path, "r") as data_file:
        saved_data = json.load(data_file)
        test_data = saved_data.get(TEST_URL1)
        request_timestring = test_data.get("request_timestamp")
        post_request_timestamp = utils.parse_timestamp_string(request_timestring)
        assert get_request_timestamp < post_request_timestamp < datetime.datetime.now()
        request_response = test_data.get("request_response")
        content = request_response.get('content')
        assert content.get('request_type') == "POST"
        assert content.get('test') == "test"

    response = agent._get_json_request(driver_type, group_id, "post", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "POST"
    assert content.get('test') == "test"

    # Currently only GET and POST supported, others should throw value error below
    with pytest.raises(ValueError, match=r"Unsupported request type for Driver HTTP Cache Agent: .+"):
        agent._get_json_request("test", "delete", "test", TEST_URL1, HEADERS)

    # Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)


@pytest.mark.driver
def test_get_json_cache():
    """

    :return:
    """
    group_id = "testid"
    driver_type = "testdriver"
    data_path = "{}_{}.json".format(driver_type, group_id)

    # Pre-Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)

    update_frequency = 60

    with pytest.raises(RuntimeError, match=r"Data file for driver.*"):
        agent._get_json_cache(driver_type, group_id, TEST_URL1, update_frequency)

    now = datetime.datetime.now()

    contents = {
        TEST_URL1: {
            "request_response": {
                "content": {
                    "request_type": "POST",
                    "test": "test1"
                }
            }
        },
        TEST_URL2: {
            "request_response": {
                "content": {
                    "request_type": "POST",
                    "test": "test2"
                }
            }
        }
    }

    store_cache = contents.copy()
    curr_timestamp = utils.format_timestamp(now)
    store_cache[TEST_URL1]["request_timestamp"] = curr_timestamp
    store_cache[TEST_URL2]["request_timestamp"] = curr_timestamp

    with open(data_path, "w") as data_file:
        json.dump(store_cache, data_file)

    read_cache = agent._get_json_cache(driver_type, group_id, TEST_URL1, update_frequency)

    utils.parse_timestamp_string(read_cache.get("request_timestamp"))
    assert read_cache == store_cache.get(TEST_URL1)

    store_cache = contents.copy()
    prev_timestamp = utils.format_timestamp(now - datetime.timedelta(seconds=120))
    store_cache[TEST_URL1]["request_timestamp"] = prev_timestamp
    store_cache[TEST_URL2]["request_timestamp"] = prev_timestamp

    with open(data_path, "w") as data_file:
        json.dump(store_cache, data_file)

    with pytest.raises(RuntimeError, match=r"Request timestamp out of date, send new request"):
        agent._get_json_cache(driver_type, group_id, TEST_URL1, update_frequency)

    # Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)


@mock.patch.object(DriverHTTPCache, 'grequests_wrapper', get_mock_response)
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.driver
def test_get_driver_data(method):
    """

    :return:
    """
    content = get_mock_response(None, method, None, None)
    group_id = "testid"
    group2_id = "testid2"
    driver_type = "testdriver"
    driver2_type = "test2driver"
    data_path = "{}_{}.json".format(driver_type, group_id)

    # Pre-Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)
    cleanup_path = "{}_{}.json".format(driver2_type, group_id)
    if os.path.isfile(cleanup_path):
        os.remove(cleanup_path)
    cleanup_path = "{}_{}.json".format(driver2_type, group2_id)
    if os.path.isfile(cleanup_path):
        os.remove(cleanup_path)

    update_frequency = 120

    driver_data_start = None
    if method == "GET":
        driver_data_start = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS,
                                                  update_frequency=update_frequency)
    elif method == "POST":
        driver_data_start = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS,
                                                   update_frequency=update_frequency)

    # First set of data should contain entirely new response
    utils.parse_timestamp_string(driver_data_start.get("request_timestamp"))
    assert driver_data_start.get("request_response") == content

    # Second set of data should be an exact copy, since a new response should not have been sent
    driver_data_repeat = None
    if method == "GET":
        driver_data_repeat = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS,
                                                   update_frequency=update_frequency)
    elif method == "POST":
        driver_data_repeat = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS,
                                                    update_frequency=update_frequency)

    assert driver_data_repeat == driver_data_start

    # Now lets try "jumping ahead in time a bit - this should result in a new request
    now = datetime.datetime.now()
    store_cache = content.copy()
    store_cache["request_timestamp"] = utils.format_timestamp(now - datetime.timedelta(seconds=120))

    with open(data_path, "w") as data_file:
        json.dump(store_cache, data_file)

    driver_data_new = None
    if method == "GET":
        driver_data_new = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS,
                                                update_frequency=update_frequency)
    elif method == "POST":
        driver_data_new = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS,
                                                 update_frequency=update_frequency)

    assert utils.parse_timestamp_string(driver_data_new.get("request_timestamp")) > now
    assert driver_data_new.get("request_response") == content

    driver_data_refresh = None
    if method == "GET":
        driver_data_refresh = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS, refresh=True,
                                                    update_frequency=update_frequency)
    if method == "POST":
        driver_data_refresh = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS, refresh=True,
                                                     update_frequency=update_frequency)

    assert utils.parse_timestamp_string(driver_data_refresh.get("request_timestamp")) > utils.parse_timestamp_string(
        driver_data_new.get("request_timestamp"))

    # If the data file is removed, we should get a new response
    os.remove(data_path)

    driver_data_rm = None
    if method == "GET":
        driver_data_rm = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS,
                                               update_frequency=update_frequency)
    if method == "POST":
        driver_data_rm = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS,
                                                update_frequency=update_frequency)

    assert utils.parse_timestamp_string(driver_data_rm.get("request_timestamp")) > now
    assert driver_data_rm.get("request_response") == content

    # And if we repeat once more, it should be the same as the previous
    driver_data_rerepeat = None
    if method == "GET":
        driver_data_rerepeat = agent.driver_data_get(driver_type, group_id, TEST_URL1, HEADERS,
                                                     update_frequency=update_frequency)
    if method == "POST":
        driver_data_rerepeat = agent.driver_data_post(driver_type, group_id, TEST_URL1, HEADERS,
                                                      update_frequency=update_frequency)

    assert driver_data_rerepeat == driver_data_rm

    # Other driver types shouldn't get confused (in the test we'd expect the timestamps to change)
    driver2_data = None
    if method == "GET":
        driver2_data = agent.driver_data_get(driver2_type, group_id, TEST_URL1, HEADERS,
                                             update_frequency=update_frequency)
    if method == "POST":
        driver2_data = agent.driver_data_post(driver2_type, group_id, TEST_URL1, HEADERS,
                                              update_frequency=update_frequency)

    assert utils.parse_timestamp_string(driver2_data.get("request_timestamp")) > utils.parse_timestamp_string(
        driver_data_rerepeat.get("request_timestamp"))

    # Other group ids shouldn't get confused (in the test we'd expect the timestamps to change)
    group2_data = None
    if method == "GET":
        group2_data = agent.driver_data_get(driver2_type, group2_id, TEST_URL1, HEADERS,
                                            update_frequency=update_frequency)
    if method == "POST":
        group2_data = agent.driver_data_post(driver2_type, group2_id, TEST_URL1, HEADERS,
                                             update_frequency=update_frequency)

    assert utils.parse_timestamp_string(group2_data.get("request_timestamp")) > utils.parse_timestamp_string(
        driver2_data.get("request_timestamp"))

    # Clean up data file
    if os.path.isfile(data_path):
        os.remove(data_path)
    cleanup_path = "{}_{}.json".format(driver2_type, group_id)
    if os.path.isfile(cleanup_path):
        os.remove(cleanup_path)
    cleanup_path = "{}_{}.json".format(driver2_type, group2_id)
    if os.path.isfile(cleanup_path):
        os.remove(cleanup_path)
