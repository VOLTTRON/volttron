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
import pytest
import gevent

from volttron.platform.agent.known_identities import (
    PLATFORM_DRIVER,
    CONFIGURATION_STORE,
)
from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.keystore import KeyStore
from volttrontesting.utils.platformwrapper import PlatformWrapper

utils.setup_logging()
logger = logging.getLogger(__name__)

# To run these tests, create a helper toggle named volttrontest in your Home Assistant instance.
# This can be done by going to Settings > Devices & services > Helpers > Create Helper > Toggle
HOMEASSISTANT_TEST_IP = ""
ACCESS_TOKEN = ""
PORT = ""

skip_msg = "Some configuration variables are not set. Check HOMEASSISTANT_TEST_IP, ACCESS_TOKEN, and PORT"

# Skip tests if variables are not set
pytestmark = pytest.mark.skipif(
    not (HOMEASSISTANT_TEST_IP and ACCESS_TOKEN and PORT),
    reason=skip_msg
)
HOMEASSISTANT_DEVICE_TOPIC = "devices/home_assistant"
HOMEASSISTANT_SWITCH_DEVICE_TOPIC = "devices/home_assistant_switch"


# Get the point which will should be off
def test_get_point(volttron_instance, config_store):
    expected_values = 0
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'get_point', 'home_assistant', 'bool_state').get(timeout=20)
    assert result == expected_values, "The result does not match the expected result."


# The default value for this fake light is 3. If the test cannot reach out to home assistant,
# the value will default to 3 making the test fail.
def test_data_poll(volttron_instance: PlatformWrapper, config_store):
    expected_values = [{'bool_state': 0}, {'bool_state': 1}]
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', 'home_assistant').get(timeout=20)
    assert result in expected_values, "The result does not match the expected result."


# Turn on the light. Light is automatically turned off every 30 seconds to allow test to turn
# it on and receive the correct value.
def test_set_point(volttron_instance, config_store):
    expected_values = {'bool_state': 1}
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(PLATFORM_DRIVER, 'set_point', 'home_assistant', 'bool_state', 1)
    gevent.sleep(10)
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', 'home_assistant').get(timeout=20)
    assert result == expected_values, "The result does not match the expected result."




# ============================================
# FIXTURE SECTION
# These fixtures prepare Volttron + Home Assistant
# test environments by creating registry configs,
# adding driver configs, and initializing Platform Driver.
# ============================================
@pytest.fixture(scope="module")
def config_store(volttron_instance, platform_driver):

    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(volttron_instance.dynamic_agent.core.publickey, capabilities)

    registry_config = "homeassistant_test.json"
    registry_obj = [{
        "Entity ID": "input_boolean.volttrontest",
        "Entity Point": "state",
        "Volttron Point Name": "bool_state",
        "Units": "On / Off",
        "Units Details": "off: 0, on: 1",
        "Writable": True,
        "Starting Value": 3,
        "Type": "int",
        "Notes": "lights hallway"
    }]

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 registry_config,
                                                 json.dumps(registry_obj),
                                                 config_type="json")
    gevent.sleep(2)
    # driver config
    driver_config = {
        "driver_config": {"ip_address": HOMEASSISTANT_TEST_IP, "access_token": ACCESS_TOKEN, "port": PORT},
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 HOMEASSISTANT_DEVICE_TOPIC,
                                                 json.dumps(driver_config),
                                                 config_type="json"
                                                 )
    gevent.sleep(2)

    yield platform_driver

    print("Wiping out store.")
    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_delete_store", PLATFORM_DRIVER)
    gevent.sleep(0.1)


@pytest.fixture(scope="module")
def config_store_switch(volttron_instance, platform_driver):
    """Registry + driver config for a switch entity."""
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(volttron_instance.dynamic_agent.core.publickey, capabilities)

    registry_config = "homeassistant_switch_test.json"
    registry_obj = [{
        "Entity ID": "switch.volttrontest_switch",
        "Entity Point": "state",
        "Volttron Point Name": "switch_state",
        "Units": "On / Off",
        "Units Details": "off: 0, on: 1",
        "Writable": True,
        "Starting Value": 3,
        "Type": "int",
        "Notes": "test switch"
    }]

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 registry_config,
                                                 json.dumps(registry_obj),
                                                 config_type="json")
    gevent.sleep(2)

    driver_config = {
        "driver_config": {"ip_address": HOMEASSISTANT_TEST_IP, "access_token": ACCESS_TOKEN, "port": PORT},
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 HOMEASSISTANT_SWITCH_DEVICE_TOPIC,
                                                 json.dumps(driver_config),
                                                 config_type="json")
    gevent.sleep(2)

    yield platform_driver

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_delete_store", PLATFORM_DRIVER)
    gevent.sleep(0.1)


