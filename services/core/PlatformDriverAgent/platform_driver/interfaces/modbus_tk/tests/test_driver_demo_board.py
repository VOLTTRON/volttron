import os

import gevent
import pytest

from pathlib import Path

from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttron.platform import jsonapi
from volttrontesting.utils.platformwrapper import PlatformWrapper

MODBUS_TEST_IP = "MODBUS_TEST_IP"

# apply skipif to all tests
skip_msg = f"Env var {MODBUS_TEST_IP} not set. Please set the env var to the proper IP to run this integration test."
pytestmark = pytest.mark.skipif(os.environ.get(MODBUS_TEST_IP) is None, reason=skip_msg)


def test_get_point(publish_agent):
    registers = ["SupplyTemp", "ReturnTemp", "OutsideTemp"]
    for point_name in registers:
        point_val = publish_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "modbustk",
                                               point_name).get(timeout=10)
        print(f"Point: {point_name} has point value of {point_val}")
        assert isinstance(point_val, int)


def test_set_point(publish_agent):
    point_name = "SecondStageCoolingDemandSetPoint"
    point_val = 42
    publish_agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "modbustk", point_name,
                               point_val).get(timeout=10)
    assert publish_agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", "modbustk",
                                      point_name).get(timeout=10) == point_val


@pytest.fixture(scope="module")
def publish_agent(volttron_instance: PlatformWrapper):
    assert volttron_instance.is_running()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    config = {
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": "false",
        "publish_depth_first": "false",
        "publish_breadth_first": "false"
    }
    puid = vi.install_agent(agent_dir=Path(__file__).parent.parent.parent.parent.parent.absolute().resolve(),
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
    gevent.sleep(1)

    # Add Modbus Driver TK registry map to Platform Driver
    registry_config_string = """Register Name,Address,Type,Units,Writable
        SupplyTemp,0,uint16,degC,FALSE
        ReturnTemp,1,uint16,degC,FALSE
        OutsideTemp,2,uint16,degC,FALSE
        SecondStageCoolingDemandSetPoint,14,uint16,degC,TRUE"""
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "m2000_rtu_TK_map.csv",
                               registry_config_string,
                               config_type="csv").get(timeout=10)

    # Add Modbus Driver registry to Platform Driver
    registry_config_string = """Register Name,Volttron Point Name
        SupplyTemp,SupplyTemp
        ReturnTemp,ReturnTemp
        OutsideTemp,OutsideTemp
        SecondStageCoolingDemandSetPoint,SecondStageCoolingDemandSetPoint"""
    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "m2000_rtu_TK.csv",
                               registry_config_string,
                               config_type="csv").get(timeout=10)

    # Add Modbus Driver config to Platform Driver
    device_address = os.environ.get(MODBUS_TEST_IP)
    driver_config = {
        "driver_config": {
            "device_address": device_address,
            "slave_id": 8,
            "port": 502,
            "register_map": "config://m2000_rtu_TK_map.csv"
        },
        "campus": "PNNL",
        "building": "DEMO",
        "unit": "M2000",
        "driver_type": "modbus_tk",
        "registry_config": "config://m2000_rtu_TK.csv",
        "interval": 60,
        "timezone": "Pacific",
        "heart_beat_point": "heartbeat"
    }

    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               PLATFORM_DRIVER,
                               "devices/modbustk",
                               jsonapi.dumps(driver_config),
                               config_type='json').get(timeout=10)

    yield publish_agent

    volttron_instance.stop_agent(puid)
    publish_agent.core.stop()
