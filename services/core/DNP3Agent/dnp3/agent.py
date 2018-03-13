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

import logging
import os
import sys

from volttron.platform.agent import utils
from volttron.platform.messaging import headers
from volttron.platform.vip.agent import Agent, Core, RPC

from pydnp3 import opendnp3
from models import PointDefinition, PointValue
from models import POINT_TYPE_ANALOG_INPUT, POINT_TYPE_BINARY_INPUT
from outstation import DNP3Outstation, OutstationApp

DEFAULT_POINT_TOPIC = 'dnp3/point'
DEFAULT_LOCAL_IP = "0.0.0.0"
DEFAULT_PORT = 20000

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.0'


class DNP3Agent(Agent):
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

    def __init__(self, point_definitions_path='', point_topic='', local_ip=None, port=None,
                 outstation_config=None, **kwargs):
        """Initialize the DNP3 agent. Set up a callback to publish point values as they're received from the master."""
        super(DNP3Agent, self).__init__(enable_web=True, **kwargs)
        self.point_definitions_path = point_definitions_path
        self.point_topic = point_topic
        self.local_ip = local_ip
        self.port = port
        self.outstation_config = outstation_config
        self.default_config = {
            'point_definitions_path': point_definitions_path,
            'point_topic': point_topic,
            'local_ip': local_ip,
            'port': port,
            'outstation_config': outstation_config,
        }
        self.vip.config.set_default('config', self.default_config)
        self.vip.config.subscribe(self._configure, actions=['NEW', 'UPDATE'], pattern='config')
        self.application = None
        self.volttron_points = None

    def _configure(self, config_name, action, contents):
        """
            Initialize/Update the DNP3Agent configuration.

            DNP3Agent configuration parameters:

            point_definitions_path: (string, required) Pathname of the JSON file containing DNP3 point definitions.
            point_topic: (string) VOLTTRON message bus topic to use when publishing DNP3 point values.
                        Default: dnp3/point.
            local_ip: (string) Outstation's host address (DNS resolved).
                        Default: 0.0.0.0.
            port: (integer) Outstation's port number - the port that the remote endpoint (Master) is listening on.
                        Default: 20000.
            outstation_config: (dictionary) Outstation configuration parameters. All are optional.
                Parameters include:
                    database_sizes: (integer) Size of each DNP3 database buffer.
                                Default: 10.
                    event_buffers: (integer) Size of the database event buffers.
                                Default: 10.
                    allow_unsolicited: (boolean) Whether to allow unsolicited requests.
                                Default: True.
                    link_local_addr: (integer) Link layer local address.
                                Default: 10.
                    link_remote_addr: (integer) Link layer remote address.
                                Default: 1.
                    log_levels: List of bit field names (OR'd together) that filter what gets logged by DNP3.
                                Default: NORMAL.
                                Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING.
                    threads_to_allocate: (integer) Threads to allocate in the manager's thread pool.
                                Default: 1.
        """
        config = self.default_config.copy()
        config.update(contents)
        self.point_definitions_path = config.get('point_definitions_path', '')
        self.point_topic = config.get('point_topic', DEFAULT_POINT_TOPIC)
        self.local_ip = config.get('local_ip', DEFAULT_LOCAL_IP)
        self.port = int(config.get('port', DEFAULT_PORT))
        self.outstation_config = config.get('outstation_config', {})
        _log.debug('DNP3Agent configuration parameters:')
        _log.debug('\tpoint_definitions_path={}'.format(self.point_definitions_path))
        _log.debug('\tpoint_topic={}'.format(self.point_topic))
        _log.debug('\tlocal_ip={}'.format(self.local_ip))
        _log.debug('\tport={}'.format(self.port))
        _log.debug('\toutstation_config={}'.format(self.outstation_config))
        self.load_point_definitions()
        DNP3Outstation.set_app(OutstationApp(publish_point_callback=self.publish_point_value))
        self.application = DNP3Outstation(self.local_ip, self.port, self.outstation_config)

    @RPC.export
    def get_point(self, point_name):
        """
            Look up the most-recently-received value for a given output point.

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @return: The (unwrapped) value of a received point.
        """
        _log.debug('Getting DNP3 point value for {}'.format(point_name))
        self._get_point(point_name)

    def _get_point(self, point_name):
        """
            (Internal) Look up the most-recently-received value for a given output point (no debug trace).

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @return: The (unwrapped) value of a received point.
        """
        try:
            point_properties = self.volttron_points.get(point_name, {})
        except AttributeError:
            raise DNP3Exception('DNP3 points have not been configured')
        try:
            group = point_properties.get('group', None)
            index = point_properties.get('index', None)
            point_type = PointDefinition.point_type_for_group(group)
            point_value = PointValue.get_current_value(point_type, index)
            return point_value.value if point_value else None
        except Exception as e:
            raise DNP3Exception(e.message)

    @RPC.export
    def get_points(self):
        """
            Look up the most-recently-received value of each configured output point.

        @return: A dictionary of point values, indexed by their VOLTTRON point names.
        """
        if self.volttron_points is None:
            raise DNP3Exception('DNP3 points have not been configured')
        else:
            _log.debug('Getting all DNP3 configured point values')
            try:
                return {name: self._get_point(name) for name in self.volttron_points}
            except Exception as e:
                raise DNP3Exception(e.message)

    @RPC.export
    def set_point(self, point_name, value):
        """
            Set the value of a given input point.

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """
        _log.debug('Setting DNP3 {} point value to {}'.format(point_name, value))
        self._set_point(point_name, value)

    def _set_point(self, point_name, value):
        """
            (Internal) Set the value of a given input point (no debug trace).

        @param point_name: The VOLTTRON point name of a DNP3 PointDefinition.
        @param value: The value to set. The value's data type must match the one in the DNP3 PointDefinition.
        """
        point_properties = self.volttron_points.get(point_name, {})
        group = point_properties.get('group', None)
        index = point_properties.get('index', None)
        point_type = PointDefinition.point_type_for_group(group)
        try:
            if point_type == POINT_TYPE_ANALOG_INPUT:
                wrapped_value = opendnp3.Analog(value)
            elif point_type == POINT_TYPE_BINARY_INPUT:
                wrapped_value = opendnp3.Binary(value)
            else:
                raise Exception('Unexpected data type for DNP3 point named {0}'.format(point_name))
            DNP3Outstation.apply_update(wrapped_value, index)
        except Exception as e:
            raise DNP3Exception(e.message)

    @RPC.export
    def set_points(self, point_list):
        """
            Set point values for a list of points.

        @param point_list: An array of (point_name, value) for a list of DNP3 points to set.
        """
        _log.debug('Setting an array of DNP3 point values')
        for (point_name, value) in point_list:
            self.set_point(point_name, value)

    @RPC.export
    def config_points(self, point_map):
        """
            For each of the agent's points, map its VOLTTRON point name to its DNP3 group and index.

        @param point_map: A dictionary that maps a point's VOLTTRON point name to its DNP3 group and index.
        """
        _log.debug('Configuring DNP3 points: {}'.format(point_map))
        self.volttron_points = point_map

    def publish_point_value(self, point_value):
        """Publish a PointValue as it is received from the DNP3 Master."""
        _log.debug('Publishing DNP3 {}'.format(point_value))
        self.vip.pubsub.publish(peer='pubsub',
                                topic=self.point_topic,
                                headers={headers.TIMESTAMP: utils.format_timestamp(utils.get_aware_utc_now())},
                                message={point_value.name: point_value.value})

    def load_point_definitions(self):
        """
            Load DNP3 PointDefinitions from a json config file.

            If the file's configured pathname contains wildcards, expand them.
        """
        expanded_path = os.path.expanduser(self.point_definitions_path)
        expanded_path = os.path.expandvars(expanded_path)
        PointDefinition.load_points(expanded_path)


class DNP3Exception(Exception):
    """Raise exceptions that are specific to the DNP3 agent. No special exception behavior is needed at this time."""
    pass


def dnp3_agent(config_path, **kwargs):
    """
        Parse the DNP3 Agent configuration. Return an agent instance created from that config.

    :param config_path: (str) Path to a configuration file.
    :returns: (DNP3Agent) The DNP3 agent
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}
    return DNP3Agent(config.get('point_definitions_path', ''),
                     config.get('point_topic', 'dnp3/point'),
                     config.get('local_ip', '0.0.0.0'),
                     config.get('port', 20000),
                     config.get('outstation_config', {}),
                     **kwargs)


def main():
    """Main method called to start the agent."""
    utils.vip_main(dnp3_agent, identity='dnp3agent', version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
