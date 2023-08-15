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

"""
py.test cases for global override settings.
"""

import pytest
import os

from volttron.platform import get_services_core, get_volttron_root, jsonapi
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
import gevent
from volttron.platform.jsonrpc import RemoteError

TEST_AGENT = "test-agent"
TEST1_AGENT = "test1-agent"
SET_FAILURE = 0.0
REVERT_FAILURE = 0.0
PLATFORM_UUID = ""

FAKE_DEVICE_CONFIG = {
    "driver_config": {},
    "registry_config": "config://fake.csv",
    "interval": 1,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver",
}

PLATFORM_DRIVER_CONFIG = {
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": False,
    "publish_depth_first_all": True,
    "publish_depth_first": False,
    "publish_breadth_first": False,
}


@pytest.fixture(scope="module")
def test_agent(volttron_instance):
    """
    Build PlatformDriverAgent, add Modbus driver & csv configurations
    """

    # Build a test agent
    md_agent = volttron_instance.build_agent(identity="test_md_agent")
    gevent.sleep(1)

    if volttron_instance.auth_enabled:
        capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
        volttron_instance.add_capabilities(md_agent.core.publickey, capabilities)

    # Clean out platform driver configurations
    # wait for it to return before adding new config
    md_agent.vip.rpc.call("config.store", "delete_store", PLATFORM_DRIVER).get()

    # Add configuration for platform driver
    md_agent.vip.rpc.call(
        "config.store",
        "set_config",
        PLATFORM_DRIVER,
        "config",
        jsonapi.dumps(PLATFORM_DRIVER_CONFIG),
        config_type="json",
    )

    # Add fake.csv to config store
    config_path = os.path.join(
        get_volttron_root(), "scripts/scalability-testing/fake_unit_testing.csv"
    )
    with open(config_path, "r") as f:
        registry_config_string = f.read()
    md_agent.vip.rpc.call(
        "config.store",
        "set_config",
        PLATFORM_DRIVER,
        "fake.csv",
        registry_config_string,
        config_type="csv",
    )

    # Add 4 driver configurations to config store
    for i in range(4):
        config_name = f"devices/fakedriver{i}"
        md_agent.vip.rpc.call(
            "config.store",
            "set_config",
            PLATFORM_DRIVER,
            config_name,
            jsonapi.dumps(FAKE_DEVICE_CONFIG),
            config_type="json",
        )

    # Install a PlatformDriverAgent
    global PLATFORM_UUID
    PLATFORM_UUID = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"), config_file={}, start=True
    )

    gevent.sleep(10)  # wait for the agent to start and start the devices

    yield md_agent

    volttron_instance.stop_agent(PLATFORM_UUID)
    md_agent.core.stop()


@pytest.mark.driver
def test_set_override(test_agent):
    device_path = "fakedriver1"
    duration = 2
    sleep_time = 1.1

    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        duration,  # Duration for override in secs
        True,  # Revert to default state is required
        True,  # Staggered revert
    ).get(timeout=10)

    # Give it enough time to send the override request but not enough time so that the override request will fail,
    # i.e. 'sleep_time' should be less than 'duration' to ensure that the override request fails
    gevent.sleep(sleep_time)

    try:
        # set point after override
        point = "SampleWritableShort1"
        value = 20.0
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            device_path,  # device path
            point,
            value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                device_path
            )
        )

    try:
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "revert_device",  # Method
            device_path,  # device path
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot revert device {} since global override is set".format(
                device_path
            )
        )


@pytest.mark.driver
def test_set_point_after_override_elapsed_interval(test_agent):
    device_path = "fakedriver1"
    duration = 1
    sleep_time = 2

    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        duration,  # Duration for override in secs
        True,  # revert to default
        True,  # staggered revert
    ).get(timeout=10)

    # Give it enough time to send the override request and override interval to timeout,
    # i.e., 'sleep_time' must be greater than 'duration'
    gevent.sleep(sleep_time)

    try:
        point = "SampleWritableShort1"
        new_value = 30.0
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        assert result == new_value
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                device_path
            )
        )
        pytest.fail(
            "Expecting successful set point. Code raised OverrideError: {}".format(
                e.message
            )
        )


