# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, 8minutenergy / Kisensum.
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
# Neither 8minutenergy nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by 8minutenergy or Kisensum.
# }}}
import argparse
import logging
import os
import collections
import yaml

from dnp3.points import PointDefinitions, PointDefinition, DNP3Exception

DEFAULT_FUNCTION_TOPIC = 'mesa/function'

# Values of StepDefinition.optional
OPTIONAL = "O"
MANDATORY = "M"
CONDITIONAL = "C"
ALL_OMC = [OPTIONAL, MANDATORY, CONDITIONAL]

# Values of the elements of StepDefinition.fcodes:
DIRECT_OPERATE = 'direct_operate'       # This is actually DIRECT OPERATE / RESPONSE
SELECT = 'select'                       # This is actually SELECT / RESPONSE
OPERATE = 'operate'                     # This is actually OPERATE / RESPONSE

# Values of StepDefinition.action:
ACTION_ECHO = 'echo'
ACTION_PUBLISH = 'publish'
ACTION_ECHO_AND_PUBLISH = 'echo_and_publish'
ACTION_PUBLISH_AND_RESPOND = 'publish_and_respond'
ACTION_NONE = 'none'

_log = logging.getLogger(__name__)


class FunctionDefinitions(collections.Mapping):
    """In-memory repository of FunctionDefinitions."""

    def __init__(self, point_definitions, function_definitions_path=None):
        self._point_definitions = point_definitions
        self._point_function_map = {}
        self._functions = {}
        self._functions_by_id = {}
        self._named_step_definitions = {}
        if function_definitions_path:
            file_path = os.path.expandvars(os.path.expanduser(function_definitions_path))
            self.load_functions_from_yaml_file(file_path)

    def __getitem__(self, point_def):
        """Return the function associated with this point. Must be unique."""
        return self._point_function_map[point_def]

    def __iter__(self):
        return iter(self._point_function_map)

    def __len__(self):
        return len(self._point_function_map)

    def step_definition_for_point(self, point_definition):
        """Return a StepDefinition for a given point. If there isn't exactly one matching StepDefinition, complain."""
        name = point_definition.name
        step_list = self._step_definitions_by_name().get(name, [])
        if not step_list:
            raise DNP3Exception('No StepDefinition named {}'.format(name))
        if len(step_list) > 1:
            raise DNP3Exception('Found multiple StepDefinitions named {}'.format(name))
        return step_list[0]

    def all_function_names(self):
        return list(self._functions_dictionary().keys())

    def support_point_names(self):
        """Return a dictionary of FunctionDefinitions keyed by their (non-null) support_point_names."""
        return {f.support_point_name: f
                for _, f in self._functions_dictionary().items()
                if f.support_point_name is not None}

    def functions(self):
        return list(self._functions.values())

    def _functions_dictionary(self):
        """Return a (cached) dictionary of FunctionDefinitions, indexed by function name."""
        return self._functions

    def load_functions_from_yaml_file(self, function_definitions_path):
        """Load and cache a YAML file of FunctionDefinitions. Index them by function name."""
        _log.debug('Loading MESA-ESS FunctionDefinitions from {}.'.format(function_definitions_path))
        if function_definitions_path:
            fdef_path = os.path.expandvars(os.path.expanduser(function_definitions_path))
            self._functions = {}
            try:
                with open(fdef_path, 'r') as f:
                    self.load_functions(yaml.load(f)['functions'])
            except Exception as err:
                raise ValueError("Problem parsing {}. Error={}".format(fdef_path, err))
        _log.debug('Loaded {} FunctionDefinitions'.format(len(self._functions)))

    def load_functions(self, function_definitions_json):
        """Load and cache a JSON dictionary of FunctionDefinitions. Index them by function name."""
        _log.debug('Loading MESA-ESS FunctionDefinitions.')
        self._functions = {}
        try:
            for function_def in function_definitions_json:
                new_function = FunctionDefinition(self._point_definitions, function_def)
                self._functions[new_function.name] = new_function

                new_function_point_defs = set(new_function.all_point_defs())
                if new_function_point_defs & set(self._point_function_map.keys()):
                    raise ValueError("Point definition referenced by two functions")
                else:
                    self._point_function_map.update(
                        {point_def: new_function for point_def in new_function_point_defs}
                    )
                # Ensure that the other function caches get rebuilt
                self._functions_by_id = {}
                self._named_step_definitions = {}
        except Exception as err:
            raise ValueError("Problem parsing FunctionDefinitions. Error={}".format(err))
        _log.debug('Loaded {} FunctionDefinitions'.format(len(self._functions)))

    def _step_definitions_by_name(self):
        """Return a (cached) dictionary of lists of StepDefinitions for each step name."""
        if not self._named_step_definitions:
            for func in self._functions_dictionary().values():
                for s in func.steps:
                    if self._named_step_definitions.get(s.name, None):
                        self._named_step_definitions[s.name].append(s)
                    else:
                        self._named_step_definitions[s.name] = [s]
        return self._named_step_definitions

    def functions_by_id(self):
        """Return a (cached) dictionary of FunctionDefinitions, indexed by function ID."""
        if not self._functions_by_id:
            self._functions_by_id = {func.function_id: func for func in self._functions_dictionary().values()}
        return self._functions_by_id

    def point_function_map(self):
        return self._point_function_map

    def function_for_id(self, function_id):
        """Return a specific function definition from (cached) dictionary of FunctionDefinitions."""
        return self.functions_by_id().get(function_id, None)


