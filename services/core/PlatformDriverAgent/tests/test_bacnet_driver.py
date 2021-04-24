import logging
import pytest
import gevent

from mock import MagicMock
from volttron.platform.agent.known_identities import (
    PLATFORM_DRIVER,
    CONFIGURATION_STORE,
)
from volttron.platform import get_services_core, get_examples
from volttron.platform.agent import utils

utils.setup_logging()
logger = logging.getLogger(__name__)

POLL_INTERVAL = 3
BACNET_PROXY_AGENT_ID = "bacnet_proxy_agent"
BACNET_DEVICE_TOPIC = "devices/bacnet"
IP_ADDR = "10.0.2.15" # This should come from docker ip address, <address:port>
DRIVER_CONFIG = {
    "driver_config": {"device_address": IP_ADDR, "device_id": 500},
    "driver_type": "bacnet",
    "registry_config": "config://bacnet.csv",
    "timezone": "US/Pacific",
    "interval": 15,
}
BACNET_PROXY_AGENT_CONFIG = {
    "device_address": IP_ADDR, # Host
    "max_apdu_length": 1024,
    "object_id": 599,
    "object_name": "Volttron BACnet driver",
    "vendor_id": 5,
    "segmentation_supported": "segmentedBoth",
}
# these are hand-picked values to be used for testing; they come from examples/configurations/drivers/bacnet.csv
REGISTER_VALUES = {"CoolingValveOutputCommand": 10.1}


def test_set_and_get(
    query_agent, platform_driver, bacnet_proxy_agent, volttron_instance
):
    query_agent.poll_callback.reset_mock()
    assert volttron_instance.is_agent_running(bacnet_proxy_agent)
    for k, v in REGISTER_VALUES.items():
        query_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "bacnet", k, v).get(
            timeout=10
        )
        print(
            f"This is the POINT: {query_agent.vip.rpc.call(PLATFORM_DRIVER, 'get_point', 'bacnet', k)}"
        )
    #
    # gevent.sleep(POLL_INTERVAL)
    #
    # query_agent.vip.rpc.call(PLATFORM_DRIVER, "heart_beat").get(timeout=10)

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


@pytest.fixture(scope="module")
def bacnet_proxy_agent(volttron_instance):
    bacnet_proxy_agent_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("BACnetProxy"),
        config_file=BACNET_PROXY_AGENT_CONFIG,
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
    query_agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        BACNET_DEVICE_TOPIC,
        DRIVER_CONFIG,
    ).get(timeout=3)
    with open(get_examples("configurations/drivers/bacnet.csv")) as registry_file:
        registry_string = registry_file.read()
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


#
#
# @pytest.fixture(scope="module")
# def bacnet_server():
#     from bacpypes.service.device import LocalDeviceObject
#     args = {"objectname": "Volttron BACnet driver",
#             "address": "172.28.5.0", #IP_ADDR,
#             "objectidentifier": "599",
#             "maxapdulengthaccepted": "1024",
#             "segmentationsupported": "segmentedBoth",
#             "vendoridentifier": "5"}
#
#     mock_device = LocalDeviceObject(
#         objectName=args["objectname"],
#         objectIdentifier=int(args["objectidentifier"]),
#         maxApduLengthAccepted=int(args["maxapdulengthaccepted"]),
#         segmentationSupported=args["segmentationsupported"],
#         vendorIdentifier=int(args["vendoridentifier"]))
#
#     from bacpypes.service.cov import ChangeOfValueServices
#     from bacpypes.app import BIPSimpleApplication
#     class BacServer(BIPSimpleApplication, ChangeOfValueServices):
#         pass
#
#     app = BacServer(mock_device, args["address"])
#
#     assert app
#     from bacpypes.object import (
#         WritableProperty,
#         AnalogValueObject,
#         BinaryValueObject,
#         register_object_type,
#     )
#     from bacpypes.primitivedata import Real
#     class WritableAnalogValueObject(AnalogValueObject):
#         properties = [WritableProperty("presentValue", Real)]
#
#     val_obj = WritableAnalogValueObject(
#         objectIdentifier=("analogValue", 1),
#         objectName="av",
#         presentValue=0.0,
#         statusFlags=[0, 0, 0, 0],
#         covIncrement=1.0,
#     )
#     app.add_object(val_obj)
#
#     yield app
#
