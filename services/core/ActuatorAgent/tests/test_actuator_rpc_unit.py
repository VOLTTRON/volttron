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
Pytest test cases for testing actuator agent using rpc calls.
"""
import logging
from datetime import datetime, timedelta

import pytest
from mock import create_autospec

from services.core.ActuatorAgent.actuator import agent
from services.core.ActuatorAgent.actuator.agent import ActuatorAgent, ScheduleManager, LockError
from services.core.ActuatorAgent.actuator.scheduler import RequestResult, DeviceState
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
ActuatorAgent.core.identity = "Foo"


class FakeResponse:
    """
    This class is used to help mock Responses from the vip subsystem
    """
    def __init__(self, result):
        self.result = result

    def get(self):
        return self.result


@pytest.mark.actuator_unit
@pytest.mark.parametrize("topic, point", [("foo/bar", None), ("foo/bar", "dfadsf")])
def test_get_point_should_succeed(topic, point):
    actuator_agent = ActuatorAgent()
    actuator_agent.driver_vip_identity = "foo"
    actuator_agent.vip.rpc.call.return_value = FakeResponse({})

    result = actuator_agent.get_point(topic, point=point)

    assert result is not None


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "point, device_state",
    [
        (
            "somepoint",
            {"foo/bar": DeviceState("requester-id-1", "task-id-1", "anytime")},
        ),
        (None, {"foo": DeviceState("requester-id-1", "task-id-1", "anytime")}),
    ],
)
def test_set_point_should_succeed(point, device_state):
    actuator_agent = ActuatorAgent()
    actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"
    actuator_agent.driver_vip_identity = "foo"
    actuator_agent._device_states = device_state
    requester_id = "requester-id-1"
    topic = "foo/bar"
    value = "some value"

    result = actuator_agent.set_point(requester_id, topic, value, point=point)

    assert result is not None


@pytest.mark.actuator_unit
@pytest.mark.parametrize("rpc_peer", [None, 42, []])
def test_set_point_should_raise_type_error(rpc_peer):
    with pytest.raises(TypeError, match="Agent id must be a nonempty string"):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = rpc_peer
        requester_id = "requester-id-1"
        topic = "foo/bar"
        value = "some value"
        point = None

        actuator_agent.set_point(requester_id, topic, value, point=point)


@pytest.mark.actuator_unit
def test_set_point_should_raise_lock_error():
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "some rpc_peer"
        actuator_agent.driver_vip_identity = "foo"
        requester_id = "requester-id-1"
        topic = "foo/bar"
        value = "some value"

        actuator_agent.set_point(requester_id, topic, value)


@pytest.mark.actuator_unit
def test_scrape_all_should_succeed():
    actuator_agent = ActuatorAgent()
    actuator_agent.driver_vip_identity = "fdafd"
    actuator_agent.vip.rpc.call.return_value = FakeResponse({})
    topic = "foo/bar"

    result = actuator_agent.scrape_all(topic)

    assert result is not None


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
    actuator_agent = ActuatorAgent()
    actuator_agent.driver_vip_identity = "some vip identity"
    actuator_agent.vip.rpc.call.return_value = FakeResponse(({"result": "value"}, {}))

    results, errors = actuator_agent.get_multiple_points(topics)

    assert results is not None
    assert not errors


@pytest.mark.actuator_unit
@pytest.mark.parametrize("invalid_topics", [[(123,)], [(None)], [[123]], [[None]]])
def test_get_multiple_points_should_return_errors(invalid_topics):
    actuator_agent = ActuatorAgent()

    results, errors = actuator_agent.get_multiple_points(invalid_topics)

    assert not results
    assert errors is not None


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "topic_values, device_states",
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
def test_set_multiple_points_should_succeed(topic_values, device_states):
    actuator_agent = ActuatorAgent()
    actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"
    actuator_agent.driver_vip_identity = "some_vip_id"
    actuator_agent._device_states = device_states
    actuator_agent.vip.rpc.call.return_value = FakeResponse(({}))

    result = actuator_agent.set_multiple_points("request-id-1", topic_values)

    assert result == {}


@pytest.mark.actuator_unit
@pytest.mark.parametrize("invalid_topic_values", [[(None,)], [(1234,)]])
def test_set_multiple_points_should_raise_value_error(invalid_topic_values):
    with pytest.raises(ValueError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"

        actuator_agent.set_multiple_points("request-id-1", invalid_topic_values)


@pytest.mark.actuator_unit
def test_set_multiple_points_should_raise_lock_error_on_empty_devices():
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"
        topic_values = [("foo/bar", "roma_value")]

        actuator_agent.set_multiple_points("request-id-1", topic_values)


@pytest.mark.actuator_unit
def test_set_multiple_points_should_raise_lock_error_on_non_matching_requester():
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "wrong-requester"
        topic_values = [("foo/bar", "roma_value")]
        actuator_agent._device_states = {
            "foo": DeviceState("requester-id-1", "task-id-1", "anytime")
        }

        actuator_agent.set_multiple_points("request-id-1", topic_values)


@pytest.mark.actuator_unit
@pytest.mark.parametrize("point", [None, "foobarpoint"])
def test_revert_point_should_raise_lock_error_on_empty_devices(point):
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"
        requester_id = "request-id-1"
        topic = "foo/bar"

        actuator_agent.revert_point(requester_id, topic, point=point)


@pytest.mark.actuator_unit
@pytest.mark.parametrize("point", [None, "foobarpoint"])
def test_revert_point_should_raise_lock_error_on_non_matching_requester(point):
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "wrong-requester"
        actuator_agent._device_states = {
            "foo": DeviceState("requester-id-1", "task-id-1", "anytime")
        }
        requester_id = "request-id-1"
        topic = "foo/bar"

        actuator_agent.revert_point(requester_id, topic, point=point)


@pytest.mark.actuator_unit
def test_revert_device_should_raise_lock_error_on_empty_devices():
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "requester-id-1"
        requester_id = "request-id-1"
        topic = "foo/bar"

        actuator_agent.revert_device(requester_id, topic)


@pytest.mark.actuator_unit
def test_revert_device_should_raise_lock_error_on_non_matching_requester():
    with pytest.raises(LockError):
        actuator_agent = ActuatorAgent()
        actuator_agent.vip.rpc.context.vip_message.peer = "wrong-requester"
        actuator_agent._device_states = {
            "foo/bar": DeviceState("requester-id-1", "task-id-1", "anytime")
        }
        requester_id = "request-id-1"
        topic = "foo/bar"

        actuator_agent.revert_device(requester_id, topic)


@pytest.mark.actuator_unit
def test_request_new_schedule_should_succeed_happy_path():
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        True, {("agent-id-1", "task-id-1")}, ""
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None

    result = actuator_agent.request_new_schedule(
        REQUESTER_ID, TASK_ID, PRIORITY_LOW, TIME_SLOT_REQUESTS
    )

    assert result["result"] == SUCCESS


@pytest.mark.actuator_unit
def test_request_new_schedule_should_succeed_when_stop_start_times_overlap():
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        True, {("agent-id-1", "task-id-1")}, ""
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    end2 = str(datetime.now() + timedelta(seconds=2))

    time_slot_requests = [["fakedriver0", start, end], ["fakedriver0", end, end2]]
    result = actuator_agent.request_new_schedule(
        REQUESTER_ID, TASK_ID, PRIORITY_LOW, time_slot_requests
    )

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
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        False, {}, expected_info
    )

    result = actuator_agent.request_new_schedule(
        REQUESTER_ID, task_id, PRIORITY_LOW, TIME_SLOT_REQUESTS
    )

    assert result["result"] == FAILURE
    assert result["info"] == expected_info


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "invalid_priority, expected_info",
    [("LOW2", "INVALID_PRIORITY"), (None, "MISSING_PRIORITY")],
)
def test_request_new_schedule_should_fail_on_invalid_priority(
    invalid_priority, expected_info
):
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        False, {}, expected_info
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None

    result = actuator_agent.request_new_schedule(
        REQUESTER_ID, TASK_ID, invalid_priority, TIME_SLOT_REQUESTS
    )

    assert result["result"] == FAILURE
    assert result["info"] == expected_info


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "time_slot_request, expected_info",
    [
        ([], "MALFORMED_REQUEST_EMPTY"),
        (
            [["fakedriver0", str(datetime.now()), ""]],
            "MALFORMED_REQUEST: ParserError: " "String does not contain a date: ",
        ),
        (
            [["fakedriver0", str(datetime.now())]],
            "MALFORMED_REQUEST: ValueError: "
            "not enough values to unpack (expected 3, got 2)",
        ),
    ],
)
def test_request_new_schedule_should_fail_invalid_time_slot_requests(
    time_slot_request, expected_info
):
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        False, {}, expected_info
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None

    result = actuator_agent.request_new_schedule(
        REQUESTER_ID, TASK_ID, PRIORITY_LOW, time_slot_request
    )

    assert result["result"] == FAILURE
    assert result["info"] == expected_info


@pytest.mark.actuator_unit
def test_request_cancel_schedule_should_succeed_happy_path():
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.cancel_task.return_value = RequestResult(
        True, {}, ""
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None

    result = actuator_agent.request_cancel_schedule(REQUESTER_ID, TASK_ID)

    assert result["result"] == SUCCESS


@pytest.mark.actuator_unit
def test_request_cancel_schedule_should_fail_on_invalid_task_id():
    actuator_agent = ActuatorAgent()
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.cancel_task.return_value = RequestResult(
        False, {}, "TASK_ID_DOES_NOT_EXIST"
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None
    invalid_task_id = "invalid-task-id"

    result = actuator_agent.request_cancel_schedule(REQUESTER_ID, invalid_task_id)

    assert result["result"] == FAILURE
    assert result["info"] == "TASK_ID_DOES_NOT_EXIST"
