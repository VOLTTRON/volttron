# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
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

TABLE_EXCEPTION_CODE = {
    "1": "ILLEGAL FUNCTION",
    "2": "ILLEGAL DATA ADDRESS",
    "3": "ILLEGAL DATA VALUE",
    "4": "SLAVE DEVICE FAILURE",
    "5": "COMMAND ACKNOWLEDGE",
    "6": "SLAVE DEVICE BUSY",
    "8": "MEMORY PARITY ERROR"
}


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
    elif state in ('f', 'n', 'false', 'no', '0', ''):
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
    if func in (scale, scale_int, scale_decimal_int_signed):
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


def transform_func_helper(multiple_lst):
    """Fix floating point decimal places."""
    value = 1
    num_digits = 0
    for val in multiple_lst:
        value *= val
        try:
            num_digits += len(str(val).split(".")[1])
        except IndexError: #int
            pass
    try:
        return round(value, num_digits)
    except TypeError: #string
        return value

def scale_decimal_int_signed(multiplier):
    """
        Scales modbus float value that is stored as a decimal number, not using
        standard signing rollover, as the PM800 Power Factor Registers.
        Inverse_func is applied just before writing the value over modbus.

    :param multiplier: Scale multiplier, eg 0.001
    :return: Returns a function used by the modbus client.
    """
    multiplier = parse_transform_arg(scale_decimal_int_signed, multiplier)

    def func(value):
        if value < 0:
            return multiplier * (0 - (value + (32768)))
        else:
            return multiplier * value

    def inverse_func(value):
        try:
            try:
                if value < 0:
                    return  (0 - (value / float(multiplier))) - 0xFFFF
                else:
                    return (value / float(multipliers))
            except TypeError: #string
                return value
        except ZeroDivisionError:
            return None

    func.inverse = inverse_func
    return func

def scale(multiplier):
    """
        Scales modbus register values on reading.  Inverse_func is
        applied just before writing the value over modbus.

    :param multiplier: Scale multiplier, eg 0.001
    :return: Returns a function used by the modbus client.
    """
    multiplier = parse_transform_arg(scale, multiplier)

    def func(value):
        return transform_func_helper([multiplier, value])

    def inverse_func(value):
        try:
            try:
                return value / float(multiplier)
            except TypeError: #string
                return value
        except ZeroDivisionError:
            return None

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
        return int(value * multiplier)

    def inverse_func(value):
        try:
            return int(value / float(multiplier))
        except ZeroDivisionError:
            return None

    func.inverse = inverse_func
    return func


def scale_reg(reg_name):
    """
        Scales modbus register values by scaling register value.

    :param reg_name: scaling register name
    :return: Returns a function used by the modbus client.
    """
    def func(value, scaling_register_value):
        try:
            return value / scaling_register_value
        except ZeroDivisionError:
            return None

    def inverse_func(value, scaling_register_value):
        return value * scaling_register_value

    func.inverse = inverse_func
    func.register_args = [reg_name,]
    return func


def scale_reg_pow_10(reg_name):
    """
        Same as scale, but multiplier is 10 power the scaling register value
        For example: -1 -> 10^-1 = scale(0.1)
                      0 -> 10^0  = scale(1)
                      1 -> 10^1  = scale(10)

    :param reg_name: scaling register name
    :return: Returns a function used by the modbus client.
    """
    def func(value, scaling_register_value):
        return transform_func_helper([value, pow(10, float(scaling_register_value))])

    def inverse_func(value, scaling_register_value):
        return value / pow(10, float(scaling_register_value))

    func.inverse = inverse_func
    func.register_args = [reg_name,]
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


def mod10k64(reverse=False):
    """
    Converts the PM800 64 bit 10K


    @todo This works for postive values but not negative.
    The reason is that each of the 2 16-bit modbus registers come over
    signed so they need to be split out in the modbus conversion.
    """
    reverse = parse_transform_arg(mod10k64, reverse)

    def mod10k_value(value):
        r4 = (value >> 48) & 0xFFFF
        r3 = (value >> 32) & 0xFFFF
        r2 = (value >> 16) & 0xFFFF
        r1 = value & 0xFFFF
        if not reverse:
            return (r1 * 10000**3) + (r2 * 10000**2) + (r3 * 10000) + r4
        else:
            return (r4 * 10000**3) + (r3 * 10000**2) + (r2 * 10000) + r1

    return mod10k_value


def mod10k48(reverse=False):
    """
    Converts the PM800 INT48-M10K register format.

    @todo This works for postive values but not negative.
    The reason is that each of the 2 16-bit modbus registers come over
    signed so they need to be split out in the modbus conversion.
    """
    reverse = parse_transform_arg(mod10k48, reverse)

    def mod10k_value(value):
        r4 = (value >> 48) & 0xFFFF
        r3 = (value >> 32) & 0xFFFF
        r2 = (value >> 16) & 0xFFFF
        r1 = value & 0xFFFF
        if not reverse:
            return (r2 * 10000**2) + (r3 * 10000) + r4
        else:
            return (r1 * 10000**2) + (r2 * 10000) + r3

    return mod10k_value
