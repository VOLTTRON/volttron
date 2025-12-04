# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import json
import logging
import os

import gevent
import pytest

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    PLATFORM_DRIVER,
    CONFIGURATION_STORE,
)
from volttron.platform.keystore import KeyStore
from volttrontesting.utils.platformwrapper import PlatformWrapper

utils.setup_logging()
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Base Home Assistant test configuration
#
# For the basic input_boolean helper tests, we use:
#   HOMEASSISTANT_TEST_FAN_IP
#   HOMEASSISTANT_FAN_ACCESS_TOKEN
#   HOMEASSISTANT_FAN_PORT
# so that all HA tests can share the same instance if desired.
# ----------------------------------------------------------------------

HOMEASSISTANT_TEST_IP = os.environ.get("HOMEASSISTANT_TEST_FAN_IP", "")
ACCESS_TOKEN = os.environ.get("HOMEASSISTANT_FAN_ACCESS_TOKEN", "")
PORT = os.environ.get("HOMEASSISTANT_FAN_PORT", "8123")

skip_msg = (
    "Some configuration variables are not set. "
    "Check HOMEASSISTANT_TEST_FAN_IP, HOMEASSISTANT_FAN_ACCESS_TOKEN, and "
    "HOMEASSISTANT_FAN_PORT"
)

pytestmark = pytest.mark.skipif(
    not (HOMEASSISTANT_TEST_IP and ACCESS_TOKEN and PORT),
    reason=skip_msg,
)

HOMEASSISTANT_DEVICE_TOPIC = "devices/home_assistant"

# ----------------------------------------------------------------------
# Basic helper toggle tests (input_boolean.volttrontest)
# ----------------------------------------------------------------------


def test_get_point(volttron_instance, config_store):
    """
    Get point from a Home Assistant helper toggle.

    The expected value is 0 (off). If the driver cannot reach Home Assistant,
    a different default would be returned and this test will fail.
    """
    expected_values = 0
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant", "bool_state"
    ).get(timeout=20)
    assert result == expected_values, "The result does not match the expected result."


def test_data_poll(volttron_instance: PlatformWrapper, config_store):
    """
    Poll data using scrape_all for the helper toggle.

    The helper may be either 0 or 1 depending on current state, so we accept
    either of those results.
    """
    expected_values = [{"bool_state": 0}, {"bool_state": 1}]
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant"
    ).get(timeout=20)
    assert result in expected_values, "The result does not match the expected result."


def test_set_point(volttron_instance, config_store):
    """
    Turn the helper toggle 'on' via set_point and confirm with scrape_all.
    """
    expected_values = {"bool_state": 1}
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant", "bool_state", 1
    )
    gevent.sleep(10)
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant"
    ).get(timeout=20)
    assert result == expected_values, "The result does not match the expected result."


@pytest.fixture(scope="module")
def config_store(volttron_instance, platform_driver):
    """
    Configure the platform driver and registry for a Home Assistant helper
    (input_boolean.volttrontest).
    """
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(
        volttron_instance.dynamic_agent.core.publickey, capabilities
    )

    registry_config = "homeassistant_test.json"
    registry_obj = [
        {
            "Entity ID": "input_boolean.volttrontest",
            "Entity Point": "state",
            "Volttron Point Name": "bool_state",
            "Units": "On / Off",
            "Units Details": "off: 0, on: 1",
            "Writable": True,
            "Starting Value": 3,
            "Type": "int",
            "Notes": "lights hallway",
        }
    ]

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    )
    gevent.sleep(2)

    driver_config = {
        "driver_config": {
            "ip_address": HOMEASSISTANT_TEST_IP,
            "access_token": ACCESS_TOKEN,
            "port": PORT,
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        HOMEASSISTANT_DEVICE_TOPIC,
        json.dumps(driver_config),
        config_type="json",
    )
    gevent.sleep(2)

    yield platform_driver

    # Cleanup of the entire store
    logger.info("Wiping out store.")
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE, "manage_delete_store", PLATFORM_DRIVER
    )
    gevent.sleep(0.1)


@pytest.fixture(scope="module")
def platform_driver(volttron_instance):
    """
    Start the PlatformDriverAgent to drive the Home Assistant interface.
    """
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={
            "publish_breadth_first_all": False,
            "publish_depth_first": False,
            "publish_breadth_first": False,
        },
        start=True,
    )
    gevent.sleep(2)
    assert volttron_instance.is_agent_running(platform_uuid)
    yield platform_uuid

    volttron_instance.stop_agent(platform_uuid)
    if not volttron_instance.debug_mode:
        volttron_instance.remove_agent(platform_uuid)


# ==================== FAN TESTS ====================

