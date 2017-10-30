# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}
"""
    Modbus client wrapper.

    The Client class provides a higher level interface to the modbus_tk library.  The Client represents
    a "Modbus Master" and communicates with a "Modbus Slave" over TCP or Serial/RS-485.

    The Client is intended to be subclassed and extended with one or more Field instances that
    represent the modbus register map.  Subclasses may be created programmatically or loaded
    from pre-defined Modbus "Maps".

    A Client subclass is created programmatically like this:

        class MyModbusMaster (Client):
            register_1 = Field(...)
            register_2 = Field(...)
            ...etc...

    The maps package generates Subclasses for well-known register maps defined in CSV files.

        MyModbusClient = maps.Catalog()['client_name'].get_class()


"""
from define import *
from datetime import datetime
import collections
import struct
import serial
import six
import logging
import modbus_tk.defines as modbus_constants
import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.modbus_rtu as modbus_rtu

logger = logging.getLogger(__name__)

# In cache representation of modbus field.
Datum = collections.namedtuple('Datum', ('value', 'timestamp'))

class Field(object):
    """Describes/defines a logical modbus field.

        A logical field may be mapped to one or more modbus registers or coils.

        Field implemements the 'descriptor' pattern with __get__ and __set__ methods.

        A field defines the modbus table, address offset, length and datatype of the
        logical field.  Getting and setting of field values is as simple as
        attribute get/set (via to descriptor pattern).

        myModbusClientInstance.float_field_1 = 3.14159
        ...
        myModbusClientInstance.write_all()    # Writes all modified fields to the modbus slave.

        Getting the value is simpler:

        myModbusClientInstance.float_field_1  #Reads from cache or from modbus slave.

    """

    def __init__(self, name, address, datatype, units, precision, transform, table, op_mode):
        self.name = name
        self.address = address
        self.type = datatype
        self.units = units
        self.precision = precision
        self.transform = transform
        self.table = table
        self.op_mode = op_mode

    def value_for_transport(self, value):
        """
            Modbus deals only in 2-byte registers.  4-byte types must be
            sent as 2 x 2-byte values. These are created using the
            Python struct library.

            Before any unpacking, we transform the value if its transform
            function has defined an inverse.

            :param value: the value to be transformed into a binary string

        """
        transformed_value = value

        if hasattr(self.transform, 'inverse'):
            try:
                transformed_value = self.transform.inverse(value)
            except ZeroDivisionError:
                transformed_value = 0

        return transformed_value

    def values_for_transport(self, value):
        """Like value_for_transport, but always returns a list"""
        values = list()
        a_value = self.value_for_transport(value)
        if type(a_value) in (list, tuple):
            values.extend(a_value)
        else:
            values.append(a_value)
        return values

    @classmethod
    def default_holding_register(cls,  name, address, type, units, transform):
        """Shortcut for common definition format."""
        return cls(name, address, type, units, 1, transform, REGISTER_READ_WRITE, OP_MODE_READ_WRITE)

    @property
    def absolute_address(self):
        return self.address + TABLE_ADDRESS[self.table]

    def transform_value(self, value):
        """
            Return the transformed value of the field or just
            the value if no transform has been defined.

        :param value: value to be transformed.
        :return:
        """
        return value if self.transform is None else self.transform(value)

    @property
    def writable(self):
        return self.table in (COIL_READ_WRITE, REGISTER_READ_WRITE) and \
               self.op_mode in (OP_MODE_READ_WRITE, OP_MODE_WRITE_ONLY)
    @property
    def single_write_function_code(self):
        if self.table == REGISTER_READ_WRITE:
            return modbus_constants.WRITE_SINGLE_REGISTER
        elif self.table == COIL_READ_WRITE:
            return modbus_constants.WRITE_SINGLE_COIL
        else:
            raise Exception("Unknown table type or write operation not supported : {0}".format(self.table))

    def __get__(self, instance, owner):
        """
        Read one field from the modbus slave.
        :param field: The Field to be read.
        :return: Field values transformed according to specification in Field()
        """
        datum = instance.get_data(self)
        if datum is None or (datetime.utcnow() - datum.timestamp).total_seconds()*1000 >= instance.latency:
            instance.fetch_field(self)
            datum = instance.get_data(self)
        return datum.value if datum else None

    def __set__(self, instance, value):
        # If value is None, its a No Op, the field is not updated
        if value is not None:
            if value < 0 and self.type in (USHORT, UINT, UINT64):
                raise ValueError("Attempting to assign negative value to unisgned type.")
            if not instance._ignore_op_mode and self.op_mode == OP_MODE_READ_ONLY:
                raise ValueError("Attempting to write read-only field.")
            instance._pending_writes[self] = value

    def fix_address(self, address_style):
        # Translate modbus addressing to absolute offsets
        if address_style in (ADDRESS_MODBUS, ADDRESS_OFFSET_PLUS_ONE):

            if address_style == ADDRESS_MODBUS:
                self.address = self.address - TABLE_ADDRESS[self.table]
                if self.address < 0 or self.address > 10000:
                    raise Exception("Modbus address out of range for table.")
            elif address_style == ADDRESS_OFFSET_PLUS_ONE:
                self.address = self.address - 1
                if self.address < 0 or self.address > 10000:
                    raise Exception("Modbus address out of range for table.")