class FunctionDefinition(object):
    """A MESA-ESS FunctionDefinition (aka mode, command)."""

    def __init__(self, point_definitions, function_def_dict):
        """
            Data holder for the definition of a MESA-ESS function.

        :param function_def_dict: A dictionary of data from which to create the FunctionDefinition.
        """
        try:
            self.function_id = function_def_dict["id"]
            self.name = function_def_dict["name"]
            self.ref = function_def_dict.get("ref", None)
            self.support_point_name = function_def_dict.get("support_point", None)
            self.steps = [StepDefinition(point_definitions, self, step_def) for step_def in function_def_dict["steps"]]
            self._point_steps_map = {}
            for step in self.steps:
                for pd in step.all_point_defs():
                    self._point_steps_map[pd] = step

            # Set supported to False if the Function has a defined support_point_name -- the Control Agent must set it.
            # To override this (support all functions), set config all_functions_supported_by_default = "True".
            self.supported = not self.support_point_name
        except AttributeError as err:
            raise AttributeError('Error creating FunctionDefinition {}, err={}'.format(self.name, err))

    def __str__(self):
        return 'Function {}'.format(self.name)

    def __contains__(self, point_def):
        return point_def in self.all_point_defs()

    def __getitem__(self, point_def):
        return self._point_steps_map[point_def]

    def instance(self):
        """Return an instance of this FunctionDefinition."""
        return Function(self)

    def describe_function(self):
        """Return a string describing a function: its name and all of its StepDefinitions."""
        return 'Function {}: {}'.format(self.name, [s.__str__() for s in self.steps])

    def all_point_defs(self):
        return list(self._point_steps_map.keys())

    def all_points(self):
        return [step_def.point_def for step_def in self.steps]

    def is_mode(self):
        for point in self.all_points():
            if 'ModEna' in point.name:
                return True
        return False

    def get_mode_enable(self):
        for point in self.all_points():
            if 'ModEna' in point.name:
                return point
        return False


class StepDefinition(object):
    """Step definition in a MESA-ESS FunctionDefinition."""

    def __init__(self, point_definitions, function_def, step_def=None):
        """
            Data holder for the definition of a step in a MESA-ESS FunctionDefinition.

        :param function_def: The FunctionDefinition to which the StepDefinition belongs.
        :param step_def: A dictionary of data from which to create the StepDefinition.
        """
        self.function = function_def
        self.point_def = point_definitions[step_def.get('point_name', None)]
        self.step_number = step_def.get('step_number', None)
        self.optional = step_def.get('optional', OPTIONAL)
        self.fcodes = step_def.get('fcodes', [])
        self.response = step_def.get('response', None)
        self.action = step_def.get('action', None)
        self.validate()

    def __str__(self):
        return '{} Step {}: {}'.format(self.function, self.step_number, self.name)

    @property
    def name(self):
        if self.point_def:
            return self.point_def.name
        else:
            return '<Step has no point_def>'

    def all_point_defs(self):
        all_defs = [self.point_def]
        if self.point_def.is_array_head_point:
            all_defs.extend(self.point_def.array_point_definitions)
        return all_defs

    def validate(self):
        if self.step_number is None:
            raise AttributeError('Missing step number in {}'.format(self))
        if self.name is None:
            raise AttributeError('Missing name in {}'.format(self))
        if self.optional not in ALL_OMC:
            raise AttributeError('Invalid optional value in {}: {}'.format(self, self.optional))
        if type(self.fcodes) != list:
            raise ValueError('Invalid fcode for {}, type={}'.format(self.name, type(self.fcodes)))
        for fc in self.fcodes:
            if fc not in [DIRECT_OPERATE, SELECT, OPERATE]:
                raise ValueError('Invalid fcode for {}, fcode={}'.format(self.name, type(self.fcodes)))


