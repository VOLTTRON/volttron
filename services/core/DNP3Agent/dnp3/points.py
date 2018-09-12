# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / 8minutenergy / Kisensum.
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
# This material was prepared in part as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor SLAC, nor 8minutenergy, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, 8minutenergy, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

from datetime import datetime
import json
import logging
import os
import pytz
import re

from pydnp3 import opendnp3

DEFAULT_POINT_TOPIC = 'dnp3/point'
DEFAULT_OUTSTATION_STATUS_TOPIC = 'mesa/outstation_status'
DEFAULT_LOCAL_IP = "0.0.0.0"
DEFAULT_PORT = 20000

# PointDefinition.fcodes values:
DIRECT_OPERATE = 'direct_operate'       # This is actually DIRECT OPERATE / RESPONSE
SELECT = 'select'                       # This is actually SELECT / RESPONSE
OPERATE = 'operate'                     # This is actually OPERATE / RESPONSE

# Some PointDefinition.point_type values:
POINT_TYPE_ANALOG_INPUT = 'Analog Input'
POINT_TYPE_ANALOG_OUTPUT = 'Analog Output'
POINT_TYPE_BINARY_INPUT = 'Binary Input'
POINT_TYPE_BINARY_OUTPUT = 'Binary Output'

# Default event group and variation for each of these types, in case they weren't spec'd for a point in the data file.
EVENT_DEFAULTS_BY_POINT_TYPE = {
    POINT_TYPE_ANALOG_INPUT: {"group": 32, "variation": 3},
    POINT_TYPE_ANALOG_OUTPUT: {"group": 42, "variation": 3},
    POINT_TYPE_BINARY_INPUT: {"group": 2, "variation": 1},
    POINT_TYPE_BINARY_OUTPUT: {"group": 11, "variation": 1}
}

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
    3: 'Double Bit Binary',             # Double-Bit Binary Input (static): Reporting present state value
    4: 'Double Bit Binary',             # Double-Bit Binary Input Event: Reporting double-bit binary input events and flag bit changes
    # Binary Output: See DNP3 spec, Section A.6-A.9 and Table 11-12
    10: POINT_TYPE_BINARY_OUTPUT,       # Binary Output (static): Reporting the present output status
    11: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Event: Reporting changes to the output status or flag bits
    12: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Command: Issuing control commands
    13: POINT_TYPE_BINARY_OUTPUT,       # Binary Output Command Event: Reporting control command was issued regardless of its source
    # Counter: See DNP3 spec, Section A.10-A.13 and Table 11-13
    20: 'Counter',                      # Counter: Reporting the count value
    21: 'Counter',                      # Frozen Counter: Reporting the frozen count value or changed flag bits
    22: 'Counter',                      # Counter Event: Reporting counter events
    23: 'Counter',                      # Frozen Counter Event: Reporting frozen counter events
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
    50: 'Time And Date',
    51: 'Time And Date',                # Time and Date Common Time-of-Occurrence
    52: 'Time And Date',                # Time Delay
    # Class Objects: See DNP3 spec, Section A.26
    60: 'Class Objects',
    # File-Control: See DNP3 spec, Section A.27
    70: 'File-Control',
    # Information Objects: See DNP3 spec, Section A.28-A.31
    80: 'Internal Indications',
    81: 'Device Storage',
    82: 'Device Profile',
    83: 'Data Set Registration',
    # Data Set Objects: See DNP3 spec, Section A.32-A.35
    85: 'Data Set Prototype',
    86: 'Data Set Descriptor',
    87: 'Data Set',
    88: 'Data Set Event',
    # Application & Status of Operation Information Objects: See DNP3 spec, Section A.36-A.37
    90: 'Application',
    91: 'Status of Requested Operation',
    # Floating-Point (Obsolete): See DNP3 spec, Section A.38
    100: 'Floating-Point',
    # Numeric Static Objects: See DNP3 spec, Section A.39-A.40
    101: 'BCD',                         # Device-dependent values in Binary-Coded Decimal form (Table 11-11)
    102: 'Unsigned Integer',
    # Octet String: See DNP3 spec, Section A.41-A.42 and Table 11-16
    110: 'Octet String',                # To convey the present value
    111: 'Octet String',                # Reporting an octet string event
    # Virtual Terminal: See DNP3 spec, Section A.43-A.44 and Table 11-18
    112: 'Virtual Terminal',            # Conveying data to the command interpreter at the outstation
    113: 'Virtual Terminal',            # Conveying data from the command interpreter at the outstation
    # Security: See DNP3 spec, Section A.45
    120: 'Authentication',
    # Security Statistic: See DNP3 spec, Section A.46-A.47 and Table 11-20
    121: 'Security Statistic',          # Reporting the current value of the statistics
    122: 'Security Statistic'           # Reporting changes to the statistics
}