class Request (object):
    """
        Represents a contiguous set of logical fields, registers or coils.  The first
        field starts at self.address.

        Request is used to query a collection of fields, possibly of different datatypes,
        in a single modbus request.

    """

    def __init__(self, name=None, table=None, address=0, count=0, data_format='>', fields=None):
        self.table = table
        self.address = address
        self.count = count
        self.data_format = data_format
        self.fields = fields if fields else list()
        self.name = name

    def table_name(self):
        """Returns display name of modbus table to be accessed by request"""

        if self.table == REGISTER_READ_WRITE:
            return "REGISTER_READ_WRITE"
        elif self.table == REGISTER_READ_ONLY:
            return "REGISTER_READ_ONLY"
        elif self.table == COIL_READ_WRITE:
            return "COIL_READ_WRITE"
        elif self.table == COIL_READ_ONLY:
            return "COIL_READ_ONLY"
        else:
            return "UNKNOWN"

    def __str__(self):
        return u"<Request: {0} - {1}[{2}] x {3} | {4}".format(
            self.name,
            self.table_name(),
            self.address,
            self.count,
            self.data_format
        )

    @property
    def read_function_code(self):
        """Returns a modbus read function code appropriate for the table."""

        if self.table == REGISTER_READ_WRITE:
            modbus_function_code = modbus_constants.READ_HOLDING_REGISTERS
        elif self.table == REGISTER_READ_ONLY:
            modbus_function_code = modbus_constants.READ_INPUT_REGISTERS
        elif self.table == COIL_READ_WRITE:
            modbus_function_code = modbus_constants.READ_COILS
        elif self.table == COIL_READ_ONLY:
            modbus_function_code = modbus_constants.READ_DISCRETE_INPUTS
        else:
            raise Exception("Unknown table type : {0}".format(self.table))

        return modbus_function_code

    @property
    def write_function_code(self):
        """Returns a modbus write function code appropriate for the table."""

        if self.table == REGISTER_READ_WRITE:
            # WRITE_MULTIPLE is used unless client cannot support it, see _write_single_values in Client.__init__
            return modbus_constants.WRITE_MULTIPLE_REGISTERS
        elif self.table == COIL_READ_WRITE:
            # @TODO Temp hack around COIL write problem.
            return modbus_constants.WRITE_SINGLE_COIL if self.count == 1 \
                else modbus_constants.WRITE_MULTIPLE_COILS
        else:
            raise Exception("Unknown table type or write operation not supported : {0}".format(self.table))

    @property
    def formatting(self):
        """
            Provide a struct library format string for non-COIL data types.

            For COILS, we leave the formatting to modbus-tk.
        """
        if self.table not in (COIL_READ_ONLY, COIL_READ_WRITE):
            return self.data_format
        else:
            return None

def compile_requests(fields, byte_order):
    """

    Creates a set of Modbus requests for the fields provided.  The fields
    are sorted by table and address so that a minimum number of
    requests can be created.

    These requests are used for both reading and writing.

    :param fields: List of fields sorted by address.
    :param byte_order: Byte order of the modbus slave.
    :return: List of Requests
    """

    register_count = 0
    requests = list()

    if not fields:
        return requests

    fields.sort(key=lambda f: f.table * 100000 + f.address)

    # Set up the initial request before starting the loop
    current_request = None
    next_address = None

    for f in fields:
        # Decide if we need to start a new request
        if ((current_request is None) or
                (current_request.table != f.table or next_address != f.address) or
                (f.type[LENGTH] > 1)):
            current_request = Request(name=f.name, table=f.table, address=f.address, data_format=byte_order)
            requests.append(current_request)
            next_address = f.address

        # Add the field to the current request.
        # current_request.data_format += (f.type[FORMAT] * f.type[LENGTH])
        try:
            struct_format = str(f.type[LENGTH]) + f.type[FORMAT]
        except TypeError:
            print(f)
            print(f)
        struct_size = struct.calcsize(struct_format)
        if struct_size % 2 == 1:
            struct_size += 1
        current_request.data_format += struct_format
        # current_request.count += f.type[SIZE] * f.type[LENGTH]
        current_request.count += struct_size / 2
        current_request.fields.append(f)
        next_address += struct_size / 2

    return requests

