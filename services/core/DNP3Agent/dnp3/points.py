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
import logging
import os
import pytz
import re

from volttron.platform import jsonapi
from pydnp3 import opendnp3
from dnp3 import POINT_TYPES, POINT_TYPE_SELECTOR_BLOCK, POINT_TYPE_ENUMERATED, POINT_TYPE_ARRAY
from dnp3 import DATA_TYPE_ANALOG_INPUT, DATA_TYPE_ANALOG_OUTPUT, DATA_TYPE_BINARY_INPUT, DATA_TYPE_BINARY_OUTPUT
from dnp3 import EVENT_CLASSES, DATA_TYPES_BY_GROUP
from dnp3 import DEFAULT_GROUP_BY_DATA_TYPE, DEFAULT_EVENT_CLASS
from dnp3 import PUBLISH_AND_RESPOND

_log = logging.getLogger(__name__)


class DNP3Exception(Exception):
    """Raise exceptions that are specific to the DNP3 agent. No special exception behavior is needed at this time."""
    pass


class PointDefinitions(object):
    """In-memory repository of PointDefinitions."""

    def __init__(self, point_definitions_path=None):
        self._points = {}           # {data_type: {point_index: PointDefinition}}
        self._point_name_dict = {}  # {point_name: [PointDefinition]}
        if point_definitions_path:
            file_path = os.path.expandvars(os.path.expanduser(point_definitions_path))
            self.load_points_from_json_file(file_path)

    def __getitem__(self, name):
        """Return the PointDefinition associated with this name. Must be unique."""
        if name in [None, 'n/a']:
            return None
        return self.get_point_named(name)

    def load_points_from_json_file(self, point_definitions_path):
        """Load and cache a dictionary of PointDefinitions, indexed by point_type and point index."""
        if point_definitions_path:
            try:
                file_path = os.path.expandvars(os.path.expanduser(point_definitions_path))
                _log.debug('Loading DNP3 point definitions from {}.'.format(file_path))
                with open(file_path, 'r') as f:
                    # Filter comments out of the file's contents before loading it as jsonapi.
                    self.load_points(jsonapi.loads(self.strip_comments(f.read())))
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
                    if element.get('type', None) != POINT_TYPE_ARRAY:
                        point_def = PointDefinition(element)
                        self.update_point(point_def)
                    else:
                        point_def = ArrayHeadPointDefinition(element)
                        self.update_point(point_def)
                        # Load a separate ArrayPointDefinition for each interior point in the array.
                        for pt in point_def.create_array_point_definitions(element):
                            self.update_point(pt)
                except ValueError as err:
                    raise DNP3Exception('Validation error for point with json: {}: {}'.format(element, err))
        except Exception as err:
            raise ValueError('Problem parsing PointDefinitions. Error={}'.format(err))
        _log.debug('Loaded {} PointDefinitions'.format(len(self.all_points())))

    def update_point(self, point_def):
        """Add a PointDefinition to self._points and self._point_name_dict."""
        data_type, name, index = point_def.data_type, point_def.name, point_def.index
        data_type_dict = self._points.setdefault(data_type, {})
        name_lst = self._point_name_dict.setdefault(name, [])
        if index in data_type_dict:
            raise ValueError('Duplicate index {} for data type {}'.format(index, data_type))
        if name_lst and point_def.type != 'array':
            raise ValueError('Duplicated point name {}'.format(name))
        data_type_dict[index] = point_def
        name_lst.append(point_def)

    def for_group_and_index(self, group, index):
        """Return a PointDefinition for given group and index"""
        data_type = DATA_TYPES_BY_GROUP.get(group, None)
        if not data_type:
            _log.error('No DNP3 point type found for group {}'.format(group))
        return self._points.get(data_type, {}).get(index, None)

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
        data_type = DATA_TYPE_BINARY_OUTPUT if function_code else DATA_TYPE_ANALOG_OUTPUT
        point_def = self.for_data_type_and_index(data_type, index)
        if not point_def:
            raise DNP3Exception('No DNP3 PointDefinition found for point type {} and index {}'.format(data_type, index))
        point_value = PointValue(command_type,
                                 function_code,
                                 command.value if not function_code else None,
                                 point_def,
                                 index,
                                 op_type)
        _log.debug('Received DNP3 {}'.format(point_value))
        return point_value

    def for_data_type_and_index(self, data_type, index):
        """
            Return a PointDefinition for given data type and index.

        @param data_type: A data type (string).
        @param index: Unique integer index of the PointDefinition to be looked up.
        """
        return self._points.get(data_type, {}).get(index, None)

    def point_named(self, name, index=None):
        """
            Return the PointDefinition with the indicated name and (optionally) index, or None if no match.

        :param name: (string) The point's name.
        :param index: (integer) An optional index value. If supplied, search for an array point at this DNP3 index.
        """
        point_def_list = self._point_name_dict.get(name, None)
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
        for inner_dict in self._points.values():
            point_list.extend(inner_dict.values())
        return point_list