_log = logging.getLogger(__name__)


class DNP3Exception(Exception):
    """Raise exceptions that are specific to the DNP3 agent. No special exception behavior is needed at this time."""
    pass


class PointDefinitions(object):
    """In-memory repository of PointDefinitions."""

    def __init__(self, point_definitions_path=None):
        self._points = {}
        self._point_variation_dict = {}
        self._point_name_dict = {}
        if point_definitions_path:
            file_path = os.path.expandvars(os.path.expanduser(point_definitions_path))
            self.load_points_from_json_file(file_path)

    def __getitem__(self, name):
        """Return the PointDefinition associated with this name. Must be unique."""
        return self.get_point_named(name)

    def load_points_from_json_file(self, point_definitions_path):
        """Load and cache a dictionary of PointDefinitions, indexed by point_type and point index."""
        if point_definitions_path:
            try:
                file_path = os.path.expandvars(os.path.expanduser(point_definitions_path))
                _log.debug('Loading DNP3 point definitions from {}.'.format(file_path))
                with open(file_path, 'r') as f:
                    # Filter comments out of the file's contents before loading it as JSON.
                    self.load_points(json.loads(self.strip_comments(f.read())))
            except Exception as err:
                raise ValueError('Problem parsing {}. Error={}'.format(point_definitions_path, err))
        else:
            _log.debug('No point_definitions_path specified, loading no points')

    def strip_comments(self, raw_string):
        """
            Return a string with comments stripped.

            Both JavaScript-style comments (//... and /*...*/) and hash (#...) comments are removed.
            Thanks to VOLTTRON volttron/platform/agent/utils.py/strip_comments() for this logic.
        """
        def _repl(match):
            return match.group(1) or ''

        _comment_re = re.compile(r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))', re.MULTILINE | re.DOTALL)
        return _comment_re.sub(_repl, raw_string)

    def load_points(self, point_definitions_json):
        """Load and cache a dictionary of PointDefinitions, indexed by point_type and point index."""
        try:
            self._points = {}           # If they're already loaded, force a reload.
            for element in point_definitions_json:
                # Load a PointDefinition (or subclass) from JSON, and add it to the dictionary of points.
                # If the point defines an array, load additional definitions for each interior point in the array.
                try:
                    if element.get('type', None) != 'array':
                        point_def = PointDefinition(element)
                        self.index_point(point_def)
                    else:
                        point_def = ArrayHeadPointDefinition(element)
                        self.index_point(point_def)
                        # Load a separate ArrayPointDefinition for each interior point in the array.
                        for pt in point_def.create_array_point_definitions(element):
                            self.index_point(pt)
                except ValueError as err:
                    raise DNP3Exception('Validation error for point with json: {}: {}'.format(element, err))
        except Exception as err:
            raise ValueError('Problem parsing PointDefinitions. Error={}'.format(err))
        _log.debug('Loaded {} PointDefinitions'.format(len(self.all_points())))

    def index_point(self, point_def):
        """Add a PointDefinition to the dictionary of points."""
        point_type_dict = self._points.setdefault(point_def.point_type, {})
        if point_def.index in point_type_dict:
            error_message = 'Discarding DNP3 duplicate {0} (conflicting {1})'
            raise DNP3Exception(error_message.format(point_def, point_type_dict[point_def.index]))
        else:
            point_type_dict[point_def.index] = point_def

    def _points_dictionary(self):
        """Return a (cached) dictionary of PointDefinitions, indexed by point_type and point index."""
        return self._points

    def for_group_and_index(self, group, index):
        return self._points_dictionary().get(PointDefinition.point_type_for_group(group), {}).get(index, None)

    def point_value_for_command(self, command_type, command, index, op_type):
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
        point_def = self.for_point_type_and_index(point_type, index)
        if not point_def:
            raise DNP3Exception('No DNP3 PointDefinition found for point type {0} and index {1}'.format(point_type,
                                                                                                        index))
        point_value = PointValue(command_type,
                                 function_code,
                                 command.value if not function_code else None,
                                 point_def,
                                 index,
                                 op_type)
        _log.debug('Received DNP3 {}'.format(point_value))
        return point_value

    def for_point_type_and_index(self, point_type, index):
        """
            Return a PointDefinition for a given data type and index.

        @param point_type: A point type (string).
        @param index: Unique integer index of the PointDefinition to be looked up.
        @return: A PointDefinition.
        """
        return self._points_dictionary().get(point_type, {}).get(index, None)

    def _points_by_variation(self):
        """Return a (cached) dictionary of PointDefinitions, indexed by group, variation and index."""
        if not self._point_variation_dict:
            for point_type, inner_dict in self._points_dictionary().items():
                for index, point_def in inner_dict.items():
                    if self._point_variation_dict.get(point_def.group, None):
                        self._point_variation_dict[point_def.group] = {}
                    if self._point_variation_dict[point_def.group].get(point_def.variation, None):
                        self._point_variation_dict[point_def.group][point_def.variation] = {}
                    self._point_variation_dict[point_def.group][point_def.variation][index] = point_def
        return self._point_variation_dict

    def point_for_variation_and_index(self, group, variation, index):
        """Return a PointDefinition for a given group, variation and index."""
        return self._points_by_variation().get(group, {}).get(variation, {}).get(index, None)

    def points_by_name(self):
        """Return a (cached) dictionary of PointDefinition lists, indexed by name."""
        if not self._point_name_dict:
            for point_type, inner_dict in self._points_dictionary().items():
                for index, point_def in inner_dict.items():
                    point_name = point_def.name
                    if point_name not in self._point_name_dict:
                        self._point_name_dict[point_name] = []
                    self._point_name_dict[point_name].append(point_def)
        return self._point_name_dict

    def point_named(self, name, index=None):
        """
            Return the PointDefinition with the indicated name and (optionally) index.

        :param name: (string) The point's name.
        :param index: (integer) An optional index value. If supplied, search for an array point at this DNP3 index.
        :return A PointDefinition, or None if no match.
        """
        point_def_list = self.points_by_name().get(name, None)
        if point_def_list is None:
            return None                     # No points with that name

        if index is not None:
            # Return the PointDefinition with a matching index.
            for pt in point_def_list:
                if pt.index == index:
                    return pt
            return None

        # In multi-element lists, give preference to the ArrayHeadPointDefinition.
        for pt in point_def_list:
            if pt.is_array_head_point:
                return pt
        return point_def_list[0]

    def get_point_named(self, name, index=None):
        """
            Return the PointDefinition with the indicated name and (optionally) index.
            Raise an exception if none found.

        :param name: (string) The point's name.
        :param index: (integer) An optional index value. If supplied, search for an array point at this DNP3 index.
        :return A PointDefinition.
        """
        point_def = self.point_named(name, index=index)
        if point_def is None:
            if index is not None:
                raise DNP3Exception('No point named {} with index {}'.format(name, index))
            else:
                raise DNP3Exception('No point named {}'.format(name))
        return point_def

    def all_points(self):
        """Return a flat list of all PointDefinitions."""
        point_list = []
        for inner_dict in self._points_dictionary().values():
            point_list.extend(inner_dict.values())
        return point_list

    def all_point_names(self):
        return self.points_by_name().keys()


