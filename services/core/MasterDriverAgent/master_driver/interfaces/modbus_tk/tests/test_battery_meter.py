import pytest
import gevent
import logging
import time
import threading
import os.path

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
        "addressing": "offset",
        "register_map": "config://modbus_tk_map.csv"
},
    "driver_type": "modbus_tk",
    "registry_config": "config://modbus_tk.csv",
    "interval": 60,
    "timezone": "UTC"
}"""

# New modbus_tk csv config
REGISTRY_CONFIG_STRING = """Volttron Point Name,Register Name
BRAND (),BRAND ()
MODEL (),MODEL ()
COMS STATUS (),COMS STATUS ()
COMS QUALITY (),COMS QUALITY ()
NUMBER OF QUERIES (),NUMBER OF QUERIES ()
NUMBER OF FAILS (),NUMBER OF FAILS ()
DATE LAST ACQUISITION (),DATE LAST ACQUISITION ()
LAST SAMPLING DURATION (s),LAST SAMPLING DURATION (s)
ACCUMULATED REAL ENERGY NET (IMPORT-EXPORT) (kWh),ACCUMULATED REAL ENERGY NET (IMPORT-EXPORT) (kWh)
REAL ENERGY QUADRANTS 1-4 IMPORT (kWh),REAL ENERGY QUADRANTS 1-4 IMPORT (kWh)
REAL ENERGY QUADRANTS 2-3 EXPORT (kWh),REAL ENERGY QUADRANTS 2-3 EXPORT (kWh)
REACTIVE ENERGY - QUADRANT 1 IMPORT (kVARh),REACTIVE ENERGY - QUADRANT 1 IMPORT (kVARh)
REACTIVE ENERGY - QUADRANT 2 IMPORT (kVARh),REACTIVE ENERGY - QUADRANT 2 IMPORT (kVARh)
REACTIVE ENERGY - QUADRANT 3 EXPORT (kVARh),REACTIVE ENERGY - QUADRANT 3 EXPORT (kVARh)
REACTIVE ENERGY - QUADRANT 4 EXPORT (kVARh),REACTIVE ENERGY - QUADRANT 4 EXPORT (kVARh)
APPARENT ENERGY NET (IMPORT/EXPORT) (kVAh),APPARENT ENERGY NET (IMPORT/EXPORT) (kVAh)
APPARENT QUADRANTS 1-4 IMPORT (kVAh),APPARENT QUADRANTS 1-4 IMPORT (kVAh)
APPARENT QUADRANTS 2-3 EXPORT (kVAh),APPARENT QUADRANTS 2-3 EXPORT (kVAh)
TOTAL INSTANTANEOUS REAL POWER (kW),TOTAL INSTANTANEOUS REAL POWER (kW)
TOTAL INSTANTANEOUS REACTIVE POWER (kVAR),TOTAL INSTANTANEOUS REACTIVE POWER (kVAR)
TOTAL INSTANTANEOUS APPARENT POWER (kVA),TOTAL INSTANTANEOUS APPARENT POWER (kVA)
TOTAL POWER FACTOR (-),TOTAL POWER FACTOR (-)
AVERAGE VOLTAGE L-L (V),AVERAGE VOLTAGE L-L (V)
AVERAGE VOLTAGE L-N (V),AVERAGE VOLTAGE L-N (V)
AVERAGE CURRENT (A),AVERAGE CURRENT (A)
FREQUENCY (Hz),FREQUENCY (Hz)
TOTAL REAL POWER PRESENT DEMAND (kW),TOTAL REAL POWER PRESENT DEMAND (kW)
TOTAL REACTIVE POWER PRESENT DEMAND (kVAR),TOTAL REACTIVE POWER PRESENT DEMAND (kVAR)
TOTAL APPARENT POWER PRESENT DEMAND (kVA),TOTAL APPARENT POWER PRESENT DEMAND (kVA)
TOTAL REAL POWER MAX. DEMAND IMPORT (kW),TOTAL REAL POWER MAX. DEMAND IMPORT (kW)
TOTAL REACTIVE POWER MAX. DEMAND IMPORT (kVAR),TOTAL REACTIVE POWER MAX. DEMAND IMPORT (kVAR)
TOTAL APPARENT POWER MAX. DEMAND IMPORT (kVA),TOTAL APPARENT POWER MAX. DEMAND IMPORT (kVA)
TOTAL REAL POWER MAX. DEMAND EXPORT (kW),TOTAL REAL POWER MAX. DEMAND EXPORT (kW)
TOTAL REACTIVE POWER MAX. DEMAND EXPORT (kVAR),TOTAL REACTIVE POWER MAX. DEMAND EXPORT (kVAR)
TOTAL APPARENT POWER MAX. DEMAND EXPORT (kVA),TOTAL APPARENT POWER MAX. DEMAND EXPORT (kVA)
PULSE COUNTER 1 (-),PULSE COUNTER 1 (-)
PULSE COUNTER 2 (-),PULSE COUNTER 2 (-)
ACCUMULATED REAL ENERGY PHASE A IMPORT (kWh),ACCUMULATED REAL ENERGY PHASE A IMPORT (kWh)
ACCUMULATED REAL ENERGY PHASE B IMPORT (kWh),ACCUMULATED REAL ENERGY PHASE B IMPORT (kWh)
ACCUMULATED REAL ENERGY PHASE C IMPORT (kWh),ACCUMULATED REAL ENERGY PHASE C IMPORT (kWh)
ACCUMULATED REAL ENERGY PHASE A EXPORT (kWh),ACCUMULATED REAL ENERGY PHASE A EXPORT (kWh)
ACCUMULATED REAL ENERGY PHASE B EXPORT (kWh),ACCUMULATED REAL ENERGY PHASE B EXPORT (kWh)
ACCUMULATED REAL ENERGY PHASE C EXPORT (kWh),ACCUMULATED REAL ENERGY PHASE C EXPORT (kWh)
ACCUMULATED Q1 REACTIVE ENERGY PHASE A IMPORT (kVARh),ACCUMULATED Q1 REACTIVE ENERGY PHASE A IMPORT (kVARh)
ACCUMULATED Q1 REACTIVE ENERGY PHASE B IMPORT (kVARh),ACCUMULATED Q1 REACTIVE ENERGY PHASE B IMPORT (kVARh)
ACCUMULATED Q1 REACTIVE ENERGY PHASE C IMPORT (kVARh),ACCUMULATED Q1 REACTIVE ENERGY PHASE C IMPORT (kVARh)
ACCUMULATED Q2 REACTIVE ENERGY PHASE A IMPORT (kVARh),ACCUMULATED Q2 REACTIVE ENERGY PHASE A IMPORT (kVARh)
ACCUMULATED Q2 REACTIVE ENERGY PHASE B IMPORT (kVARh),ACCUMULATED Q2 REACTIVE ENERGY PHASE B IMPORT (kVARh)
ACCUMULATED Q2 REACTIVE ENERGY PHASE C IMPORT (kVARh),ACCUMULATED Q2 REACTIVE ENERGY PHASE C IMPORT (kVARh)
ACCUMULATED Q3 REACTIVE ENERGY PHASE A EXPORT (kVARh),ACCUMULATED Q3 REACTIVE ENERGY PHASE A EXPORT (kVARh)
ACCUMULATED Q3 REACTIVE ENERGY PHASE B EXPORT (kVARh),ACCUMULATED Q3 REACTIVE ENERGY PHASE B EXPORT (kVARh)
ACCUMULATED Q3 REACTIVE ENERGY PHASE C EXPORT (kVARh),ACCUMULATED Q3 REACTIVE ENERGY PHASE C EXPORT (kVARh)
ACCUMULATED Q4 REACTIVE ENERGY PHASE A EXPORT (kVARh),ACCUMULATED Q4 REACTIVE ENERGY PHASE A EXPORT (kVARh)
ACCUMULATED Q4 REACTIVE ENERGY PHASE B EXPORT (kVARh),ACCUMULATED Q4 REACTIVE ENERGY PHASE B EXPORT (kVARh)
ACCUMULATED Q4 REACTIVE ENERGY PHASE C EXPORT (kVARh),ACCUMULATED Q4 REACTIVE ENERGY PHASE C EXPORT (kVARh)
ACCUMULATED APPARENT ENERGY PHASE A IMPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE A IMPORT (kVAh)
ACCUMULATED APPARENT ENERGY PHASE B IMPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE B IMPORT (kVAh)
ACCUMULATED APPARENT ENERGY PHASE C IMPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE C IMPORT (kVAh)
ACCUMULATED APPARENT ENERGY PHASE A EXPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE A EXPORT (kVAh)
ACCUMULATED APPARENT ENERGY PHASE B EXPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE B EXPORT (kVAh)
ACCUMULATED APPARENT ENERGY PHASE C EXPORT (kVAh),ACCUMULATED APPARENT ENERGY PHASE C EXPORT (kVAh)
REAL POWER PHASE A (kW),REAL POWER PHASE A (kW)
REAL POWER PHASE B (kW),REAL POWER PHASE B (kW)
REAL POWER PHASE C (kW),REAL POWER PHASE C (kW)
REACTIVE POWER PHASE A (kVAR),REACTIVE POWER PHASE A (kVAR)
REACTIVE POWER PHASE B (kVAR),REACTIVE POWER PHASE B (kVAR)
REACTIVE POWER PHASE C (kVAR),REACTIVE POWER PHASE C (kVAR)
APPARENT POWER PHASE A (kVA),APPARENT POWER PHASE A (kVA)
APPARENT POWER PHASE B (kVA),APPARENT POWER PHASE B (kVA)
APPARENT POWER PHASE C (kVA),APPARENT POWER PHASE C (kVA)
POWER FACTOR PHASE A (-),POWER FACTOR PHASE A (-)
POWER FACTOR PHASE B (-),POWER FACTOR PHASE B (-)
POWER FACTOR PHASE C (-),POWER FACTOR PHASE C (-)
VOLTAGE PHASE A-B (V),VOLTAGE PHASE A-B (V)
VOLTAGE PHASE B-C (V),VOLTAGE PHASE B-C (V)
VOLTAGE PHASE A-C (V),VOLTAGE PHASE A-C (V)
VOLTAGE PHASE A-N (V),VOLTAGE PHASE A-N (V)
VOLTAGE PHASE B-N (V),VOLTAGE PHASE B-N (V)
VOLTAGE PHASE C-N (V),VOLTAGE PHASE C-N (V)
CURRENT PHASE A (A),CURRENT PHASE A (A)
CURRENT PHASE B (A),CURRENT PHASE B (A)
CURRENT PHASE C (A),CURRENT PHASE C (A)"""

REGISTER_MAP = """Register Name,Address,Type,Units,Writable,Transform,Table,Mixed Endian
ACCUMULATED REAL ENERGY NET (IMPORT-EXPORT) (kWh),399,float,kWh,TRUE,,analog_output_holding_registers,TRUE
REAL ENERGY QUADRANTS 1-4 IMPORT (kWh),401,float,kWh,TRUE,,analog_output_holding_registers,TRUE
REAL ENERGY QUADRANTS 2-3 EXPORT (kWh),403,float,kWh,TRUE,,analog_output_holding_registers,TRUE
REACTIVE ENERGY - QUADRANT 1 IMPORT (kVARh),405,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
REACTIVE ENERGY - QUADRANT 2 IMPORT (kVARh),407,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
REACTIVE ENERGY - QUADRANT 3 EXPORT (kVARh),409,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
REACTIVE ENERGY - QUADRANT 4 EXPORT (kVARh),411,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
APPARENT ENERGY NET (IMPORT/EXPORT) (kVAh),413,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
APPARENT QUADRANTS 1-4 IMPORT (kVAh),415,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
APPARENT QUADRANTS 2-3 EXPORT (kVAh),417,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
TOTAL INSTANTANEOUS REAL POWER (kW),419,float,kW,TRUE,,analog_output_holding_registers,TRUE
TOTAL INSTANTANEOUS REACTIVE POWER (kVAR),421,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
TOTAL INSTANTANEOUS APPARENT POWER (kVA),423,float,kVA,TRUE,,analog_output_holding_registers,TRUE
TOTAL POWER FACTOR (-),425,float,,TRUE,,analog_output_holding_registers,TRUE
AVERAGE VOLTAGE L-L (V),427,float,V,TRUE,,analog_output_holding_registers,TRUE
AVERAGE VOLTAGE L-N (V),429,float,V,TRUE,,analog_output_holding_registers,TRUE
AVERAGE CURRENT (A),431,float,A,TRUE,,analog_output_holding_registers,TRUE
FREQUENCY (Hz),433,float,Hz,TRUE,,analog_output_holding_registers,TRUE
TOTAL REAL POWER PRESENT DEMAND (kW),435,float,kW,TRUE,,analog_output_holding_registers,TRUE
TOTAL REACTIVE POWER PRESENT DEMAND (kVAR),437,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
TOTAL APPARENT POWER PRESENT DEMAND (kVA),439,float,kVA,TRUE,,analog_output_holding_registers,TRUE
TOTAL REAL POWER MAX. DEMAND IMPORT (kW),441,float,kW,TRUE,,analog_output_holding_registers,TRUE
TOTAL REACTIVE POWER MAX. DEMAND IMPORT (kVAR),443,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
TOTAL APPARENT POWER MAX. DEMAND IMPORT (kVA),445,float,kVA,TRUE,,analog_output_holding_registers,TRUE
TOTAL REAL POWER MAX. DEMAND EXPORT (kW),447,float,kW,TRUE,,analog_output_holding_registers,TRUE
TOTAL REACTIVE POWER MAX. DEMAND EXPORT (kVAR),449,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
TOTAL APPARENT POWER MAX. DEMAND EXPORT (kVA),451,float,kVA,TRUE,,analog_output_holding_registers,TRUE
PULSE COUNTER 1 (-),453,float,,TRUE,,analog_output_holding_registers,TRUE
PULSE COUNTER 2 (-),455,float,,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE A IMPORT (kWh),457,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE B IMPORT (kWh),459,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE C IMPORT (kWh),461,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE A EXPORT (kWh),463,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE B EXPORT (kWh),465,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED REAL ENERGY PHASE C EXPORT (kWh),467,float,kWh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q1 REACTIVE ENERGY PHASE A IMPORT (kVARh),469,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q1 REACTIVE ENERGY PHASE B IMPORT (kVARh),471,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q1 REACTIVE ENERGY PHASE C IMPORT (kVARh),473,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q2 REACTIVE ENERGY PHASE A IMPORT (kVARh),475,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q2 REACTIVE ENERGY PHASE B IMPORT (kVARh),477,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q2 REACTIVE ENERGY PHASE C IMPORT (kVARh),479,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q3 REACTIVE ENERGY PHASE A EXPORT (kVARh),481,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q3 REACTIVE ENERGY PHASE B EXPORT (kVARh),483,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q3 REACTIVE ENERGY PHASE C EXPORT (kVARh),485,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q4 REACTIVE ENERGY PHASE A EXPORT (kVARh),487,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q4 REACTIVE ENERGY PHASE B EXPORT (kVARh),489,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED Q4 REACTIVE ENERGY PHASE C EXPORT (kVARh),491,float,kVARh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE A IMPORT (kVAh),493,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE B IMPORT (kVAh),495,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE C IMPORT (kVAh),497,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE A EXPORT (kVAh),499,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE B EXPORT (kVAh),501,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
ACCUMULATED APPARENT ENERGY PHASE C EXPORT (kVAh),503,float,kVAh,TRUE,,analog_output_holding_registers,TRUE
REAL POWER PHASE A (kW),505,float,kW,TRUE,,analog_output_holding_registers,TRUE
REAL POWER PHASE B (kW),507,float,kW,TRUE,,analog_output_holding_registers,TRUE
REAL POWER PHASE C (kW),509,float,kW,TRUE,,analog_output_holding_registers,TRUE
REACTIVE POWER PHASE A (kVAR),511,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
REACTIVE POWER PHASE B (kVAR),513,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
REACTIVE POWER PHASE C (kVAR),515,float,kVAR,TRUE,,analog_output_holding_registers,TRUE
APPARENT POWER PHASE A (kVA),517,float,kVA,TRUE,,analog_output_holding_registers,TRUE
APPARENT POWER PHASE B (kVA),519,float,kVA,TRUE,,analog_output_holding_registers,TRUE
APPARENT POWER PHASE C (kVA),521,float,kVA,TRUE,,analog_output_holding_registers,TRUE
POWER FACTOR PHASE A (-),523,float,,TRUE,,analog_output_holding_registers,TRUE
POWER FACTOR PHASE B (-),525,float,,TRUE,,analog_output_holding_registers,TRUE
POWER FACTOR PHASE C (-),527,float,,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE A-B (V),529,float,V,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE B-C (V),531,float,V,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE A-C (V),533,float,V,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE A-N (V),535,float,V,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE B-N (V),537,float,V,TRUE,,analog_output_holding_registers,TRUE
VOLTAGE PHASE C-N (V),539,float,V,TRUE,,analog_output_holding_registers,TRUE
CURRENT PHASE A (A),541,float,A,TRUE,,analog_output_holding_registers,TRUE
CURRENT PHASE B (A),543,float,A,TRUE,,analog_output_holding_registers,TRUE
CURRENT PHASE C (A),545,float,A,TRUE,,analog_output_holding_registers,TRUE"""

# Register values dictionary for testing set_point and get_point
registers_dict = {"ACCUMULATED REAL ENERGY NET (IMPORT-EXPORT) (kWh)": 74.0,
                  "REAL ENERGY QUADRANTS 1-4 IMPORT (kWh)": 73.0,
                  "REAL ENERGY QUADRANTS 2-3 EXPORT (kWh)": 72.0,
                  "REACTIVE ENERGY - QUADRANT 1 IMPORT (kVARh)": 71.0,
                  "REACTIVE ENERGY - QUADRANT 2 IMPORT (kVARh)": 70.0,
                  "REACTIVE ENERGY - QUADRANT 3 EXPORT (kVARh)": 69.0,
                  "REACTIVE ENERGY - QUADRANT 4 EXPORT (kVARh)": 68.0,
                  "APPARENT ENERGY NET (IMPORT/EXPORT) (kVAh)": 67.0,
                  "APPARENT QUADRANTS 1-4 IMPORT (kVAh)": 66.0,
                  "APPARENT QUADRANTS 2-3 EXPORT (kVAh)": 65.0,
                  "TOTAL INSTANTANEOUS REAL POWER (kW)": 64.0,
                  "TOTAL INSTANTANEOUS REACTIVE POWER (kVAR)": 63.0,
                  "TOTAL INSTANTANEOUS APPARENT POWER (kVA)": 62.0,
                  "TOTAL POWER FACTOR (-)": 61.0,
                  "AVERAGE VOLTAGE L-L (V)": 60.0,
                  "AVERAGE VOLTAGE L-N (V)": 59.0,
                  "AVERAGE CURRENT (A)": 58.0,
                  "FREQUENCY (Hz)": 57.0,
                  "TOTAL REAL POWER PRESENT DEMAND (kW)": 56.0,
                  "TOTAL REACTIVE POWER PRESENT DEMAND (kVAR)": 55.0,
                  "TOTAL APPARENT POWER PRESENT DEMAND (kVA)": 54.0,
                  "TOTAL REAL POWER MAX. DEMAND IMPORT (kW)": 53.0,
                  "TOTAL REACTIVE POWER MAX. DEMAND IMPORT (kVAR)": 52.0,
                  "TOTAL APPARENT POWER MAX. DEMAND IMPORT (kVA)": 51.0,
                  "TOTAL REAL POWER MAX. DEMAND EXPORT (kW)": 50.0,
                  "TOTAL REACTIVE POWER MAX. DEMAND EXPORT (kVAR)": 49.0,
                  "TOTAL APPARENT POWER MAX. DEMAND EXPORT (kVA)": 48.0,
                  "PULSE COUNTER 1 (-)": 47.0,
                  "PULSE COUNTER 2 (-)": 46.0,
                  "ACCUMULATED REAL ENERGY PHASE A IMPORT (kWh)": 45.0,
                  "ACCUMULATED REAL ENERGY PHASE B IMPORT (kWh)": 44.0,
                  "ACCUMULATED REAL ENERGY PHASE C IMPORT (kWh)": 43.0,
                  "ACCUMULATED REAL ENERGY PHASE A EXPORT (kWh)": 42.0,
                  "ACCUMULATED REAL ENERGY PHASE B EXPORT (kWh)": 41.0,
                  "ACCUMULATED REAL ENERGY PHASE C EXPORT (kWh)": 40.0,
                  "ACCUMULATED Q1 REACTIVE ENERGY PHASE A IMPORT (kVARh)": 39.0,
                  "ACCUMULATED Q1 REACTIVE ENERGY PHASE B IMPORT (kVARh)": 38.0,
                  "ACCUMULATED Q1 REACTIVE ENERGY PHASE C IMPORT (kVARh)": 37.0,
                  "ACCUMULATED Q2 REACTIVE ENERGY PHASE A IMPORT (kVARh)": 36.0,
                  "ACCUMULATED Q2 REACTIVE ENERGY PHASE B IMPORT (kVARh)": 35.0,
                  "ACCUMULATED Q2 REACTIVE ENERGY PHASE C IMPORT (kVARh)": 34.0,
                  "ACCUMULATED Q3 REACTIVE ENERGY PHASE A EXPORT (kVARh)": 33.0,
                  "ACCUMULATED Q3 REACTIVE ENERGY PHASE B EXPORT (kVARh)": 32.0,
                  "ACCUMULATED Q3 REACTIVE ENERGY PHASE C EXPORT (kVARh)": 31.0,
                  "ACCUMULATED Q4 REACTIVE ENERGY PHASE A EXPORT (kVARh)": 30.0,
                  "ACCUMULATED Q4 REACTIVE ENERGY PHASE B EXPORT (kVARh)": 29.0,
                  "ACCUMULATED Q4 REACTIVE ENERGY PHASE C EXPORT (kVARh)": 28.0,
                  "ACCUMULATED APPARENT ENERGY PHASE A IMPORT (kVAh)": 27.0,
                  "ACCUMULATED APPARENT ENERGY PHASE B IMPORT (kVAh)": 26.0,
                  "ACCUMULATED APPARENT ENERGY PHASE C IMPORT (kVAh)": 25.0,
                  "ACCUMULATED APPARENT ENERGY PHASE A EXPORT (kVAh)": 24.0,
                  "ACCUMULATED APPARENT ENERGY PHASE B EXPORT (kVAh)": 23.0,
                  "ACCUMULATED APPARENT ENERGY PHASE C EXPORT (kVAh)": 22.0,
                  "REAL POWER PHASE A (kW)": 21.0,
                  "REAL POWER PHASE B (kW)": 20.0,
                  "REAL POWER PHASE C (kW)": 19.0,
                  "REACTIVE POWER PHASE A (kVAR)": 18.0,
                  "REACTIVE POWER PHASE B (kVAR)": 17.0,
                  "REACTIVE POWER PHASE C (kVAR)": 16.0,
                  "APPARENT POWER PHASE A (kVA)": 15.0,
                  "APPARENT POWER PHASE B (kVA)": 14.0,
                  "APPARENT POWER PHASE C (kVA)": 13.0,
                  "POWER FACTOR PHASE A (-)": 12.0,
                  "POWER FACTOR PHASE B (-)": 11.0,
                  "POWER FACTOR PHASE C (-)": 10.0,
                  "VOLTAGE PHASE A-B (V)": 9.0,
                  "VOLTAGE PHASE B-C (V)": 8.0,
                  "VOLTAGE PHASE A-C (V)": 7.0,
                  "VOLTAGE PHASE A-N (V)": 6.0,
                  "VOLTAGE PHASE B-N (V)": 5.0,
                  "VOLTAGE PHASE C-N (V)": 4.0,
                  "CURRENT PHASE A (A)": 3.0,
                  "CURRENT PHASE B (A)": 2.0,
                  "CURRENT PHASE C (A)": 1.0}


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
    ModbusClient = Catalog()['battery_meter'].get_class()

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

    def test_scrape_all(self, agent):
        for key in registers_dict.keys():
            self.set_point(agent, 'modbus_tk', key, registers_dict[key])
            assert self.get_point(agent, 'modbus_tk', key) == registers_dict[key]

        assert type(self.scrape_all(agent, 'modbus_tk')) is dict
