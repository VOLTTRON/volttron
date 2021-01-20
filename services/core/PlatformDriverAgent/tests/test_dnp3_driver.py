import pytest
import gevent
import logging
from services.core.DNP3Agent.dnp3 import DATA_TYPE_ANALOG_INPUT
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform import get_services_core
from volttron.platform.agent import utils

utils.setup_logging()
logger = logging.getLogger(__name__)

DNP3_AGENT_ID = 'dnp3agent'

DRIVER_CONFIG_STRING = """{
    "driver_config": {
        "dnp3_agent_id": "dnp3agent"
    },
    "campus": "campus",
    "building": "building",
    "unit": "dnp3",
    "driver_type": "dnp3",
    "registry_config": "config://dnp3.csv",
    "interval": 15,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}"""

REGISTRY_CONFIG_STRING = """Volttron Point Name,DNP3 Point Name,Data Type,Scaling,Units,Writable
Test1,DCHD.WinTms,int,1.0,,TRUE
Test2,DCHD.RmpTms,int,1.0,,TRUE"""

DNP3_AGENT_CONFIG = {
    "points": [
        {
            "name": "DCHD.WinTms",
            "group": 30,
            "variation": 1,
            "index": 1,
            "data_type": DATA_TYPE_ANALOG_INPUT,
        },
        {
            "name": "DCHD.RmpTms",
            "group": 30,
            "variation": 1,
            "index": 2,
            "data_type": DATA_TYPE_ANALOG_INPUT,
        }
    ],
    "point_topic": "dnp3/point",
    "outstation_status_topic": "dnp3/outstation_status",
    "outstation_config": {
        "database_sizes": 10000,
        "log_levels": ["NORMAL"]
    },
    "local_ip": "0.0.0.0",
    "port": 20000
}

# Test values for set_point and get_point RPC calls
REGISTER_VALUES = {
    'Test1': 10,
    'Test2': 10,
}


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
    """Build PlatformDriverAgent and add DNP3 driver config to it."""

    test_agent = volttron_instance.build_agent()

    def update_config(agent_id, name, value, cfg_type):
        test_agent.vip.rpc.call('config.store', 'manage_store', agent_id, name, value, config_type=cfg_type)

    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(test_agent.core.publickey, capabilities)

    gevent.sleep(1)

    # Build and start DNP3Agent
    dnp3_agent_uuid = volttron_instance.install_agent(agent_dir=get_services_core("DNP3Agent"),
                                                      config_file=DNP3_AGENT_CONFIG,
                                                      vip_identity=DNP3_AGENT_ID,
                                                      start=True)

    # Build and start PlatformDriverAgent

    test_agent.vip.rpc.call('config.store', 'manage_delete_store', PLATFORM_DRIVER)

    platform_uuid = volttron_instance.install_agent(agent_dir=get_services_core("PlatformDriverAgent"),
                                                  config_file={},
                                                  start=True)

    update_config(PLATFORM_DRIVER, 'devices/dnp3', DRIVER_CONFIG_STRING, 'json')
    update_config(PLATFORM_DRIVER, 'dnp3.csv', REGISTRY_CONFIG_STRING, 'csv')

    # Wait for the agent to start and start the devices
    gevent.sleep(3)

    def stop():
        volttron_instance.stop_agent(platform_uuid)
        volttron_instance.stop_agent(dnp3_agent_uuid)
        test_agent.core.stop()

    request.addfinalizer(stop)
    return test_agent


class TestDNP3Driver:
    """Regression tests for the DNP3 driver interface."""

    def test_set_and_get(self, agent):
        for key, val in REGISTER_VALUES.items():
            self.issue_dnp3_rpc(agent, 'set_point', key, val)
            assert self.issue_dnp3_rpc(agent, 'get_point', key) == val

    @staticmethod
    def issue_dnp3_rpc(agent, rpc_call, *args):
        return agent.vip.rpc.call('platform.driver', rpc_call, 'dnp3', *args).get(timeout=10)
