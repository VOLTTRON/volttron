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

import logging
import contextlib
from datetime import datetime, date, time
from mock import create_autospec

import pytest
import pytz

from platform_driver import agent
from platform_driver.agent import DriverAgent
from platform_driver.interfaces import BaseInterface
from platform_driver.interfaces.fakedriver import Interface as FakeInterface
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging.utils import Topic
from volttron.platform.vip.agent.core import ScheduledEvent


agent._log = logging.getLogger("test_logger")
DriverAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.mark.driver_unit
def test_update_publish_types_should_only_set_depth_first_to_true():
    publish_depth_first_all = True
    publish_breadth_first_all = True
    publish_depth_first = True
    publish_breadth_first = True

    with get_driver_agent() as driver_agent:
        driver_agent.update_publish_types(publish_depth_first_all, publish_breadth_first_all,
                                          publish_depth_first, publish_breadth_first)

        assert not driver_agent.publish_depth_first_all
        assert not driver_agent.publish_breadth_first_all
        assert driver_agent.publish_depth_first
        assert not driver_agent.publish_breadth_first


@pytest.mark.driver_unit
@pytest.mark.parametrize("time_slot, driver_scrape_interval, group, group_offset_interval, "
                         "expected_time_slot_offset, expected_group",
                         [(60, 2, 0, 3, 0, 0),
                          (1, 4, 2, 3, 10, 2)])
def test_update_scrape_schedule_should_set_periodic_event(time_slot, driver_scrape_interval, group, group_offset_interval,
                                                          expected_time_slot_offset, expected_group):
    with get_driver_agent(has_periodic_read_event=True, has_core_schedule=True) as driver_agent:
        driver_agent.update_scrape_schedule(time_slot, driver_scrape_interval, group, group_offset_interval)

        assert driver_agent.group == expected_group
        assert driver_agent.time_slot_offset == expected_time_slot_offset
        assert isinstance(driver_agent.periodic_read_event, ScheduledEvent)


@pytest.mark.driver_unit
def test_update_scrape_schedule_should_return_none_when_no_periodic_read_event():
    time_slot = 1
    driver_scrape_interval = 4
    group = 2
    group_offset = 3
    expected_time_slot_offset = 10

    with get_driver_agent() as driver_agent:
        result = driver_agent.update_scrape_schedule(time_slot, driver_scrape_interval, group, group_offset)

        assert result is None
        assert driver_agent.time_slot_offset == expected_time_slot_offset


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
def test_find_starting_datetime_should_return_new_datetime(seconds, expected_datetime):
    # Note: the expected datetime depends on the interval attribute of driver_agent
    now = datetime.combine(date(2020, 6, 1), time(5, 30, seconds))

    with get_driver_agent() as driver_agent:
        actual_start_datetime = driver_agent.find_starting_datetime(now)

        assert actual_start_datetime == expected_datetime


@pytest.mark.driver_unit
def test_get_interface_should_return_fakedriver_interface():
    driver_type = "fakedriver"
    config_dict = {}
    config_string = [{"Point Name": "HPWH_Phy0_PowerState",
                      "Writable": "TRUE",
                      "Volttron Point Name": "PowerState",
                      "Units": "1/0",
                      "Starting Value": "0",
                      "Type": "int"}]

    with get_driver_agent() as driver_agent:
        interface = driver_agent.get_interface(driver_type, config_dict, config_string)

        assert isinstance(interface, FakeInterface)


@pytest.mark.driver_unit
def test_starting_should_succeed():
    sender = "somesender"
    expected_path_depth = "devices/path/to/my/device/all"
    expected_path_breadth = "devices/all/device/my/to/path"

    with get_driver_agent(has_core_schedule=True) as driver_agent:
        driver_agent.starting(sender)

        assert driver_agent.all_path_depth == expected_path_depth
        assert driver_agent.all_path_breadth == expected_path_breadth
        assert isinstance(driver_agent.periodic_read_event, ScheduledEvent)


@pytest.mark.driver_unit
def test_setup_device_should_succeed():
    expected_base_topic = Topic("devices/path/to/my/device/{point}")
    expected_device_name = Topic("path/to/my/device")
    expected_meta_data = {'PowerState': {'units': '1/0', 'type': 'integer', 'tz': 'US/Pacific'}}

    with get_driver_agent() as driver_agent:
        driver_agent.setup_device()

        assert driver_agent.base_topic == expected_base_topic
        assert driver_agent.device_name == expected_device_name
        assert driver_agent.meta_data == expected_meta_data


@pytest.mark.driver_unit
def test_periodic_read_should_succeed():
    now = pytz.UTC.localize(datetime.utcnow())

    with get_driver_agent(has_core_schedule=True, meta_data={"foo": "bar"},
                          has_base_topic=True, mock_publish_wrapper=True,
                          interface_scrape_all={"foo": "bar"}) as driver_agent:
        driver_agent.periodic_read(now)

        driver_agent.parent.scrape_starting.assert_called_once()
        driver_agent.parent.scrape_ending.assert_called_once()
        driver_agent._publish_wrapper.assert_called_once()
        assert isinstance(driver_agent.periodic_read_event, ScheduledEvent)


@pytest.mark.driver_unit
@pytest.mark.parametrize("scrape_all_response", [{}, Exception()])
def test_periodic_read_should_return_none_on_scrape_response(scrape_all_response):
    now = pytz.UTC.localize(datetime.utcnow())

    with get_driver_agent(has_core_schedule=True, meta_data={"foo": "bar"},
                          mock_publish_wrapper=True, interface_scrape_all=scrape_all_response) as driver_agent:
        result = driver_agent.periodic_read(now)

        assert result is None
        driver_agent.parent.scrape_starting.assert_called_once()
        driver_agent.parent.scrape_ending.assert_not_called()
        driver_agent._publish_wrapper.assert_not_called()
        assert isinstance(driver_agent.periodic_read_event, ScheduledEvent)


