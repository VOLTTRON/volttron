import pytest
import gevent
import logging
import time
import os.path

from volttron.platform import get_services_core
from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk.maps import Map, Catalog

logger = logging.getLogger(__name__)

# ion6200 driver config
ION6200_DRIVER_CONFIG = """{
    "driver_config": {"name": "ion6200",
                      "device_address": "127.0.0.1",
                      "port": 5020,
                      "slave_id": 1,
                      "baudrate": 9600,
                      "bytesize": 8,
                      "parity": "none",
                      "stopbits": 1,
                      "xonxoff": 0,
                      "addressing": "address",
                      "endian": "big",
                      "register_map": "config://ion6200_map.csv"},
    "driver_type": "modbus_tk",
    "registry_config": "config://ion6200.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

# ion6200 csv config
ION6200_CSV_CONFIG = """Volttron Point Name,Register Name
Serial,serial
Freq,freq
Vln_a,vln_a
Vln_avg,vln_avg
Vll_avg,vll_avg
I_a,i_a
I_b,i_b
I_c,i_c
I_avg,i_avg
kW sum,kw_sum
kVAR sum,kvar_sum
kW peak demand,kw_peak_demand
kWh del,kwh_del
kWh rec,kwh_rec
kVARh del,kvar_del
kVARh rec,kvar_rec
kVARh del+rec,kvarh_del_p_rec
PPS,prog_power_scale
Demand sub interval,demand_sub_interval"""

ION6200_CSV_MAP = """Register Name,Address,Type,Units,Writable,Transform,Table
serial,40001,uint32,SERIAL,TRUE,,analog_output_holding_registers
freq,40025,uint32,Hz,TRUE,,analog_output_holding_registers
vln_a,40100,uint16,Volts,TRUE,scale(0.1),analog_output_holding_registers
vln_avg,40103,uint16,Volts,TRUE,,analog_output_holding_registers
vll_avg,40107,uint16,Volts,TRUE,scale(0.1),analog_output_holding_registers
i_a,40108,uint16,Amps,TRUE,scale(1),analog_output_holding_registers
i_b,40109,uint16,Amps,TRUE,scale(1),analog_output_holding_registers
i_c,40110,uint16,Amps,TRUE,scale(1),analog_output_holding_registers
i_avg,40111,uint16,Amps,TRUE,scale(0.1),analog_output_holding_registers
kw_sum,40120,int16,kW,TRUE,scale(0.1),analog_output_holding_registers
kvar_sum,40121,int16,kVAR,TRUE,scale(1.0),analog_output_holding_registers
kw_peak_demand,40133,int16,kW,TRUE,scale(0.1),analog_output_holding_registers
kwh_del,40138,uint32,kWh,TRUE,mod10k(True),analog_output_holding_registers
kwh_rec,40140,uint32,kWh,TRUE,mod10k(True),analog_output_holding_registers
kvar_del,40142,uint32,kVARh,TRUE,scale(1.0),analog_output_holding_registers
kvar_rec,40144,uint32,kVARh,TRUE,scale(1.0),analog_output_holding_registers
kvarh_del_p_rec,40146,uint32,kVARh,TRUE,scale(1.0),analog_output_holding_registers
prog_power_scale,44015,uint16,kVAR,TRUE,,analog_output_holding_registers
demand_sub_interval,44016,uint16,interval,TRUE,,analog_output_holding_registers"""


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
                          'devices/ion6200',
                          ION6200_DRIVER_CONFIG,
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'ion6200.csv',
                          ION6200_CSV_CONFIG,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'ion6200_map.csv',
                          ION6200_CSV_MAP,
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
    #                  addressing='address', name='ion6200', file='ion6200.csv', endian='big')
    # ModbusClient = modbus_map.get_class()

    ModbusClient = Catalog()['ion6200'].get_class()

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

    def test_default_values(self, agent):
        """Test setting default values
        """
        self.revert_all(agent, 'ion6200')
        default_values = self.scrape_all(agent, 'ion6200')
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0 or 0.0

    def test_set_point(self, agent):
        """Serial set point
        """
        set_value = self.set_point(agent, 'ion6200', 'Serial', 9600)
        assert set_value == 9600

    def test_get_point(self, agent):
        """Serial get point after set point
        """
        get_value = self.get_point(agent, 'ion6200', 'Serial')
        assert get_value == 9600

    def test_revert_point(self,agent):
        """Serial revert to default value
        """
        self.revert_point(agent, 'ion6200', 'Serial')
        assert self.get_point(agent, 'ion6200', 'Serial') == 0

    def test_revert_all_new(self, agent):
        """Test revert device to default values
        """
        self.revert_all(agent, 'ion6200')

        default_values = self.scrape_all(agent, 'ion6200')
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0 or 0.0