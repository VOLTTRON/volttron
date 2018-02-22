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

import modbus_tk.defines as modbus_constants

# Defines Python struct format strings and size (in modbus register units)
# More info on 'struct' is here: https://docs.python.org/2/library/struct.html
FORMAT, SIZE, LENGTH = 0, 1, 2

FLOAT = ("f", 2, 1)
INT = ("i", 2, 1)
UINT = ("I", 2, 1)
INT64 = ("q", 4, 1)
UINT64 = ("Q", 4, 1)
SHORT = ("h", 1, 1)
USHORT = ("H", 1, 1)
BOOL = ("?", 1, 1)
CHAR = ("c", 1, 1)
STRING = ("s", 2, 1)

# BYTE Ordering
BIG = 'big'
BIG_ENDIAN = ">"
LITTLE_ENDIAN = "<"

# MODBUS Table/Block Types
COIL_READ_WRITE = modbus_constants.COILS
COIL_READ_ONLY = modbus_constants.DISCRETE_INPUTS
REGISTER_READ_ONLY = modbus_constants.ANALOG_INPUTS
REGISTER_READ_WRITE = modbus_constants.HOLDING_REGISTERS


TABLE_ADDRESS = {
    COIL_READ_WRITE:            1,
    COIL_READ_ONLY:         10001,
    REGISTER_READ_ONLY:     30001,
    REGISTER_READ_WRITE:    40001
}

# Operating Modes
OP_MODE_READ_ONLY = 0
OP_MODE_WRITE_ONLY = 1
OP_MODE_READ_WRITE = 2

# Addresing
OFFSET = 'offset'
ADDRESS_OFFSET = 0
ADDRESS_MODBUS = 1
ADDRESS_OFFSET_PLUS_ONE = 2

META_FIELDS = '_fields'
META_REQUESTS = '_requests'
META_REQUEST_MAP = '_request_map'
META_PROPERTIES = '_properties'


def array(type, length):
    if type in (SHORT, USHORT):
        return type[FORMAT], type[SIZE], length
    else:
        raise Exception("Only SHORT and USHORT are supported as array types.")


def string(length):
    return 's', 1, length


def str2bool(str_val):
    """
        Convert string to boolean

    :param str_val: boolean in str
    :return: value in bool or raise error if not matched
    """
    state = str_val.strip().lower()
    if state in ('t', 'y', 'true', 'yes', '1'):
        return True
    elif state in ('f', 'n', 'false', 'no', '0'):
        return False
    else:
        raise ValueError


def parse_transform_arg(func, arg):
    """
        Parse the transform argument to the correct data type.

    :param func: transform function
    :param arg: argument of the transform function
    :return: the correct argument or raise exception if not matched
    """
    parse_arg = arg
    if func in (scale, scale_int):
        if type(arg) not in (int, long, float):
            try:
                parse_arg = int(arg, 10)
            except ValueError:
                try:
                    parse_arg = float(arg)
                except ValueError:
                    raise Exception('Parsing wrong argument for transform')
    else:
        if type(arg) is not bool:
            try:
                parse_arg = str2bool(arg)
            except ValueError:
                raise Exception('Parsing wrong argument for transform')

    return parse_arg


def scale(multiplier):
    """
        Scales modbus register values on reading.  Inverse_func is
        applied just before writing the value over modbus.

    :param multiplier: Scale multiplier, eg 0.001
    :return: Returns a function used by the modbus client.
    """
    multiplier = parse_transform_arg(scale, multiplier)

    def func(value):
        return value*multiplier

    def inverse_func(value):
        try:
            inverse_value = value / float(multiplier)
        except TypeError:
            inverse_value = value
        return inverse_value

    func.inverse = inverse_func
    return func


def scale_int(multiplier):
    """
        Same as scale, except that the function casts its return value to an integer data type.

    :param multiplier: Scale multiplier, eg 0.001
    :return: Returns a function used by the modbus client.
    """
    multiplier = parse_transform_arg(scale_int, multiplier)

    def func(value):
        return value * multiplier

    def inverse_func(value):
        return int(value / float(multiplier))

    func.inverse = inverse_func
    return func


def no_op(value):
    return value


def mod10k(reverse=False):
    """
    Converts the ION 8600 INT32-M10K register format.
    See ION8600 Modbus Protocol doc for details.

    In the ION6200 hundred, the registers are reversed
    for some reason, see Note 11 in the doc:
        PowerLogic ION6200 Serial Communications Protocol

    @todo This works for postive values but not negative.
    The reason is that each of the 2 16-bit modbus registers come over
    signed so they need to be split out in the modbus conversion.
    """
    reverse = parse_transform_arg(mod10k, reverse)

    def mod10k_value(value):
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF
        if not reverse:
            return high * 10000 + low
        else:
            return low * 10000 + high

    return mod10k_value