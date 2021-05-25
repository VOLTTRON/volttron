import logging
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
from volttron.platform import get_services_core, get_examples
from volttron.platform.agent import utils

utils.setup_logging()
logger = logging.getLogger(__name__)

BACNET_DEVICE_TOPIC = "devices/bacnet"


def test_set_and_get(
    bacnet_device, query_agent, platform_driver, bacnet_proxy_agent, volttron_instance
):
    query_agent.poll_callback.reset_mock()
    assert volttron_instance.is_agent_running(bacnet_proxy_agent)
    register_values = {"CoolingValveOutputCommand": 42.42,
                       "GeneralExhaustFanCommand": 1}
    for k, v in register_values.items():
        print(f"Setting and getting point: {k} with value: {v}")
        query_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "bacnet", k, v).get(
            timeout=10
        )
        async_res = query_agent.vip.rpc.call(PLATFORM_DRIVER, 'get_point', 'bacnet', k)
        updated_v = async_res.get()
        print(f"Updated value: {updated_v}")

        if isinstance(updated_v, float):
            assert(math.isclose(v, updated_v, rel_tol=0.05))
        else:
            assert updated_v == v

    # check read multiple points
    # p = query_agent.vip.rpc.call(PLATFORM_DRIVER, "scrape_all", "bacnet").get(
    #     timeout=10
    # )
    # print(f"The RESULT: {p}")
    #
    
    # print(f"This is the CALLBACK count: {query_agent.poll_callback.call_count}")
    # print(f"This is the args: {query_agent.poll_callback.call_args_list}")
    # 
    # assert query_agent.poll_callback.call_count == 1
    # args = query_agent.poll_callback.call_args_list
    # print(args)

    # TODO: add another test on COV
    # have a COV f0lag column, set to true
    # subscrive to point on volt msg
    # bacnet server


@pytest.fixture(scope="module")
def bacnet_proxy_agent(volttron_instance):
    device_address = socket.gethostbyname(socket.gethostname() + ".local")
    bacnet_proxy_agent_config = {
        "device_address": device_address,
        # below are optional; values use the default values
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
    # TODO: Get docker IP address
    ip_addr = "172.28.5.1"  # This should come from docker ip address, <address:port>
    driver_config = {
        "driver_config": {"device_address": ip_addr,
                          "device_id": 599},
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

    registry_string = """Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Notes
    Building/FCB.Local Application.CLG-O,CoolingValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000107,Resolution: 0.1
    Building/FCB.Local Application.GEF-C,GeneralExhaustFanCommand,Enum,0-1 (default 0),binaryOutput,presentValue,TRUE,3000114,"BinaryPV: 0=inactive, 1=active"""

    query_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        "bacnet.csv",
        registry_string,
        config_type="csv",
    ).get(timeout=3)

    # now start the platform driver
    volttron_instance.start_agent(platform_driver)

    # Wait for the agent to start and start the devices
    gevent.sleep(3)

    assert volttron_instance.is_agent_running(platform_driver)

    yield platform_driver

    print("In teardown method of Platform Driver")
    volttron_instance.stop_agent(platform_driver)


@pytest.fixture()
def bacnet_device():
    pass
    # TODO: add docker specific commands for setup adn teardown
    """
    # setup
    docker build -t bacnet_device -f Dockerfile.test.bacnet_device --no-cache --force-rm .
    dk network create --subnet=172.28.0.0/16 --driver=bridge bacnet_network
    dk run --network bacnet_network --ip 172.28.5.1 -it --name bacnet_test bacnet_device
    
    # cleanup
    dk rm --force bacnet_test
    dk network rm bacnet_network
    dk rmi bacnet_device
    """
    client = docker.from_env()

    yield client

    print("Teardown for bacnet device on Docker")
    # client.images.build()
    # # container =
