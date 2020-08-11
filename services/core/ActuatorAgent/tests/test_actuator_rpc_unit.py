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

"""
Unit test cases for testing actuator agent using rpc calls.
"""
import logging
from datetime import datetime, timedelta

import pytest

from services.core.ActuatorAgent.actuator import agent
from services.core.ActuatorAgent.actuator.agent import ActuatorAgent, LockError
from services.core.ActuatorAgent.actuator.scheduler import RequestResult, DeviceState
from services.core.ActuatorAgent.tests.actuator_fixtures import MockedAsyncResult, \
    get_actuator_agent
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent


PRIORITY_LOW = "LOW"
SUCCESS = "SUCCESS"
FAILURE = "FAILURE"
REQUESTER_ID = "foo"
TASK_ID = "task-id"
TIME_SLOT_REQUESTS = [
    ["fakedriver0", str(datetime.now()), str(datetime.now() + timedelta(seconds=1))]
]

agent._log = logging.getLogger("test_logger")
ActuatorAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.mark.actuator_unit
@pytest.mark.parametrize("topic, point", [("path/topic", None), ("another/path/to/topic", 42)])
def test_get_point_should_succeed(topic, point):
    with get_actuator_agent(vip_rpc_call_res=MockedAsyncResult(10.0)) as actuator_agent:
        result = actuator_agent.get_point(topic, point=point)

        actuator_agent.vip.rpc.call.assert_called_once()
        assert result is not None


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "point, device_state",
    [
        (
            42,
            {"foo/bar": DeviceState("requester-id-1", "task-id-1", "anytime")},
        ),
        (
            None,
            {"foo": DeviceState("requester-id-1", "task-id-1", "anytime")}),
    ],
)
def test_set_point_should_succeed(point, device_state):
    requester_id = "requester-id-1"
    topic = "foo/bar"
    value = "some value"

    with get_actuator_agent(vip_message_peer=requester_id, device_state=device_state) as \
            actuator_agent:
        result = actuator_agent.set_point(requester_id, topic, value, point=point)

        assert result is not None


@pytest.mark.actuator_unit
@pytest.mark.parametrize("rpc_peer", [None, 42, []])
def test_set_point_should_raise_type_error(rpc_peer):
    with pytest.raises(TypeError, match="Agent id must be a nonempty string"):
        requester_id = "requester-id-1"
        topic = "foo/bar"
        value = "some value"
        point = None

        with get_actuator_agent(vip_message_peer=rpc_peer) as actuator_agent:
            actuator_agent.set_point(requester_id, topic, value, point=point)


@pytest.mark.actuator_unit
def test_set_point_should_raise_lock_error_on_non_matching_device():
    with pytest.raises(LockError):
        requester_id = "requester-id-1"
        topic = "foo/bar"
        value = "some value"

        with get_actuator_agent(vip_message_peer="some rpc_peer") as actuator_agent:
            actuator_agent.set_point(requester_id, topic, value)


@pytest.mark.actuator_unit
def test_scrape_all_should_succeed():
    with get_actuator_agent(vip_rpc_call_res=MockedAsyncResult({})) as actuator_agent:
        topic = "whan/that/aprille"

        result = actuator_agent.scrape_all(topic)

        assert isinstance(result, dict)



@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "topics",
    [
        ["foo/bar"],
        ["foo/bar", "sna/foo"],
        [["dev1", "point1"]],
        [["dev1", "point1"], ["dev2", "point2"]],
    ],
)
def test_get_multiple_points_should_succeed(topics):
    mocked_rpc_call_res = MockedAsyncResult(({"result": "value"}, {}))
    with get_actuator_agent(vip_rpc_call_res=mocked_rpc_call_res) as actuator_agent:
        results, errors = actuator_agent.get_multiple_points(topics)

        assert isinstance(results, dict)
        assert isinstance(errors, dict)
        assert len(errors) == 0


