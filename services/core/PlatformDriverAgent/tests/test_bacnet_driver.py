import logging
import os
import time
import pytest
import gevent
import math
import socket
import docker

from mock import MagicMock
from volttron.platform.agent.known_identities import (
    PLATFORM_DRIVER,
    CONFIGURATION_STORE,
)
from volttron.platform import get_services_core
from volttron.platform.agent import utils
from bacnet_device_fixture import (
    BACNET_DEVICE_IP_ADDR,
    BACNET_SUBNET,
    COOLING_VALVE_OUTPUT_COMMAND_OBJECT_ID,
    GENERAL_EXHAUST_FAN_COMMAND_OBJECT_ID,
)

utils.setup_logging()
logger = logging.getLogger(__name__)

BACNET_DEVICE_TOPIC = "devices/bacnet"


def test_set_and_get(
    bacnet_device, query_agent, platform_driver, bacnet_proxy_agent, volttron_instance
):
    query_agent.poll_callback.reset_mock()
    assert volttron_instance.is_agent_running(bacnet_proxy_agent)

    register_values = {
        "CoolingValveOutputCommand": 42.42,
        "GeneralExhaustFanCommand": 1,
    }
    for k, v in register_values.items():
        logger.info(f"Setting and getting point: {k} with value: {v}")
        query_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "bacnet", k, v).get(
            timeout=10
        )
        async_res = query_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "bacnet", k)
        updated_v = async_res.get()
        logger.info(f"Updated value: {updated_v}")

        if isinstance(updated_v, float):
            assert math.isclose(v, updated_v, rel_tol=0.05)
        else:
            assert updated_v == v


def test_revert_all(
    bacnet_device, query_agent, platform_driver, bacnet_proxy_agent, volttron_instance
):
    query_agent.poll_callback.reset_mock()
    assert volttron_instance.is_agent_running(bacnet_proxy_agent)

    cooling_valve = "CoolingValveOutputCommand"
    general_exhaust = "GeneralExhaustFanCommand"
    register_values_default = {
        cooling_valve: 0.0,
        general_exhaust: 0
    }
    register_values_updated = {
        cooling_valve: 42.42,
        general_exhaust: 1
    }

    # change the points from the initial to new values
    for k, v in register_values_updated.items():
        logger.info(f"Setting and getting point: {k} with value: {v}")
        query_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "bacnet", k, v).get(
            timeout=10
        )
        async_res = query_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "bacnet", k)
        updated_v = async_res.get()
        logger.info(f"Updated value: {updated_v}")

        if isinstance(updated_v, float):
            assert math.isclose(v, updated_v, rel_tol=0.05)
        else:
            assert updated_v == v

    # revert all the changed points
    query_agent.vip.rpc.call(PLATFORM_DRIVER, "revert_all", "bacnet").get(timeout=10)
    for k, default_v in register_values_default:
        async_res = query_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "bacnet", k)
        reverted_v = async_res.get()
        logger.info(f"Updated value:{reverted_v}")
        assert reverted_v == default_v

# TODO: add test for "scrape_all"
# p = query_agent.vip.rpc.call(PLATFORM_DRIVER, "scrape_all", "bacnet").get(timeout=10)

# TODO: add another test on COV
# have a COV flag column on registry config and set to true


@pytest.fixture(scope="module")
def bacnet_proxy_agent(volttron_instance):
    device_address = socket.gethostbyname(socket.gethostname() + ".local")
    bacnet_proxy_agent_config = {
        "device_address": device_address,
        # below are optional; values are set to show configuration options; values use the default values
        "max_apdu_length": 1024,
        "object_id": 599,
        "object_name": "Volttron BACnet driver",
        "vendor_id": 15,
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
def query_agent(volttron_instance):
    query_agent = volttron_instance.build_agent()

    # create a mock callback to use with a subscription to the driver's publish publishes
    query_agent.poll_callback = MagicMock(name="poll_callback")

    # subscribe to device topic results
    query_agent.vip.pubsub.subscribe(
        peer="pubsub",
        prefix=BACNET_DEVICE_TOPIC,
        callback=query_agent.poll_callback,
    ).get()

    # give the query agent the capability to modify the platform_driver's config store
    capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(query_agent.core.publickey, capabilities)
    # A sleep was required here to get the platform to consistently add the edit config store capability
    gevent.sleep(1)

    yield query_agent

    print("In teardown method of query_agent")
    query_agent.core.stop()


@pytest.fixture(scope="module")
def platform_driver(volttron_instance, query_agent):
    """Build PlatformDriverAgent and add BACNET driver config to it."""
    # Install a Platform Driver instance without starting it
    platform_driver = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        start=False,
        config_file={
            "publish_breadth_first_all": False,
            "publish_depth_first": False,
            "publish_breadth_first": False,
        },
    )

    # store bacnet driver configuration
    driver_config = {
        "driver_config": {"device_address": BACNET_DEVICE_IP_ADDR, "device_id": 599},
        "driver_type": "bacnet",
        "registry_config": "config://bacnet.csv",
        "timezone": "US/Pacific",
        "interval": 15,
    }
    query_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        BACNET_DEVICE_TOPIC,
        driver_config,
    ).get(timeout=3)

    registry_string = f"""Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Notes
    Building/FCB.Local Application.CLG-O,CoolingValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,{str(COOLING_VALVE_OUTPUT_COMMAND_OBJECT_ID)},Resolution: 0.1
    Building/FCB.Local Application.GEF-C,GeneralExhaustFanCommand,Enum,0-1 (default 0),binaryOutput,presentValue,TRUE,{str(GENERAL_EXHAUST_FAN_COMMAND_OBJECT_ID)},"BinaryPV: 0=inactive, 1=active"""

    query_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        "bacnet.csv",
        registry_string,
        config_type="csv",
    ).get(timeout=3)

    # start the platform driver
    volttron_instance.start_agent(platform_driver)

    # Wait for the agent to start and start the devices
    gevent.sleep(3)

    assert volttron_instance.is_agent_running(platform_driver)

    yield platform_driver

    print("In teardown method of Platform Driver")
    volttron_instance.stop_agent(platform_driver)


@pytest.fixture()
def bacnet_device():
    client = docker.from_env()
    image_name = "bacnet_device"
    network_name = "bacnet_network"

    # build the test image
    client.images.build(
        path=os.getcwd(),
        nocache=True,
        rm=True,
        forcerm=True,
        dockerfile="Dockerfile.test.bacnet",
        tag=image_name,
    )

    # create a custom docker network
    ipam_pool = docker.types.IPAMPool(subnet=BACNET_SUBNET)
    ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
    bacnet_network = client.networks.create(
        network_name, driver="bridge", ipam=ipam_config
    )

    # run the container and assign it a static IP from custom docker network
    bacnet_container = client.containers.create(
        image_name,
        name="bacnet_test",
        detach=True,
    )
    client.networks.get(network_name).connect(
        bacnet_container, ipv4_address=BACNET_DEVICE_IP_ADDR
    )
    bacnet_container.start()

    error_time = time.time() + 10
    while bacnet_container.status != "running":
        if time.time() > error_time:
            raise RuntimeError("Bacnet_device container timeout during fixture setup")
        time.sleep(0.1)
        bacnet_container.reload()

    yield bacnet_container

    print("Teardown for bacnet device on Docker")

    bacnet_container.remove(force=True)
    client.images.remove(image_name)
    bacnet_network.remove()
