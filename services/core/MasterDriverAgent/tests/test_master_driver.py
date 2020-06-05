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

import json
import pytest

from services.core.MasterDriverAgent.master_driver import agent
from services.core.MasterDriverAgent.master_driver.agent import MasterDriverAgent, OverrideError
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent

agent._log = logging.getLogger("test_logger")
MasterDriverAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)
driver_config = json.dumps({
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": False,
    "publish_depth_first": False,
    "publish_breadth_first": False
})


class FakeInstanceValue:
    def revert_all(self):
        pass


@pytest.fixture
def master_driver_agent():
    master_driver_agent = MasterDriverAgent(driver_config)
    yield master_driver_agent

    master_driver_agent.vip.reset_mock()


@pytest.mark.driver_unit
@pytest.mark.parametrize("pattern, expected_device_override", [("campus/building1/*", 1),
                                                               ("campus/building1/", 1),
                                                               ("wrongcampus/building", 0)])
def test_set_override_on_should_succeed(master_driver_agent, pattern, expected_device_override):
    master_driver_agent._override_patterns = set()
    master_driver_agent.instances = {"campus/building1/": FakeInstanceValue()}
    master_driver_agent.core.spawn_return_value = None

    master_driver_agent.set_override_on(pattern)

    assert len(master_driver_agent._override_patterns) == 1
    assert len(master_driver_agent._override_devices) == expected_device_override
    master_driver_agent.vip.config.set.assert_called_once()


@pytest.mark.driver_unit
def test_set_override_on_should_succeed_on_definite_duration(master_driver_agent):
    master_driver_agent._override_patterns = set()
    master_driver_agent.instances = {"campus/building1/": FakeInstanceValue()}
    master_driver_agent.core.spawn_return_value = None
    master_driver_agent._override_interval_events = {"campus/building1/*": None}
    pattern = "campus/building1/*"
    duration = 42.9

    master_driver_agent.set_override_on(pattern, duration=duration)

    assert len(master_driver_agent._override_patterns) == 1
    assert len(master_driver_agent._override_devices) == 1
    master_driver_agent.vip.config.set.assert_not_called()


@pytest.mark.driver_unit
def test_set_override_off_should_succeed(master_driver_agent):
    master_driver_agent._override_patterns = {"foobar", "device1"}
    override_patterns_count = len(master_driver_agent._override_patterns)
    master_driver_agent._cancel_override_events_return_value = None
    master_driver_agent.instances = {"device1": "foo"}
    master_driver_agent._override_interval_events = {"device1": None}
    pattern = "foobar"

    master_driver_agent.set_override_off(pattern)

    assert len(master_driver_agent._override_patterns) == override_patterns_count - 1
    master_driver_agent.vip.config.set.assert_called_once()


@pytest.mark.driver_unit
def test_set_override_off_should_raise_override_error(master_driver_agent):
    with pytest.raises(OverrideError):
        master_driver_agent._override_patterns = set()
        pattern = "foobar"

        master_driver_agent.set_override_off(pattern)