@pytest.mark.driver
def test_set_hierarchical_override(test_agent):
    device_path = "*"
    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        1,  # Duration for override in secs
        True,
        True,
    ).get(timeout=10)

    fakedriver1_path = "fakedriver2"
    try:
        point = "SampleWritableFloat"
        value = 12.5
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver1_path,  # device path
            point,
            value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned: {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver1_path
            )
        )
    gevent.sleep(4)


@pytest.mark.driver
def test_set_override_no_revert(test_agent):
    device_path = "fakedriver1"
    point = "SampleWritableFloat1"
    old_value = 0.0
    # Get get device point value
    old_value = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "get_point",  # Method
        device_path,  # device path
        point,
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        2,  # Duration for override in secs
        False,  # revert flag to False
        False,
    ).get(timeout=10)

    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "get_point",  # Method
        device_path,  # device path
        point,
    ).get(timeout=10)
    assert result == old_value
    gevent.sleep(2)


@pytest.mark.driver
def test_set_override_off(test_agent):
    device_path = "fakedriver1"

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        60,  # Duration for override in secs
        False,  # revert flag to False
        True,
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(1.1)

    # Get override devices list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_override_devices"  # Target agent  # Method
    ).get(timeout=10)
    assert result == ["fakedriver1"]

    # Get override patterns list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_override_patterns"  # Target agent  # Method
    ).get(timeout=10)
    assert result == ["fakedriver1"]

    # Remove override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_off",  # Method
        device_path,  # Override Pattern
    ).get(timeout=10)

    try:
        point = "SampleWritableFloat1"
        value = 12.5
        # Try to set a point
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            device_path,  # device path
            point,
            value,
        ).get(timeout=10)
        assert result == value
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                device_path
            )
        )
        pytest.fail(
            "Expecting successful set point. Code raised OverrideError: {}".format(
                e.message
            )
        )

    # Get override patterns list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "get_override_patterns",  # Method
    ).get(timeout=10)
    assert result == []

    # Get override devices list
    result = test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "get_override_devices",  # Method
    ).get(timeout=10)
    assert result == []


@pytest.mark.driver
def test_overlapping_override_onoff(test_agent):
    fakedriver1_device_path = "fakedriver1"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        fakedriver1_device_path,  # Override Pattern
        5,  # Duration for override in secs
        False,  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    device_path = "*"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        5,  # Duration for override in secs
        False,
        False,  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    fakedriver1_device_path = "fakedriver1"
    # Remove override feature on fakedriver1 alone
    point = "SampleWritableFloat1"
    new_value = 65.5
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_off",  # Method
        fakedriver1_device_path,  # Override Pattern
    ).get(timeout=10)

    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver1_device_path
            )
        )

    fakedriver2_device_path = "fakedriver2"
    try:
        # Try to set a point on fakedriver2
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver2_device_path
            )
        )

    # Wait for timeout
    gevent.sleep(6)
    try:
        # Try to set a point on fakedriver2
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        assert result == new_value
        print("New value of fake driver2, SampleWritableFloat1: {}".format(new_value))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver2_device_path
            )
        )
        pytest.fail(
            "Expecting successful set point. Code raised OverrideError: {}".format(
                e.message
            )
        )


@pytest.mark.driver
def test_overlapping_override_onoff2(test_agent):
    all_device_path = "*"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        all_device_path,  # Override Pattern
        5,  # Duration for override in secs
        True,  # revert flag to True
        True,
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    fakedriver1_device_path = "fakedriver1"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        fakedriver1_device_path,  # Override Pattern
        2,  # Duration for override in secs
        False,  # revert flag to False
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.5)

    # Remove override feature on '*'
    all_device_path = "*"
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_off",  # Method
        all_device_path,  # Override Pattern
    ).get(timeout=10)

    point = "SampleWritableFloat1"
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver1_device_path
            )
        )

    fakedriver2_device_path = "fakedriver2"
    try:
        # Try to set a point on fakedriver2
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver2_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        assert result == new_value
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver2_device_path
            )
        )
        pytest.fail(
            "Expecting successful set point. Code raised OverrideError: {}".format(
                e.message
            )
        )

    # Wait for timeout
    gevent.sleep(6)

    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        assert result == new_value
        print("New value of fake driver1, SampleWritableFloat1: {}".format(new_value))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver1_device_path
            )
        )
        pytest.fail(
            "Expecting successful set point. Code raised OverrideError: {}".format(
                e.message
            )
        )


