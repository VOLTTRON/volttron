import pytest
import gevent
import logging
import time

from volttron.platform import get_services_core
from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk.maps import Map, Catalog

logger = logging.getLogger(__name__)

# modbus_tk driver config
DRIVER_CONFIG_STRING = """{
    "driver_config": {
        "name": "write_single_registers",
        "device_address": "127.0.0.1",
        "port": 5020,
        "slave_id": 1,
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "none",
        "stopbits": 1,
        "xonxoff": 0,
        "addressing": "offset",
        "endian": "big",
        "write_multiple_registers": false,
        "register_map": "config://write_single_registers_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config": "config://write_single_registers.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

# modbus_tk csv config
REGISTRY_CONFIG_STRING = """Volttron Point Name,Register Name
unsigned short,unsigned_short
sample bool,sample_bool"""

REGISTRY_CONFIG_MAP = """Register Name,Address,Type,Units,Writable,Default Value,Transform
unsigned_short,0,uint16,None,TRUE,0,scale(10)
sample_bool,16,bool,None,TRUE,False,"""


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
                          'devices/write_single_registers',
                          DRIVER_CONFIG_STRING,
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'write_single_registers.csv',
                          REGISTRY_CONFIG_STRING,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'write_single_registers_map.csv',
                          REGISTRY_CONFIG_MAP,
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
    ModbusClient = Catalog()['write_single_registers'].get_class()

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
        Regression tests for the write_single_registers driver interface.
    """

    def get_point(self, agent, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @return: The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'get_point', 'write_single_registers', point_name).get(timeout=10)

    def set_point(self, agent, point_name, point_value):
        """
            Issue a set_point RPC call for the named point and value, and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param point_value: The value to set on the point.
        @return:The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'set_point', 'write_single_registers', point_name, point_value).get(timeout=10)

    def scrape_all(self, agent):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @return: The dictionary mapping point names to their actual values from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'scrape_all', 'write_single_registers').get(timeout=10)

    def revert_all(self, agent):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_device', 'write_single_registers').get(timeout=10)

    def revert_point(self, agent, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_point', 'write_single_registers', point_name).get(timeout=10)

    def test_default_values(self, agent):
        """Test set default values
        """
        self.revert_all(agent)

        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0

    def test_set_point(self, agent):
        """Test set points to a new values
        """
        set_value = self.set_point(agent, 'unsigned short', 6530)
        assert set_value == 6530

        set_value = self.set_point(agent, 'sample bool', True)
        assert set_value == True

    def test_get_point(self, agent):
        """Test get point after set point
        """
        self.set_point(agent, 'unsigned short', 1230)
        get_value = self.get_point(agent, 'unsigned short')
        assert get_value == 1230

    def test_revert_point(self, agent):
        """Test revert point to default value
        """
        self.revert_point(agent, 'unsigned short')
        get_value = self.get_point(agent, 'unsigned short')
        assert get_value == 0

        self.revert_point(agent, 'sample bool')
        get_value = self.get_point(agent, 'sample bool')
        assert get_value == False

    def test_revert_all(self, agent):
        """Test revert device to default values
        """
        self.revert_all(agent)

        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0