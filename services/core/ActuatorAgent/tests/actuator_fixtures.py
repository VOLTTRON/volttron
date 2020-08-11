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

import contextlib

from mock import create_autospec

from services.core.ActuatorAgent.actuator.agent import ActuatorAgent, ScheduleManager
from services.core.ActuatorAgent.actuator.scheduler import RequestResult


class MockedAsyncResult:
    """
    This class is used to help mock Responses from the vip subsystem
    """
    def __init__(self, result):
        self.result = result

    def get(self):
        return self.result


@contextlib.contextmanager
def get_actuator_agent(vip_identity: str = "fake_vip_identity",
                       vip_rpc_call_res: MockedAsyncResult = MockedAsyncResult("fake_result"),
                       vip_message_peer: str = None,
                       device_state: dict = {},
                       slot_requests_res: RequestResult = RequestResult(True, {("agent-id-1", "task-id-1")}, ""),
                       cancel_schedule_result: RequestResult = None):
    """
    Creates an Actuator agent and mocks all required dependencies for unit testing
    :param vip_identity: the identity of the Agent's Subsystem
    :param vip_rpc_call_res: the response returned when calling a method of the Agent's Subsystem
    :param vip_message_peer: the identity of the Agent's VIP, which is used internally
    :param device_state: a mapping between a path and a DeviceState; this is an protected field of the Agent
    :param slot_requests_res: the response returned when calling request_slots method of Agent's Schedule Manager
    :param cancel_schedule_result: the response retunred when callin cancel_task method of Agent's Schedule Manaager
    :return:
    """
    ActuatorAgent.core.identity = "fake_core_identity"
    actuator_agent = ActuatorAgent()
    if vip_identity is not None:
        actuator_agent.driver_vip_identity = vip_identity
    actuator_agent.vip.rpc.call.return_value = vip_rpc_call_res
    actuator_agent.vip.rpc.context.vip_message.peer = vip_message_peer
    actuator_agent._device_states = device_state
    actuator_agent._schedule_manager = create_autospec(ScheduleManager)
    actuator_agent._schedule_manager.request_slots.return_value = slot_requests_res
    actuator_agent._schedule_manager.get_next_event_time.return_value = None
    actuator_agent._schedule_manager.cancel_task.return_value = cancel_schedule_result
    actuator_agent._schedule_manager.get_schedule_state.return_value = {}
    actuator_agent.core.schedule.return_value = None

    try:
        yield actuator_agent
    finally:
        actuator_agent.vip.reset_mock()
