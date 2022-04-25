# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
import logging
import os

from datetime import datetime

import pytest
import json
import gevent
import pytest

from volttron.platform import get_services_core
from volttron.platform.messaging.health import STATUS_GOOD
from platform_driver import agent
from platform_driver.agent import PlatformDriverAgent, OverrideError
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent


agent._log = logging.getLogger("test_logger")
PlatformDriverAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.mark.driver_unit
@pytest.mark.parametrize("pattern, expected_device_override", [("campus/building1/*", 1),
                                                               ("campus/building1/", 1),
                                                               ("wrongcampus/building", 0)])
def test_set_override_on_should_succeed(pattern, expected_device_override):
    with get_platform_driver_agent() as platform_driver_agent:
        platform_driver_agent.set_override_on(pattern)

        assert len(platform_driver_agent._override_patterns) == 1
        assert len(platform_driver_agent._override_devices) == expected_device_override
        platform_driver_agent.vip.config.set.assert_called_once()


@pytest.mark.driver_unit
def test_set_override_on_should_succeed_on_definite_duration():
    pattern = "campus/building1/*"
    duration = 42.9
    override_interval_events = {"campus/building1/*": None}

    with get_platform_driver_agent(override_interval_events=override_interval_events) as platform_driver_agent:
        platform_driver_agent.set_override_on(pattern, duration=duration)

        assert len(platform_driver_agent._override_patterns) == 1
        assert len(platform_driver_agent._override_devices) == 1
        platform_driver_agent.vip.config.set.assert_not_called()


@pytest.mark.driver_unit
def test_set_override_off_should_succeed():
    patterns = {"foobar", "device1"}
    override_interval_events = {"device1": None}
    pattern = "foobar"

    with get_platform_driver_agent(override_interval_events=override_interval_events, patterns=patterns) as platform_driver_agent:
        override_patterns_count = len(platform_driver_agent._override_patterns)

        platform_driver_agent.set_override_off(pattern)

        assert len(platform_driver_agent._override_patterns) == override_patterns_count - 1
        platform_driver_agent.vip.config.set.assert_called_once()


@pytest.mark.driver_unit
def test_set_override_off_should_raise_override_error():
    with pytest.raises(OverrideError):
        with get_platform_driver_agent() as platform_driver_agent:
            pattern = "foobar"

            platform_driver_agent.set_override_off(pattern)


@pytest.mark.driver_unit
def test_derive_device_topic_should_succeed():
    config_name = "mytopic/foobar_topic"
    expected_result = "foobar_topic"

    with get_platform_driver_agent() as platform_driver_agent:
        result = platform_driver_agent.derive_device_topic(config_name)

        assert result == expected_result


@pytest.mark.driver_unit
def test_stop_driver_should_return_none():
    device_topic = "mytopic/foobar_topic"

    with get_platform_driver_agent() as platform_driver_agent:
        result = platform_driver_agent.stop_driver(device_topic)

    assert result is None


@pytest.mark.driver_unit
def test_scrape_starting_should_return_none_on_false_scalability_test():
    topic = "mytopic/foobar"

    with get_platform_driver_agent() as platform_driver_agent:
        result = platform_driver_agent.scrape_starting(topic)

    assert result is None


@pytest.mark.driver_unit
def test_scrape_starting_should_start_new_measurement_on_true_scalability_test():
    topic = "mytopic/foobar"

    with get_platform_driver_agent(scalability_test=True) as platform_driver_agent:
        platform_driver_agent.scrape_starting(topic)

        assert platform_driver_agent.current_test_start < datetime.now()
        # This should equal the size of the agent's instances
        assert len(platform_driver_agent.waiting_to_finish) == 1


@pytest.mark.driver_unit
def test_scrape_ending_should_return_none_on_false_scalability_test():
    topic = "mytopic/foobar"

    with get_platform_driver_agent() as platform_driver_agent:
        result = platform_driver_agent.scrape_ending(topic)
        assert result is None


@pytest.mark.driver_unit
def test_scrape_ending_should_increase_test_results_iterations():
    waiting_to_finish = set()
    waiting_to_finish.add("mytopic/foobar")
    topic = "mytopic/foobar"

    with get_platform_driver_agent(scalability_test=True,
                                 waiting_to_finish=waiting_to_finish,
                                 current_test_start=datetime.now()) as platform_driver_agent:
        platform_driver_agent.scrape_ending(topic)

        assert len(platform_driver_agent.test_results) > 0
        assert platform_driver_agent.test_iterations > 0


@pytest.mark.driver_unit
def test_clear_overrides():
    override_patterns = set("ffdfdsfd")

    with get_platform_driver_agent(override_patterns=override_patterns) as platform_driver_agent:
        platform_driver_agent.clear_overrides()

        assert len(platform_driver_agent._override_interval_events) == 0
        assert len(platform_driver_agent._override_devices) == 0
        assert len(platform_driver_agent._override_patterns) == 0


class MockedInstance:
    def revert_all(self):
        pass


@contextlib.contextmanager
def get_platform_driver_agent(override_patterns: set = set(),
                            override_interval_events: dict = {},
                            patterns: dict = None,
                            scalability_test: bool = None,
                            waiting_to_finish: set = None,
                            current_test_start: datetime = None):
    driver_config = json.dumps({
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": False,
        "publish_depth_first": False,
        "publish_breadth_first": False
    })

    if scalability_test:
        platform_driver_agent = PlatformDriverAgent(driver_config, scalability_test=scalability_test)
    else:
        platform_driver_agent = PlatformDriverAgent(driver_config)

    platform_driver_agent._override_patterns = override_patterns
    platform_driver_agent.instances = {"campus/building1/": MockedInstance()}
    platform_driver_agent.core.spawn_return_value = None
    platform_driver_agent._override_interval_events = override_interval_events
    platform_driver_agent._cancel_override_events_return_value = None
    platform_driver_agent.vip.config.set.return_value = ""

    if patterns is not None:
        platform_driver_agent._override_patterns = patterns
    if waiting_to_finish is not None:
        platform_driver_agent.waiting_to_finish = waiting_to_finish
    if current_test_start is not None:
        platform_driver_agent.current_test_start = current_test_start

    try:
        yield platform_driver_agent
    finally:
        platform_driver_agent.vip.reset_mock()
        platform_driver_agent._override_patterns.clear()


@pytest.mark.driver
def test_default_config(volttron_instance):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = volttron_instance.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_services_core("PlatformDriverAgent"), "platform-driver.agent")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)

    volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")

    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