HOMEASSISTANT_TEST_FAN_ENTITY = os.environ.get("HOMEASSISTANT_TEST_FAN_ENTITY", "")

skip_fan_tests = pytest.mark.skipif(
    not HOMEASSISTANT_TEST_FAN_ENTITY,
    reason=(
        "Fan entity not configured. Set HOMEASSISTANT_TEST_FAN_ENTITY "
        "to run fan tests."
    ),
)

HOMEASSISTANT_FAN_DEVICE_TOPIC = "devices/home_assistant_fan"


@skip_fan_tests
def test_get_fan_state(volttron_instance, fan_config_store):
    """
    Test getting fan state - should return 0/1 or on/off.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_fan", "fan_state"
    ).get(timeout=20)
    assert result in [0, 1, "off", "on"], (
        f"Fan state should be 0/1 or on/off, got {result}"
    )


@skip_fan_tests
def test_fan_scrape_all(volttron_instance, fan_config_store):
    """
    Test scraping all fan data points.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant_fan"
    ).get(timeout=20)
    assert "fan_state" in result, "Result should contain fan_state"
    if "fan_speed" in result:
        assert isinstance(
            result["fan_speed"], (int, str)
        ), "Fan speed should be int or string"


@skip_fan_tests
def test_set_fan_on(volttron_instance, fan_config_store):
    """
    Test turning fan on.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_state", 0
    )
    gevent.sleep(3)

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_state", 1
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_fan", "fan_state"
    ).get(timeout=20)
    assert result in [1, "on"], f"Fan should be on, got {result}"


@skip_fan_tests
def test_set_fan_off(volttron_instance, fan_config_store):
    """
    Test turning fan off.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_state", 1
    )
    gevent.sleep(3)

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_state", 0
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_fan", "fan_state"
    ).get(timeout=20)
    assert result in [0, "off"], f"Fan should be off, got {result}"


@skip_fan_tests
def test_set_fan_speed(volttron_instance, fan_config_store):
    """
    Test setting fan speed.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_state", 1
    )
    gevent.sleep(3)

    test_speed = 75
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_fan", "fan_speed", test_speed
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_fan", "fan_speed"
    ).get(timeout=20)
    assert result is not None, "Fan speed should return a value"


@pytest.fixture(scope="module")
def fan_config_store(volttron_instance, platform_driver):
    """
    Fixture for configuring fan tests.
    """
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(
        volttron_instance.dynamic_agent.core.publickey, capabilities
    )

    registry_config = "homeassistant_fan_test.json"
    registry_obj = [
        {
            "Entity ID": HOMEASSISTANT_TEST_FAN_ENTITY,
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Units Details": "off: 0, on: 1",
            "Writable": True,
            "Type": "int",
            "Notes": "Fan state control",
        },
        {
            "Entity ID": HOMEASSISTANT_TEST_FAN_ENTITY,
            "Entity Point": "percentage",
            "Volttron Point Name": "fan_speed",
            "Units": "Percent",
            "Units Details": "0-100",
            "Writable": True,
            "Type": "int",
            "Notes": "Fan speed percentage",
        },
    ]

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    )
    gevent.sleep(2)

    driver_config = {
        "driver_config": {
            "ip_address": HOMEASSISTANT_TEST_IP,
            "access_token": ACCESS_TOKEN,
            "port": PORT,
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        HOMEASSISTANT_FAN_DEVICE_TOPIC,
        json.dumps(driver_config),
        config_type="json",
    )
    gevent.sleep(5)

    yield platform_driver

    logger.info("Cleaning up fan test configuration.")
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_delete_config",
        PLATFORM_DRIVER,
        HOMEASSISTANT_FAN_DEVICE_TOPIC,
    )
    gevent.sleep(0.1)


# ==================== SWITCH TESTS ====================

HOMEASSISTANT_TEST_SWITCH_IP = os.environ.get("HOMEASSISTANT_TEST_SWITCH_IP", "")
HOMEASSISTANT_SWITCH_ACCESS_TOKEN = os.environ.get("HOMEASSISTANT_SWITCH_ACCESS_TOKEN", "")
HOMEASSISTANT_SWITCH_PORT = os.environ.get("HOMEASSISTANT_SWITCH_PORT", "8123")
HOMEASSISTANT_TEST_SWITCH_ENTITY = os.environ.get("HOMEASSISTANT_TEST_SWITCH_ENTITY", "")

skip_switch_tests = pytest.mark.skipif(
    not HOMEASSISTANT_TEST_SWITCH_ENTITY,
    reason=(
        "Switch entity not configured. Set HOMEASSISTANT_TEST_SWITCH_ENTITY "
        "to run switch tests."
    ),
)

HOMEASSISTANT_SWITCH_DEVICE_TOPIC = "devices/home_assistant_switch"


@skip_switch_tests
def test_get_switch_state(volttron_instance, switch_config_store):
    """
    Test getting switch state - should return 0/1 or on/off.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result in [0, 1, "off", "on"], (
        f"Switch state should be 0/1 or on/off, got {result}"
    )


