import pytest
import gevent
import logging
import time

from volttron.platform import get_services_core
from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk.maps import Map, Catalog

logger = logging.getLogger(__name__)

# New modbus_tk driver config
DRIVER_CONFIG_STRING = """{
    "driver_config": {
        "name": "test",
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
        "register_map": "config://modbus_tk_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config":"config://modbus_tk.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

# Old voltron modbus driver config
OLD_VOLTTRON_DRIVER_CONFIG = """{
    "driver_config": {
        "device_address": "127.0.0.1",
         "port": 5020,
         "slave_id": 1
    },
    "driver_type": "modbus_tk",
    "registry_config":"config://modbus.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

# New modbus_tk csv config
REGISTRY_CONFIG_STRING = """Volttron Point Name,Register Name
unsigned short,unsigned_short
unsigned int,unsigned_int
unsigned long,unsigned_long
sample short,sample_short
sample int,sample_int
sample float,sample_float
sample long,sample_long
sample bool,sample_bool
sample str,sample_str"""

REGISTER_MAP = """Register Name,Address,Type,Units,Writable,Default Value,Transform
unsigned_short,0,uint16,None,TRUE,0,scale(10)
unsigned_int,1,uint32,None,TRUE,0,scale(10)
unsigned_long,3,uint64,None,TRUE,0,scale(10)
sample_short,7,int16,None,TRUE,0,scale(10)
sample_int,8,int32,None,TRUE,0,scale(10)
sample_float,10,float,None,TRUE,0.0,scale(10)
sample_long,12,int64,None,TRUE,0,scale(10)
sample_bool,16,bool,None,TRUE,False,
sample_str,17,string[12],None,TRUE,hello world!,"""

# Old volttron modbus csv config
OLD_VOLTTRON_REGISTRY_CONFIG = """Volttron Point Name,Units,Modbus Register,Writable,Point Address,Default Value
unsigned short,None,>H,True,0,0
unsigned int,None,>I,True,1,0
unsigned long,None,>Q,True,3,0
sample short,None,>h,True,7,0
sample int,None,>i,True,8,0
sample float,None,>f,True,10,0.0
sample long,None,>q,True,12,0
sample bool,None,BOOL,True,16,False
sample str,None,string[12],True,17,hello world!"""

# Register values dictionary for testing set_point and get_point
registers_dict = {"unsigned short": 65530,
                  "unsigned int": 4294967290,
                  "unsigned long": 18446744073709550,
                  "sample short": -32760,
                  "sample int": -2147483640,
                  "sample float": -12340.0,
                  "sample long": -922337203685470,
                  "sample bool": True,
                  "sample str": "SampleString"}

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

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'devices/modbus',
                          OLD_VOLTTRON_DRIVER_CONFIG,
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

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'modbus.csv',
                          OLD_VOLTTRON_REGISTRY_CONFIG,
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

    def test_default_values_old(self, agent):
        """Test setting default values from old volttron modbus driver & csv config
        """
        self.revert_all(agent, 'modbus')

        default_values = self.scrape_all(agent, 'modbus')
        assert type(default_values) is dict

        for key in default_values.keys():
            if key == 'sample str':
                assert default_values[key] == 'hello world!'
            else:
                assert default_values[key] == 0 or 0.0

    def test_default_values_new(self, agent):
        """Test setting default values from new modbus_tk driver & csv config
        """
        self.revert_all(agent, 'modbus_tk')

        default_values = self.scrape_all(agent, 'modbus_tk')
        assert type(default_values) is dict

        for key in default_values.keys():
            if key == 'sample str':
                assert default_values[key] == 'hello world!'
            else:
                assert default_values[key] == 0 or 0.0

    def test_set_point_old(self, agent):
        """Test setting new values for old volttron modbus driver & csv config
        """
        for key in registers_dict.keys():
            self.set_point(agent, 'modbus', key, registers_dict[key])
            assert self.get_point(agent, 'modbus', key) == registers_dict[key]
        assert self.scrape_all(agent, 'modbus') == registers_dict

    def test_set_point_new(self, agent):
        """Test setting new values for new modbus_tk driver & csv config
        """
        for key in registers_dict.keys():
            self.set_point(agent, 'modbus_tk', key, registers_dict[key])
            assert self.get_point(agent, 'modbus_tk', key) == registers_dict[key]
        assert self.scrape_all(agent, 'modbus_tk') == registers_dict

    def test_get_point_new(self, agent):
        """Simple test case to set & get value for one single register from new modbus_tk driver & csv config
        """
        set_value = self.set_point(agent, 'modbus_tk', 'unsigned short', 10)
        assert set_value == 10

        self.revert_point(agent, 'modbus_tk', 'unsigned short')

        get_value = self.get_point(agent, 'modbus_tk', 'unsigned short')
        assert get_value == 0

    def test_revert_all_new(self, agent):
        """Test revert device to default values for new modbus_tk driver
        """
        self.revert_all(agent, 'modbus_tk')

        default_values = self.scrape_all(agent, 'modbus_tk')
        assert type(default_values) is dict

        for key in default_values.keys():
            if key == 'sample str':
                assert default_values[key] == 'hello world!'
            else:
                assert default_values[key] == 0 or 0.0