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
import logging
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import RPC

from dnp3.base_dnp3_agent import BaseDNP3Agent

from dnp3.points import DNP3Exception
from dnp3 import DEFAULT_LOCAL_IP, DEFAULT_PORT
from dnp3 import DEFAULT_POINT_TOPIC, DEFAULT_OUTSTATION_STATUS_TOPIC
from dnp3 import PUBLISH, PUBLISH_AND_RESPOND

from dnp3.mesa.functions import DEFAULT_FUNCTION_TOPIC, ACTION_PUBLISH_AND_RESPOND
from dnp3.mesa.functions import FunctionDefinitions, Function, FunctionException

__version__ = '1.1'

utils.setup_logging()
_log = logging.getLogger(__name__)


class MesaAgent(BaseDNP3Agent):
    """
        MesaAgent is a VOLTTRON agent that handles MESA-ESS DNP3 outstation communications.

        MesaAgent models a DNP3 outstation, communicating with a DNP3 master.

        For further information about this agent, MESA-ESS, and DNP3 communications, please
        see the VOLTTRON MESA-ESS agent specification, which can be found in VOLTTRON readthedocs
        at http://volttron.readthedocs.io/en/develop/specifications/mesa_agent.html.

        This agent can be installed from a command-line shell as follows:
            $ export VOLTTRON_ROOT=<volttron github install directory>
            $ cd $VOLTTRON_ROOT
            $ source services/core/DNP3Agent/install_mesa_agent.sh
        That file specifies a default agent configuration, which can be overridden as needed.
    """

    def __init__(self, functions=None, function_topic='', outstation_status_topic='',
                 all_functions_supported_by_default=False,
                 local_function_definitions_path=None, function_validation=False, **kwargs):
        """Initialize the MESA agent."""
        super(MesaAgent, self).__init__(**kwargs)
        self.functions = functions
        self.function_topic = function_topic
        self.outstation_status_topic = outstation_status_topic
        self.all_functions_supported_by_default = all_functions_supported_by_default
        self.function_validation = function_validation

        # Update default config
        self.default_config.update({
            'functions': functions,
            'function_topic': function_topic,
            'outstation_status_topic': outstation_status_topic,
            'all_functions_supported_by_default': all_functions_supported_by_default,
            'function_validation': function_validation
        })

        # Update default config in config store.
        self.vip.config.set_default('config', self.default_config)

        self.function_definitions = None
        self._local_function_definitions_path = local_function_definitions_path

        self._current_functions = dict()  # {function_id: Function}
        self._current_block = dict()      # {name: name, index: index}
        self._selector_block = dict()     # {selector_block_point_name: {selector_index: [Step]}}
        self._edit_selectors = list()     # [{name: name, index: index}]

    def _configure_parameters(self, contents):
        """
            Initialize/Update the MesaAgent configuration.

            See also the superclass version of this method, which does most of the initialization.
            MesaAgent configuration parameters:

            functions: (string) A JSON structure of function definitions to be loaded.
            function_topic: (string) Message bus topic to use when publishing MESA-ESS functions.
                        Default: mesa/function.
            all_functions_supported_by_default: (boolean) When deciding whether to reject points for unsupported
                        functions, ignore the values of their 'supported' points: simply treat all functions as
                        supported.
                        Default: False.
        """
        config = super(MesaAgent, self)._configure_parameters(contents)
        self.functions = config.get('functions', {})
        self.function_topic = config.get('function_topic', DEFAULT_FUNCTION_TOPIC)
        self.all_functions_supported_by_default = config.get('all_functions_supported_by_default', False)
        self.function_validation = config.get('function_validation', False)
        _log.debug('MesaAgent configuration parameters:')
        _log.debug('\tfunctions type={}'.format(type(self.functions)))
        _log.debug('\tfunction_topic={}'.format(self.function_topic))
        _log.debug('\tall_functions_supported_by_default={}'.format(bool(self.all_functions_supported_by_default)))
        _log.debug('\tfuntion_validation={}'.format(bool(self.function_validation)))
        self.load_function_definitions()
        self.supported_functions = []
        # Un-comment the next line to do more detailed validation and print definition statistics.
        # validate_definitions(self.point_definitions, self.function_definitions)

    def load_function_definitions(self):
        """Populate the FunctionDefinitions repository from JSON in the config store."""
        _log.debug('Loading MESA function definitions')
        try:
            self.function_definitions = FunctionDefinitions(self.point_definitions)
            self.function_definitions.load_functions(self.functions['functions'])
        except (AttributeError, TypeError) as err:
            if self._local_function_definitions_path:
                _log.warning("Attempting to load Function Definitions from local path.")
                self.function_definitions = FunctionDefinitions(
                    self.point_definitions,
                    function_definitions_path=self._local_function_definitions_path)
            else:
                raise DNP3Exception("Failed to load Function Definitions from config store: {}".format(err))

    @RPC.export
    def reset(self):
        """Reset the agent's internal state, emptying point value caches. Used during iterative testing."""
        super(MesaAgent, self).reset()
        self._current_functions = dict()
        self._current_block = dict()
        self._selector_block = dict()
        self._edit_selectors = list()

    @RPC.export
    def get_selector_block(self, block_name, index):
        try:
            return {step.definition.name: step.as_json() for step in self._selector_block[block_name][index]}
        except KeyError:
            _log.debug('Have not received data for Selector Block {} at Edit Selector {}'.format(block_name, index))
            return None

    def _process_point_value(self, point_value):
        """
            A PointValue was received from the Master. Process its payload.

        :param point_value: A PointValue.
        """
        try:
            point_val = super(MesaAgent, self)._process_point_value(point_value)

            if point_val:
                if point_val.point_def.is_selector_block:
                    self._current_block = {
                        'name': point_val.point_def.name,
                        'index': float(point_val.value)
                    }
                    _log.debug('Starting to receive Selector Block {name} at Edit Selector {index}'.format(
                        **self._current_block
                    ))

                # Publish mesa/point if the point action is PUBLISH or PUBLISH_AND_RESPOND
                if point_val.point_def.action in (PUBLISH, PUBLISH_AND_RESPOND):
                    self.publish_point_value(point_value)

                self.update_function_for_point_value(point_val)

                if self._current_functions:
                    for current_func_id, current_func in self._current_functions.items():
                        # if step action is ACTION_ECHO or ACTION_ECHO_AND_PUBLISH
                        if current_func.has_input_point():
                            self.update_input_point(
                                self.get_point_named(current_func.input_point_name()),
                                point_val.unwrapped_value()
                            )

                        # if step is the last curve or schedule step
                        if self._current_block and point_val.point_def == current_func.definition.last_step.point_def:
                            current_block_name = self._current_block['name']
                            self._selector_block.setdefault(current_block_name, dict())
                            self._selector_block[current_block_name][self._current_block['index']] = current_func.steps

                            _log.debug('Saved Selector Block {} at Edit Selector {}: {}'.format(
                                self._current_block['name'],
                                self._current_block['index'],
                                self.get_selector_block(self._current_block['name'], self._current_block['index'])
                            ))

                            self._current_block = dict()

                        # if step reference to a curve or schedule function
                        func_ref = current_func.last_step.definition.func_ref
                        if func_ref:
                            block_name = self.function_definitions[func_ref].first_step.name
                            block_index = float(point_val.value)
                            if not self._selector_block.get(block_name, dict()).get(block_index, None):
                                error_msg = 'Have not received data for Selector Block {} at Edit Selector {}'
                                raise DNP3Exception(error_msg.format(block_name, block_index))
                            current_edit_selector = {
                                'name': block_name,
                                'index': block_index
                            }
                            if current_edit_selector not in self._edit_selectors:
                                self._edit_selectors.append(current_edit_selector)

                        # if step action is ACTION_PUBLISH, ACTION_ECHO_AND_PUBLISH, or ACTION_PUBLISH_AND_RESPOND
                        if current_func.publish_now():
                            self.publish_function_step(current_func.last_step)

                        # if current function is completed
                        if current_func.complete:
                            self._current_functions.pop(current_func_id)
                            self._edit_selectors = list()

        except (DNP3Exception, FunctionException) as err:
            self._current_functions = dict()
            self._edit_selectors = list()
            if type(err) == DNP3Exception:
                raise DNP3Exception('Error processing point value: {}'.format(err))

    def update_function_for_point_value(self, point_value):
        """Add point_value to the current Function if appropriate."""
        error_msg = None
        current_functions = self.current_function_for(point_value.point_def)
        if not current_functions:
            return None
        for function_id, current_function in current_functions.items():
            try:
                if point_value.point_def.is_array_point:
                    self.update_array_for_point(point_value)
                current_function.add_point_value(point_value,
                                                 current_array=self._current_array,
                                                 function_validation=self.function_validation)
            except (DNP3Exception, FunctionException) as err:
                current_functions.pop(function_id)
                if type(err) == DNP3Exception:
                    error_msg = err
        if error_msg and not current_functions:
            raise DNP3Exception('Error updating function: {}'.format(error_msg))

    def current_function_for(self, new_point_def):
        """A point was received. Return the current Function, updating it if necessary."""
        new_point_function_def = self.function_definitions.get_fdef_for_pdef(new_point_def)
        if new_point_function_def is None:
            return None
        if self._current_functions:
            current_funcs = dict()
            for func_def in new_point_function_def:
                val = self._current_functions.pop(func_def.function_id, None)
                if val:
                    current_funcs.update({func_def.function_id: val})
            self._current_functions = current_funcs
        else:
            for func_def in new_point_function_def:
                if not self.all_functions_supported_by_default and not func_def.supported:
                    raise DNP3Exception('Received a point for unsupported {}'.format(func_def))
                self._current_functions[func_def.function_id] = Function(func_def)
        return self._current_functions

    def update_input_point(self, point_def, value):
        """
            Update an input point. This may send its PointValue to the Master.

        :param point_def: A PointDefinition.
        :param value: A value to send (unwrapped simple data type, or else a list/array).
        """
        super(MesaAgent, self).update_input_point(point_def, value)
        if type(value) != list:
            # Side-effect: If it's a Support point for a Function, update the Function's "supported" property.
            func = self.function_definitions.support_point_names().get(point_def.name, None)
            if func is not None and func.supported != value:
                _log.debug('Updating supported property to {} in {}'.format(value, func))
                func.supported = value

    def publish_function_step(self, step_to_send):
        """A Function Step was received from the DNP3 Master. Publish the Function."""
        function_to_send = step_to_send.function

        points = {step.definition.name: step.as_json() for step in function_to_send.steps}
        for edit_selector in self._edit_selectors:
            block_name = edit_selector['name']
            index = edit_selector['index']
            try:
                points[block_name][index] = self.get_selector_block(block_name, index)
            except (KeyError, TypeError):
                points[block_name] = {
                    index: self.get_selector_block(block_name, index)
                }

        msg = {
            "function_id": function_to_send.definition.function_id,
            "function_name": function_to_send.definition.name,
            "points": points
        }
        if step_to_send.definition.action == ACTION_PUBLISH_AND_RESPOND:
            msg["expected_response"] = step_to_send.definition.response
        _log.info('Publishing MESA {} message {}'.format(function_to_send, msg))
        self.publish_data(self.function_topic, msg)


def mesa_agent(config_path, **kwargs):
    """
        Parse the MesaAgent configuration. Return an agent instance created from that config.

    :param config_path: (str) Path to a configuration file.
    :returns: (MesaAgent) The MESA agent
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return MesaAgent(points=config.get('points', []),
                     functions=config.get('functions', []),
                     point_topic=config.get('point_topic', DEFAULT_POINT_TOPIC),
                     function_topic=config.get('function_topic', DEFAULT_FUNCTION_TOPIC),
                     outstation_status_topic=config.get('outstation_status_topic', DEFAULT_OUTSTATION_STATUS_TOPIC),
                     local_ip=config.get('local_ip', DEFAULT_LOCAL_IP),
                     port=config.get('port', DEFAULT_PORT),
                     outstation_config=config.get('outstation_config', {}),
                     all_functions_supported_by_default=config.get('all_functions_supported_by_default', False),
                     function_validation=config.get('function_validation', False),
                     **kwargs)


def main():
    """Main method called to start the agent."""
    utils.vip_main(mesa_agent, identity='mesaagent', version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