class BasePointDefinition(object):
    """Abstract superclass for PointDefinition data holders."""

    def __init__(self, element_def):
        """Initialize an instance of the PointDefinition from a dictionary of point attributes."""
        self.name = str(element_def.get('name', ''))
        self.type = element_def.get('type', None)
        self.group = element_def.get('group', None)
        self.variation = element_def.get('variation', None)
        self.index = element_def.get('index', None)
        self.description = element_def.get('description', '')
        self.scaling_multiplier = element_def.get('scaling_multiplier', 1)
        self.units = element_def.get('units', '')
        self.event_class = element_def.get('event_class', 2)
        self.event_group = element_def.get('event_group', None)
        self.event_variation = element_def.get('event_variation', None)
        self.selector_block_start = element_def.get('selector_block_start', None)
        self.selector_block_end = element_def.get('selector_block_end', None)
        self.save_on_write = element_def.get('save_on_write', None)

    @property
    def is_array_point(self):
        return False

    @property
    def is_array_head_point(self):
        return False

    @property
    def is_array(self):
        return self.is_array_point or self.is_array_head_point

    def validate_point(self):
        """A PointDefinition has been created. Perform a variety of validations on it."""
        if self.type is not None and self.type not in ['array', 'selector_block']:
            raise ValueError('Invalid type for {}: {}'.format(self.name, self.type))
        if self.group is None:
            raise ValueError('Missing group for {}'.format(self.name))
        if self.variation is None:
            raise ValueError('Missing variation for {}'.format(self.name))
        if self.index is None:
            raise ValueError('Missing index for {}'.format(self.name))

        # Use intelligent defaults for event_group and event_variation based on data type
        if self.event_group is None:
            if self.point_type in EVENT_DEFAULTS_BY_POINT_TYPE:
                self.event_group = EVENT_DEFAULTS_BY_POINT_TYPE[self.point_type]["group"]
            else:
                raise ValueError('Missing event group for {}'.format(self.name))
        if self.event_variation is None:
            if self.point_type in EVENT_DEFAULTS_BY_POINT_TYPE:
                self.event_variation = EVENT_DEFAULTS_BY_POINT_TYPE[self.point_type]["variation"]
            else:
                raise ValueError('Missing event variation for {}'.format(self.name))

        if self.is_selector_block:
            if self.selector_block_start is None:
                raise ValueError('Missing selector_block_end for block named {}'.format(self.name))
            if self.selector_block_end is None:
                raise ValueError('Missing selector_block_end for block named {}'.format(self.name))
            if self.selector_block_start > self.selector_block_end:
                raise ValueError('Selector block end index < start index for block named {}'.format(self.name))
        else:
            if self.selector_block_start is not None:
                raise ValueError('selector_block_start defined for non-selector-block point {}'.format(self.name))
            if self.selector_block_end is not None:
                raise ValueError('selector_block_end defined for non-selector-block point {}'.format(self.name))

    def as_json(self):
        """Return a json description of the PointDefinition."""
        point_json = {
            "name": self.name,
            "group": self.group,
            "variation": self.variation,
            "index": self.index,
            "scaling_multiplier": self.scaling_multiplier,
            "event_class": self.event_class
        }
        if self.type is not None:
            point_json["type"] = self.type
        if self.description is not None:
            point_json["description"] = self.description
        if self.units is not None:
            point_json["units"] = self.units
        if self.event_group is not None:
            point_json["event_group"] = self.event_group
        if self.event_variation is not None:
            point_json["event_variation"] = self.event_variation
        if self.selector_block_start is not None:
            point_json["selector_block_start"] = self.selector_block_start
        if self.selector_block_end is not None:
            point_json["selector_block_end"] = self.selector_block_end
        if self.save_on_write is not None:
            point_json["save_on_write"] = self.save_on_write
        return point_json

    def __str__(self):
        """Return a string description of the PointDefinition."""
        try:
            return '{0} {1} ({2}, index={3}, type={4})'.format(self.__class__.__name__,
                                                               self.name,
                                                               self.group_and_variation,
                                                               self.index,
                                                               self.point_type)
        except UnicodeEncodeError as err:
            _log.error('Unable to convert point definition to string, err = {}'.format(err))
            return ''

    @property
    def group_and_variation(self):
        """Return a string representation of the PointDefinition's group and variation."""
        return '{0}.{1}'.format(self.group, self.variation)

    @property
    def event_group_and_variation(self):
        """Return a string representation of the PointDefinition's event group and event variation."""
        return '{0}.{1}'.format(self.event_group, self.event_variation)

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
    def is_selector_block(self):
        return self.type == 'selector_block'

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
    def point_type_for_group(cls, group):
        """Return the point type for a group value."""
        ptype = POINT_TYPES_BY_GROUP.get(group, None)
        if ptype is None:
            _log.error('No DNP3 point type found for group {}'.format(group))
        return ptype


