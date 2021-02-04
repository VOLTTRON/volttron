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

from collections import defaultdict
from datetime import datetime
import logging

from volttron.platform.agent.known_identities import CONTROL_CONNECTION, PROCESS_IDENTITIES
from volttron.platform.agent.utils import format_timestamp
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
from datetime import timedelta
from volttron.utils.rmq_config_params import RMQConfig
from volttron.utils.rmq_setup import start_rabbit, RabbitMQStartError
from volttron.platform.agent.utils import get_messagebus

_log = logging.getLogger(__name__)


class HealthService(Agent):

    def __init__(self, monitor_rabbit=False, **kwargs):
        super(HealthService, self).__init__(**kwargs)

        # Store the health stats for given peers in a dictionary with
        # keys being the identity of the connected agent.
        self._health_dict = defaultdict(dict)
        self._monitor_rabbit = monitor_rabbit

    def peer_added(self, peer):
        """
        The `peer_added` method should be called whenever an agent is connected to the
        platform.

        :param peer: The identity of the agent connected to the platform
        """
        health = self._health_dict[peer]

        health['peer'] = peer
        health['service_agent'] = peer in PROCESS_IDENTITIES
        health['connected'] = format_timestamp(datetime.now())

    def peer_dropped(self, peer):
        # TODO: Should there be an option for  a db/log file for agents coming and going from the platform?
        self._health_dict[peer]['disconnected'] = format_timestamp(datetime.now())
        del self._health_dict[peer]

    @RPC.export
    def get_platform_health(self):
        """
        The `get_platform_health` retrieves all of the connected agent's health structures,
        except for the `CONTROL_CONNECTION` (vctl's known identity).  Vctl's identity is used for short
        term connections and is not relevant to the core health system.

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
        agents = {k: v for k, v in self._health_dict.items()
                              if not v.get('peer') == CONTROL_CONNECTION}
        return agents

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
        time_now = format_timestamp(datetime.now())
        if not health:
            health['connected'] = time_now
            health['peer'] = sender
            health['service_agent'] = sender in PROCESS_IDENTITIES

        health['last_heartbeat'] = time_now
        health['message'] = message

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Start subscribing to heartbeat topic to get updates from the health subsystem.
        self.vip.pubsub.subscribe('pubsub', 'heartbeat', callback=self._heartbeat_updates)
        # Schedule RabbitMQ Server monitoring. Do not monitor if RabbitMQ is running as service,
        # systemd will take care of monitoring, restart etc.
        if get_messagebus() == 'rmq':
            rmq_config = RMQConfig()
            if self._monitor_rabbit and not rmq_config.rabbitmq_as_service:
                _log.info(f"{self._monitor_rabbit}, {rmq_config.rabbitmq_as_service}, {rmq_config.monitor_delay}")
                delay = utils.get_aware_utc_now() + timedelta(seconds=rmq_config.monitor_delay)
                self.core.schedule(delay, self.__monitor_rabbit__)

    def __monitor_rabbit__(self):
        # Check if RabbitMQ is running. If not running, restart the server
        rmq_config = RMQConfig()
        try:
            _log.info("Checking status of rabbitmq")
            # Check if RabbitMQ is running. If not running, restart the server
            start_rabbit(rmq_config.rmq_home)
        except RabbitMQStartError as e:
            # Raise KeyboardInterrupt error which will eventually shutdown platform
            _log.exception(f"Unable to start RabbitMQ server: {e}")
            raise KeyboardInterrupt()

        delay = utils.get_aware_utc_now() + timedelta(seconds=rmq_config.monitor_delay)
        self.core.schedule(delay, self.__monitor_rabbit__)


