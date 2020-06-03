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


def test_set_override_off_should_raise_override_error(master_driver_agent):
    with pytest.raises(OverrideError):
        master_driver_agent._override_patterns = set()
        pattern = "foobar"

        master_driver_agent.set_override_off(pattern)
