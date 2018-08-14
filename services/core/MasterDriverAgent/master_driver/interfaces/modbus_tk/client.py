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
from datetime import datetime
import collections
import struct
import serial
import six.moves
import logging
import math

import modbus_tk.defines as modbus_constants
import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.modbus_rtu as modbus_rtu
from modbus_tk.exceptions import ModbusError

import helpers

logger = logging.getLogger(__name__)

# In cache representation of modbus field.
Datum = collections.namedtuple('Datum', ('value', 'timestamp'))


class ModbusFieldException(Exception):
    pass


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

    def __init__(self, name, address, datatype, units, precision, transform, table, op_mode, mixed=False):
        self._name = name
        self._address = address
        self._type = datatype
        self._units = units
        self._precision = precision
        self._transform = transform
        self._table = table
        self._op_mode = op_mode
        self._mixed = mixed

    @property
    def is_struct_format(self):
        """Returns True if the type of this field is described by a struct
            format string, eg:  ">h", instead of one of the field tuples.
        """
        return isinstance(self._type, str) and len(self._type) and \
            self._type[0] in (helpers.BIG_ENDIAN, helpers.LITTLE_ENDIAN)

    @property
    def format_string(self):
        """Generate a struct format string from the type, which may be a tuple
           like:  ("I", 2, 1)   # representing UINT
           or an actual struct format strng like:  ">2h"
        """
        if isinstance(self._type, tuple):
            try:
                return str(self.length) + self._type[helpers.FORMAT]
            except TypeError:
                logger.warning("Undefined type for {0}".format(self))
        elif isinstance(self._type, str):
            return self._type[1:]
        else:
            raise ModbusFieldException("Unknown type string for {0}".format(self))

    @property
    def byte_order(self):
        """Byte order is None (default) unless self._type is a format string
        with the first character specifying byte order.

        :return: byte_order is specified or None
        """
        if self.is_struct_format:
            return self._type[0]

        return None

    @property
    def length(self):
        if isinstance(self._type, tuple):
            return self._type[helpers.LENGTH]
        # Returning length of 1 on struct types (non tuples) which means that they
        # will not be converted into list by modbus client
        return 1

    @property
    def table(self):
        return self._table

    @property
    def address(self):
        return self._address

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def units(self):
        return self._units

    @property
    def precision(self):
        return self._precision

    @property
    def transform(self):
        return self._transform

    @property
    def is_array_field(self):
        return self.length > 1 and self._type[helpers.FORMAT] != 's'

    @property
    def mixed(self):
        return self._mixed

    def value_for_transport(self, value, modbus_client=None):
        """
            Modbus deals only in 2-byte registers.  4-byte types must be
            sent as 2 x 2-byte values. These are created using the
            Python struct library.

            Before any unpacking, we transform the value if its transform
            function has defined an inverse.

            :param value: the value to be transformed into a binary string

        """
        transformed_value = value
        transform_args = [value]
        if hasattr(self._transform, 'inverse'):
            try:
                if hasattr(self._transform, 'register_args'):
                    for reg_name in self._transform.register_args:
                        transform_args.append(getattr(modbus_client, reg_name))

                transformed_value = self._transform.inverse(*transform_args)
            except ZeroDivisionError:
                transformed_value = 0
        return transformed_value

    @classmethod
    def default_holding_register(cls,  name, address, type, units, transform):
        """Shortcut for common definition format."""
        return cls(name, address, type, units, 1, transform, helpers.REGISTER_READ_WRITE, helpers.OP_MODE_READ_WRITE)

    @property
    def absolute_address(self):
        return self.address + helpers.TABLE_ADDRESS[self._table]

    def transform_value(self, value, modbus_client=None):
        """
            Return the transformed value of the field or just
            the value if no transform has been defined.

        :param value: value to be transformed.
        :return:
        """
        transform_args = [value]
        if value == 0:
            return value
        if self._transform:
            if hasattr(self._transform, 'register_args'):
                for reg_name in self._transform.register_args:
                    transform_args.append(getattr(modbus_client, reg_name))

            return self._transform(*transform_args)
        return None

    @property
    def writable(self):
        return self._table in (helpers.COIL_READ_WRITE, helpers.REGISTER_READ_WRITE) and \
               self._op_mode in (helpers.OP_MODE_READ_WRITE, helpers.OP_MODE_WRITE_ONLY)

    @property
    def single_write_function_code(self):
        if self._table == helpers.REGISTER_READ_WRITE:
            return modbus_constants.WRITE_SINGLE_REGISTER
        elif self._table == helpers.COIL_READ_WRITE:
            return modbus_constants.WRITE_SINGLE_COIL
        else:
            raise Exception("Unknown table type or write operation not supported : {0}".format(self._table))

    def __get__(self, instance, owner):
        """
        Return fields data value.
        :param instance: Modbus client
        :param owner: Field object
        :return: Field value from modbus client.
        """
        datum = instance.get_data(self)
        if datum is None or (datetime.utcnow() - datum.timestamp).total_seconds()*1000 >= instance.latency:
            instance.fetch_field(self)
            datum = instance.get_data(self)
        if datum:
            value = Field.convert_mixed(self.type, datum.value) if self._mixed else datum.value
            return self.transform_value(value, instance)
        return None

    def __set__(self, instance, value):
        # If value is None, its a No Op, the field is not updated
        if value is not None:
            if value < 0 and self._type in (helpers.USHORT, helpers.UINT, helpers.UINT64):
                raise ValueError("Attempting to assign negative value to unisgned type.")
            if not instance._ignore_op_mode and self._op_mode == helpers.OP_MODE_READ_ONLY:
                raise ValueError("Attempting to write read-only field.")
            value = self.value_for_transport(value, instance)
            if self._mixed:
                value = Field.convert_mixed(self.type, value)
            instance._pending_writes[self] = value

    @staticmethod
    def convert_mixed(datatype, value):
        """Reverse order of register

        :param datatype: register type
        :param value: register value to reverse
        """
        try:
            datatype = datatype[1:] if datatype.startswith((">", "<")) else datatype
            parse_struct = struct.Struct(">{}".format(datatype))
        except AttributeError:
            parse_struct = struct.Struct(">{}".format(datatype[0]))

        value_bytes = parse_struct.pack(value)
        register_values = []
        for i in xrange(0, len(value_bytes), 2):
            register_values.extend(struct.unpack(">H", value_bytes[i:i + 2]))
        register_values.reverse()
        convert_bytes = ''.join([struct.pack(">H", i) for i in register_values])

        return parse_struct.unpack(convert_bytes)[0]

    def fix_address(self, address_style):
        # Translate modbus addressing to absolute offsets
        if address_style in (helpers.ADDRESS_MODBUS, helpers.ADDRESS_OFFSET_PLUS_ONE):

            if address_style == helpers.ADDRESS_MODBUS:
                self._address = self._address - helpers.TABLE_ADDRESS[self._table]
            elif address_style == helpers.ADDRESS_OFFSET_PLUS_ONE:
                self._address = self._address - 1
            if self._address < 0 or self._address > 10000:
                raise Exception("Modbus address out of range for table.")


