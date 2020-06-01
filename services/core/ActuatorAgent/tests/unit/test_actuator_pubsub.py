import logging
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from mock import create_autospec

import pytest

from services.core.ActuatorAgent.actuator import agent
from services.core.ActuatorAgent.actuator.agent import ActuatorAgent, ScheduleManager
from services.core.ActuatorAgent.actuator.scheduler import RequestResult, DeviceState
from volttrontesting.utils.utils import AgentMock, FakeResponse
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


@pytest.fixture()
def actuator_agent():
    actuator_agent = ActuatorAgent()
    yield actuator_agent

    actuator_agent.vip.reset_mock()


@pytest.mark.actuator_pubsub
def test_handle_get_should_succeed(actuator_agent):
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_get(PEER, SENDER, BUS, GET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called_once()


@pytest.mark.actuator_pubsub
def test_handle_get_should_handle_standard_error(actuator_agent, caplog):
    actuator_agent.handle_get(PEER, SENDER, BUS, GET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message
        == "Actuator Agent Error: {'type': 'AttributeError', "
        "'value': \"'ActuatorAgent' object has no attribute 'driver_vip_identity'\"}"
    )


@pytest.mark.actuator_pubsub
@pytest.mark.parametrize(
    "sender, message, device_states",
    [
        (
            SENDER,
            MESSAGE,
            {"somepath": DeviceState("sender-1", "task-id-1", "anytime")},
        ),
        (
            "pubsub.compat",
            MESSAGE,
            {"somepath": DeviceState("pubsub.compat", "task-id-1", "anytime")},
        ),
    ],
)
def test_handle_set_should_succeed(actuator_agent, sender, message, device_states):
    actuator_agent._device_states = device_states
    actuator_agent.vip.rpc.call.return_value = FakeResponse({"foo": "bar"})
    actuator_agent.driver_vip_identity = "vip identity"

    actuator_agent.handle_set(PEER, sender, BUS, SET_TOPIC, HEADERS, message)

    actuator_agent.vip.rpc.call.assert_called_once()
    actuator_agent.vip.pubsub.publish.assert_called()


@pytest.mark.actuator_pubsub
def test_handle_set_should_return_none_on_none_message(actuator_agent, caplog):
    result = actuator_agent.handle_set(PEER, SENDER, BUS, SET_TOPIC, HEADERS, None)

    assert not result
    actuator_agent.vip.pubsub.publish.assert_called_once()
    actuator_agent.vip.rpc.call.assert_not_called()
    assert (
        caplog.records[-1].message
        == "ValueError: {'type': 'ValueError', 'value': 'missing argument'}"
    )


@pytest.mark.actuator_pubsub
def test_handle_set_should_handle_type_error_on_invalid_sender(actuator_agent, caplog):
    actuator_agent.handle_set(PEER, None, BUS, SET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'TypeError', "
        "'value': 'Agent id must be a nonempty string'}"
    )


@pytest.mark.actuator_pubsub
def test_handle_set_should_handle_lock_error(actuator_agent, caplog):
    actuator_agent.handle_set(PEER, SENDER, BUS, SET_TOPIC, HEADERS, MESSAGE)

    actuator_agent.vip.rpc.call.assert_not_called()
    actuator_agent.vip.pubsub.publish.assert_called_once()
    assert (
        caplog.records[-1].message == "Actuator Agent Error: {'type': 'LockError', "
        "'value': 'caller (sender-1) does not have this lock'}"
    )


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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


@pytest.mark.actuator_pubsub
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