class Client (object):

    """
    Generic modbus master.  It functions as a traditional "client" making requests of
    a modbus slave which acts like a traditional "server".

    Subclass this class with Field class variables.  See module description above.
    """

    byte_order = BIG_ENDIAN
    addressing = ADDRESS_OFFSET

    __meta = None

    @classmethod
    def _build_meta(cls):
        if cls.__meta is None:
            meta = dict()
            for name, obj in cls.__dict__.items():
                if type(obj) == Field:
                    obj.fix_address(getattr(cls, 'addressing'))
                    meta[name] = obj

            # Maintain a list of fields sorted by address (ascending)
            meta[META_FIELDS] = list(meta.values())                         # Turns Python3 view into a list.
            meta[META_FIELDS].sort(key=lambda f : f.address)
            meta[META_REQUESTS] = compile_requests(meta[META_FIELDS], cls.byte_order)
            # Dictionary for easy lookup of the request that corresponds to a field.
            meta[META_REQUEST_MAP] = { field:request for request in meta[META_REQUESTS] for field in request.fields }
            cls.__meta = meta
        return cls.__meta

    def __init__(self, *args, **kwargs):
        """
            Sets up the Modbus Master to communicate with a slave.  Supports ModbusTCP and ModbusRTU depending
            on the values provided in device_address and port.  If port == None, ModbusRTU is used.

        :param device_address:  IP address if using ModbusTCP, a device id (eg /dev/ttyAMA0) if using ModbusRTU
        :param port: Port number for ModbusTCP, None if using ModbusRTU
        :param slave_address: Unique ID of the Modbus slave.
        :param baud: Baud rate for ModbusRTU.
        :param latency: Controls the cache refresh rate.  Max age of data values read from slave.
        :param ignore_op_mode: Turns read/write error checking off or on.  Deprecated.
        :param timeout_in_sec: Time to wait for a response from the slave.
        :param verbose:
        :param write_single_values: Write registers or coils one value at a time (WRITE_SINGLE_REGISTER, etc.).
        :return:
        """

        # Build up metadata dictionaries from the Fields defined on the class
        self._build_meta()

        # Support for legacy usage where device_address, port are passed in constructor.
        device_address = None if len(args) == 0 else args[0]
        port = None if len(args) < 2 or args[1] is None else int(args[1])
        self.slave_address = None if len(args) < 3 or args[2] is None else int(args[2])

        # Optional keyword arguments

        if self.slave_address is None:
            self.slave_address = kwargs.pop('slave_address', 1)
        self.latency = kwargs.pop('latency', 1000)
        self._ignore_op_mode = kwargs.pop('ignore_op_mode', False) #Protection against unintended writes

        # Some modbus clients do not support the WRITE_MULTIPLE_REGISTERS function call.
        self._write_single_values = kwargs.pop('write_single_values', False)

        baud = kwargs.pop('baudrate', 19200)
        bytesize = kwargs.pop('bytesize', 8)
        parity = kwargs.pop('parity', 'N')
        stopbits = kwargs.pop('stopbits', 1)
        timeout_in_sec = kwargs.pop('timeout_in_sec', 1.0)
        verbose = kwargs.pop('verbose', False)

        if device_address:
            if port is not None:
                self.client = modbus_tcp.TcpMaster(host=device_address, port=port, timeout_in_sec=timeout_in_sec)
            else:
                self.client = modbus_rtu.RtuMaster(
                    serial.Serial(device_address,
                                  baudrate=baud,
                                  bytesize=bytesize,
                                  parity=parity,
                                  stopbits=stopbits,
                                  xonxoff=0)
                )
                self.client.set_timeout(1.0)
            self.client.set_verbose(verbose)

        self._data = collections.OrderedDict()
        self._pending_writes = dict()
        self._error_count = 0

    def set_transport_tcp(self, hostname, port, timeout_in_sec=1.0):
        self.client = modbus_tcp.TcpMaster(host=hostname, port=int(port), timeout_in_sec=timeout_in_sec)
        return self

    def set_transport_rtu(self, device, baudrate, bytesize, parity, stopbits, xonxoff):
        self.client = modbus_rtu.RtuMaster(
            serial.Serial(device,
                          baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, xonxoff=xonxoff,
                          rtscts=False, writeTimeout=None, dsrdtr=False, interCharTimeout=None)
        )
        self.client.set_timeout(1.0)
        return self

    def __str__(self):
        return u'data: {0}\npending_writes: {1}'.format(self._data, self._pending_writes)

    def pprint(self):
        response = "pending writes: \n"
        for f,v in six.iteritems(self._pending_writes):
            response = response + "\t{0} : {1}".format(f,v)
        return response

    @property
    def has_pending_writes(self):
        return bool(self._pending_writes)

    def requests (self):
        return self.__meta[META_REQUESTS]

    def fields(self):
        return self.__meta[META_FIELDS]

    def field_by_name(self, name):
        return self.__meta.get(name, None)

    @property
    def _fields(self):
        return self.__meta['']

    def get_data(self, field):
        return self._data.get(field, None)

    @property
    def write_single_values(self):
        return self._write_single_values

    def get_request(self, field):
        return self.__meta[META_REQUEST_MAP].get(field, None)

    def read_request(self, request):
        logger.debug("Requesting: %s", request)
        try:
            results = self.client.execute(
                self.slave_address,
                request.read_function_code,
                request.address,
                quantity_of_x=request.count,
                data_format=request.formatting,
                threadsafe=False
            )
            # @TODO - this additional param, added above is causing problemss: expected_length=request.count+5
            now = datetime.utcnow()
            if len(request.fields) == 1 and request.fields[0].type[LENGTH] > 1 and request.fields[0].type[FORMAT] != 's':
                field = request.fields[0]
                # Array
                field_values = {
                    field : Datum([field.transform_value(r) for r in results], now)
                }
            else:
                # Everything else
                field_values = collections.OrderedDict(
                    [(field, Datum(field.transform_value(value), now)) for field, value in six.moves.zip(request.fields, results)]
                )
            self._data.update(field_values)
        except AttributeError as err:
            logger.warning("modbus read_all() failure on request: %s\tError: %s", request, err)

    def read_all(self):
        requests = self.__meta[META_REQUESTS]
        self._data.clear()
        for r in requests:
            self.read_request(r)

    def dump_all(self):
        self.read_all()
        return [(f, d.value, d.timestamp) for f,d in six.iteritems(self._data)]

    def write_all(self):
        logger.debug("In write_all")
        fields = list(self._pending_writes.keys())
        if self.write_single_values:
            # Convert values if necessary for transport as modbus supported types.
            for f in fields:
                values = f.values_for_transport(self._pending_writes.pop(f))
                logger.debug("Writing modbus data for field %s: %s", f.name, values)
                self.client.execute(
                    self.slave_address,
                    f.single_write_function_code,
                    f.address,
                    quantity_of_x=len(values),
                    output_value=values[0] if len(values) == 1 else values,
                    threadsafe=False
                )
        else:
            requests = compile_requests(fields, self.byte_order)
            for r in requests:
                values = list()
                # Convert values if necessary for transport as modbus supported types.
                for f in r.fields:
                    value = f.value_for_transport(self._pending_writes.pop(f))
                    if type(value) in (list, tuple):
                        values.extend(value)
                    else:
                        values.append(value)
                # Temp workaround for COIL write problem.
                if r.write_function_code == modbus_constants.WRITE_SINGLE_COIL:
                    values = values[0]
                self.client.execute(
                    self.slave_address,
                    r.write_function_code,
                    r.address,
                    quantity_of_x=r.count,
                    output_value=values,
                    data_format=r.formatting,
                    threadsafe=False
                )

        if self._pending_writes:
            logger.warning("Did not write ALL values!")
        self._pending_writes.clear()
        self._data.clear()

    def fetch_field(self, field):
        """
            Make a modbus request for the block containing field.
        """
        request = self.get_request(field)
        if request:
            self.read_request(request)

    def close(self):
        self.client.close()