@skip_switch_tests
def test_switch_scrape_all(volttron_instance, switch_config_store):
    """
    Test scraping all switch data points.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant_switch"
    ).get(timeout=20)
    assert "switch_state" in result, "Result should contain switch_state"
    assert result["switch_state"] in [
        0,
        1,
        "on",
        "off",
    ], f"Switch state should be valid, got {result['switch_state']}"


@skip_switch_tests
def test_set_switch_on(volttron_instance, switch_config_store):
    """
    Test turning switch on.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 0
    )
    gevent.sleep(3)

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 1
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result in [1, "on"], f"Switch should be on, got {result}"


@skip_switch_tests
def test_set_switch_off(volttron_instance, switch_config_store):
    """
    Test turning switch off.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 1
    )
    gevent.sleep(3)

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 0
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result in [0, "off"], f"Switch should be off, got {result}"


@skip_switch_tests
def test_switch_toggle(volttron_instance, switch_config_store):
    """
    Test toggling switch on/off multiple times.
    """
    agent = volttron_instance.dynamic_agent

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 1
    )
    gevent.sleep(3)
    result1 = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result1 in [1, "on"], (
        f"Switch should be on after first toggle, got {result1}"
    )

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 0
    )
    gevent.sleep(3)
    result2 = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result2 in [0, "off"], (
        f"Switch should be off after second toggle, got {result2}"
    )

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 1
    )
    gevent.sleep(3)
    result3 = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert result3 in [1, "on"], (
        f"Switch should be on after third toggle, got {result3}"
    )


@skip_switch_tests
def test_invalid_switch_value(volttron_instance, switch_config_store):
    """
    Test that invalid switch values are handled correctly.
    """
    agent = volttron_instance.dynamic_agent

    try:
        agent.vip.rpc.call(
            PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 2
        )
        gevent.sleep(2)
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
        ).get(timeout=20)
        assert result in [
            0,
            1,
            "on",
            "off",
        ], f"Switch state should remain valid even after invalid input, got {result}"
    except Exception as e:
        assert (
            "should be an integer value of 1 or 0" in str(e)
            or "ValueError" in str(type(e).__name__)
        ), (
            f"Expected ValueError for invalid switch value, "
            f"got {type(e).__name__}: {e}"
        )


@pytest.fixture(scope="module")
def switch_config_store(volttron_instance, platform_driver):
    """
    Fixture for configuring switch tests.
    """
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(
        volttron_instance.dynamic_agent.core.publickey, capabilities
    )

    registry_config = "homeassistant_switch_test.json"
    registry_obj = [
        {
            "Entity ID": HOMEASSISTANT_TEST_SWITCH_ENTITY,
            "Entity Point": "state",
            "Volttron Point Name": "switch_state",
            "Units": "On / Off",
            "Units Details": "off: 0, on: 1",
            "Writable": True,
            "Type": "int",
            "Notes": "Switch state control",
        }
    ]

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    )
    gevent.sleep(2)

    driver_config = {
        "driver_config": {
            "ip_address": HOMEASSISTANT_TEST_SWITCH_IP or HOMEASSISTANT_TEST_IP,
            "access_token": HOMEASSISTANT_SWITCH_ACCESS_TOKEN or ACCESS_TOKEN,
            "port": HOMEASSISTANT_SWITCH_PORT or PORT,
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        HOMEASSISTANT_SWITCH_DEVICE_TOPIC,
        json.dumps(driver_config),
        config_type="json",
    )
    gevent.sleep(5)

    yield platform_driver

    logger.info("Cleaning up switch test configuration.")
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_delete_config",
        PLATFORM_DRIVER,
        HOMEASSISTANT_SWITCH_DEVICE_TOPIC,
    )
    gevent.sleep(0.1)


# ==================== COVER TESTS ====================

COVER_TEST_IP = os.environ.get("HOMEASSISTANT_TEST_COVER_IP", "")
COVER_ACCESS_TOKEN = os.environ.get("HOMEASSISTANT_COVER_ACCESS_TOKEN", "")
COVER_PORT = os.environ.get("HOMEASSISTANT_COVER_PORT", "8123")
HOMEASSISTANT_TEST_COVER_ENTITY = os.environ.get("HOMEASSISTANT_TEST_COVER_ENTITY", "")

skip_cover_tests = pytest.mark.skipif(
    not HOMEASSISTANT_TEST_COVER_ENTITY,
    reason=(
        "Cover entity not configured. Set HOMEASSISTANT_TEST_COVER_ENTITY "
        "to run cover tests."
    ),
)

HOMEASSISTANT_COVER_DEVICE_TOPIC = "devices/home_assistant_cover"


@skip_cover_tests
def test_get_cover_state(volttron_instance, cover_config_store):
    """
    Test getting cover state - should return numeric or string status.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_cover", "cover_state"
    ).get(timeout=20)
    assert result in [
        0,
        1,
        "open",
        "closed",
        "opening",
        "closing",
        "unknown",
    ], f"Unexpected cover state: {result}"


