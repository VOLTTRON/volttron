# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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



import datetime
import logging
import time

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import CONTROL
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.messaging.health import Status, STATUS_BAD, STATUS_GOOD
from volttron.platform.vip.agent import Agent, Core, PubSub, Unreachable
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.scheduling import periodic

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.2'


class FailoverAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(FailoverAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)

        # Get agent and remote ids
        agent_id = config["agent_id"]
        if agent_id == "primary":
            self.agent_id = "primary"
            self.remote_id = "secondary"
        elif agent_id == "secondary":
            self.agent_id = "secondary"
            self.remote_id = "primary"
        else:
            _log.error("agent_id must be either 'primary' or 'secondary'")

        # Modify ids if we're using the simple option
        # Defaults to true pending vc coordination
        use_simple = config.get("simple_behavior", True)
        if use_simple:
            self.agent_id = "simple_" + self.agent_id
            self.remote_id = "simple_" + self.remote_id

        self.remote_vip = config["remote_vip"]

        hosts = KnownHostsStore()
        self.remote_serverkey = hosts.serverkey(self.remote_vip)
        if self.remote_serverkey is None:
            self.remote_serverkey = config["remote_serverkey"]

        self.agent_vip_identity = config["agent_vip_identity"]
        self.heartbeat_period = config["heartbeat_period"]
        self.timeout = config["timeout"]

        self.vc_timeout = self.timeout
        self.remote_timeout = self.timeout
        self.agent_uuid = None
        self.heartbeat = None
        self.last_connected = None

        self._state = True, True
        self._state_machine = getattr(self, self.agent_id + '_state_machine')

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        # Start an agent to send heartbeats to the other failover instance
        self.heartbeat = self.build_connection()

        connected = self.heartbeat.is_connected()
        _log.debug("is connected to remote instance: {}".format(connected))

        def heartbeat():
            try:
                self.heartbeat.publish('heartbeat/{}'.format(self.agent_id))
                self.last_connected = self.timestamp()
            except Unreachable:
                if self.timestamp() < self.last_connected + self.timeout:
                    _log.debug("Attempting reconnect to remote instance")
                    self.heartbeat.kill()
                    self.heartbeat = self.build_connection()
                    self.last_connected = self.timestamp()

        self.core.schedule(periodic(self.heartbeat_period), heartbeat)
        self.core.schedule(periodic(1), self.check_pulse)

    def timestamp(self):
        return time.mktime(datetime.datetime.now().timetuple())

    def build_connection(self):
        return Connection(self.remote_vip,
                          peer='',
                          serverkey=self.remote_serverkey,
                          publickey=self.core.publickey,
                          secretkey=self.core.secretkey)

    @PubSub.subscribe('pubsub', 'heartbeat')
    def on_match(self, peer, sender, bus, topic, headers, message):
        if topic.startswith('heartbeat/VolttronCentralAgent'):
            self.vc_timeout = self.timeout
        elif topic.startswith('heartbeat/' + self.remote_id):
            self.remote_timeout = self.timeout

    def _find_agent_uuid(self):
        self.agent_uuid = None
        agents = self.vip.rpc.call(CONTROL, 'list_agents').get()
        uuids = [a['uuid'] for a in agents]
        for uuid in uuids:
            vip_id = self.vip.rpc.call(CONTROL,
                                       'agent_vip_identity',
                                       uuid).get()

            if vip_id == self.agent_vip_identity:
                self.agent_uuid = uuid

        if self.agent_uuid is None:
            _log.error("Agent {} is not installed"
                       .format(self.agent_vip_identity))

    def check_pulse(self):
        self.vc_timeout -= 1
        self.remote_timeout -= 1

        vc_is_up = self.vc_timeout > 0
        remote_is_up = self.remote_timeout > 0
        current_state = remote_is_up, vc_is_up

        self._find_agent_uuid()
        if self.agent_uuid is None:
            return

        self._state_machine(current_state)

    def _agent_control(self, command):
        try:
            self.vip.rpc.call(CONTROL, command, self.agent_uuid).get()
        except RemoteError as e:
            _log.error("Error calling {} on control".format(command))

    def primary_state_machine(self, current_state):
        """Function representing the state machine for a primary
        instace.

        Start the target agent if either the secondary instance or
        Volttron Central are active. Otherwise stop the target agent.

        :param current_state: Indicates if remote platforms are active.
        :type current_state: tuple of booleans
        """
        raise NotImplementedError("Coordination with VC not implemeted")

        secondary_is_up, vc_is_up = current_state
        if secondary_is_up or vc_is_up:
            self._agent_control('start_agent')
        else:
            self._agent_control('stop_agent')

    def secondary_state_machine(self, current_state):
        """Function representing the state machine for a secondary
        instance.

        If this agent stops getting heartbeats from the primary, it will
        ask Volttron Central for verification that the primary is inactive
        before starting the target agent.

        The target agent will be stopped if both the primary instance
        and Volttron Central are not communicating.

        :param current_state: Indicates if remote platforms are active.
        :type current_state: tuple of booleans
        """
        raise NotImplementedError("Coordination with VC not implemeted")

        primary_is_up, vc_is_up = current_state
        if not primary_is_up and vc_is_up:
            pass # verify and start master
        else:
            self._agent_control('stop_agent')

    def simple_primary_state_machine(self, current_state):
        """Function representing the state machine for a simple primary
        instance. Always tries to start the target agent.

        :param current_state: Indicates if remote platforms are active. Ingored.
        :type current_state: tuple of booleans
        """
        alert_key = 'failover {}'.format(self.agent_id)
        if current_state != self._state:
            context = 'Starting agent {}'.format(self.agent_vip_identity)
            self._state = current_state
            _log.warning(context)
            status = Status.build(STATUS_GOOD, context=context)
            self.vip.health.send_alert(alert_key, status)

        proc_info = self.vip.rpc.call(CONTROL,
                                      'agent_status',
                                      self.agent_uuid).get()

        is_running = proc_info[0] > 0 and proc_info[1] == None
        if not is_running:
            self._agent_control('start_agent')

    def simple_secondary_state_machine(self, current_state):
        """Function representing the state machine for a simple secondary
        instance. Starts the target agent if the simple primary is not
        communicating.

        :param current_state: Indicates if remote platforms are
            active. Ignores the Volttron Central status.
        :type current_state: tuple of booleans
        """
        primary_is_up, _ = current_state

        alert_key = 'failover {}'.format(self.agent_id)

        if primary_is_up:
            context = 'Primary is active stopping agent {}'.format(
                self.agent_vip_identity)
            if current_state != self._state:
                self._state = current_state
                _log.warning(context)
                status = Status.build(STATUS_GOOD, context=context)
                self.vip.health.send_alert(alert_key, status)

            self._agent_control('stop_agent')

        else:
            context = 'Primary is inactive starting agent {}'.format(
                self.agent_vip_identity)
            if current_state != self._state:
                self._state = current_state
                _log.warning(context)
                status = Status.build(STATUS_BAD, context=context)
                self.vip.health.send_alert(alert_key, status)

            proc_info = self.vip.rpc.call(CONTROL,
                                          'agent_status',
                                          self.agent_uuid).get()
            is_running = proc_info[0] > 0 and proc_info[1] == None
            if not is_running:
                self._agent_control('start_agent')


def main():
    try:
        utils.vip_main(FailoverAgent, version=__version__)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
