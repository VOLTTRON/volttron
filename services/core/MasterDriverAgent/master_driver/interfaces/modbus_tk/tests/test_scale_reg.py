import pytest
import gevent
import logging
import time

from volttron.platform import get_services_core
from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk.maps import Map, Catalog

logger = logging.getLogger(__name__)

DRIVER_CONFIG_STRING = """{
    "driver_config": {
        "name": "test",
        "device_address": "127.0.0.1",
        "port": 5020,
        "addressing": "offset",
        "register_map": "config://modbus_tk_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config":"config://modbus_tk.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

REGISTRY_CONFIG_STRING = """Volttron Point Name,Register Name
I_AC_Current,I_AC_Current
I_AC_CurrentA,I_AC_CurrentA
I_AC_CurrentB,I_AC_CurrentB
I_AC_CurrentC,I_AC_CurrentC
I_AC_CurrentSF,I_AC_CurrentSF"""

REGISTER_MAP = """Register Name,Address,Type,Units,Writable,Default Value,Transform
I_AC_Current,1,uint16,Amp,TRUE,0,scale_reg(I_AC_CurrentSF)
I_AC_CurrentA,2,uint16,Amp,TRUE,0,scale_reg(I_AC_CurrentSF)
I_AC_CurrentB,3,uint16,Amp,TRUE,0,scale_reg(I_AC_CurrentSF)
I_AC_CurrentC,4,uint16,Amp,TRUE,0,scale_reg(I_AC_CurrentSF)
I_AC_CurrentSF,5,uint16,Amp,TRUE,0,"""

registers_dict = {"I_AC_Current": 540,
                  "I_AC_CurrentA": 420,
                  "I_AC_CurrentB": 360,
                  "I_AC_CurrentC": 890,
                  "I_AC_CurrentSF": 20}


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
    """Build MasterDriverAgent, add modbus driver & csv configurations
    """

    # Build master driver agent
    md_agent = volttron_instance.build_agent()

    # Clean out master driver configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_delete_store',
                          'platform.driver')

    # Add driver configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'devices/modbus_tk',
                          DRIVER_CONFIG_STRING,
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus_tk.csv',
                          REGISTRY_CONFIG_STRING,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus_tk_map.csv',
                          REGISTER_MAP,
                          config_type='csv')

    master_uuid = volttron_instance.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                   config_file={},
                                                   start=True)

    gevent.sleep(10)  # wait for the agent to start and start the devices

    def stop():
        """Stop master driver agent
        """
        volttron_instance.stop_agent(master_uuid)
        md_agent.core.stop()

    request.addfinalizer(stop)
    return md_agent


@pytest.fixture(scope='class')
def modbus_server(request):
    ModbusClient = Catalog()['scale_reg'].get_class()

    server_process = Server(address='127.0.0.1', port=5020)
    server_process.define_slave(1, ModbusClient, unsigned=False)

    server_process.start()
    time.sleep(1)
    yield server_process
    time.sleep(1)
    server_process.stop()


@pytest.mark.usefixtures("modbus_server")
class TestModbusTKDriver:
    """
        Regression tests for the modbus_tk driver interface.
    """

    def get_point(self, agent, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @return: The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'get_point', 'modbus_tk', point_name).get(timeout=10)

    def set_point(self, agent, point_name, point_value):
        """
            Issue a set_point RPC call for the named point and value, and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param value: The value to set on the point.
        @return:The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'set_point', 'modbus_tk', point_name, point_value).get(timeout=10)

    def scrape_all(self, agent):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @return: The dictionary mapping point names to their actual values from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'scrape_all', 'modbus_tk').get(timeout=10)

    def revert_all(self, agent):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_device', 'modbus_tk').get(timeout=10)

    def revert_point(self, agent, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_point', 'modbus_tk', point_name).get(timeout=10)

    def test_default_values(self, agent):
        """Set all default values to 0 and check reading those values."""
        self.revert_all(agent)

        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0

    def test_set_point(self, agent):
        """Set register values and confirm getting the correct reading values."""
        self.set_point(agent, 'I_AC_CurrentSF', 20)

        for key in registers_dict.keys():
            self.set_point(agent, key, registers_dict[key])    
            assert self.get_point(agent, key) == registers_dict[key]
        
        assert self.scrape_all(agent) == registers_dict

    def test_get_point(self, agent):
        """Simple test case to set, get, and revert value for one single register."""
        self.set_point(agent, 'I_AC_CurrentSF', 20)

        set_value = self.set_point(agent, 'I_AC_Current', 200)
        assert set_value == 200

        self.revert_point(agent, 'I_AC_Current')
        get_value = self.get_point(agent, 'I_AC_Current')
        assert get_value == 0

    def test_revert_all(self, agent):
        """Test revert device to default values."""
        self.revert_all(agent)

        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0
