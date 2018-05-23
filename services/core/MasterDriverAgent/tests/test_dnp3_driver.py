import pytest
import gevent
import logging

from volttron.platform import get_services_core

logger = logging.getLogger(__name__)

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

REGISTRY_CONFIG_STRING = """Volttron Point Name,DNP3 Field Name,Data Type,Scaling,Units,Writable
DCHD.WinTms,DCHD.WinTms,int,1.0,,FALSE
DCHD.RmpTms,DCHD.RmpTms,int,1.0,,FALSE
DCHD.RevtTms,DCHD.RevtTms,int,1.0,,FALSE
DCHD.WTgt,DCHD.WTgt,int,1.0,,FALSE
DCHD.RmpUpRte,DCHD.RmpUpRte,int,1.0,,FALSE
DCHD.RmpDnRte,DCHD.RmpDnRte,int,1.0,,FALSE
DCHD.ChaRmpUpRte,DCHD.ChaRmpUpRte,int,1.0,,FALSE
DCHD.ChaRmpDnRte,DCHD.ChaRmpDnRte,int,1.0,,FALSE
DCHD.ModPrty,DCHD.ModPrty,int,1.0,,FALSE
DCHD.VArAct,DCHD.VArAct,int,1.0,,FALSE
DCHD.ModEna,DCHD.ModEna,int,1.0,,FALSE"""


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
    """Build MasterDriverAgent and add DNP3 driver config to it."""

    def update_config_store(*args, **kwargs):
        master_driver_agent.vip.rpc.call('config.store', 'manage_store', *args, **kwargs)

    master_driver_agent = volttron_instance.build_agent()
    master_driver_agent.vip.rpc.call('config.store', 'manage_delete_store', 'platform.driver')
    update_config_store('platform.driver', 'devices/dnp3', DRIVER_CONFIG_STRING, config_type='json')
    update_config_store('platform.driver', 'dnp3.csv', REGISTRY_CONFIG_STRING, config_type='csv')
    master_driver_uuid = volttron_instance.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                         config_file={},
                                                         start=True)

    dnp3_agent = volttron_instance.build_agent()
    dnp3_agent_uuid = volttron_instance.install_agent(agent_dir=get_services_core("DNP3Agent"),
                                                      config_file={},
                                                      start=True)

    gevent.sleep(10)  # wait for the agent to start and start the devices

    def stop():
        volttron_instance.stop_agent(master_driver_uuid)
        master_driver_agent.core.stop()
        volttron_instance.stop_agent(dnp3_agent_uuid)
        dnp3_agent.core.stop()

    request.addfinalizer(stop)
    return master_driver_agent


class TestDNP3Driver:
    """Regression tests for the DNP3 driver interface."""

    # Register values dictionary for testing set_point and get_point
    register_values = {
        'DCHD.WinTms': 10,
        'DCHD.RmpTms': 10,
        'DCHD.RevtTms': 10,
        'DCHD.WTgt': 10,
        'DCHD.RmpUpRte': 10,
        'DCHD.RmpDnRte': 10,
        'DCHD.ChaRmpUpRte': 10,
        'DCHD.ChaRmpDnRte': 10,
        'DCHD.ModPrty': 10,
        'DCHD.VArAct': 10,
        'DCHD.ModEna': None
    }

    @pytest.mark.skip(reason='Dependency on pydnp3 library')
    def test_rpc_calls(self, agent):
        for key, val in self.register_values.iteritems():
            self.issue_dnp3_rpc(agent, 'set_point', key, val)
            assert self.issue_dnp3_rpc(agent, 'get_point', key) == val
        assert self.issue_dnp3_rpc(agent, 'scrape_all') == self.register_values

    @staticmethod
    def issue_dnp3_rpc(agent, rpc_call, *args):
        return agent.vip.rpc.call('platform.driver', rpc_call, 'dnp3', *args).get(timeout=10)