@pytest.mark.actuator_unit
@pytest.mark.parametrize("invalid_topics", [[(123,)], [(None)], [[123]], [[None]]])
def test_get_multiple_points_should_return_errors(invalid_topics):
    with get_actuator_agent() as actuator_agent:

        results, errors = actuator_agent.get_multiple_points(invalid_topics)

        assert isinstance(results, dict)
        assert isinstance(errors, dict)
        assert len(errors) == 1


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "topic_values, device_state",
    [
        ([], {}),
        (
            [("foo/bar", "roma_value")],
            {"foo": DeviceState("requester-id-1", "task-id-1", "anytime")},
        ),
        (
            [("foo/bar", "roma_value"), ("sna/fu", "amor_value")],
            {
                "foo": DeviceState("requester-id-1", "task-id-1", "anytime"),
                "sna": DeviceState("requester-id-1", "task-id-1", "anytime"),
            },
        ),
    ],
)
@pytest.mark.actuator_unit
def test_set_multiple_points_should_succeed(topic_values, device_state):
    requester_id = "requester-id-1"
    mocked_rpc_call_res = MockedAsyncResult(({}))
    with get_actuator_agent(vip_message_peer=requester_id, device_state=device_state,
                            vip_rpc_call_res=mocked_rpc_call_res) as actuator_agent:
        result = actuator_agent.set_multiple_points("request-id-1", topic_values)

        assert result == {}


@pytest.mark.actuator_unit
@pytest.mark.parametrize("invalid_topic_values", [[(None,)], [(1234,)]])
def test_set_multiple_points_should_raise_value_error(invalid_topic_values):
    with pytest.raises(ValueError):
        requester_id = "requester-id-1"

        with get_actuator_agent(vip_message_peer=requester_id) as actuator_agent:
            actuator_agent.set_multiple_points("request-id-1", invalid_topic_values)


@pytest.mark.actuator_unit
def test_set_multiple_points_should_raise_lock_error_on_empty_devices():
    with pytest.raises(LockError):
        requester_id = "requester-id-1"
        topic_values = [("foo/bar", "roma_value")]

        with get_actuator_agent(vip_message_peer=requester_id) as actuator_agent:
            actuator_agent.set_multiple_points("request-id-1", topic_values)


@pytest.mark.actuator_unit
def test_set_multiple_points_should_raise_lock_error_on_non_matching_requester():
    with pytest.raises(LockError):
        requester_id = "wrong-requester"
        topic_values = [("foo/bar", "roma_value")]
        device_state = {
            "foo": DeviceState("requester-id-1", "task-id-1", "anytime")
        }

        with get_actuator_agent(vip_message_peer=requester_id, device_state=device_state) \
                as actuator_agent:
            actuator_agent.set_multiple_points("request-id-1", topic_values)


@pytest.mark.actuator_unit
@pytest.mark.parametrize("point", [None, "foobarpoint"])
def test_revert_point_should_raise_lock_error_on_empty_devices(point):
    with pytest.raises(LockError):
        requester_id = "request-id-1"
        topic = "foo/bar"

        with get_actuator_agent(vip_message_peer="requester-id-1") as actuator_agent:
            actuator_agent.revert_point(requester_id, topic, point=point)


@pytest.mark.actuator_unit
@pytest.mark.parametrize("point", [None, "foobarpoint"])
def test_revert_point_should_raise_lock_error_on_non_matching_requester(point):
    with pytest.raises(LockError):
        device_state = {
            "foo": DeviceState("requester-id-1", "task-id-1", "anytime")
        }
        requester_id = "request-id-1"
        topic = "foo/bar"

        with get_actuator_agent(vip_message_peer="wrong-requester", device_state=device_state) \
                as actuator_agent:
            actuator_agent.revert_point(requester_id, topic, point=point)


@pytest.mark.actuator_unit
def test_revert_device_should_raise_lock_error_on_empty_devices():
    with pytest.raises(LockError):
        requester_id = "request-id-1"
        topic = "foo/bar"

        with get_actuator_agent(vip_message_peer="requester-id-1") as actuator_agent:
            actuator_agent.revert_device(requester_id, topic)


@pytest.mark.actuator_unit
def test_revert_device_should_raise_lock_error_on_non_matching_requester():
    with pytest.raises(LockError):
        device_state = {
            "foo/bar": DeviceState("requester-id-1", "task-id-1", "anytime")
        }
        requester_id = "request-id-1"
        topic = "foo/bar"

        with get_actuator_agent(vip_message_peer="wrong-requester", device_state=device_state) \
                as actuator_agent:
            actuator_agent.revert_device(requester_id, topic)