class PointDefinition(BasePointDefinition):
    """Data holder for an OpenDNP3 data element."""

    def __init__(self, element_def):
        """Initialize an instance of the PointDefinition from a dictionary of point attributes."""
        super(PointDefinition, self).__init__(element_def)
        self.validate_point()

    def validate_point(self):
        """A PointDefinition has been created. Perform a variety of validations on it."""
        super(PointDefinition, self).validate_point()
        if self.type is not None and self.type != 'selector_block':
            raise ValueError('Invalid type for {}: {}'.format(self.name, self.type))


class ArrayHeadPointDefinition(BasePointDefinition):
    """Data holder for an OpenDNP3 data element that is the head point in an array."""

    def __init__(self, json_element):
        """
            Initialize an ArrayPointDefinition instance.
            An ArrayPointDefinition defines an interior point (not the head point) in an array.

        :param json_element: A JSON dictionary of point attributes.
        """
        super(ArrayHeadPointDefinition, self).__init__(json_element)
        self.array_points = json_element.get('array_points', None)
        self.array_times_repeated = json_element.get('array_times_repeated', None)
        self.array_point_definitions = []         # Holds all ArrayPointDefinitions belonging to this array.
        self.validate_point()

    def validate_point(self):
        """An ArrayHeadPointDefinition has been created. Perform a variety of validations on it."""
        super(ArrayHeadPointDefinition, self).validate_point()
        if self.type != 'array':
            raise ValueError('Invalid type {} for array named {}'.format(self.type, self.name))
        if self.array_points is None:
            raise ValueError('Missing array_points for array named {}'.format(self.name))
        if self.array_times_repeated is None:
            raise ValueError('Missing array_times_repeated for array named {}'.format(self.name))

    @property
    def is_array_point(self):
        return True

    @property
    def is_array_head_point(self):
        return True

    def as_json(self):
        """Return a json description of the ArrayHeadPointDefinition."""
        point_json = super(ArrayHeadPointDefinition, self).as_json()
        # array_points has been excluded because it's not a simple data type. Is it needed in the json?
        # if self.array_points is not None:
        #     point_json["array_points"] = self.array_points
        if self.array_times_repeated is not None:
            point_json["array_times_repeated"] = self.array_times_repeated
        return point_json

    @property
    def array_last_index(self):
        """Calculate and return the array's last index value."""
        if self.is_array_head_point:
            return self.index + self.array_times_repeated * len(self.array_points) - 1
        else:
            return None

    def create_array_point_definitions(self, element):
        """Create a separate ArrayPointDefinition for each interior point in the array."""
        for row_number in range(self.array_times_repeated):
            for column_number, pt in enumerate(self.array_points):
                # The ArrayHeadPointDefinition is already defined -- don't create a redundant definition.
                if row_number > 0 or column_number > 0:
                    array_pt_def = ArrayPointDefinition(element, self, row_number, column_number, pt['name'])
                    self.array_point_definitions.append(array_pt_def)
        return self.array_point_definitions


