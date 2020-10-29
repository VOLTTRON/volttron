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

from collections import defaultdict
from datetime import datetime
import logging

from volttron.platform.agent.known_identities import CONTROL_CONNECTION
from volttron.platform.agent.utils import format_timestamp
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)


class HealthService(Agent):

    def __init__(self, **kwargs):
        super(HealthService, self).__init__(**kwargs)

        # Store the health stats for given peers in a dictionary with
        # keys being the identity of the connected agent.
        self._health_dict = defaultdict(dict)

    def peer_added(self, peer):
        """
        The `peer_added` method should be called whenever an agent is connected to the
        platform.

        :param peer: The identity of the agent connected to the platform
        """
        self._health_dict[peer]['peer'] = peer
        self._health_dict[peer]['service_agent'] = False
        self._health_dict[peer]['connected'] = format_timestamp(datetime.now())
        self._health_dict[peer].pop('disconnected', None)

    def peer_dropped(self, peer):
        # TODO: Should there be an option for  a db/log file for agents coming and going from the platform?
        self._health_dict[peer]['disconnected'] = format_timestamp(datetime.now())
        del self._health_dict[peer]

    @RPC.export
    def get_platform_health(self):
        """
        The `get_platform_health` retrieves all of the connected agent's health structures,
        except for the service_agents and the CONTROL_CONNECTION.  These are filtered out
        because they aren't relevant to the vctl command in general.  The vctl command
        usese CONTROL_CONNECTION to connect to the volttron process so it is not relevant
        either.

        This function returns a dictionary in the form identity: values such as the following:

        .. code-block :: json

            {
                "listeneragent-3.3_35":
                {
                    "peer": "listeneragent-3.3_35",
                    "service_agent": False,
                    "connected": "2020-10-28T12:46:58.701119",
                    "last_heartbeat": "2020-10-28T12:47:03.709605",
                    "message": "GOOD"
                }
            }

        :return:
        """
        # Ignore the connection from control in the health as it will only be around for a short while.
        non_service_agents = {k: v for k, v in self._health_dict.items()
                              if not v.get('peer') == CONTROL_CONNECTION}
        return non_service_agents

    def _heartbeat_updates(self, peer, sender, bus, topic, headers, message):
        """
        This method is called whenever a publish goes on the message bus from the
        heartbeat* topic.

        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        health = self._health_dict[sender]
        if not health:
            _log.warning(f"Missing health from peer {sender}")
        health['last_heartbeat'] = format_timestamp(datetime.now())
        health['message'] = message

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):

        # assume that when this agent starts all other agents connected to the platform right now are service
        # agents.  This should be a valid assumption because in main.py this is the last agent started
        # as a service agent and none of the user agents has been added yet.
        peers = self.vip.peerlist().get(timeout=10)
        for p in peers:
            self._health_dict[p]['service_agent'] = True
            self._health_dict[p]['connected'] = format_timestamp(datetime.now())
            self._health_dict[p]['health'] = self.vip.rpc.call(p, 'health.get_status_json').get(timeout=1)

        # Start subscribing to heartbeat topic to get updates from the health subsystem.
        self.vip.pubsub.subscribe('pubsub', 'heartbeat', callback=self._heartbeat_updates)