@pytest.mark.driver_unit
def test_heart_beat_should_return_none_on_no_heart_beat_point():
    with get_driver_agent() as driver_agent:
        result = driver_agent.heart_beat()

        assert result is None
        assert not driver_agent.heart_beat_value
        driver_agent.interface.set_point.assert_not_called()


@pytest.mark.driver_unit
def test_heart_beat_should_set_heart_beat():
    with get_driver_agent(has_heart_beat_point=True) as driver_agent:
        driver_agent.heart_beat()

        assert driver_agent.heart_beat_value
        driver_agent.interface.set_point.assert_called_once()


@pytest.mark.driver_unit
def test_get_paths_for_point_should_return_depth_breadth():
    expected_depth = "foobar/roma"
    expected_breadth = "devices/roma"
    point = "foobar/roma"

    with get_driver_agent(has_base_topic=True) as driver_agent:
        actual_depth, actual_breadth = driver_agent.get_paths_for_point(point)

        assert actual_depth == expected_depth
        assert actual_breadth == expected_breadth


@pytest.mark.driver_unit
def test_get_point_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.get_point("pointname")

        driver_agent.interface.get_point.assert_called_once()


@pytest.mark.driver_unit
def test_set_point_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.set_point("pointname", "value")

        driver_agent.interface.set_point.assert_called_once()


@pytest.mark.driver_unit
def test_scrape_all_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.scrape_all()

        driver_agent.interface.scrape_all.assert_called_once()


@pytest.mark.driver_unit
def test_get_multiple_points_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.get_multiple_points("pointnames")

        driver_agent.interface.get_multiple_points.assert_called_once()


@pytest.mark.driver_unit
def test_set_multiple_points_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.set_multiple_points("pointnamevalues")

        driver_agent.interface.set_multiple_points.assert_called_once()


@pytest.mark.driver_unit
def test_revert_point_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.revert_point("pointnamevalues")

        driver_agent.interface.revert_point.assert_called_once()


@pytest.mark.driver_unit
def test_revert_all_should_succeed():
    with get_driver_agent() as driver_agent:
        driver_agent.revert_all()

        driver_agent.interface.revert_all.assert_called_once()


@pytest.mark.driver_unit
def test_publish_cov_value_should_succeed_when_publish_depth_first_is_true():
    point_name = "pointname"
    point_values = {"pointname": "value"}

    with get_driver_agent(mock_publish_wrapper=True,
                          meta_data={"pointname": "values"},
                          has_base_topic=True) as driver_agent:
        driver_agent.publish_cov_value(point_name, point_values)

        driver_agent._publish_wrapper.assert_called_once()


class MockedParent:
    def scrape_starting(self, device_name):
        pass

    def scrape_ending(self, device_name):
        pass


class MockedBaseTopic:
    def __call__(self, point):
        return point


class MockedPublishWrapper:
    def __call__(self, depth_first_topic, headers, message):
        pass


@contextlib.contextmanager
def get_driver_agent(has_base_topic: bool = False,
                     has_periodic_read_event: bool = False,
                     has_core_schedule: bool = False,
                     meta_data: dict = None,
                     mock_publish_wrapper: bool = False,
                     interface_scrape_all: any = None,
                     has_heart_beat_point: bool = False):
    """
    Creates a Driver Agent and mocks its dependencies to be used for unit testing.
    :param has_base_topic:
    :param has_periodic_read_event:
    :param has_core_schedule:
    :param meta_data:
    :param mock_publish_wrapper:
    :param interface_scrape_all:
    :param has_heart_beat_point:
    :return:
    """

    parent = create_autospec(MockedParent)
    # since parent is a mock and not a real instance of a class, we have to set attributes directly
    # create_autospec does not set attributes in a class' constructor
    parent.vip = ""

    config = {"driver_config": {},
              "driver_type": "fakedriver",
              "registry_config": [{"Point Name": "HPWH_Phy0_PowerState",
                                   "Writable": "TRUE",
                                   "Volttron Point Name": "PowerState",
                                   "Units": "1/0",
                                   "Starting Value": "0",
                                   "Type": "int"
                                   }],
              "interval": 60,
              "publish_depth_first_all": False,
              "publish_breadth_first_all": False,
              "publish_depth_first": True,
              "publish_breadth_first": False,
              "heart_beat_point": "Heartbeat",
              "timezone": "US/Pacific",
              }
    time_slot = 2
    driver_scrape_interval = 2
    device_path = "path/to/my/device"
    group = 42
    group_offset_interval = 0

    driver_agent = DriverAgent(parent, config, time_slot, driver_scrape_interval, device_path,
                               group, group_offset_interval)

    driver_agent.interface = create_autospec(BaseInterface)

    if interface_scrape_all is not None:
        driver_agent.interface.scrape_all.return_value = interface_scrape_all

    if has_base_topic:
        driver_agent.base_topic = MockedBaseTopic()

    if has_periodic_read_event:
        driver_agent.periodic_read_event = create_autospec(ScheduledEvent)

    if has_core_schedule:
        driver_agent.core.schedule.return_value = create_autospec(ScheduledEvent)
        driver_agent.core.schedule.cancel = None

    if meta_data is not None:
        driver_agent.meta_data = meta_data

    if mock_publish_wrapper:
        driver_agent._publish_wrapper = create_autospec(MockedPublishWrapper)

    if has_heart_beat_point:
        driver_agent.heart_beat_point = 42
    else:
        driver_agent.heart_beat_point = None

    yield driver_agent