class ArrayPointDefinition(BasePointDefinition):
    """Data holder for an OpenDNP3 data element that is interior to an array."""

    def __init__(self, json_element, base_point_def, row, column, array_element_name):
        """
            Initialize an ArrayPointDefinition instance.
            An ArrayPointDefinition defines an interior point (not the head point) in an array.

        :param json_element: A JSON dictionary of point attributes.
        :param base_point_def: The PointDefinition of the head point in the array.
        :param row: The point's row number in the array.
        :param column: The point's column number in the array.
        :param array_element_name: The point's column name in the array.
        """
        super(ArrayPointDefinition, self).__init__(json_element)
        self.base_point_def = base_point_def
        self.row = row
        self.column = column
        self.index = self.base_point_def.index + row * len(self.base_point_def.array_points) + column
        self.array_element_name = array_element_name
        self.validate_point()

    def validate_point(self):
        """An ArrayPointDefinition has been created. Perform a variety of validations on it."""
        super(ArrayPointDefinition, self).validate_point()
        if self.type != 'array':
            raise ValueError('Invalid type {} for array named {}'.format(self.type, self.name))
        if self.base_point_def is None:
            raise ValueError('Missing base point definition for array point named {}'.format(self.name))
        if self.row is None:
            raise ValueError('Missing row number for array point named {}'.format(self.name))
        if self.column is None:
            raise ValueError('Missing column number for array point named {}'.format(self.name))
        if self.index is None:
            raise ValueError('Missing index value for array point named {}'.format(self.name))
        if self.array_element_name is None:
            raise ValueError('Missing array element name for array point named {}'.format(self.name))

    @property
    def is_array_point(self):
        return True

    @property
    def is_array_head_point(self):
        return False

    def as_json(self):
        """Return a json description of the ArrayPointDefinition."""
        point_json = super(ArrayPointDefinition, self).as_json()
        if self.row is not None:
            point_json["row"] = self.row
        if self.row is not None:
            point_json["column"] = self.column
        if self.row is not None:
            point_json["array_element_name"] = self.array_element_name
        return point_json


