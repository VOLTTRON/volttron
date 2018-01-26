import pytest
import gevent
import logging
import time

from volttron.platform import get_services_core
from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk.maps import Map, Catalog

logger = logging.getLogger(__name__)

# Original VOLTTRON modbus driver & registry config
ORIGINAL_DRIVER_CONFIG = """{
    "driver_config": {
        "device_address": "127.0.0.1",
         "port": 5020,
         "slave_id": 1
    },
    "driver_type": "modbus",
    "registry_config":"config://modbus.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

ORIGINAL_REGISTRY_CONFIG = """Volttron Point Name,Units,Modbus Register,Writable,Point Address,Default Value,Mixed Endian
unsigned short,None,>H,True,0,0,True
unsigned int,None,>I,True,1,0,True
unsigned long,None,>Q,True,3,0,True
sample short,None,>h,True,7,0,True
sample int,None,>i,True,8,0,True
sample float,None,>f,True,10,0.0,True
sample long,None,>q,True,12,0,True"""

# New Kisensum modbus driver & registry config
NEW_DRIVER_CONFIG = """{
    "driver_config": {
        "name": "test",
        "device_address": "127.0.0.1",
        "port": 5020,
        "register_map": "config://modbus_tk_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config":"config://modbus_tk.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

NEW_REGISTRY_CONFIG = """Volttron Point Name,Register Name
unsigned short,unsigned_short
unsigned int,unsigned_int
unsigned long,unsigned_long
sample short,sample_short
sample int,sample_int
sample float,sample_float
sample long,sample_long"""

NEW_REGISTER_MAP = """Register Name,Address,Type,Units,Writable,Default Value,Mixed Endian
unsigned_short,0,uint16,None,TRUE,0,True
unsigned_int,1,>I,None,TRUE,0,True
unsigned_long,3,uint64,None,TRUE,0,True
sample_short,7,>h,None,TRUE,0,True
sample_int,8,int32,None,TRUE,0,True
sample_float,10,>f,None,TRUE,0.0,True
sample_long,12,int64,None,TRUE,0,True"""


# Register values dictionary for testing set_point and get_point
registers_dict = {"unsigned short": 65530,
                  "unsigned int": 4294967290,
                  "unsigned long": 18446744073709550,
                  "sample short": -32760,
                  "sample int": -2147483640,
                  "sample float": -12340.0,
                  "sample long": -922337203685470}

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
                          'devices/modbus',
                          ORIGINAL_DRIVER_CONFIG,
                          config_type='json')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'devices/modbus_tk',
                          NEW_DRIVER_CONFIG,
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus.csv',
                          ORIGINAL_REGISTRY_CONFIG,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus_tk.csv',
                          NEW_REGISTRY_CONFIG,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus_tk_map.csv',
                          NEW_REGISTER_MAP,
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
    # modbus_map = Map(map_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "maps")),
    #                  addressing='offset', name='modbus_tk_test', file='modbus_tk_test.csv', endian='big')
    # ModbusClient = modbus_map.get_class()

    ModbusClient = Catalog()['modbus_tk_test'].get_class()

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

    def get_point(self, agent, device_name, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @param point_name: The name of the point to query.
        @return: The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'get_point', device_name, point_name).get(timeout=10)

    def set_point(self, agent, device_name, point_name, point_value):
        """
            Issue a set_point RPC call for the named point and value, and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @param point_name: The name of the point to query.
        @param value: The value to set on the point.
        @return:The actual reading value of the point name from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'set_point', device_name, point_name, point_value).get(timeout=10)

    def scrape_all(self, agent, device_name):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @return: The dictionary mapping point names to their actual values from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'scrape_all', device_name).get(timeout=10)

    def revert_all(self, agent, device_name):
        """
            Issue a get_point RPC call for the device and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_device', device_name).get(timeout=10)

    def revert_point(self, agent, device_name, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param device_name: The driver name, by default: 'devices/device_name'.
        @param point_name: The name of the point to query.
        @return: Return value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'revert_point', device_name, point_name).get(timeout=10)

    def test_simple_set_point(self, agent):
        """
            Do set point and get point from different client to the same server with same set of registers

        :param agent: The test Agent.
        :return: Return value from the RPC call.
        """
        self.set_point(agent, 'modbus', 'unsigned short', 12345)
        assert self.get_point(agent, 'modbus_tk', 'unsigned short') == 12345

        self.set_point(agent, 'modbus_tk', 'unsigned int', 7654321)
        assert self.get_point(agent, 'modbus', 'unsigned int') == 7654321

    def test_original_set_point(self, agent):
        """Test setting new values for original volttron modbus driver & csv config
        """
        for key in registers_dict.keys():
            self.set_point(agent, 'modbus', key, registers_dict[key])
            assert self.get_point(agent, 'modbus', key) == registers_dict[key]

        assert self.scrape_all(agent, 'modbus') == registers_dict
        assert self.scrape_all(agent, 'modbus') == self.scrape_all(agent, 'modbus_tk')

    def test_new_set_point(self, agent):
        """Test setting new values for new modbus_tk driver & csv config
        """
        for key in registers_dict.keys():
            self.set_point(agent, 'modbus_tk', key, registers_dict[key])
            assert self.get_point(agent, 'modbus_tk', key) == registers_dict[key]

        assert self.scrape_all(agent, 'modbus_tk') == registers_dict
        assert self.scrape_all(agent, 'modbus_tk') == self.scrape_all(agent, 'modbus')

    def test_revert_all(self, agent):
        """Test revert device to default values
        """
        self.revert_all(agent, 'modbus')

        default_values = self.scrape_all(agent, 'modbus')
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0 or 0.0

        assert self.scrape_all(agent, 'modbus') == self.scrape_all(agent, 'modbus_tk')