class Request (object):
    """
        Represents a contiguous set of logical fields, registers or coils.  The first
        field starts at self.address.

        Request is used to query a collection of fields, possibly of different datatypes,
        in a single modbus request.

    """

    def __init__(self, first_field, data_format='>'):
        self._table = first_field.table
        self._address = first_field.address
        self._next_address = first_field.address
        self._name = first_field.name
        self._count = 0
        self._data_format = first_field.byte_order or data_format
        self._fields = list()

        self.add_field(first_field)

    def table_name(self):
        """Returns display name of modbus table to be accessed by request"""

        if self._table == helpers.REGISTER_READ_WRITE:
            return "REGISTER_READ_WRITE"
        elif self._table == helpers.REGISTER_READ_ONLY:
            return "REGISTER_READ_ONLY"
        elif self._table == helpers.COIL_READ_WRITE:
            return "COIL_READ_WRITE"
        elif self._table == helpers.COIL_READ_ONLY:
            return "COIL_READ_ONLY"
        else:
            return "UNKNOWN"

    def __str__(self):
        return u"<Request: {0} - {1}[{2}] x {3} | {4}".format(
            self._name,
            self.table_name(),
            self._address,
            self._count,
            self._data_format
        )

    @property
    def name(self):
        return self._name

    @property
    def fields(self):
        return self._fields

    @property
    def address(self):
        return self._address

    @property
    def count(self):
        return self._count

    @property
    def table(self):
        return self._table

    @property
    def read_function_code(self):
        """Returns a modbus read function code appropriate for the table."""

        if self._table == helpers.REGISTER_READ_WRITE:
            modbus_function_code = modbus_constants.READ_HOLDING_REGISTERS
        elif self._table == helpers.REGISTER_READ_ONLY:
            modbus_function_code = modbus_constants.READ_INPUT_REGISTERS
        elif self._table == helpers.COIL_READ_WRITE:
            modbus_function_code = modbus_constants.READ_COILS
        elif self._table == helpers.COIL_READ_ONLY:
            modbus_function_code = modbus_constants.READ_DISCRETE_INPUTS
        else:
            raise Exception("Unknown table type : {0}".format(self._table))

        return modbus_function_code

    @property
    def write_function_code(self):
        """Returns a modbus write function code appropriate for the table."""

        if self._table == helpers.REGISTER_READ_WRITE:
            # WRITE_MULTIPLE is used unless client cannot support it, see _write_single_values in Client.__init__
            return modbus_constants.WRITE_MULTIPLE_REGISTERS
        elif self._table == helpers.COIL_READ_WRITE:
            # @TODO Temp hack around COIL write problem.
            return modbus_constants.WRITE_SINGLE_COIL if self._count == 1 \
                else modbus_constants.WRITE_MULTIPLE_COILS
        else:
            raise Exception("Unknown table type or write operation not supported : {0}".format(self._table))

    @property
    def formatting(self):
        """
            Provide a struct library format string for non-COIL data types.

            For COILS, we leave the formatting to modbus-tk.
        """
        if self._table not in (helpers.COIL_READ_ONLY, helpers.COIL_READ_WRITE):
            return self._data_format
        else:
            return None

    def able_to_add(self, field):
        return self._table == field.table and \
           self._next_address == field.address and \
           self._count + math.ceil(struct.calcsize(field.format_string) / 2.0) < 124 and \
           field.length == 1 and not field.byte_order and \
           not field.is_struct_format

    def add_field(self, field):
        """Add field to request if it is compatible and contiguous
        otherwise raise

        :return:
        """
        struct_format = field.format_string
        struct_size = struct.calcsize(struct_format)
        if struct_size % 2 == 1:
            struct_size += 1
        self._data_format += struct_format
        # current_request.count += f.type[SIZE] * f.type[LENGTH]
        self._count += struct_size / 2
        self._fields.append(field)
        self._next_address += struct_size / 2

    def block_info(self):
        return self._name, self._table, self._address, self._count

    def parse_values(self, results):
        """Parse field values out of the modbus_tk results

        :param results: unpacked results from modbus_tk execute()
        :return: a dictionary of {field_name: value, ...}
        """
        now = datetime.utcnow()
        field_values = {}
        if len(self.fields) == 1 and self.fields[0].is_array_field:
            field = self.fields[0]
            # Array
            field_values = {
                field: Datum([r for r in results], now)
            }
        else:
            # Struct formatted registers and processed as a single field.
            if self.fields and self.fields[0].is_struct_format:
                if type(results) is list or type(results) is tuple:
                    if len(results) > 1:
                        results = (results,)
            # Everything else))
            field_values = collections.OrderedDict(
                [(field, Datum(value, now)) for field, value in six.moves.zip(self.fields, results)]
            )
        return field_values

    @classmethod
    def compile_requests(cls, fields, byte_order):
        """

        Creates a set of Modbus requests for the fields provided.  The fields
        are sorted by table and address so that a minimum number of
        requests can be created.

        These requests are used for both reading and writing.

        :param fields: List of fields sorted by address.
        :param byte_order: Byte order of the modbus slave.
        :return: List of Requests
        """
        requests = list()

        if not fields:
            return requests

        fields.sort(key=lambda f: f.table * 100000 + f.address)

        # Set up the initial request before starting the loop
        current_request = None

        for f in fields:
            # Decide if we need to start a new request

            if current_request is None or not current_request.able_to_add(f):
                current_request = Request(f, data_format=byte_order)
                requests.append(current_request)
                if f.is_struct_format or f.is_array_field:
                    current_request = None
            else:
                current_request.add_field(f)

        return requests