@pytest.fixture(scope="module")
def config_store_cover(volttron_instance, platform_driver):
    """Registry + driver config for a cover entity."""
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(volttron_instance.dynamic_agent.core.publickey, capabilities)

    registry_config = "homeassistant_cover_test.json"
    registry_obj = [{
        "Entity ID": "cover.volttrontest_cover",
        "Entity Point": "state",
        "Volttron Point Name": "cover_state",
        "Units": "open/close",
        "Units Details": "0=close,1=open,2=stop",
        "Writable": True,
        "Starting Value": 0,
        "Type": "int",
        "Notes": "test cover"
    }]

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 registry_config,
                                                 json.dumps(registry_obj),
                                                 config_type="json")
    gevent.sleep(2)

    driver_config = {
        "driver_config": {"ip_address": HOMEASSISTANT_TEST_IP, "access_token": ACCESS_TOKEN, "port": PORT},
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE,
                                                 "manage_store",
                                                 PLATFORM_DRIVER,
                                                 "devices/home_assistant_cover",
                                                 json.dumps(driver_config),
                                                 config_type="json")
    gevent.sleep(2)

    yield platform_driver

    volttron_instance.dynamic_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_delete_store", PLATFORM_DRIVER)
    gevent.sleep(0.1)


@pytest.fixture(scope="module")
def config_store_fan(volttron_instance, platform_driver):
    """Registry + driver config for a fan entity (supports state + percentage)."""

    # Allow dynamic agent to edit CONFIG STORE
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(
        volttron_instance.dynamic_agent.core.publickey, 
        capabilities
    )

    # Registry configuration file name
    registry_config = "homeassistant_fan_test.json"

    # Register two writable points:
    # 1. fan_state (0/1 on/off)
    # 2. fan_percentage (0–100)
    registry_obj = [
        {
            "Entity ID": "fan.volttrontest_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On/Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
            "Notes": "test fan state"
        },
        {
            "Entity ID": "fan.volttrontest_fan",
            "Entity Point": "percentage",
            "Volttron Point Name": "fan_percentage",
            "Units": "%",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
            "Notes": "test fan speed percentage"
        }
    ]

    # Write registry config into Volttron
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    )
    gevent.sleep(2)

    # Generate driver configuration
    driver_config = {
        "driver_config": {
            "ip_address": HOMEASSISTANT_TEST_IP,
            "access_token": ACCESS_TOKEN,
            "port": PORT
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 30,
    }

    # Store driver config
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        "devices/home_assistant_fan",
        json.dumps(driver_config),
        config_type="json"
    )
    gevent.sleep(2)

    # Provide to tests
    yield platform_driver

    # Cleanup
    volttron_instance.dynamic_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_delete_store",
        PLATFORM_DRIVER
    )
    gevent.sleep(0.1)






# ============================================
# TEST SECTION
# These tests verify that set_point/get_point/scrape_all
# work correctly for the implemented device types.
# ============================================
def test_fan_on_off(volttron_instance, config_store_fan):
    """Test turning fan ON/OFF using set_point."""
    agent = volttron_instance.dynamic_agent

    # Turn fan ON
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point",
        "home_assistant", "fan_state", 1
    )
    gevent.sleep(10)

    # Verify via scrape_all
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant"
    ).get(timeout=20)

    assert result["fan_state"] == 1, "Fan ON command failed"


def test_fan_percentage(volttron_instance, config_store_fan):
    """Test writing fan speed (percentage 0–100)."""
    agent = volttron_instance.dynamic_agent

    # Set fan speed to 50%
    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point",
        "home_assistant", "fan_percentage", 50
    )
    gevent.sleep(10)

    # Verify via scrape_all
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant"
    ).get(timeout=20)

    assert result["fan_percentage"] == 50, "Fan percentage did not update to 50"


def test_cover_set_point(volttron_instance, config_store_cover):
    agent = volttron_instance.dynamic_agent

    # 1. Open cover
    agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "home_assistant", "cover_state", 1)
    gevent.sleep(5)
    r_open = agent.vip.rpc.call(PLATFORM_DRIVER, "scrape_all", "home_assistant").get(timeout=20)
    assert r_open == {"cover_state": 1}

    # 2. Close cover
    agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "home_assistant", "cover_state", 0)
    gevent.sleep(5)
    r_close = agent.vip.rpc.call(PLATFORM_DRIVER, "scrape_all", "home_assistant").get(timeout=20)
    assert r_close == {"cover_state": 0}


def test_switch_get_point(volttron_instance, config_store_switch):
    expected_values = 0
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'get_point', 'home_assistant', 'switch_state').get(timeout=20)
    assert result == expected_values, "The switch get_point result does not match expected value."


def test_switch_data_poll(volttron_instance, config_store_switch):
    expected_values = [{'switch_state': 0}, {'switch_state': 1}]
    agent = volttron_instance.dynamic_agent
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', 'home_assistant').get(timeout=20)
    assert result in expected_values, "The switch scrape_all result does not match expected values."


def test_switch_set_point(volttron_instance, config_store_switch):
    expected_values = {'switch_state': 1}
    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(PLATFORM_DRIVER, 'set_point', 'home_assistant', 'switch_state', 1)
    gevent.sleep(10)
    result = agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', 'home_assistant').get(timeout=20)
    assert result == expected_values, "The switch set_point result does not match expected value."


@pytest.fixture(scope="module")
def platform_driver(volttron_instance):
    # Start the platform driver agent which would in turn start the bacnet driver
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={
            "publish_breadth_first_all": False,
            "publish_depth_first": False,
            "publish_breadth_first": False,
        },
        start=True,
    )
    gevent.sleep(2)  # wait for the agent to start and start the devices
    assert volttron_instance.is_agent_running(platform_uuid)
    yield platform_uuid

    volttron_instance.stop_agent(platform_uuid)
    if not volttron_instance.debug_mode:
        volttron_instance.remove_agent(platform_uuid)