class PointValue(object):
    """Data holder for a point value (DNP3 measurement or command) received by an outstation."""

    def __init__(self, command_type, function_code, value, point_def, index, op_type):
        """Initialize an instance of the PointValue."""
        # Don't rely on VOLTTRON utils in this code, which may run outside of VOLTTRON
        # self.when_received = utils.get_aware_utc_now()
        self.when_received = pytz.UTC.localize(datetime.utcnow())
        self.command_type = command_type
        self.function_code = function_code
        self.value = value
        self.point_def = point_def
        self.index = index          # MESA Array point indexes can differ from the indexes of their PointDefinitions.
        self.op_type = op_type

    def __str__(self):
        """Return a string description of the PointValue."""
        str_desc = 'Point value {0} ({1}, {2}.{3}, {4})'
        return str_desc.format(self.value or self.function_code,
                               self.name,
                               self.point_def.group_and_variation,
                               self.index,
                               self.command_type)

    @property
    def name(self):
        """Return the name of the PointDefinition."""
        return self.point_def.name

    def unwrapped_value(self):
        """Unwrap the point's value, returning the sample data type (e.g. an integer, binary, etc. instance)."""
        if self.value is None:
            # For binary commands, send True if function_code is LATCH_ON, False otherwise
            return self.function_code == opendnp3.ControlCode.LATCH_ON
        else:
            return self.value


class PointArray(object):
    """Data holder for a MESA-ESS Array."""

    def __init__(self, point_def):
        """
            The "points" variable is a dictionary of dictionaries:
                0: {
                    0: PointValue,
                    1: PointValue
                },
                1: {
                    0: PointValue,
                    1: PointValue
                }
                (etc.)
            It's stored as dictionaries indexed by index numbers, not as lists,
            because there's no guarantee that array elements will arrive in order.

        :param point_def: The PointDefinition of the array's head point.
        """
        _log.debug('New Array {} starting at {} with bounds ({}, {})'.format(point_def.name,
                                                                             point_def.index,
                                                                             point_def.index,
                                                                             point_def.array_last_index))
        self.point_def = point_def
        self.points = {}

    def __str__(self):
        return 'Array, points = {}'.format(self.points)

    def as_json(self):
        """
            Return a JSON representation of the PointArray:

                [
                    {name1: val1a, name2: val2a, ...},
                    {name1: val1b, name2: val2b, ...},
                    ...
                ]
        """
        names = [d['name'] for d in self.point_def.array_points]
        json_array = []
        for pt_dict_key in sorted(self.points):
            pt_dict = self.points[pt_dict_key]
            json_array.append({name: (pt_dict[i].value if i in pt_dict else None) for i, name in enumerate(names)})
        return json_array

    def contains_index(self, index):
        """Answer whether this Array contains the point index."""
        return self.point_def.index <= index <= self.point_def.array_last_index

    def add_point_value(self, point_value):
        """Add point_value to the Array's "points" dictionary."""
        point_def = point_value.point_def
        row = 0 if point_def.is_array_head_point else point_def.row
        col = 0 if point_def.is_array_head_point else point_def.column
        if row not in self.points:
            self.points[row] = {}
        self.points[row][col] = point_value