@pytest.mark.actuator_unit
def test_request_new_schedule_should_succeed():
    with get_actuator_agent() as actuator_agent:
        result = actuator_agent.request_new_schedule(REQUESTER_ID, TASK_ID,
                                                     PRIORITY_LOW, TIME_SLOT_REQUESTS)

        assert result["result"] == SUCCESS


@pytest.mark.actuator_unit
def test_request_new_schedule_should_succeed_when_stop_start_times_overlap():
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    end2 = str(datetime.now() + timedelta(seconds=2))
    time_slot_requests = [["fakedriver0", start, end], ["fakedriver0", end, end2]]

    with get_actuator_agent() as actuator_agent:
        result = actuator_agent.request_new_schedule(REQUESTER_ID, TASK_ID,
                                                     PRIORITY_LOW, time_slot_requests)

        assert result["result"] == SUCCESS


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "task_id, expected_info",
    [
        (1234, "MALFORMED_REQUEST: TypeError: taskid must be a nonempty string"),
        ("", "MALFORMED_REQUEST: TypeError: taskid must be a nonempty string"),
        (None, "MISSING_TASK_ID"),
        ("task-id-duplicate", "TASK_ID_ALREADY_EXISTS"),
    ],
)
def test_request_new_schedule_should_fail_on_invalid_taskid(task_id, expected_info):
    false_request_result = RequestResult(False, {}, expected_info)

    with get_actuator_agent(slot_requests_res=false_request_result) as actuator_agent:
        result = actuator_agent.request_new_schedule(REQUESTER_ID, task_id,
                                                     PRIORITY_LOW, TIME_SLOT_REQUESTS)

        assert result["result"] == FAILURE
        assert result["info"] == expected_info


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "invalid_priority, expected_info",
    [("LOW2", "INVALID_PRIORITY"), (None, "MISSING_PRIORITY")],
)
def test_request_new_schedule_should_fail_on_invalid_priority(invalid_priority, expected_info):
    false_request_result = RequestResult(False, {}, expected_info)

    with get_actuator_agent(slot_requests_res=false_request_result) as actuator_agent:
        result = actuator_agent.request_new_schedule(REQUESTER_ID, TASK_ID,
                                                     invalid_priority, TIME_SLOT_REQUESTS)

        assert result["result"] == FAILURE
        assert result["info"] == expected_info


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "time_slot_request, expected_info",
    [
        (
            [],
            "MALFORMED_REQUEST_EMPTY"),
        (
            [["fakedriver0", str(datetime.now()), ""]],
            "MALFORMED_REQUEST: ParserError: String does not contain a date: ",
        ),
        (
            [["fakedriver0", str(datetime.now())]],
            "MALFORMED_REQUEST: ValueError: "
            "not enough values to unpack (expected 3, got 2)",
        ),
    ],
)
def test_request_new_schedule_should_fail_invalid_time_slot_requests(time_slot_request,
                                                                     expected_info):
    false_request_result = RequestResult(False, {}, expected_info)

    with get_actuator_agent(slot_requests_res=false_request_result) as actuator_agent:
        result = actuator_agent.request_new_schedule(
            REQUESTER_ID, TASK_ID, PRIORITY_LOW, time_slot_request
        )

        assert result["result"] == FAILURE
        assert result["info"] == expected_info


@pytest.mark.actuator_unit
def test_request_cancel_schedule_should_succeed_happy_path():
    true_request_result = RequestResult(
        True, {}, ""
    )

    with get_actuator_agent(cancel_schedule_result=true_request_result) as actuator_agent:
        result = actuator_agent.request_cancel_schedule(REQUESTER_ID, TASK_ID)

        assert result["result"] == SUCCESS


@pytest.mark.actuator_unit
def test_request_cancel_schedule_should_fail_on_invalid_task_id():
    false_request_result = RequestResult(
        False, {}, "TASK_ID_DOES_NOT_EXIST"
    )
    invalid_task_id = "invalid-task-id"

    with get_actuator_agent(cancel_schedule_result=false_request_result) as actuator_agent:
        result = actuator_agent.request_cancel_schedule(REQUESTER_ID, invalid_task_id)

        assert result["result"] == FAILURE
        assert result["info"] == "TASK_ID_DOES_NOT_EXIST"
