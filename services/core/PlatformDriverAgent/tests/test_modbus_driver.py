import pytest
import gevent
import logging
import time
from struct import pack, unpack

from volttron.platform import get_services_core, jsonapi
from platform_driver.interfaces.modbus_tk.server import Server
from platform_driver.interfaces.modbus_tk.client import Client, Field
from platform_driver.interfaces.modbus_tk import helpers
from volttrontesting.utils.utils import get_rand_ip_and_port
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

logger = logging.getLogger(__name__)

IP, _port = get_rand_ip_and_port().split(":")
PORT = int(_port)

DRIVER_CONFIG = {
    "driver_config": {
        "device_address": IP,
        "port": PORT,
        "slave_id": 1
    },
    "driver_type": "modbus",
    "registry_config": "config://modbus.csv",
    "interval": 120,
    "timezone": "UTC"
}

# This registry configuration contains only required fields
REGISTRY_CONFIG_STRING = """Volttron Point Name,Units,Modbus Register,Writable,Point Address
BigUShort,PPM,>H,TRUE,0
BigUInt,PPM,>I,TRUE,1
BigULong,PPM,>Q,TRUE,3
BigShort,PPM,>h,TRUE,7
BigInt,PPM,>i,TRUE,8
BigFloat,PPM,>f,TRUE,10
BigLong,PPM,>q,TRUE,12
LittleUShort,PPM,<H,TRUE,100
LittleUInt,PPM,<I,TRUE,101
LittleULong,PPM,<Q,TRUE,103
LittleShort,PPM,<h,TRUE,107
LittleInt,PPM,<i,TRUE,108
LittleFloat,PPM,<f,TRUE,110
LittleLong,PPM,<q,TRUE,112"""

# Register values dictionary for testing set_point and get_point
registers_dict = {"BigUShort": 2**16-1,
                  "BigUInt": 2**32-1,
                  "BigULong": 2**64-1,
                  "BigShort": -(2**16)//2,
                  "BigInt": -(2**32)//2,
                  "BigFloat": -1234.0,
                  "BigLong": -(2**64)//2,
                  "LittleUShort": 0,
                  "LittleUInt": 0,
                  "LittleULong": 0,
                  "LittleShort": (2**16)//2-1,
                  "LittleInt": (2**32)//2-1,
                  "LittleFloat": 1.0,
                  "LittleLong": (2**64)//2-1
                  }


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
    """
    Build PlatformDriverAgent, add Modbus driver & csv configurations
    """

    # Build platform driver agent
    md_agent = volttron_instance.build_agent(identity="test_md_agent")
    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(md_agent.core.publickey, capabilities)
    gevent.sleep(1)
    # Clean out platform driver configurations
    # wait for it to return before adding new config
    md_agent.vip.rpc.call('config.store',
                          'manage_delete_store',
                          PLATFORM_DRIVER).get()

    # Add driver configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          PLATFORM_DRIVER,
                          'devices/modbus',
                          jsonapi.dumps(DRIVER_CONFIG),
                          config_type='json')

    # Add csv configurations
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          PLATFORM_DRIVER,
                          'modbus.csv',
                          REGISTRY_CONFIG_STRING,
                          config_type='csv')

    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={},
        start=True)

    gevent.sleep(10)  # wait for the agent to start and start the devices

    def stop():
        """Stop platform driver agent
        """
        volttron_instance.stop_agent(platform_uuid)
        md_agent.core.stop()

    request.addfinalizer(stop)
    return md_agent


class PPSPi32Client(Client):
    """
    Define some registers to PPSPi32Client
    """

    def __init__(self, *args, **kwargs):
        super(PPSPi32Client, self).__init__(*args, **kwargs)

    byte_order = helpers.BIG_ENDIAN
    addressing = helpers.ADDRESS_OFFSET

    BigUShort = Field("BigUShort", 0, helpers.USHORT, 'PPM', 2, helpers.no_op,
                      helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigUInt = Field("BigUInt", 1, helpers.UINT, 'PPM', 2, helpers.no_op,
                    helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigULong = Field("BigULong", 3, helpers.UINT64, 'PPM', 2, helpers.no_op,
                     helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigShort = Field("BigShort", 7, helpers.SHORT, 'PPM', 2, helpers.no_op,
                     helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigInt = Field("BigInt", 8, helpers.INT, 'PPM', 2, helpers.no_op,
                   helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigFloat = Field("BigFloat", 10, helpers.FLOAT, 'PPM', 2, helpers.no_op,
                     helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigLong = Field("BigLong", 12, helpers.INT64, 'PPM', 2, helpers.no_op,
                    helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleUShort = Field(
        "LittleUShort", 100, helpers.USHORT, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleUInt = Field(
        "LittleUInt", 101, helpers.UINT, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleULong = Field(
        "LittleULong", 103, helpers.UINT64, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleShort = Field(
        "LittleShort", 107, helpers.SHORT, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleInt = Field(
        "LittleInt", 108, helpers.INT, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleFloat = Field(
        "LittleFloat", 110, helpers.FLOAT, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleLong = Field(
        "LittleLong", 112, helpers.INT64, 'PPM', 2, helpers.no_op,
        helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)


@pytest.fixture
def modbus_server(request):
    modbus_server = Server(address=IP, port=PORT)
    modbus_server.define_slave(1, PPSPi32Client, unsigned=True)

    # Set values for registers from server as the default values
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigUShort"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigUInt"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigULong"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigShort"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigInt"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigFloat"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("BigLong"), 0)
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleUShort"), unpack('<H', pack('>H', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleUInt"), unpack('<HH', pack('>I', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleULong"), unpack('<HHHH', pack('>Q', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleShort"), unpack('<H', pack('>h', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleInt"), unpack('<HH', pack('>i', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleFloat"), unpack('<HH', pack('>f', 0)))
    modbus_server.set_values(1, PPSPi32Client().field_by_name("LittleLong"), unpack('<HHHH', pack('>q', 0)))

    modbus_server.start()
    time.sleep(1)
    yield modbus_server
    modbus_server.stop()


@pytest.mark.usefixtures("modbus_server")
class TestModbusDriver:
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
        return agent.vip.rpc.call(PLATFORM_DRIVER, 'get_point', 'modbus', point_name).get(timeout=10)

    def set_point(self, agent, point_name, point_value):
        """
        Issue a set_point RPC call for the named point and value, and return
        the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param point_value: The value to set on the point.
        @return: The returned value from the RPC call.
        """
        return agent.vip.rpc.call(PLATFORM_DRIVER, 'set_point', 'modbus', point_name, point_value).get(timeout=10)

    def scrape_all(self, agent):
        """
        Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @return: The returned value from the RPC call.
        """
        return agent.vip.rpc.call(PLATFORM_DRIVER, 'scrape_all', 'modbus').get(timeout=10)

    def test_default_values(self, agent):
        """
        By default server setting, all registers values are 0
        """
        default_values = self.scrape_all(agent)
        assert type(default_values) is dict

        for key in default_values.keys():
            assert default_values[key] == 0 or 0.0

    def test_set_point(self, agent):
        for key in registers_dict.keys():
            self.set_point(agent, key, registers_dict[key])
            assert self.get_point(agent, key) == registers_dict[key]
        assert self.scrape_all(agent) == registers_dict
