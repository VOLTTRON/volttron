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
import json
import logging
import sys

from pydnp3 import opendnp3

from volttron.platform.agent import utils
from volttron.platform.vip.agent import RPC, Core

from dnp3.base_dnp3_agent import BaseDNP3Agent
from dnp3.outstation import DNP3Outstation

from dnp3.points import DNP3Exception
from dnp3.points import DEFAULT_LOCAL_IP, DEFAULT_PORT
from dnp3.points import DEFAULT_POINT_TOPIC, DEFAULT_OUTSTATION_STATUS_TOPIC

from dnp3.mesa.functions import DEFAULT_FUNCTION_TOPIC, ACTION_PUBLISH_AND_RESPOND
from dnp3.mesa.functions import FunctionDefinitions, Function
from dnp3.mesa.functions import validate_definitions

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

    def __init__(self, points=None, functions=None,
                 point_topic='', local_ip=None, port=None, outstation_config=None,
                 function_topic='', outstation_status_topic='',
                 all_functions_supported_by_default='',
                 local_function_definitions_path=None, **kwargs):
        """Initialize the MESA agent."""
        super(MesaAgent, self).__init__(**kwargs)
        self.functions = functions
        self.function_topic = function_topic
        self.outstation_status_topic = outstation_status_topic
        self.all_functions_supported_by_default = all_functions_supported_by_default
        self.default_config = {
            'points': points,
            'functions': functions,
            'point_topic': point_topic,
            'local_ip': local_ip,
            'port': port,
            'outstation_config': outstation_config,
            'function_topic': function_topic,
            'outstation_status_topic': outstation_status_topic,
            'all_functions_supported_by_default': all_functions_supported_by_default
        }
        self.vip.config.set_default('config', self.default_config)
        self.vip.config.subscribe(self._configure, actions=['NEW', 'UPDATE'], pattern='config')

        self.function_definitions = None
        self._current_func = None
        self._local_function_definitions_path = local_function_definitions_path

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
        self.all_functions_supported_by_default = config.get('all_functions_supported_by_default', "False")
        _log.debug('MesaAgent configuration parameters:')
        _log.debug('\tfunctions type={}'.format(type(self.functions)))
        _log.debug('\tfunction_topic={}'.format(self.function_topic))
        _log.debug('\tall_functions_supported_by_default={}'.format(self.all_functions_supported_by_default))
        self.load_function_definitions()
        self.supported_functions = []
        # Un-comment the next line to do more detailed validation and print definition statistics.
        # validate_definitions(self.point_definitions, self.function_definitions)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """Start the DNP3Outstation instance, kicking off communication with the DNP3 Master."""
        self._configure_parameters(self.default_config)
        _log.info('Starting DNP3Outstation')
        self.publish_outstation_status('starting')
        self.application = DNP3Outstation(self.local_ip, self.port, self.outstation_config)
        self.application.start()
        self.publish_outstation_status('running')

    def load_function_definitions(self):
        """Populate the FunctionDefinitions repository from JSON in the config store."""
        _log.debug('Loading MESA function definitions')
        try:
            if type(self.functions) == str:
                function_defs = self.get_from_config_store(self.functions)
            else:
                function_defs = self.functions
            self.function_definitions = FunctionDefinitions(self.point_definitions)
            self.function_definitions.load_functions(function_defs['functions'])
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
        self.set_current_function(None)

    def _process_point_value(self, point_value):
        """
            A PointValue was received from the Master. Process its payload.

        :param point_value: A PointValue.
        """
        try:
            point_val = super(MesaAgent, self)._process_point_value(point_value)
            if point_val:
                self.update_function_for_point_value(point_val)
                # If we don't have a function, we don't care.
                if self.current_function:
                    if self.current_function.has_input_point():
                        self.update_input_point(
                            self.get_point_named(self.current_function.input_point_name()),
                            point_val.unwrapped_value()
                        )
                    if self.current_function.publish_now():
                        self.publish_function_step(self.current_function.last_step)

        except Exception as err:
            self.set_current_function(None)             # Discard the current function
            raise DNP3Exception('Error processing point value: {}'.format(err))

    def update_function_for_point_value(self, point_value):
        """Add point_value to the current Function if appropriate."""
        try:
            current_function = self.current_function_for(point_value.point_def)
            if current_function is None:
                return None
            if point_value.point_def.is_array_point:
                self.update_array_for_point(point_value)
            current_function.add_point_value(point_value, current_array=self._current_array)
        except DNP3Exception as err:
            raise DNP3Exception('Error updating function: {}'.format(err))

    def current_function_for(self, new_point_def):
        """A point was received. Return the current Function, updating it if necessary."""
        new_point_function_def = self.function_definitions.get(new_point_def, None)
        if new_point_function_def is None:
            return None
        if self.current_function and new_point_function_def != self.current_function.definition:
            if not self.current_function.complete:
                raise DNP3Exception('Mismatch: {} does not belong to {}'.format(new_point_def, self.current_function))
            # The current Function is done, and a new Function is arriving. Discard the old one.
            self.set_current_function(None)
        if not self.current_function:
            self.set_current_function(Function(new_point_function_def))
        return self.current_function

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

    @property
    def current_function(self):
        """Return the Function being accumulated by the Outstation."""
        return self._current_func

    def set_current_function(self, func):
        """Set the Function being accumulated by the Outstation to the supplied value, which might be None."""
        if func:
            if self.all_functions_supported_by_default != "True":
                if not func.definition.supported:
                    raise DNP3Exception('Received a point for unsupported {}'.format(func))
        self._current_func = func
        return func

    def publish_function_step(self, step_to_send):
        """A Function Step was received from the DNP3 Master. Publish the Function."""
        function_to_send = step_to_send.function
        msg = {
            "function_name": function_to_send.definition.name,
            "points": {step.definition.name: step.as_json(self.get_point_named(step.definition.name).type)
                       for step in function_to_send.steps}
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
    except StandardError:
        config = {}
    return MesaAgent(points=config.get('points', []),
                     functions=config.get('functions', []),
                     point_topic=config.get('point_topic', DEFAULT_POINT_TOPIC),
                     function_topic=config.get('function_topic', DEFAULT_FUNCTION_TOPIC),
                     outstation_status_topic=config.get('outstation_status_topic', DEFAULT_OUTSTATION_STATUS_TOPIC),
                     local_ip=config.get('local_ip', DEFAULT_LOCAL_IP),
                     port=config.get('port', DEFAULT_PORT),
                     outstation_config=config.get('outstation_config', {}),
                     all_functions_supported_by_default=config.get('all_functions_supported_by_default', "False"),
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
