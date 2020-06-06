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

import logging
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from mock import create_autospec

import pytest

from services.core.ActuatorAgent.actuator import agent
from services.core.ActuatorAgent.actuator.agent import ActuatorAgent, ScheduleManager
from services.core.ActuatorAgent.actuator.scheduler import RequestResult, DeviceState
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent


PEER = "peer-1"
SENDER = "sender-1"
HEADERS = {"requesterID": "id-12345"}
MESSAGE = "message-1"
BUS = "bus-1"
GET_TOPIC = "devices/actuators/get/somepath/actuationpoint"
SET_TOPIC = "devices/actuators/set/somepath/actuationpoint"
REQUEST_TOPIC = "devices/actuators/schedule/request"
REVERT_DEVICE_TOPIC = "devices/actuators/revert/device/somedevicepath"
REVERT_POINT_TOPIC = "actuators/revert/point/somedevicepath/someactuationpoint"

agent._log = logging.getLogger("test_logger")
ActuatorAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)
ActuatorAgent.core.identity = "foobar"


class FakeResponse:
    """
    This class is used to help mock Responses from the vip subsystem
    """
    def __init__(self, result):
        self.result = result

    def get(self):
        return self.result


@pytest.fixture()
def actuator_agent():
    actuator_agent = ActuatorAgent()
    yield actuator_agent

    actuator_agent.vip.reset_mock()


@pytest.mark.actuator_unit
def test_handle_get_should_succeed(actuator_agent):
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_get(PEER, SENDER, BUS, GET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called_once()


@pytest.mark.actuator_unit
def test_handle_get_should_handle_standard_error(actuator_agent, caplog):
    actuator_agent.handle_get(PEER, SENDER, BUS, GET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message
        == "Actuator Agent Error: {'type': 'AttributeError', "
        "'value': \"'ActuatorAgent' object has no attribute 'driver_vip_identity'\"}"
    )


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "sender, device_states",
    [
        (
            SENDER,
            {"somepath": DeviceState("sender-1", "task-id-1", "anytime")},
        ),
        (
            "pubsub.compat",
            {"somepath": DeviceState("pubsub.compat", "task-id-1", "anytime")},
        ),
    ],
)
def test_handle_set_should_succeed(actuator_agent, sender, device_states):
    actuator_agent._device_states = device_states
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_set(PEER, sender, BUS, SET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called()


@pytest.mark.actuator_unit
def test_handle_set_should_return_none_on_none_message(actuator_agent, caplog):
    result = actuator_agent.handle_set(PEER, SENDER, BUS, SET_TOPIC, HEADERS, None)

    assert not result
    actuator_agent.vip.pubsub.publish.assert_called_once()
    actuator_agent.vip.rpc.call.assert_not_called()
    assert (
        caplog.records[-1].message
        == "ValueError: {'type': 'ValueError', 'value': 'missing argument'}"
    )


@pytest.mark.actuator_unit
def test_handle_set_should_handle_type_error_on_invalid_sender(actuator_agent, caplog):
    actuator_agent.handle_set(PEER, None, BUS, SET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'TypeError', "
        "'value': 'Agent id must be a nonempty string'}"
    )


@pytest.mark.actuator_unit
def test_handle_set_should_handle_lock_error(actuator_agent, caplog):
    actuator_agent.handle_set(PEER, SENDER, BUS, SET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'LockError', "
        "'value': 'caller (sender-1) does not have this lock'}"
    )


@pytest.mark.actuator_unit
def test_handle_revert_point_should_succeed(actuator_agent):
    actuator_agent._device_states = {
        "actuators/revert/point/somedevicepath": DeviceState(
            "sender-1", "task-id-1", "anytime"
        )
    }
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_revert_point(
        PEER, SENDER, BUS, REVERT_POINT_TOPIC, HEADERS, MESSAGE
    )

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called_once()


@pytest.mark.actuator_unit
def test_handle_revert_point_should_handle_lock_error(actuator_agent, caplog):
    actuator_agent.handle_revert_point(
        PEER, SENDER, BUS, REVERT_POINT_TOPIC, HEADERS, MESSAGE
    )

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'LockError', "
        "'value': 'caller does not have this lock'}"
    )


@pytest.mark.actuator_unit
def test_handle_revert_device_should_succeed(actuator_agent):
    actuator_agent._device_states = {
        "somedevicepath": DeviceState("sender-1", "task-id-1", "anytime")
    }
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_revert_device(
        PEER, SENDER, BUS, REVERT_DEVICE_TOPIC, HEADERS, MESSAGE
    )

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called_once()


@pytest.mark.actuator_unit
def test_handle_revert_device_should_handle_lock_error(actuator_agent, caplog):
    actuator_agent.handle_revert_device(
        PEER, SENDER, BUS, REVERT_DEVICE_TOPIC, HEADERS, MESSAGE
    )

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'LockError', "
        "'value': 'caller does not have this lock'}"
    )


@pytest.mark.actuator_unit
@pytest.mark.parametrize(
    "priority, success",
    [
        ("HIGH", True),
        ("LOW", True),
        ("LOW_PREEMPT", True),
        ("HIGH", False),
        ("LOW", False),
        ("LOW_PREEMPT", False),
    ],
)
def test_handle_schedule_request_should_succeed_on_new_schedule_request_type(
    actuator_agent, priority, success
):
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = RequestResult(
        success, {("agent-id-1", "task-id-1")}, ""
    )
    actuator_agent._schedule_manager.get_next_event_time.return_value = None
    headers = {
        "type": "NEW_SCHEDULE",
        "requesterID": "id-123",
        "taskID": "12345",
        "priority": priority,
    }

    actuator_agent.handle_schedule_request(
        PEER, SENDER, BUS, REQUEST_TOPIC, headers, create_message()
    )

    actuator_agent.vip.pubsub.publish.assert_called()


@pytest.mark.actuator_unit
@pytest.mark.parametrize("success", [True, False])
def test_handle_schedule_request_should_succeed_on_cancel_schedule_request_type(
    actuator_agent, success
):
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.cancel_task.return_value = RequestResult(
        success, {("agent-id-1", "task-id-1")}, ""
    )
    actuator_agent._schedule_manager.get_schedule_state.return_value = {}
    actuator_agent._schedule_manager.get_next_event_time.return_value = None
    actuator_agent.core.schedule.return_value = None
    headers = {"type": "CANCEL_SCHEDULE", "requesterID": "id-123", "taskID": "12345"}

    actuator_agent.handle_schedule_request(
        PEER, SENDER, BUS, REQUEST_TOPIC, headers, create_message()
    )

    actuator_agent.vip.pubsub.publish.assert_called()


@pytest.mark.actuator_unit
@pytest.mark.parametrize("invalid_request_type", ["bad request type", None])
def test_handle_schedule_request_should_log_invalid_request_type(
    actuator_agent, invalid_request_type, caplog
):
    headers = {
        "type": invalid_request_type,
        "requesterID": "id-123",
        "taskID": "12345",
        "priority": "HIGH",
    }

    actuator_agent.handle_schedule_request(
        PEER, SENDER, BUS, REQUEST_TOPIC, headers, create_message()
    )

    actuator_agent.vip.pubsub.publish.assert_called()
    assert caplog.records[-1].message == "handle-schedule_request, invalid request type"


def create_message():
    start = str(datetime.now(tz=tzutc()) + timedelta(seconds=10))
    end = str(datetime.now(tz=tzutc()) + timedelta(seconds=20))
    return ["campus/building/device1", start, end]
