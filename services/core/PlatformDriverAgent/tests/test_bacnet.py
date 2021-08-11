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
import os
import pytest
import gevent
import socket

from mock import MagicMock
from volttron.platform.agent.known_identities import (
    PLATFORM_DRIVER,
    CONFIGURATION_STORE,
)
from volttron.platform import get_services_core
from volttron.platform.agent import utils

utils.setup_logging()
logger = logging.getLogger(__name__)

BACNET_DEVICE_TOPIC = "devices/bacnet"
BACNET_TEST_IP = "BACNET_TEST_IP"


def test_scrape_all_should_succeed(bacnet_test_agent):
    register_values = [
        "3820a/Field Bus.3820A CHILLER.AHU-COIL-CHWR-T",
        "3820a/Field Bus.3820A CHILLER.CHW-FLOW",
    ]
    actual_values = bacnet_test_agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "bacnet"
    ).get(timeout=10)
    logger.info(f"Result of scrape_all: {actual_values}")

    for register in register_values:
        assert register in actual_values


def test_get_point_should_succeed(bacnet_test_agent):
    register_values = [
        "3820a/Field Bus.3820A CHILLER.AHU-COIL-CHWR-T",
        "3820a/Field Bus.3820A CHILLER.CHW-FLOW",
    ]
    for register in register_values:
        async_res = bacnet_test_agent.vip.rpc.call(
            PLATFORM_DRIVER, "get_point", "bacnet", register
        )
        value = async_res.get()
        logger.info(f"Value for point {register}: {value}")
        assert isinstance(value, float)


@pytest.fixture(scope="module")
def bacnet_proxy_agent(volttron_instance):
    device_address = socket.gethostbyname(socket.gethostname() + ".local")
    print(f"Device address for proxy agent for testing: {device_address}")
    bacnet_proxy_agent_config = {
        "device_address": device_address,
        # below are optional; values are set to show configuration options; values use the default values
        "max_apdu_length": 1024,
        "object_id": 599,
        "object_name": "Volttron BACnet driver",
        "vendor_id": 5,
        "segmentation_supported": "segmentedBoth",
    }
    bacnet_proxy_agent_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("BACnetProxy"),
        config_file=bacnet_proxy_agent_config,
    )
    gevent.sleep(1)
    volttron_instance.start_agent(bacnet_proxy_agent_uuid)
    assert volttron_instance.is_agent_running(bacnet_proxy_agent_uuid)

    yield bacnet_proxy_agent_uuid

    print("Teardown of bacnet_proxy_agent")
    volttron_instance.stop_agent(bacnet_proxy_agent_uuid)


@pytest.fixture(scope="module")
def bacnet_test_agent(test_ip, bacnet_proxy_agent, config_store, volttron_instance):
    test_agent = volttron_instance.build_agent(identity="test-agent")

    # create a mock callback to use with a subscription to the driver's publish publishes
    test_agent.poll_callback = MagicMock(name="poll_callback")

    # subscribe to device topic results
    test_agent.vip.pubsub.subscribe(
        peer="pubsub",
        prefix=BACNET_DEVICE_TOPIC,
        callback=test_agent.poll_callback,
    ).get()

    # give the test agent the capability to modify the platform_driver's config store
    capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(test_agent.core.publickey, capabilities)

    # A sleep was required here to get the platform to consistently add the edit config store capability
    gevent.sleep(1)

    yield test_agent

    print("In teardown method of query_agent")
    test_agent.core.stop()


@pytest.fixture(scope="module")
def test_ip():
    if not os.environ.get(BACNET_TEST_IP):
        pytest.skip(
            f"Env var {BACNET_TEST_IP} not set. Please set the env var to the proper IP to run this integration test.")
    return os.environ.get(BACNET_TEST_IP)


@pytest.fixture(scope="module")
def config_store_connection(volttron_instance):
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    connection = volttron_instance.build_connection(
        peer=CONFIGURATION_STORE, capabilities=capabilities
    )
    gevent.sleep(1)

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

    yield connection

    volttron_instance.stop_agent(platform_uuid)
    volttron_instance.remove_agent(platform_uuid)
    connection.kill()


@pytest.fixture(scope="module")
def config_store(test_ip, config_store_connection):
    # this fixture will setup a the BACnet driver that will communicate with a live BACnet device located at PNNL campus in Richland at the given device_address
    device_address = test_ip
    if os.system("ping -c 1 " + device_address) != 0:
        pytest.skip(f"BACnet device cannot be reached at {device_address} ")

    registry_config = "bacnet_test.csv"
    registry_string = f"""Reference Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Write Priority,Notes
        3820a/Field Bus.3820A CHILLER.AHU-COIL-CHWR-T,3820a/Field Bus.3820A CHILLER.AHU-COIL-CHWR-T,degreesFahrenheit,-50.00 to 250.00,analogInput,presentValue,FALSE,3000741,,Primary CHW Return Temp
        3820a/Field Bus.3820A CHILLER.CHW-FLOW,3820a/Field Bus.3820A CHILLER.CHW-FLOW,usGallonsPerMinute,-50.00 to 250.00,analogInput,presentValue,FALSE,3000744,,Chiller 1 CHW Flow"""

    # registry config
    config_store_connection.call(
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        registry_string,
        config_type="csv",
    )

    # driver config
    driver_config = {
        "driver_config": {"device_address": device_address, "device_id": 506892},
        "driver_type": "bacnet",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 15,
    }

    config_store_connection.call(
        "manage_store",
        PLATFORM_DRIVER,
        BACNET_DEVICE_TOPIC,
        driver_config,
    )

    yield config_store_connection

    print("Wiping out store.")
    config_store_connection.call("manage_delete_store", PLATFORM_DRIVER)
    gevent.sleep(0.1)
