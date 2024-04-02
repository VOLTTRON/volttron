# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2024 Battelle Memorial Institute
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
HOMEASSISTANT_URL = "" # Example, http://0.0.0.0:8123
ACCESS_TOKEN = ""
SSL_CERT_PATH = "" # Optional for self signed cert
VERIFY_SSL = True


def test_scrape_all(publish_agent):
    # add Home Assistant Driver to Platform Driver
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
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "homeassistant_test.json",
                               json.dumps(registry_obj),
                               config_type="json")

    driver_config = {
        "driver_config": {
            "url": HOMEASSISTANT_URL,
            "access_token": ACCESS_TOKEN,
            "verify_ssl": VERIFY_SSL,
            "ssl_cert_path": SSL_CERT_PATH
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://homeassistant_test.json",
        "timezone": "US/Pacific",
        "interval": 30,
    }
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "devices/home_assistant",
                               jsonapi.dumps(driver_config),
                               config_type='json')

    gevent.sleep(10)

    actual_scrape_all_results = publish_agent.vip.rpc.call(PLATFORM_DRIVER, "scrape_all",
                                                           "home_assistant").get(timeout=10)
    expected_scrape_all_results = {'bool_state': 0}
    assert actual_scrape_all_results == expected_scrape_all_results


def test_get_point_set_point(publish_agent):
    actual_boolValue = publish_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "home_assistant",
                                                  "bool_state").get(timeout=10)
    assert actual_boolValue == 0

    #set_point
    actual_boolValue = publish_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "home_assistant", "bool_state",
                                                  1).get(timeout=10)
    assert actual_boolValue == 1


@pytest.fixture(scope="module")
def publish_agent(volttron_instance: PlatformWrapper):
    assert volttron_instance.is_running()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    # install platform driver
    config = {
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": "false",
        "publish_depth_first": "false",
        "publish_breadth_first": "false"
    }
    puid = vi.install_agent(agent_dir="volttron-platform-driver",
                            config_file=config,
                            start=False,
                            vip_identity=PLATFORM_DRIVER)
    assert puid is not None
    gevent.sleep(1)
    assert vi.start_agent(puid)
    assert vi.is_agent_running(puid)

    # create the publish agent
    publish_agent = volttron_instance.build_agent()
    assert publish_agent.core.identity
    gevent.sleep(1)

    capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(publish_agent.core.publickey, capabilities)

    # Add Home Assistant Driver to Platform Driver
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
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "homeassistant_test.json",
                               json.dumps(registry_obj),
                               config_type="json")

    driver_config = {
        "driver_config": {
            "url": HOMEASSISTANT_URL,
            "access_token": ACCESS_TOKEN,
            "verify_ssl": VERIFY_SSL,
            "ssl_cert_path": SSL_CERT_PATH
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://homeassistant_test.json",
        "timezone": "US/Pacific",
        "interval": 30,
    }
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "devices/home_assistant",
                               jsonapi.dumps(driver_config),
                               config_type='json')

    gevent.sleep(10)

    yield publish_agent

    volttron_instance.stop_agent(puid)
    publish_agent.core.stop()