class Step(object):
    """A MESA-ESS Step that has been received by an outstation."""

    def __init__(self, definition, func, value):
        """
            Data holder for a received Step.

        :param definition: A StepDefinition.
        :param value: A PointValue.
        """
        self.definition = definition
        self.function = func
        self.value = value

    def __str__(self):
        return '{}: {}'.format(self.definition, self.value)

    def as_json(self, point_type):
        return self.value.as_json() if self.definition.point_def.is_array_head_point else self.value.unwrapped_value()

    def echoes_input(self):
        return self.definition.action in [ACTION_ECHO, ACTION_ECHO_AND_PUBLISH]

    def publish(self):
        return self.definition.action in [ACTION_PUBLISH,
                                          ACTION_ECHO_AND_PUBLISH,
                                          ACTION_PUBLISH_AND_RESPOND]


class FunctionException(Exception):
    """
        Raise exceptions that are used for _process_point_value in Mesa agent.
        Set the current function to None if the exception is raised.
    """
    pass


class Function(object):
    """A MESA-ESS Function that has been received by an outstation."""

    def __init__(self, definition):
        """
            Data holder for a Function received by an outstation.

        :param definition: A FunctionDefinition.
        """
        self.definition = definition
        self.steps = []
        self.complete = False

    def __str__(self):
        return 'Function {}'.format(self.definition.name)

    def __contains__(self, point_def):
        if not isinstance(point_def, PointDefinition):
            raise ValueError("Membership test only works for PointDefinition instance, not {}".format(point_def))
        return point_def in self.definition

    @property
    def last_step(self):
        """
            Return last received step of the function.
        """
        return self.steps[-1] if self.steps else None

    @property
    def next_remaining_mandatory_step_number(self):
        """
            Return next remaining mandatory step number of the function if there is one existed, None otherwise.
        """
        last_received_step_number = 0 if not self.last_step else self.last_step.definition.step_number
        for step_def in self.definition.steps:
            step_number = step_def.step_number
            if step_number > last_received_step_number and step_def.optional == MANDATORY:
                return step_number
        return None

    def add_step(self, step_def, value, function_validation=False):
        """
            Add a step to function if no mandatory step missing and return the step, raise exception otherwise.

        :param step_def: step definition to add to function
        :param value: value of the point in step_def
        :param function_validation: defaults to False.
            When there is mandatory step missing, raise DNP3Exception if function_validation is True,
            raise FunctionException otherwise.
            FunctionException is used for _process_point_value in Mesa agent, if the FunctionException is raised,
            reset current function to None and process the next point as the first step of a new function.
        """
        # Check for missing mandatory steps up to the current step
        if self.next_remaining_mandatory_step_number \
                and step_def.step_number > self.next_remaining_mandatory_step_number:
            exception_message = '{} is missing Mandatory step number {}'.format(
                self,
                self.next_remaining_mandatory_step_number
            )
            if function_validation:
                raise DNP3Exception(exception_message)
            raise FunctionException(exception_message)
        # add current step to self.steps
        step_value = Step(step_def, self, value)
        self.steps.append(step_value)
        return step_value

    def add_point_value(self, point_value, current_array=None, function_validation=False):
        """
            Add a received PointValue as a Step in the current Function. Return the Step.

        :param point_value: point value
        :param current_array: current array
        :param function_validation: defaults to False. If function_validation is True,
            raise DNP3Exception when getting an error while adding a new step to the current function.
            If function_validation is False, reset current function to None if missing mandatory step,
            set the adding step as the first step of the current function if step is not in order,
            or replace the last step by the adding step if step is duplicated.
        """
        step_def = self.definition[point_value.point_def]
        step_number = step_def.step_number
        if not self.last_step:
            self.add_step(step_def, point_value, function_validation)
        else:
            last_received_step_number = self.last_step.definition.step_number
            if step_number != last_received_step_number:
                if step_number < last_received_step_number:
                    if self.next_remaining_mandatory_step_number:
                        if function_validation:
                            raise DNP3Exception('Step {} received after {}'.format(step_number,
                                                                                   last_received_step_number))
                    # Since the old function was complete, treat this as the first step of a new function.
                    self.steps = []
                self.add_step(step_def, point_value, function_validation)
            else:
                if not point_value.point_def.is_array_point:
                    if function_validation:
                        raise DNP3Exception('Duplicate step number {} received'.format(step_number))
                    self.steps.pop()
                    self.add_step(step_def, point_value, function_validation)
                else:
                    # An array point was received for an existing step. Update the step's value.
                    self.last_step.value = current_array

        return self.last_step

    def has_input_point(self):
        """Function has an input pont to be echoed following last step."""
        return self.last_step.echoes_input() if self.last_step else False

    def input_point_name(self):
        """The name of the input point

        @todo This really should be a point_def
        """
        return self.last_step.definition.response if self.last_step else ''

    def publish_now(self):
        """The function has points to published following last step."""
        return self.last_step.publish() if self.last_step else False


