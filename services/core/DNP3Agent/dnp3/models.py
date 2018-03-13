# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / Kisensum.
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
# United States Department of Energy, nor SLAC, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

"""
    OpenDNP3 data model objects (Point), including methods for loading and caching them.
"""
import logging
import json
import re

from volttron.platform.agent import utils

from pydnp3 import opendnp3

utils.setup_logging()
_log = logging.getLogger(__name__)


# PointDefinition.fcodes values:
DIRECT_OPERATE = 'direct_operate'       # This is actually DIRECT OPERATE / RESPONSE
SELECT = 'select'                       # This is actually SELECT / RESPONSE
OPERATE = 'operate'                     # This is actually OPERATE / RESPONSE

# PointDefinition.point_type values:
POINT_TYPE_APPLICATION = 'Application'
POINT_TYPE_ANALOG_INPUT = 'Analog Input'
POINT_TYPE_ANALOG_OUTPUT = 'Analog Output'
POINT_TYPE_AUTHENTICATION = 'Authentication'
POINT_TYPE_BCD = 'BCD'
POINT_TYPE_BINARY_INPUT = 'Binary Input'
POINT_TYPE_BINARY_OUTPUT = 'Binary Output'
POINT_TYPE_CLASS_OBJECTS = 'Class Objects'
POINT_TYPE_COUNTER = 'Counter'
POINT_TYPE_DATA_SET = 'Data Set'
POINT_TYPE_DATA_SET_DESCRIPTOR = 'Data Set Descriptor'
POINT_TYPE_DATA_SET_EVENT = 'Data Set Event'
POINT_TYPE_DATA_SET_PROTOTYPE = 'Data Set Prototype'
POINT_TYPE_DATA_SET_REGISTRATION = 'Data Set Registration'
POINT_TYPE_DEVICE_PROFILE = 'Device Profile'
POINT_TYPE_DEVICE_STORAGE = 'Device Storage'
POINT_TYPE_DOUBLE_BIT_BINARY = 'Double Bit Binary'
POINT_TYPE_FILE_CONTROL = 'File-Control'
POINT_TYPE_FLOATING_POINT = 'Floating-Point'
POINT_TYPE_INTERNAL_INDICATIONS = 'Internal Indications'
POINT_TYPE_OCTET_STRING = 'Octet String'
POINT_TYPE_SECURITY_STATISTIC = 'Security Statistic'
POINT_TYPE_STATUS_OF_REQUESTED_OPERATION = 'Status of Requested Operation'
POINT_TYPE_TIME_AND_DATE = 'Time And Date'
POINT_TYPE_UNSIGNED_INTEGER = 'Unsigned Integer'
POINT_TYPE_VIRTUAL_TERMINAL = 'Virtual Terminal'

EVENT_CLASSES = {
    1: opendnp3.PointClass.Class1,
    2: opendnp3.PointClass.Class2,
    3: opendnp3.PointClass.Class3
}