@skip_cover_tests
def test_cover_scrape_all(volttron_instance, cover_config_store):
    """
    Test scraping all cover data points.
    """
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant_cover"
    ).get(timeout=20)
    assert "cover_state" in result, "Result should contain cover_state"
    assert "cover_position" in result, "Result should contain cover_position"


@skip_cover_tests
def test_set_cover_open(volttron_instance, cover_config_store):
    """
    Test opening the cover via set_point.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_cover", "cover_state", 1
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_cover", "cover_state"
    ).get(timeout=20)
    assert result in [
        1,
        "open",
        "opening",
    ], f"Cover should be open/opening, got {result}"


@skip_cover_tests
def test_set_cover_closed(volttron_instance, cover_config_store):
    """
    Test closing the cover via set_point.
    """
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_cover", "cover_state", 0
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_cover", "cover_state"
    ).get(timeout=20)
    assert result in [
        0,
        "closed",
        "closing",
    ], f"Cover should be closed/closing, got {result}"


@skip_cover_tests
def test_set_cover_position(volttron_instance, cover_config_store):
    """
    Test setting cover position (0–100).
    """
    agent = volttron_instance.dynamic_agent
    test_position = 50
    agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "set_point",
        "home_assistant_cover",
        "cover_position",
        test_position,
    )
    gevent.sleep(5)

    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_cover", "cover_position"
    ).get(timeout=20)
    assert result is not None, "Cover position should return a value"


@skip_cover_tests
def test_invalid_cover_value(volttron_instance, cover_config_store):
    """
    Test that invalid cover state values are rejected or handled safely.
    """
    agent = volttron_instance.dynamic_agent

    try:
        agent.vip.rpc.call(
            PLATFORM_DRIVER, "set_point", "home_assistant_cover", "cover_state", 2
        )
        gevent.sleep(2)
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER, "get_point", "home_assistant_cover", "cover_state"
        ).get(timeout=20)
        assert result in [
            0,
            1,
            "open",
            "closed",
            "opening",
            "closing",
            "unknown",
        ], f"Cover state should remain valid even after invalid input, got {result}"
    except Exception as e:
        assert (
            "should be an integer value of 1 or 0" in str(e)
            or "ValueError" in str(type(e).__name__)
        ), (
            f"Expected ValueError for invalid cover state, "
            f"got {type(e).__name__}: {e}"
        )


@pytest.fixture(scope="module")
def cover_config_store(volttron_instance, platform_driver):
    """
    Fixture for configuring cover tests.
    """
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(
        volttron_instance.dynamic_agent.core.publickey, capabilities
    )

    registry_config = "homeassistant_cover_test.json"
    registry_obj = [
        {
            "Entity ID": HOMEASSISTANT_TEST_COVER_ENTITY,
            "Entity Point": "state",
            "Volttron Point Name": "cover_state",
            "Units": "Open / Closed",
            "Units Details": "closed: 0, open: 1",
            "Writable": True,
            "Type": "int",
            "Notes": "Cover state control",
        },
        {
            "Entity ID": HOMEASSISTANT_TEST_COVER_ENTITY,
            "Entity Point": "position",
            "Volttron Point Name": "cover_position",
            "Units": "Percent",
            "Units Details": "0-100",
            "Writable": True,
            "Type": "int",
            "Notes": "Cover position",
        },
    ]

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    )
    gevent.sleep(2)

    driver_config = {
        "driver_config": {
            "ip_address": COVER_TEST_IP or HOMEASSISTANT_TEST_IP,
            "access_token": COVER_ACCESS_TOKEN or ACCESS_TOKEN,
            "port": COVER_PORT or PORT,
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        HOMEASSISTANT_COVER_DEVICE_TOPIC,
        json.dumps(driver_config),
        config_type="json",
    )
    gevent.sleep(5)

    yield platform_driver

    logger.info("Cleaning up cover test configuration.")
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_delete_config",
        PLATFORM_DRIVER,
        HOMEASSISTANT_COVER_DEVICE_TOPIC,
    )
    gevent.sleep(0.1)
