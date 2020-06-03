import logging
from datetime import datetime, date, time

import pytest

from services.core.MasterDriverAgent.master_driver import agent
from services.core.MasterDriverAgent.master_driver.agent import DriverAgent
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent

agent._log = logging.getLogger("test_logger")
DriverAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


class Fake:
    def __init__(self):
        self.vip = ""

    def __call__(self, point):
        return point


@pytest.fixture
def driver_agent():
    parent = Fake()
    config = {"interval": 60}
    time_slot = 2
    driver_scrape_interval = 2
    device_path = ""
    group = 42
    group_offset_interval = 0

    driver_agent = DriverAgent(parent, config, time_slot, driver_scrape_interval, device_path,
                               group, group_offset_interval)

    yield driver_agent


@pytest.mark.driver_unit
def test_get_paths_for_point_should_return_depth_breadth(driver_agent):
    driver_agent.base_topic = Fake()
    expected_depth = "foobar/roma"
    expected_breadth = "devices/roma"
    point = "foobar/roma"

    actual_depth, actual_breadth = driver_agent.get_paths_for_point(point)

    assert actual_depth == expected_depth
    assert actual_breadth == expected_breadth


@pytest.mark.driver_unit
@pytest.mark.parametrize("seconds, expected_datetime", [(0,
                                                        datetime.combine(
                                                            date(2020, 6, 1),
                                                            time(5, 30))),
                                                        (1,
                                                         datetime.combine(
                                                             date(2020, 6, 1),
                                                             time(5, 31, 4))),
                                                        (59,
                                                        datetime.combine(
                                                             date(2020, 6, 1),
                                                             time(5, 31, 4)))
                                                        ])
def test_find_starting_datetime_should_return_new_datetime(driver_agent, seconds, expected_datetime):
    # Note: the expected datetime depends on the interval attribute of driver_agent
    now = datetime.combine(date(2020, 6, 1), time(5, 30, seconds))

    actual_start_datetime = driver_agent.find_starting_datetime(now)

    assert actual_start_datetime == expected_datetime
