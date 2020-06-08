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

import copy
import datetime
import json
import logging
import mock
import os
import pytest
from volttron.platform.agent import utils
from integrations.DriverHTTPCache.driver_cache import DriverHTTPCache

__version__ = "0.1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

DRIVER_TYPE = "test_driver"
DRIVER_CACHE = DriverHTTPCache("test_driver")

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
            "request_url": url
        }
    }


@pytest.fixture()
def cleanup_cache(request):
    existing_keys = list(DRIVER_CACHE.cache.keys())
    for key in existing_keys:
        DRIVER_CACHE.cache.pop(key)


@mock.patch.object(DriverHTTPCache, 'grequests_wrapper', get_mock_response)
@pytest.mark.driver
def test_get_json_request(cleanup_cache):
    """
    """
    # set up group and driver ids for test
    group_id = "testid"

    # Check typical get request
    response = DRIVER_CACHE._get_json_request(group_id, "GET", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('request_url') == TEST_URL1

    response = DRIVER_CACHE._get_json_request(group_id, "GET", TEST_URL2, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('request_url') == TEST_URL2

    # compare stored data
    saved_data = DRIVER_CACHE.cache.get(DRIVER_TYPE).get(group_id)
    test1_data = saved_data.get(TEST_URL1)
    request_timestring = test1_data.get("request_timestamp")
    get_request1_timestamp = utils.parse_timestamp_string(request_timestring)
    assert get_request1_timestamp < datetime.datetime.now()
    request_response = test1_data.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('request_url') == TEST_URL1

    test2_data = saved_data.get(TEST_URL2)
    request_timestring = test2_data.get("request_timestamp")
    get_request2_timestamp = utils.parse_timestamp_string(request_timestring)
    assert get_request2_timestamp < datetime.datetime.now()
    request_response = test2_data.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('request_url') == TEST_URL2

    # Check get request bad capitals - should still work
    response = DRIVER_CACHE._get_json_request(group_id, "get", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"
    assert content.get('request_url') == TEST_URL1

    # Check POST with same rules as GET
    response = DRIVER_CACHE._get_json_request(group_id, "POST", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "POST"
    assert content.get('request_url') == TEST_URL1

    saved_data = DRIVER_CACHE.cache.get(DRIVER_TYPE).get(group_id)
    test1_data = saved_data.get(TEST_URL1)
    request_timestring = test1_data.get("request_timestamp")
    post_request1_timestamp = utils.parse_timestamp_string(request_timestring)
    assert get_request1_timestamp < post_request1_timestamp < datetime.datetime.now()
    request_response = test1_data.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "POST"
    assert content.get('request_url') == TEST_URL1

    # The other request should not have been affected
    test2_data = saved_data.get(TEST_URL2)
    request_timestring = test2_data.get("request_timestamp")
    request2_timestamp = utils.parse_timestamp_string(request_timestring)
    assert get_request2_timestamp == request2_timestamp
    request_response = test2_data.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "GET"

    response = DRIVER_CACHE._get_json_request(group_id, "post", TEST_URL1, HEADERS)
    request_response = response.get("request_response")
    content = request_response.get('content')
    assert content.get('request_type') == "POST"
    assert content.get('request_url') == TEST_URL1

    # Currently only GET and POST supported, others should throw value error below
    with pytest.raises(ValueError, match=r"Unsupported request type for Driver HTTP Cache Agent: .+"):
        DRIVER_CACHE._get_json_request("test", "delete", "test", TEST_URL1, HEADERS)


@pytest.mark.driver
def test_get_json_cache(cleanup_cache):
    """

    :return:
    """
    group_id = "testid"

    update_frequency = 60

    with pytest.raises(KeyError, match=r"No data found for test_driver driver in driver cache"):
        DRIVER_CACHE._get_json_cache(group_id, TEST_URL1, update_frequency)

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

    store_cache = copy.deepcopy(contents)
    curr_timestamp = utils.format_timestamp(now)
    store_cache[TEST_URL1]["request_timestamp"] = curr_timestamp
    store_cache[TEST_URL2]["request_timestamp"] = curr_timestamp
    DRIVER_CACHE.cache[DRIVER_TYPE] = {group_id: store_cache}

    read_cache = DRIVER_CACHE._get_json_cache(group_id, TEST_URL1, update_frequency)

    utils.parse_timestamp_string(read_cache.get("request_timestamp"))
    assert read_cache == store_cache.get(TEST_URL1)

    store_cache = copy.deepcopy(contents)
    prev_timestamp = utils.format_timestamp(now - datetime.timedelta(seconds=120))
    store_cache[TEST_URL1]["request_timestamp"] = prev_timestamp
    store_cache[TEST_URL2]["request_timestamp"] = prev_timestamp
    DRIVER_CACHE.cache[DRIVER_TYPE][group_id] = store_cache

    with pytest.raises(RuntimeError, match=r"Request timestamp out of date, send new request"):
        DRIVER_CACHE._get_json_cache(group_id, TEST_URL1, update_frequency)


@mock.patch.object(DriverHTTPCache, 'grequests_wrapper', get_mock_response)
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.driver
def test_get_driver_data(cleanup_cache, method):
    """

    :return:
    """
    content = get_mock_response(None, method, None, None)
    group_id = "testid"
    group2_id = "testid2"
    driver2_type = "test2driver"
    update_frequency = 120

    # Check that we can ask for data for 2 different endpoints and fetch both independently
    driver_data1_start = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)
    driver_data2_start = get_driver_data_method(method, group_id, TEST_URL2, update_frequency)

    # First set of data should contain entirely new response
    # TODO what's with this timestamp string
    # utils.parse_timestamp_string(driver_data1_start.get("request_timestamp"))
    request1_content = copy.deepcopy(content)
    request2_content = copy.deepcopy(content)
    request1_content["content"]["request_url"] = TEST_URL1
    assert driver_data1_start.get("request_response") == request1_content

    request2_content["content"]["request_url"] = TEST_URL2
    assert driver_data2_start.get("request_response") == request2_content

    # Second set of data should be an exact copy, since a new response should not have been sent
    driver_data1_repeat = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)

    assert driver_data1_repeat == driver_data1_start

    # Now lets try "jumping ahead in time a bit - this should result in a new request
    now = datetime.datetime.now()

    DRIVER_CACHE.cache[DRIVER_TYPE][group_id][TEST_URL1]["request_timestamp"] = \
        utils.format_timestamp(now - datetime.timedelta(seconds=120))

    driver_data1_new = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)
    driver_data2_new = get_driver_data_method(method, group_id, TEST_URL2, update_frequency)

    # the timestamp of the the newly requested data should be newer
    assert utils.parse_timestamp_string(driver_data1_new.get("request_timestamp")) > now
    assert driver_data1_new.get("request_response") == request1_content

    # The timestamp of our other request should not have updated
    assert utils.parse_timestamp_string(driver_data2_new.get("request_timestamp")) == \
           utils.parse_timestamp_string(driver_data2_start.get("request_timestamp"))
    assert driver_data2_new.get("request_response") == request2_content

    # See if timestamps using the refresh keyword are newer than the previous timestamp1
    driver_data_refresh = get_driver_data_method(method, group_id, TEST_URL1, update_frequency, refresh=True)

    assert utils.parse_timestamp_string(driver_data_refresh.get("request_timestamp")) > utils.parse_timestamp_string(
        driver_data1_new.get("request_timestamp"))

    # If the data removed, we should get a new response
    existing_keys = list(DRIVER_CACHE.cache.keys())
    for key in existing_keys:
        DRIVER_CACHE.cache.pop(key)

    driver_data_rm = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)

    assert utils.parse_timestamp_string(driver_data_rm.get("request_timestamp")) > now
    assert driver_data_rm.get("request_response") == request1_content

    # And if we repeat once more, it should be the same as the previous
    driver_data_rerepeat = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)

    assert driver_data_rerepeat == driver_data_rm

    # Other driver types shouldn't get confused (in the test we'd expect the timestamps to change)
    driver2_store = copy.deepcopy(driver_data1_new)
    driver2_timestamp = utils.format_timestamp(datetime.datetime.now())
    driver2_store["request_timestamp"] = driver2_timestamp
    driver2_data = {
        driver2_type: {
            group_id: {
                TEST_URL1: driver2_store
            }
        }
    }
    DRIVER_CACHE.cache.update(driver2_data)

    driver_data_compare = get_driver_data_method(method, group_id, TEST_URL1, update_frequency)

    assert utils.parse_timestamp_string(driver2_timestamp) > utils.parse_timestamp_string(
        driver_data_compare.get("request_timestamp"))

    # Other group ids shouldn't get confused (in the test we'd expect the timestamps to change)
    group2_data = get_driver_data_method(method, group2_id, TEST_URL1, update_frequency)

    assert utils.parse_timestamp_string(group2_data.get("request_timestamp")) > utils.parse_timestamp_string(
        driver_data_compare.get("request_timestamp"))


def get_driver_data_method(method, group_id, test_url, update_frequency, refresh=False):
    if method == "GET":
        return DRIVER_CACHE.driver_data_get(group_id, test_url, HEADERS, update_frequency=update_frequency,
                                            refresh=refresh)
    if method == "POST":
        return DRIVER_CACHE.driver_data_post(group_id, test_url, HEADERS, update_frequency=update_frequency,
                                             refresh=refresh)