@pytest.mark.driver
def test_duplicate_override_on(test_agent):
    all_device_path = "*"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        all_device_path,  # Override Pattern
        1,  # Duration for override in secs
        True,  # revert flag to True
        True,
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        all_device_path,  # Override Pattern
        0.5,  # Duration for override in secs
        True,  # revert flag to True
        True,
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.8)

    fakedriver1_device_path = "fakedriver1"
    point = "SampleWritableFloat1"
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            fakedriver1_device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                fakedriver1_device_path
            )
        )


@pytest.mark.driver
def test_indefinite_override_on(test_agent):
    device_path = "fakedriver2"
    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        -1,  # Indefinite override
        False,  # revert flag to True
        False,
    ).get(timeout=10)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        device_path,  # Override Pattern
        0.5,  # Duration for override in secs
        True,  # revert flag to True
        True,
    ).get(timeout=10)
    # Give it enough time to send the override request.
    gevent.sleep(0.8)

    point = "SampleWritableFloat1"
    new_value = 65.5
    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            device_path,  # device path
            point,
            new_value,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                device_path
            )
        )
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "clear_overrides"  # Target agent  # Method
    ).get(timeout=10)


@pytest.mark.driver
def test_indefinite_override_after_restart(test_agent, volttron_instance):
    assert volttron_instance.is_agent_running(PLATFORM_UUID)

    # start up fake drivers
    gevent.sleep(1)

    # Set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER,  # Target agent
        "set_override_on",  # Method
        "fakedriver*",  # Override Pattern
        0.0,  # Indefinite override
        False,  # revert flag to True
        False,
    ).get(timeout=10)

    # Give it enough time to set indefinite override.
    gevent.sleep(1)
    volttron_instance.stop_agent(PLATFORM_UUID)
    gevent.sleep(0.5)
    # Start the platform driver agent which would in turn start the fake driver
    #  using the configs created above
    volttron_instance.start_agent(PLATFORM_UUID)
    gevent.sleep(1)  # wait for the agent to start and start the devices

    device = "fakedriver1"
    point = "SampleWritableFloat1"

    try:
        # Try to set a point on fakedriver1
        result = test_agent.vip.rpc.call(
            PLATFORM_DRIVER,  # Target agent
            "set_point",  # Method
            device,  # device path
            point,
            65.5,
        ).get(timeout=10)
        pytest.fail("Expecting Override Error. Code returned : {}".format(result))
    except RemoteError as e:
        assert e.exc_info["exc_type"] == "__main__.OverrideError"
        assert (
            e.message
            == "Cannot set point on device {} since global override is set".format(
                device
            )
        )
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "clear_overrides"  # Target agent  # Method
    ).get(timeout=10)


@pytest.mark.driver
def test_override_pattern(test_agent):
    config_path = "devices/{}"
    device_path = "fakedriver1"
    config_name = config_path.format(device_path)
    gevent.sleep(1.1)

    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_override_on", device_path, 2, True, True
    ).get(timeout=10)
    # Give it enough time to send the override request, then ensure that it has created the override
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(
        timeout=3
    )
    assert device_path in devices

    test_agent.vip.rpc.call(PLATFORM_DRIVER, "clear_overrides")

    # add an override pattern with capitalization that doesn't match an installed driver
    camel_device_path = "fakeDriver1"
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_override_on", camel_device_path, 2, True, True
    ).get(timeout=10)
    # Give it enough time to send the override request, then ensure that it has created the override
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(
        timeout=3
    )
    assert not devices

    # add another device to the store using the same string with different casing
    config_name = config_path.format(camel_device_path)
    test_agent.vip.rpc.call(
        "config.store",
        "set_config",
        PLATFORM_DRIVER,
        config_name,
        jsonapi.dumps(FAKE_DEVICE_CONFIG),
        config_type="json",
    )
    gevent.sleep(1.1)
    # set override feature on device
    test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_override_on", camel_device_path, 2, True, True
    ).get(timeout=10)
    gevent.sleep(1.1)
    devices = test_agent.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices").get(
        timeout=3
    )
    assert camel_device_path in devices
    assert device_path not in devices