class Client (object):

    """
    Generic modbus master.  It functions as a traditional "client" making requests of
    a modbus slave which acts like a traditional "server".

    Subclass this class with Field class variables.  See module description above.
    """

    byte_order = helpers.BIG_ENDIAN
    addressing = helpers.ADDRESS_OFFSET

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
            meta[helpers.META_FIELDS] = list(meta.values())                         # Turns Python3 view into a list.
            meta[helpers.META_FIELDS].sort(key=lambda f: f.address)
            meta[helpers.META_REQUESTS] = Request.compile_requests(meta[helpers.META_FIELDS], cls.byte_order)
            # Dictionary for easy lookup of the request that corresponds to a field.
            meta[helpers.META_REQUEST_MAP] = {field: request for request in meta[helpers.META_REQUESTS]
                                              for field in request._fields}
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
        self._ignore_op_mode = kwargs.pop('ignore_op_mode', False)  # Protection against unintended writes

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
        for f, v in six.iteritems(self._pending_writes):
            response = response + "\t{0} : {1}".format(f, v)
        return response

    @property
    def has_pending_writes(self):
        return bool(self._pending_writes)

    def requests(self):
        return self.__meta[helpers.META_REQUESTS]

    def fields(self):
        return self.__meta[helpers.META_FIELDS]

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
        return self.__meta[helpers.META_REQUEST_MAP].get(field, None)

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
            self._data.update(request.parse_values(results))
        except (AttributeError, ModbusError) as err:
            if "Exception code" in err.message:
                raise Exception("{0}: {1}".format(err.message,
                                                  helpers.TABLE_EXCEPTION_CODE.get(err.message[-1], "UNDEFINED")))
            logger.warning("modbus read_all() failure on request: %s\tError: %s", request, err)

    def read_all(self):
        requests = self.__meta[helpers.META_REQUESTS]
        self._data.clear()
        for r in requests:
            self.read_request(r)

    def dump_all(self):
        self.read_all()
        return [(f,
                 f.transform_value(Field.convert_mixed(f.type, d.value), self) if f.mixed else f.transform_value(d.value, self),
                 d.timestamp) for f, d in six.iteritems(self._data)]

    def write_all(self):
        logger.debug("In write_all")
        fields = list(self._pending_writes.keys())
        if self.write_single_values:
            # Convert values if necessary for transport as modbus supported types.
            for f in fields:
                value = self._pending_writes.pop(f)
                values = list()
                if type(value) in (list, tuple):
                    values.extend(value)
                else:
                    values.append(value)
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
            requests = Request.compile_requests(fields, self.byte_order)
            for r in requests:
                values = list()
                # Convert values if necessary for transport as modbus supported types.
                for f in r.fields:
                    value = self._pending_writes.pop(f)
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