GROUP_AND_VARIATIONS = {
    '1.1': opendnp3.StaticBinaryVariation.Group1Var1,
    '1.2': opendnp3.StaticBinaryVariation.Group1Var2,
    '2.1': opendnp3.EventBinaryVariation.Group2Var1,
    '2.2': opendnp3.EventBinaryVariation.Group2Var2,
    '2.3': opendnp3.EventBinaryVariation.Group2Var3,
    '3.2': opendnp3.StaticDoubleBinaryVariation.Group3Var2,
    '4.1': opendnp3.EventDoubleBinaryVariation.Group4Var1,
    '4.2': opendnp3.EventDoubleBinaryVariation.Group4Var2,
    '4.3': opendnp3.EventDoubleBinaryVariation.Group4Var3,
    '10.2': opendnp3.StaticBinaryOutputStatusVariation.Group10Var2,
    '11.1': opendnp3.EventBinaryOutputStatusVariation.Group11Var1,
    '11.2': opendnp3.EventBinaryOutputStatusVariation.Group11Var2,
    '20.1': opendnp3.StaticCounterVariation.Group20Var1,
    '20.2': opendnp3.StaticCounterVariation.Group20Var2,
    '20.5': opendnp3.StaticCounterVariation.Group20Var5,
    '20.6': opendnp3.StaticCounterVariation.Group20Var6,
    '21.1': opendnp3.StaticFrozenCounterVariation.Group21Var1,
    '21.2': opendnp3.StaticFrozenCounterVariation.Group21Var2,
    '21.5': opendnp3.StaticFrozenCounterVariation.Group21Var5,
    '21.6': opendnp3.StaticFrozenCounterVariation.Group21Var6,
    '21.9': opendnp3.StaticFrozenCounterVariation.Group21Var9,
    '21.10': opendnp3.StaticFrozenCounterVariation.Group21Var10,
    '22.1': opendnp3.EventCounterVariation.Group22Var1,
    '22.2': opendnp3.EventCounterVariation.Group22Var2,
    '22.5': opendnp3.EventCounterVariation.Group22Var5,
    '22.6': opendnp3.EventCounterVariation.Group22Var6,
    '23.1': opendnp3.EventFrozenCounterVariation.Group23Var1,
    '23.2': opendnp3.EventFrozenCounterVariation.Group23Var2,
    '23.5': opendnp3.EventFrozenCounterVariation.Group23Var5,
    '23.6': opendnp3.EventFrozenCounterVariation.Group23Var6,
    '30.1': opendnp3.StaticAnalogVariation.Group30Var1,
    '30.2': opendnp3.StaticAnalogVariation.Group30Var2,
    '30.3': opendnp3.StaticAnalogVariation.Group30Var3,
    '30.4': opendnp3.StaticAnalogVariation.Group30Var4,
    '30.5': opendnp3.StaticAnalogVariation.Group30Var5,
    '30.6': opendnp3.StaticAnalogVariation.Group30Var6,
    '32.1': opendnp3.EventAnalogVariation.Group32Var1,
    '32.2': opendnp3.EventAnalogVariation.Group32Var2,
    '32.3': opendnp3.EventAnalogVariation.Group32Var3,
    '32.4': opendnp3.EventAnalogVariation.Group32Var4,
    '32.5': opendnp3.EventAnalogVariation.Group32Var5,
    '32.6': opendnp3.EventAnalogVariation.Group32Var6,
    '32.7': opendnp3.EventAnalogVariation.Group32Var7,
    '32.8': opendnp3.EventAnalogVariation.Group32Var8,
    '40.1': opendnp3.StaticAnalogOutputStatusVariation.Group40Var1,
    '40.2': opendnp3.StaticAnalogOutputStatusVariation.Group40Var2,
    '40.3': opendnp3.StaticAnalogOutputStatusVariation.Group40Var3,
    '40.4': opendnp3.StaticAnalogOutputStatusVariation.Group40Var4,
    '42.1': opendnp3.EventAnalogOutputStatusVariation.Group42Var1,
    '42.2': opendnp3.EventAnalogOutputStatusVariation.Group42Var2,
    '42.3': opendnp3.EventAnalogOutputStatusVariation.Group42Var3,
    '42.4': opendnp3.EventAnalogOutputStatusVariation.Group42Var4,
    '42.5': opendnp3.EventAnalogOutputStatusVariation.Group42Var5,
    '42.6': opendnp3.EventAnalogOutputStatusVariation.Group42Var6,
    '42.7': opendnp3.EventAnalogOutputStatusVariation.Group42Var7,
    '42.8': opendnp3.EventAnalogOutputStatusVariation.Group42Var8,
    '50.4': opendnp3.StaticTimeAndIntervalVariation.Group50Var4,
    '121.1': opendnp3.StaticSecurityStatVariation.Group121Var1,
    '122.1': opendnp3.EventSecurityStatVariation.Group122Var1,
    '122.2': opendnp3.EventSecurityStatVariation.Group122Var2
}