class BasePointDefinition(object):
    """Abstract superclass for PointDefinition data holders."""

    def __init__(self, element_def):
        """Initialize an instance of the PointDefinition from a dictionary of point attributes."""
        self.name = str(element_def.get('name', ''))
        self.data_type = element_def.get('data_type', None)
        self.index = element_def.get('index', None)
        self.type = element_def.get('type', None)
        self.description = element_def.get('description', '')
        self.scaling_multiplier = element_def.get('scaling_multiplier', 1)  # Only used for Analog data_type
        self.units = element_def.get('units', '')
        self.event_class = element_def.get('event_class', DEFAULT_EVENT_CLASS)
        self.selector_block_start = element_def.get('selector_block_start', None)
        self.selector_block_end = element_def.get('selector_block_end', None)
        self.action = element_def.get('action', None)
        self.response = element_def.get('response', None)
        self.category = element_def.get('category', None)
        self.ln_class = element_def.get('ln_class', None)
        self.data_object = element_def.get('data_object', None)
        self.common_data_class = element_def.get('common_data_class', None)
        self.minimum = element_def.get('minimum', -2147483648)              # Only used for Analog data_type
        self.maximum = element_def.get('maximum', 2147483647)               # Only used for Analog data_type
        self.scaling_offset = element_def.get('scaling_offset', 0)          # Only used for Analog data_type
        self.allowed_values = self.convert_allowed_values(element_def.get('allowed_values', None))

    @property
    def is_enumerated(self):
        return self.type == POINT_TYPE_ENUMERATED

    @property
    def is_array_point(self):
        return False

    @property
    def is_array_head_point(self):
        return False

    @property
    def is_array(self):
        return self.is_array_point or self.is_array_head_point

    def convert_allowed_values(self, allowed_values):
        if allowed_values:
            return {int(str_val): description for str_val, description in allowed_values.items()}
        return None

    def validate_point(self):
        """A PointDefinition has been created. Perform a variety of validations on it."""
        if not self.name:
            raise ValueError('Missing point name')
        if self.index is None:
            raise ValueError('Missing index for point {}'.format(self.name))
        if not self.data_type:
            raise ValueError('Missing data type for point {}'.format(self.name))
        if self.data_type not in DEFAULT_GROUP_BY_DATA_TYPE:
            raise ValueError('Invalid data type {} for point {}'.format(self.data_type, self.name))
        if not self.eclass:
            raise ValueError('Invalid event class {} for point {}'.format(self.event_class, self.name))
        if self.type and self.type not in POINT_TYPES:
            raise ValueError('Invalid type {} for point {}'.format(self.type, self.name))
        if self.action == PUBLISH_AND_RESPOND and not self.response:
            raise ValueError('Missing response point name for point {}'.format(self.name))
        if self.is_enumerated and not self.allowed_values:
            raise ValueError('Missing allowed values mapping for point {}'.format(self.name))
        if self.is_selector_block:
            if self.selector_block_start is None:
                raise ValueError('Missing selector_block_start for block named {}'.format(self.name))
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
            "data_type": self.data_type,
            "index": self.index,
            "group": self.group,
            "event_class": self.event_class
        }
        if self.type:
            point_json["type"] = self.type
        if self.description:
            point_json["description"] = self.description
        if self.units:
            point_json["units"] = self.units
        if self.selector_block_start is not None:
            point_json["selector_block_start"] = self.selector_block_start
        if self.selector_block_end is not None:
            point_json["selector_block_end"] = self.selector_block_end
        if self.allowed_values:
            point_json["allowed_values"] = self.allowed_values
        if self.action:
            point_json["action"] = self.action
        if self.response:
            point_json["response"] = self.response
        if self.category:
            point_json["category"] = self.category
        if self.ln_class:
            point_json["ln_class"] = self.ln_class
        if self.data_object:
            point_json["data_object"] = self.data_object
        if self.common_data_class:
            point_json["common_data_class"] = self.common_data_class
        if self.data_type in [DATA_TYPE_ANALOG_INPUT, DATA_TYPE_ANALOG_OUTPUT]:
            point_json.update({
                "scaling_multiplier": self.scaling_multiplier,
                "scaling_offset": self.scaling_offset,
                "minimum": self.minimum,
                "maximum": self.maximum
            })

        return point_json

    def __str__(self):
        """Return a string description of the PointDefinition."""
        try:
            return '{0} {1} (event_class={2}, index={3}, type={4})'.format(
                self.__class__.__name__,
                self.name,
                self.event_class,
                self.index,
                self.data_type
            )
        except UnicodeEncodeError as err:
            _log.error('Unable to convert point definition to string, err = {}'.format(err))
            return ''

    @property
    def group(self):
        return DEFAULT_GROUP_BY_DATA_TYPE.get(self.data_type, None)

    @property
    def is_input(self):
        """Return True if the PointDefinition is a Binary or Analog input point (i.e., sent by the Outstation)."""
        return self.data_type in [DATA_TYPE_ANALOG_INPUT, DATA_TYPE_BINARY_INPUT]

    @property
    def is_output(self):
        """Return True if the PointDefinition is a Binary or Analog output point (i.e., sent by the Master)."""
        return self.data_type in [DATA_TYPE_ANALOG_OUTPUT, DATA_TYPE_BINARY_OUTPUT]

    @property
    def is_selector_block(self):
        return self.type == POINT_TYPE_SELECTOR_BLOCK

    @property
    def eclass(self):
        """Return the PointDefinition's event class, or the default (2) if no event class was defined for the point."""
        return EVENT_CLASSES.get(self.event_class, None)


class PointDefinition(BasePointDefinition):
    """Data holder for an OpenDNP3 data element."""

    def __init__(self, element_def):
        """Initialize an instance of the PointDefinition from a dictionary of point attributes."""
        super(PointDefinition, self).__init__(element_def)
        self.validate_point()

    def validate_point(self):
        """A PointDefinition has been created. Perform a variety of validations on it."""
        super(PointDefinition, self).validate_point()
        if self.type and self.type not in ['selector_block', 'enumerated']:
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
        self.array_point_definitions = []  # Holds all ArrayPointDefinitions belonging to this array.
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
                               self.point_def.event_class,
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
