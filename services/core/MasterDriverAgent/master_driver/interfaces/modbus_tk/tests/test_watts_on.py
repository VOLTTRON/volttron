import pytest
import gevent
import logging

from volttron.platform import get_services_core

logger = logging.getLogger(__name__)

DRIVER_CONFIG_STRING = """{
    "driver_config": {
        "name": "watts_on",
        "device_address": "/dev/tty.usbserial-AL00IEEY",
        "port": 0,
        "slave_id": 2,
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "none",
        "stopbits": 1,
        "xonxoff": 0,
        "addressing": "offset",
        "endian": "big",
        "register_map": "config://watts_on_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config": "config://watts_on.csv",
    "interval": 120,
    "timezone": "UTC"
}"""

# This registry configuration contains only required fields
REGISTRY_CONFIG_STRING = """Volttron Point Name,Register Name
Active Power Total,active_power_total
Reactive Power Total,reactive_power_total
Apparent Power Total,apparent_power_total
Voltage Average,voltage_average
Current Average,current_average
Voltage AB,voltage_ab
Current A,current_a
Little Endian Mode,little_endian_mode
Serial Baud Rate,serial_baud_rate
Serial Commit,serial_commit"""

REGISTRY_CONFIG_MAP = """Register Name,Address,Type,Units,Writable
active_power_total,0x200,float,kW,TRUE
reactive_power_total,0x202,float,kVAR,TRUE
apparent_power_total,0x204,float,kVA,TRUE
voltage_average,0x206,float,V,TRUE
current_average,0x20A,float,A,TRUE
voltage_ab,0x226,float,V,TRUE
current_a,0x22C,float,A,TRUE
little_endian_mode,0x51A,uint16,None,TRUE
serial_baud_rate,0x601,uint16,None,TRUE
serial_commit,0x605,uint16,None,TRUE"""

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
                          'devices/watts_on',
                          DRIVER_CONFIG_STRING,
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'watts_on.csv',
                          REGISTRY_CONFIG_STRING,
                          config_type='csv')

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'watts_on_map.csv',
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


@pytest.mark.skip(reason="rtu transport: need to connect to the Elkor Watts On meter by usb to the RS-485 interface")
class TestModbusTKDriver:
    """
        Regression tests for the modbus driver interface.
    """

    def get_point(self, agent, point_name):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @return: The returned value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'get_point', 'watts_on', point_name).get(timeout=10)

    def set_point(self, agent, point_name, point_value):
        """
            Issue a set_point RPC call for the named point and value, and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param value: The value to set on the point.
        @return: The returned value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'set_point', 'watts_on', point_name, point_value).get(timeout=10)

    def scrape_all(self, agent):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param: driver_name: The driver name (default: modbus).
        @return: The returned value from the RPC call.
        """
        return agent.vip.rpc.call('platform.driver', 'scrape_all', 'watts_on').get(timeout=10)

    def test_scrape_all(self, agent):
        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

    def test_get_points(self, agent):
        assert self.get_point(agent, 'Serial Baud Rate') == 115
        assert self.get_point(agent, 'Little Endian Mode') == 0
        assert self.get_point(agent, 'Serial Commit') == 0

    def test_set_points(self, agent):
        assert self.set_point(agent, 'Little Endian Mode', 1) == 1
        assert self.set_point(agent, 'Little Endian Mode', 0) == 0