POINT_TYPES_BY_GROUP = {
    # Single-Bit Binary: See DNP3 spec, Section A.2-A.5 and Table 11-17
    1: POINT_TYPE_BINARY_INPUT,         # Binary Input (static): Reporting the present value of a single-bit binary object
    2: POINT_TYPE_BINARY_INPUT,         # Binary Input Event: Reporting single-bit binary input events and flag bit changes
    # Double-Bit Binary: See DNP3 spec, Section A.4 and Table 11-15
    3: POINT_TYPE_DOUBLE_BIT_BINARY,    # Double-Bit Binary Input (static): Reporting present state value
    4: POINT_TYPE_DOUBLE_BIT_BINARY,    # Double-Bit Binary Input Event: Reporting double-bit binary input events and flag bit changes
    # Binary Output: See DNP3 spec, Section A.6-A.9 and Table 11-12
    10: POINT_TYPE_BINARY_OUTPUT,       # Binary Output (static): Reporting the present output status
    11: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Event: Reporting changes to the output status or flag bits
    12: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Command: Issuing control commands
    13: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Command Event: Reporting control command was issued regardless of its source
    # Counter: See DNP3 spec, Section A.10-A.13 and Table 11-13
    20: POINT_TYPE_COUNTER,             # Counter: Reporting the count value
    21: POINT_TYPE_COUNTER,             # Frozen Counter: Reporting the frozen count value or changed flag bits
    22: POINT_TYPE_COUNTER,             # Counter Event: Reporting counter events
    23: POINT_TYPE_COUNTER,             # Frozen Counter Event: Reporting frozen counter events
    # Analog Input: See DNP3 spec, Section A.14-A.18 and Table 11-9
    30: POINT_TYPE_ANALOG_INPUT,        # Analog Input (static): Reporting the present value
    31: POINT_TYPE_ANALOG_INPUT,        # Frozen Analog Input (static): Reporting the frozen value
    32: POINT_TYPE_ANALOG_INPUT,        # Analog Input Event: Reporting analog input events or changes to the flag bits
    33: POINT_TYPE_ANALOG_INPUT,        # Frozen Analog Input Event: Reporting frozen analog input events
    34: POINT_TYPE_ANALOG_INPUT,        # Analog Input Reporting Deadband (static): Reading and writing analog deadband values
    # Analog Output: See DNP3 spec, Section A.19-A.22 and Table 11-10
    40: POINT_TYPE_ANALOG_OUTPUT,       # Analog Output Status (static): Reporting present value of analog outputs
    41: POINT_TYPE_ANALOG_OUTPUT,       # Analog Output (command): Controlling analog output values
    42: POINT_TYPE_ANALOG_OUTPUT,       # Analog Output Event: Reporting changes to the analog output or flag bits
    43: POINT_TYPE_ANALOG_OUTPUT,       # Analog Output Command Event: Reporting output points being commanded from any source
    # Time and Date: See DNP3 spec, Section A.23-A.25
    50: POINT_TYPE_TIME_AND_DATE,
    51: POINT_TYPE_TIME_AND_DATE,       # Time and Date Common Time-of-Occurrence
    52: POINT_TYPE_TIME_AND_DATE,       # Time Delay
    # Class Objects: See DNP3 spec, Section A.26
    60: POINT_TYPE_CLASS_OBJECTS,
    # File-Control: See DNP3 spec, Section A.27
    70: POINT_TYPE_FILE_CONTROL,
    # Information Objects: See DNP3 spec, Section A.28-A.31
    80: POINT_TYPE_INTERNAL_INDICATIONS,
    81: POINT_TYPE_DEVICE_STORAGE,
    82: POINT_TYPE_DEVICE_PROFILE,
    83: POINT_TYPE_DATA_SET_REGISTRATION,
    # Data Set Objects: See DNP3 spec, Section A.32-A.35
    85: POINT_TYPE_DATA_SET_PROTOTYPE,
    86: POINT_TYPE_DATA_SET_DESCRIPTOR,
    87: POINT_TYPE_DATA_SET,
    88: POINT_TYPE_DATA_SET_EVENT,
    # Application & Status of Operation Information Objects: See DNP3 spec, Section A.36-A.37
    90: POINT_TYPE_APPLICATION,
    91: POINT_TYPE_STATUS_OF_REQUESTED_OPERATION,
    # Floating-Point (Obsolete): See DNP3 spec, Section A.38
    100: POINT_TYPE_FLOATING_POINT,
    # Numeric Static Objects: See DNP3 spec, Section A.39-A.40
    101: POINT_TYPE_BCD,                   # Device-dependent values in Binary-Coded Decimal form (Table 11-11)
    102: POINT_TYPE_UNSIGNED_INTEGER,
    # Octet String: See DNP3 spec, Section A.41-A.42 and Table 11-16
    110: POINT_TYPE_OCTET_STRING,          # To convey the present value
    111: POINT_TYPE_OCTET_STRING,          # Reporting an octet string event
    # Virtual Terminal: See DNP3 spec, Section A.43-A.44 and Table 11-18
    112: POINT_TYPE_VIRTUAL_TERMINAL,      # Conveying data to the command interpreter at the outstation
    113: POINT_TYPE_VIRTUAL_TERMINAL,      # Conveying data from the command interpreter at the outstation
    # Security: See DNP3 spec, Section A.45
    120: POINT_TYPE_AUTHENTICATION,
    # Security Statistic: See DNP3 spec, Section A.46-A.47 and Table 11-20
    121: POINT_TYPE_SECURITY_STATISTIC,    # Reporting the current value of the statistics
    122: POINT_TYPE_SECURITY_STATISTIC     # Reporting changes to the statistics
}

# Use a regular expression to filter comments out of the JSON configuration file's definitions
_comment_re = re.compile(
    r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))',
    re.MULTILINE | re.DOTALL)