def load_and_validate_definitions():
    """
        Standalone method, intended to be invoked from the command line.

        Load PointDefinition and FunctionDefinition files as specified in command line args,
        and validate their contents.
    """
    # Grab JSON and YAML definition file paths from the command line.
    parser = argparse.ArgumentParser()
    parser.add_argument('point_defs', help='path of the point definitions file (json)')
    parser.add_argument('function_defs', help='path of the function definitions file (yaml)')
    args = parser.parse_args()

    point_definitions = PointDefinitions(point_definitions_path=args.point_defs)
    function_definitions = FunctionDefinitions(point_definitions, function_definitions_path=args.function_defs)
    validate_definitions(point_definitions, function_definitions)


def validate_definitions(point_definitions, function_definitions):
    """Validate PointDefinitions, Arrays, SelectorBlocks and FunctionDefinitions."""

    print('\nValidating Point definitions...')
    all_points = point_definitions.all_points()
    print('\t{} point definitions'.format(len(all_points)))

    print('\nValidating Array definitions...')
    array_head_points = [pt for pt in all_points if pt.is_array_head_point]
    array_bounds = {pt: [pt.index, pt.array_last_index] for pt in array_head_points}
    for pt in array_head_points:
        # Print each array's definition. Also, check for overlapping array bounds.
        print('\t{} ({}): indexes=({},{}), elements={}'.format(pt.name,
                                                               pt.point_type,
                                                               pt.index,
                                                               pt.array_last_index,
                                                               len(pt.array_points)))
        for other_pt, other_bounds in array_bounds.items():
            if pt.name != other_pt.name:
                if other_bounds[0] <= pt.index <= other_bounds[1]:
                    print('\tERROR: Overlapping array definition in {} and {}'.format(pt, other_pt))
                if other_bounds[0] <= pt.array_last_index <= other_bounds[1]:
                    print('\tERROR: Overlapping array definition in {} and {}'.format(pt, other_pt))
    print('\t{} array definitions'.format(len(array_head_points)))

    print('\nValidating Selector Block definitions...')
    selector_block_points = [pt for pt in all_points if pt.is_selector_block]
    selector_block_bounds = {pt: [pt.selector_block_start, pt.selector_block_end] for pt in selector_block_points}
    for pt in selector_block_points:
        # Print each selector block's definition. Also, check for overlapping selector block bounds.
        print('\t{} ({}): indexes=({},{})'.format(pt.name,
                                                  pt.point_type,
                                                  pt.selector_block_start,
                                                  pt.selector_block_end))
        for other_pt, other_bounds in selector_block_bounds.items():
            if pt.name != other_pt.name:
                if other_bounds[0] <= pt.selector_block_start <= other_bounds[1]:
                    print('\tERROR: Overlapping selector blocks in {} and {}'.format(pt, other_pt))
                if other_bounds[0] <= pt.selector_block_end <= other_bounds[1]:
                    print('\tERROR: Overlapping selector blocks in {} and {}'.format(pt, other_pt))
    # Check that each save_on_write point references a selector_block_point
    save_on_write_points = [pt for pt in all_points if pt.save_on_write]
    selector_block_point_names = [pt.name for pt in selector_block_points]
    for pt in save_on_write_points:
        if pt.save_on_write not in selector_block_point_names:
            print('\tERROR: {} save_on_write value {} is not a selector block name'.format(pt.name, pt.save_on_write))
    print('\t{} selector block definitions'.format(len(selector_block_points)))

    print('\nValidating Function definitions...')
    functions = function_definitions.all_function_names()
    print('\t{} function definitions'.format(len(functions)))
