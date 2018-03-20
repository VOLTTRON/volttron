from master_driver.interfaces.modbus_tk.server import Server
from master_driver.interfaces.modbus_tk import helpers
from master_driver.interfaces.modbus_tk.client import Client, Field
from master_driver.interfaces.modbus_tk.maps import Map, Catalog
import serial

from struct import pack, unpack
import logging

logger = logging.getLogger(__name__)


class ModbusTkClient (Client):
    """
        Testing for tcp transport
    """

    byte_order = helpers.BIG_ENDIAN
    addressing = helpers.ADDRESS_OFFSET

    unsigned_short = Field("unsigned_short", 0, helpers.USHORT, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    unsigned_int = Field("unsigned_int", 1, helpers.UINT, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    unsigned_long = Field("unsigned_long", 3, helpers.UINT64, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_short = Field("sample_short", 7, helpers.SHORT, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_int = Field("sample_int", 8, helpers.INT, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_float = Field("sample_float", 10, helpers.FLOAT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_long = Field("sample_long", 12, helpers.INT64, 'PPM', 0, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_bool = Field('sample_bool', 16, helpers.BOOL, 'PPM', 0, helpers.no_op, helpers.COIL_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    sample_str = Field("sample_str", 17, helpers.string(4), "bytes", 4, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)


class WattsOn (Client):
    """
        Testing Stub for WattsOn modbus device.
    """

    byte_order = helpers.BIG_ENDIAN
    addressing = helpers.ADDRESS_OFFSET

    active_power_total = Field.default_holding_register('Active Power Total', 0x200, helpers.FLOAT, "kW", helpers.no_op)
    active_power_A = Field.default_holding_register('Active Power A', 0x232, helpers.FLOAT, "kW", helpers.no_op)
    apparent_power_A = Field.default_holding_register('Apparent Power A', 0x23E, helpers.FLOAT, "kW", helpers.no_op)
    net_total_energy = Field.default_holding_register('Net Total Energy', 0x1100, helpers.FLOAT, "kWh", helpers.no_op)
    voltage_A = Field.default_holding_register('Voltage A', 0x220, helpers.FLOAT, "V", helpers.no_op)
    current_A = Field.default_holding_register('Current A', 0x22C, helpers.FLOAT, "A", helpers.no_op)


class PPSPi32Client (Client):
    """
        Define some regiesters to PPSPi32Client
    """

    def __init__(self, *args, **kwargs):
        super(PPSPi32Client, self).__init__(*args, **kwargs)

    byte_order = helpers.BIG_ENDIAN
    addressing = helpers.ADDRESS_OFFSET

    BigUShort = Field("BigUShort", 0, helpers.USHORT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigUInt = Field("BigUInt", 1, helpers.UINT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigULong = Field("BigULong", 3, helpers.UINT64, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigShort = Field("BigShort", 7, helpers.SHORT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigInt = Field("BigInt", 8, helpers.INT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigFloat = Field("BigFloat", 10, helpers.FLOAT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    BigLong = Field("BigLong", 12, helpers.INT64, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleUShort = Field(
        "LittleUShort", 100, helpers.USHORT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleUInt = Field(
        "LittleUInt", 101, helpers.UINT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleULong = Field(
        "LittleULong", 103, helpers.UINT64, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleShort = Field(
        "LittleShort", 107, helpers.SHORT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleInt = Field(
        "LittleInt", 108, helpers.INT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleFloat = Field(
        "LittleFloat", 110, helpers.FLOAT, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)
    LittleLong = Field(
        "LittleLong", 112, helpers.INT64, 'PPM', 2, helpers.no_op, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)


def watts_on_server():
    # For rtu transport: connect to the Elkor Watts On meter by usb to the RS-485 interface
    # Can define ModbusClient2 by Map or defined the class as ModbusClient1 or ModbusClient2

    # modbus_map = Map(
    #     map_dir='/Users/anhnguyen/repos/kisensum-volttron/volttron/services/core/MasterDriverAgent/master_driver/interfaces/modbus_tk/maps',
    #     addressing='offset', name='watts_on', file='watts_on.csv', endian='big')
    # ModbusClient2 = modbus_map.get_class()

    ModbusClient2 = Catalog()['watts_on'].get_class()

    client = ModbusClient2(slave_address=2, verbose=True)
    client.set_transport_rtu('/dev/tty.usbserial-AL00IEEY',
                             115200,
                             serial.EIGHTBITS,
                             serial.PARITY_NONE,
                             serial.STOPBITS_ONE,
                             False)

    # Get reading values for defined registers
    print dict((field.name, value) for field, value, timestamp in client.dump_all())

    setattr(client, "serial_baud_rate", 115)
    client.write_all()
    print getattr(client, "serial_baud_rate")


if __name__ == '__main__':
    # For tcp transport
    ModbusClient = Catalog()['modbus_tk_test'].get_class()
    server_process = Server(address='127.0.0.1', port=5020)
    server_process.define_slave(1, ModbusClient, unsigned=True)
    server_process.start()

    # For rtu transport
    # watts_on_server()