class PointDefinition:
    """Data holder for an OpenDNP3 data element."""

    points = {}
    point_variation_dict = {}

    def __init__(self, element_def):
        """Initialize an instance of the PointDefinition from a dictionary of point attributes."""
        self.name = element_def.get('name')
        self.group = element_def.get('group')
        self.variation = element_def.get('variation')
        self.index = element_def.get('index')
        self.description = element_def.get('description', '')
        self.scaling_multiplier = element_def.get('scaling_multiplier', 1)
        self.units = element_def.get('units', '')
        self.event_class = element_def.get('event_class', 2)
        self.event_group = element_def.get('event_group', None)
        self.event_variation = element_def.get('event_variation', None)
        self.fcodes = element_def.get('fcodes', [])
        self.echo = element_def.get('echo', None)

    def __str__(self):
        """Return a string description of the PointDefinition."""
        return 'PointDefinition {0} ({1}, index={2}, type={3})'.format(self.name,
                                                                       self.group_and_variation,
                                                                       self.index,
                                                                       self.point_type)

    @property
    def group_and_variation(self):
        """Return a string representation of the PointDefinition's group and variation."""
        return '{0}.{1}'.format(self.group, self.variation)

    @property
    def event_group_and_variation(self):
        """Return a string representation of the PointDefinition's event group and event variation."""
        return '{0}.{1}'.format(self.event_group, self.event_variation)

    @classmethod
    def point_type_for_group(cls, group):
        """Return the point type for a group value."""
        ptype = POINT_TYPES_BY_GROUP.get(group, None)
        if ptype is None:
            _log.error('No DNP3 point type found for group {}'.format(group))
        return ptype

    @property
    def point_type(self):
        """Return the PointDefinition's point type, derived from its group (indexing is within point type)."""
        return self.point_type_for_group(self.group)

    @property
    def is_input(self):
        """Return True if the PointDefinition is a Binary or Analog input point (i.e., sent by the Outstation)."""
        return self.point_type in [POINT_TYPE_ANALOG_INPUT, POINT_TYPE_BINARY_INPUT]

    @property
    def is_output(self):
        """Return True if the PointDefinition is a Binary or Analog output point (i.e., sent by the Master)."""
        return self.point_type in [POINT_TYPE_ANALOG_OUTPUT, POINT_TYPE_BINARY_OUTPUT]

    @property
    def eclass(self):
        """Return the PointDefinition's event class, or the default (2) if no event class was defined for the point."""
        return EVENT_CLASSES.get(self.event_class, 2)

    @property
    def svariation(self):
        """Return the PointDefinition's group-and-variation enumerated type."""
        return GROUP_AND_VARIATIONS.get(self.group_and_variation)

    @property
    def evariation(self):
        """Return the PointDefinition's event group-and-variation enumerated type."""
        return GROUP_AND_VARIATIONS.get(self.event_group_and_variation)

    @classmethod
    def points_dictionary(cls):
        """Return a (cached) dictionary of PointDefinitions, indexed by point_type and point index."""
        return cls.points

    @classmethod
    def point_list(cls):
        """Return a flat list of all PointDefinitions."""
        point_list = []
        for inner_dict in cls.points_dictionary().values():
            point_list.extend(inner_dict.values())
        return point_list

    @classmethod
    def load_points(cls, point_definitions_path):
        """
            Load and cache a dictionary of PointDefinitions from a json list.

            Index the dictionary by point_type and point index.
        """

        def _repl(match):
            """
                Replace the match group with an appropriate string.

                If the first group was matched, a quoted string was matched and should be returned unchanged.
                Otherwise a comment was matched and an empty string should be returned.
            """
            return match.group(1) or ''

        _log.debug('Loading DNP3 point definitions.')
        try:
            with open(point_definitions_path, 'r') as f:
                cls.points = {}           # If they're already loaded, force a reload.
                # Filter comments out of the json before loading it.
                for element in json.loads(_comment_re.sub(_repl, f.read())):
                    point_def = PointDefinition(element)
                    if cls.points.get(point_def.point_type, None) is None:
                        cls.points[point_def.point_type] = {}
                    point_type_dict = cls.points[point_def.point_type]
                    duplicate_point = point_type_dict.get(point_def.index, None)
                    if duplicate_point:
                        error_message = 'Discarding DNP3 duplicate {0} (conflicting {1})'
                        _log.error(error_message.format(point_def, duplicate_point))
                    else:
                        point_type_dict[point_def.index] = point_def
        except Exception as err:
            raise ValueError('Problem parsing {}. No data loaded. Error={}'.format(point_definitions_path, err))

    @classmethod
    def for_point_type_and_index(cls, point_type, index):
        """
            Return a PointDefinition for a given data type and index.

        :param point_type: A point type (string).
        :param index: Unique integer index of the PointDefinition to be looked up.
        :return: A PointDefinition.
        """
        return cls.points_dictionary().get(point_type, {}).get(index, None)

    @classmethod
    def points_by_variation(cls):
        """Return a (cached) dictionary of PointDefinitions, indexed by group, variation and index."""
        if not cls.point_variation_dict:
            for point_type, inner_dict in cls.points_dictionary().items():
                for index, point_def in inner_dict.items():
                    if cls.point_variation_dict.get(point_def.group, None):
                        cls.point_variation_dict[point_def.group] = {}
                    if cls.point_variation_dict[point_def.group].get(point_def.variation, None):
                        cls.point_variation_dict[point_def.group][point_def.variation] = {}
                    cls.point_variation_dict[point_def.group][point_def.variation][index] = point_def
        return cls.point_variation_dict

    @classmethod
    def point_for_variation_and_index(cls, group, variation, index):
        """Return a PointDefinition for a given group, variation and index."""
        return cls.points_by_variation().get(group, {}).get(variation, {}).get(index, None)


