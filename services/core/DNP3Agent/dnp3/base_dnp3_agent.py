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

import logging
import numbers
import os

from pydnp3 import opendnp3

from volttron.platform.vip.agent import RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers
from volttron.platform.vip.agent import Agent

from outstation import DNP3Outstation
from dnp3 import DEFAULT_POINT_TOPIC, DEFAULT_OUTSTATION_STATUS_TOPIC
from dnp3 import DEFAULT_LOCAL_IP, DEFAULT_PORT
from dnp3 import DATA_TYPE_ANALOG_INPUT, DATA_TYPE_BINARY_INPUT
from dnp3 import PUBLISH_AND_RESPOND
from points import PointDefinitions, PointDefinition, PointArray
from points import DNP3Exception

utils.setup_logging()
_log = logging.getLogger(__name__)


class BaseDNP3Agent(Agent):
    """
        DNP3Agent is a VOLTTRON agent that handles DNP3 outstation communications.

        DNP3Agent models a DNP3 outstation, communicating with a DNP3 master.

        For further information about this agent and DNP3 communications, please see the VOLTTRON
        DNP3 specification, located in VOLTTRON readthedocs
        under http://volttron.readthedocs.io/en/develop/specifications/dnp3_agent.html.

        This agent can be installed from a command-line shell as follows:
            export VOLTTRON_ROOT=<your volttron install directory>
            export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent
            cd $VOLTTRON_ROOT
            python scripts/install-agent.py -s $DNP3_ROOT -i dnp3agent -c $DNP3_ROOT/dnp3agent.config -t dnp3agent -f
    """

    def __init__(self, points=None, point_topic='', local_ip=None, port=None,
                 outstation_config=None, local_point_definitions_path=None, **kwargs):
        """Initialize the DNP3 agent."""
        super(BaseDNP3Agent, self).__init__(**kwargs)
        self.points = points
        self.point_topic = point_topic
        self.local_ip = local_ip
        self.port = port
        self.outstation_config = outstation_config
        self.default_config = {
            'points': points,
            'point_topic': point_topic,
            'local_ip': local_ip,
            'port': port,
            'outstation_config': outstation_config,
        }
        self.application = None
        self.volttron_points = None

        self.point_definitions = None
        self._current_point_values = {}
        self._current_array = None
        self._local_point_definitions_path = local_point_definitions_path

        self.vip.config.set_default('config', self.default_config)
        self.vip.config.subscribe(self._configure, actions=['NEW', 'UPDATE'], pattern='config')

    def _configure(self, config_name, action, contents):
        """Initialize/Update the agent configuration."""
        self._configure_parameters(contents)

    def load_point_definitions(self):
        """
            Load and cache a dictionary of PointDefinitions from a json list.

            Index the dictionary by point_type and point index.
        """
        _log.debug('Loading DNP3 point definitions.')
        try:
            self.point_definitions = PointDefinitions()
            self.point_definitions.load_points(self.points)
        except (AttributeError, TypeError) as err:
            if self._local_point_definitions_path:
                _log.warning("Attempting to load point definitions from local path.")
                self.point_definitions = PointDefinitions(point_definitions_path=self._local_point_definitions_path)
            else:
                raise DNP3Exception("Failed to load point definitions from config store: {}".format(err))

    def start_outstation(self):
        """Start the DNP3Outstation instance, kicking off communication with the DNP3 Master."""
        _log.info('Starting DNP3Outstation')
        self.publish_outstation_status('starting')
        self.application = DNP3Outstation(self.local_ip, self.port, self.outstation_config)
        self.application.start()
        self.publish_outstation_status('running')

    def stop_outstation(self):
        """Shutdown the DNP3Outstation application."""
        _log.info('Stopping DNP3Outstation')
        self.publish_outstation_status('stopping')
        self.application.shutdown()
        self.publish_outstation_status('stopped')
        self.application = None

    def _configure_parameters(self, contents):
        """
            Initialize/Update the DNP3 agent configuration.

            DNP3Agent configuration parameters (the MesaAgent subclass has some more):

            points: (string) A JSON structure of point definitions to be loaded.
            point_topic: (string) Message bus topic to use when publishing DNP3 point values.
                        Default: mesa/point.
            outstation_status_topic: (string) Message bus topic to use when publishing outstation status.
                        Default: mesa/outstation_status.
            local_ip: (string) Outstation's host address (DNS resolved).
                        Default: 0.0.0.0.
            port: (integer) Outstation's port number - the port that the remote endpoint (Master) is listening on.
                        Default: 20000.
            outstation_config: (dictionary) Outstation configuration parameters. All are optional.
                Parameters include:
                    database_sizes: (integer) Size of each DNP3 database buffer.
                                Default: 10000.
                    event_buffers: (integer) Size of the database event buffers.
                                Default: 10.
                    allow_unsolicited: (boolean) Whether to allow unsolicited requests.
                                Default: True.
                    link_local_addr: (integer) Link layer local address.
                                Default: 10.
                    link_remote_addr: (integer) Link layer remote address.
                                Default: 1.
                    log_levels: List of bit field names (OR'd together) that filter what gets logged by DNP3.
                                Default: [NORMAL].
                                Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING.
                    threads_to_allocate: (integer) Threads to allocate in the manager's thread pool.
                                Default: 1.
        """
        config = self.default_config.copy()
        config.update(contents)
        self.points = config.get('points', [])
        self.point_topic = config.get('point_topic', DEFAULT_POINT_TOPIC)
        self.outstation_status_topic = config.get('outstation_status_topic', DEFAULT_OUTSTATION_STATUS_TOPIC)
        self.local_ip = config.get('local_ip', DEFAULT_LOCAL_IP)
        self.port = int(config.get('port', DEFAULT_PORT))
        self.outstation_config = config.get('outstation_config', {})
        _log.debug('DNP3Agent configuration parameters:')
        _log.debug('\tpoints type={}'.format(type(self.points)))
        _log.debug('\tpoint_topic={}'.format(self.point_topic))
        _log.debug('\toutstation_status_topic={}'.format(self.outstation_status_topic))
        _log.debug('\tlocal_ip={}'.format(self.local_ip))
        _log.debug('\tport={}'.format(self.port))
        _log.debug('\toutstation_config={}'.format(self.outstation_config))
        self.load_point_definitions()
        DNP3Outstation.set_agent(self)

        # Stop outstation if DNP3 config has been changed
        if self.application and (
            self.application.local_ip, self.application.port, self.application.outstation_config) != (
                self.local_ip, self.port, self.outstation_config):
            self.stop_outstation()

        # Start outstation if the DNP3 application has not started
        if not self.application:
            self.start_outstation()

        return config

    @RPC.export
    def reset(self):
        """Reset the agent's internal state, emptying point value caches. Used during iterative testing."""
        _log.info('Resetting agent state.')
        self._current_point_values = {}
        self._current_array = {}

    def get_current_point_value(self, data_type, index):
        """Return the most-recently-received PointValue for a given PointDefinition."""
        if data_type not in self._current_point_values or index not in self._current_point_values[data_type]:
            return None
        else:
            return self._current_point_values[data_type][index]

    def _set_point(self, point_name, value):
        """
            (Internal) Set the value of a given input point (no debug trace).

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """
        point_properties = self.volttron_points.get(point_name, {})
        data_type = point_properties.get('data_type', None)
        index = point_properties.get('index', None)
        try:
            if data_type == DATA_TYPE_ANALOG_INPUT:
                wrapped_value = opendnp3.Analog(value)
            elif data_type == DATA_TYPE_BINARY_INPUT:
                wrapped_value = opendnp3.Binary(value)
            else:
                raise Exception('Unexpected data type for DNP3 point named {0}'.format(point_name))
            DNP3Outstation.apply_update(wrapped_value, index)
        except Exception as e:
            raise DNP3Exception(e)

    def process_point_value(self, command_type, command, index, op_type):
        """
            A point value was received from the Master. Process its payload.

        @param command_type: Either 'Select' or 'Operate'.
        @param command: A ControlRelayOutputBlock or else a wrapped data value (AnalogOutputInt16, etc.).
        @param index: DNP3 index of the payload's data definition.
        @param op_type: An OperateType, or None if command_type == 'Select'.
        @return: A CommandStatus value.
        """
        try:
            point_value = self.point_definitions.point_value_for_command(command_type, command, index, op_type)
            if point_value is None:
                return opendnp3.CommandStatus.DOWNSTREAM_FAIL
        except Exception as ex:
            _log.error('No DNP3 PointDefinition for command with index {}'.format(index))
            return opendnp3.CommandStatus.DOWNSTREAM_FAIL

        try:
            self._process_point_value(point_value)
        except Exception as ex:
            _log.error('Error processing DNP3 command: {}'.format(ex))
            # Delete a cached point value (typically occurs only if an error is being handled).
            try:
                self._current_point_values.get(point_value.point_def.data_type, {}).pop(int(point_value.index), None)
            except Exception as err:
                _log.error('Error discarding cached value {}'.format(point_value))
            return opendnp3.CommandStatus.DOWNSTREAM_FAIL

        return opendnp3.CommandStatus.SUCCESS

    def _process_point_value(self, point_value):
        _log.info('Received DNP3 {}'.format(point_value))
        if point_value.command_type == 'Select':
            # Perform any needed validation now, then wait for the subsequent Operate command.
            return None
        else:
            # Update a dictionary that holds the most-recently-received value of each point.
            self._current_point_values.setdefault(point_value.point_def.data_type, {})[
                int(point_value.index)] = point_value
            return point_value

    def get_point_named(self, point_name):
        return self.point_definitions.get_point_named(point_name)

    def update_array_for_point(self, point_value):
        """A received point belongs to a PointArray. Update it."""
        if point_value.point_def.is_array_head_point:
            self._current_array = PointArray(point_value.point_def)
        elif self._current_array is None:
            raise DNP3Exception('Array point received, but there is no current Array.')
        elif not self._current_array.contains_index(point_value.index):
            raise DNP3Exception('Received Array point outside of current Array.')
        self._current_array.add_point_value(point_value)

    def update_input_point(self, point_def, value):
        """
            Update an input point. This may send its PointValue to the Master.

        :param point_def: A PointDefinition.
        :param value: A value to send (unwrapped simple data type, or else a list/array).
        """
        if type(value) == list:
            # It's an array. Break it down into its constituent points, and apply each one separately.
            col_count = len(point_def.array_points)
            cols_by_name = {pt['name']: col for col, pt in enumerate(point_def.array_points)}
            for row_number, point_dict in enumerate(value):
                for pt_name, pt_val in point_dict.iteritems():
                    pt_index = point_def.index + col_count * row_number + cols_by_name[pt_name]
                    array_point_def = self.point_definitions.get_point_named(point_def.name, index=pt_index)
                    self._apply_point_update(array_point_def, pt_index, pt_val)
        else:
            self._apply_point_update(point_def, point_def.index, value)

    @staticmethod
    def _apply_point_update(point_def, point_index, value):
        """
            Set an input point in the outstation database. This may send its PointValue to the Master.

        :param point_def: A PointDefinition.
        :param point_index: A numeric index for the point.
        :param value: A value to send (unwrapped, simple data type).
        """
        data_type = point_def.data_type
        if data_type == DATA_TYPE_ANALOG_INPUT:
            wrapped_val = opendnp3.Analog(float(value))
            if isinstance(value, bool) or not isinstance(value, numbers.Number):
                # Invalid data type
                raise DNP3Exception('Received {} value for {}.'.format(type(value), point_def))
        elif data_type == DATA_TYPE_BINARY_INPUT:
            wrapped_val = opendnp3.Binary(value)
            if not isinstance(value, bool):
                # Invalid data type
                raise DNP3Exception('Received {} value for {}.'.format(type(value), point_def))
        else:
            # The agent supports only DNP3's Analog and Binary point types at this time.
            raise DNP3Exception('Unsupported point type {}'.format(data_type))
        if wrapped_val is not None:
            DNP3Outstation.apply_update(wrapped_val, point_index)
        _log.debug('Sent DNP3 point {}, value={}'.format(point_def, wrapped_val.value))

    def publish_point_value(self, point_value):
        """Publish a PointValue as it is received from the DNP3 Master."""
        _log.info('Publishing DNP3 {}'.format(point_value))
        msg = {
            point_value.name: (point_value.unwrapped_value() if point_value else None)
        }

        if point_value.point_def.action == PUBLISH_AND_RESPOND:
            msg.update({
                'response': point_value.point_def.response
            })

        self.publish_data(self.point_topic, msg)

    def publish_outstation_status(self, outstation_status):
        """Publish outstation status."""
        _log.info('Publishing outstation status: {}'.format(outstation_status))
        self.publish_data(self.outstation_status_topic, outstation_status)

    def publish_data(self, topic, msg):
        """Publish a payload to the message bus."""
        try:
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=topic,
                                    headers={headers.TIMESTAMP: utils.format_timestamp(utils.get_aware_utc_now())},
                                    message=msg)
        except Exception as err:
            if os.environ.get('UNITTEST', False):
                _log.debug('Disregarding publish_data exception during unit test')
            else:
                raise DNP3Exception('Error publishing topic {}, message {}: {}'.format(topic, msg, err))

    def dnp3_point_name(self, point_name):
        """
            Return a point's DNP3 point name, mapped from its VOLTTRON point name if necessary.

            If VOLTTRON point names were configured (by the DNP device driver), map them to DNP3 point names.
        """
        dnp3_point_name = self.volttron_points.get(point_name, '') if self.volttron_points else point_name
        if not dnp3_point_name:
            raise DNP3Exception('No configured point for {}'.format(point_name))
        return dnp3_point_name

    @RPC.export
    def get_point(self, point_name):
        """
            Look up the most-recently-received value for a given output point.

        @param point_name: The point name of a DNP3 PointDefinition.
        @return: The (unwrapped) value of a received point.
        """
        _log.info('Getting point value for {}'.format(point_name))
        try:
            point_name = self.dnp3_point_name(point_name)
            point_def = self.point_definitions.get_point_named(point_name)
            point_value = self.get_current_point_value(point_def.data_type, point_def.index)
            return point_value.unwrapped_value() if point_value else None
        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def get_point_by_index(self, data_type, index):
        """
            Look up the most-recently-received value for a given point.

        @param data_type: The data_type of a DNP3 point.
        @param index: The index of a DNP3 point.
        @return: The (unwrapped) value of a received point.
        """
        _log.info('Getting point value for data_type {} and index {}'.format(data_type, index))
        try:
            point_value = self.get_current_point_value(data_type, index)
            return point_value.unwrapped_value() if point_value else None
        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def get_points(self, point_list):
        """
            Look up the most-recently-received value of each configured output point.

        @param point_list: A list of point names.
        @return: A dictionary of point values, indexed by their point names.
        """
        _log.info('Getting values for the following points: {}'.format(point_list))
        try:
            return {name: self.get_point(name) for name in point_list}
        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def get_configured_points(self):
        """
            Look up the most-recently-received value of each configured point.

        @return: A dictionary of point values, indexed by their point names.
        """
        if self.volttron_points is None:
            raise DNP3Exception('DNP3 points have not been configured')

        _log.info('Getting all DNP3 configured point values')
        try:
            return {name: self.get_point(name) for name in self.volttron_points}
        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def set_point(self, point_name, value):
        """
            Set the value of a given input point.

        @param point_name: The point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """
        _log.info('Setting DNP3 {} point value = {}'.format(point_name, value))
        try:
            self.update_input_point(self.get_point_named(self.dnp3_point_name(point_name)), value)

        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def set_points(self, point_dict):
        """
            Set point values for a dictionary of points.

        @param point_dict: A dictionary of {point_name: value} for a list of DNP3 points to set.
        """
        _log.info('Setting DNP3 point values: {}'.format(point_dict))
        try:
            for point_name, value in point_dict.iteritems():
                self.update_input_point(self.get_point_named(self.dnp3_point_name(point_name)), value)
        except Exception as e:
            raise DNP3Exception(e)

    @RPC.export
    def config_points(self, point_map):
        """
            For each of the agent's points, map its VOLTTRON point name to its DNP3 group and index.

        @param point_map: A dictionary that maps a point's VOLTTRON point name to its DNP3 group and index.
        """
        _log.info('Configuring DNP3 points: {}'.format(point_map))
        self.volttron_points = point_map

    @RPC.export
    def get_point_definitions(self, point_name_list):
        """
            For each DNP3 point name in point_name_list, return a dictionary with each of the point definitions.

            The returned dictionary looks like this:

            {
                "point_name1": {
                    "property1": "property1_value",
                    "property2": "property2_value",
                    ...
                },
                "point_name2": {
                    "property1": "property1_value",
                    "property2": "property2_value",
                    ...
                }
            }

            If a definition cannot be found for a point name, it is omitted from the returned dictionary.

        :param point_name_list: A list of point names.
        :return: A dictionary of point definitions.
        """
        _log.info('Fetching a list of DNP3 point definitions for {}'.format(point_name_list))
        try:
            response = {}
            for name in point_name_list:
                point_def = self.point_definitions.get_point_named(self.dnp3_point_name(name))
                if point_def is not None:
                    response[name] = point_def.as_json()
            return response
        except Exception as e:
            raise DNP3Exception(e)