class PointValue:
    """Data holder for a point value (DNP3 measurement or command) received by an outstation."""

    current_values = {}

    def __init__(self, command_type, function_code, value, point_def, index, op_type):
        """Initialize an instance of the PointValue."""
        self.command_type = command_type
        self.function_code = function_code
        self.value = value
        self.point_def = point_def
        self.index = index
        self.op_type = op_type

    def __str__(self):
        """Return a string description of the PointValue."""
        str_desc = 'Point value ({0}): variation={1}\t index={2}\t name={3}\t function={4}\t value={5}\t op_type={6}'
        return str_desc.format(self.command_type,
                               self.point_def.group_and_variation,
                               self.index,
                               self.name,
                               self.function_code,
                               self.value,
                               self.op_type)

    @property
    def name(self):
        """Return this PointValue's name, which is the name of its PointDefinition."""
        return self.point_def.name

    @classmethod
    def add_to_current_values(cls, value):
        """Update a dictionary that holds the most-recently-received value of each point."""
        point_type = value.point_def.point_type
        if point_type not in cls.current_values:
            cls.current_values[point_type] = {}
        cls.current_values[point_type][int(value.index)] = value

    @classmethod
    def get_current_value(cls, point_type, index):
        """Return the most-recently-received PointValue for a given PointDefinition."""
        if point_type not in cls.current_values:
            return None
        elif index not in cls.current_values[point_type]:
            return None
        else:
            return cls.current_values[point_type][index]

    @classmethod
    def get_all_current_input_points(cls):
        """Return a list of the most-recently-set values of all Input points."""
        vals = []
        for dt, val_dict in cls.current_values.iteritems():
            if dt in [POINT_TYPE_ANALOG_INPUT, POINT_TYPE_BINARY_INPUT]:
                vals.extend([v for v in val_dict.itervalues()])
        return vals

    @classmethod
    def get_all_current_output_points(cls):
        """Return a list of the most-recently-received values of all Output points."""
        vals = []
        for dt, val_dict in cls.current_values.iteritems():
            if dt in [POINT_TYPE_ANALOG_OUTPUT, POINT_TYPE_BINARY_OUTPUT]:
                vals.extend([v for v in val_dict.itervalues()])
        return vals

    @classmethod
    def for_command(cls, command_type, command, index, op_type):
        """
            A DNP3 Select or Operate was received from the master. Create and return a PointValue for its data.

        :param command_type: Either 'Select' or 'Operate'.
        :param command: A ControlRelayOutputBlock or else a wrapped data value (AnalogOutputInt16, etc.).
        :param index: DNP3 index of the payload's data definition.
        :param op_type: An OperateType, or None if command_type == 'Select'.
        :return: An instance of PointValue
        """
        function_code = command.functionCode if type(command) == opendnp3.ControlRelayOutputBlock else None
        point_type = POINT_TYPE_BINARY_OUTPUT if function_code else POINT_TYPE_ANALOG_OUTPUT
        point_def = PointDefinition.for_point_type_and_index(point_type, index)
        if point_def:
            point_value = PointValue(command_type,
                                     function_code,
                                     command.value if not function_code else None,
                                     point_def,
                                     index,
                                     op_type)
            _log.debug('Received DNP3 {}'.format(point_value))
            return point_value
        else:
            _log.error('No DNP3 PointDefinition found for point type {0} and index {1}'.format(point_type, index))
            return None
