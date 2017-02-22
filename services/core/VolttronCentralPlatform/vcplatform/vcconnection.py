# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


from __future__ import absolute_import, print_function

import base64
from collections import defaultdict
import datetime
from enum import Enum
import hashlib
import logging
import os
import shutil
import sys
import tempfile
import urlparse

import gevent
import gevent.event
import psutil

from volttron.platform import jsonrpc
from volttron.platform.agent.utils import (get_utc_seconds_from_epoch)
from volttron.platform.agent import utils
from volttron.platform.agent.exit_codes import INVALID_CONFIGURATION_CODE
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, CONTROL, CONFIGURATION_STORE)
from volttron.platform.agent.utils import (get_aware_utc_now)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS)
from volttron.platform.messaging import topics
from volttron.platform.messaging.topics import (LOGGER, )
from volttron.platform.vip.agent import (Agent, Core, RPC, PubSub, Unreachable)
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.vip.agent.utils import build_connection
from volttron.platform.web import DiscoveryInfo, DiscoveryError
from . bacnet_proxy_reader import BACnetReader


class VCConnection(Agent):
    """
    This agent will connect to an instance with volttron.central agent connected
    to it.  The volttron.central agent will use this agent to communicate with
    the platform.agent(vcp) running on the current instance of the platform.
    """
    def __init__(self, **kwargs):
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.debug('KWARGS Passed: {}'.format(kwargs))
        super(VCConnection, self).__init__(**kwargs)
        self._main_agent = None

    def set_main_agent(self, main_agent):
        """
        The main agent is the VCP that is using this agent to connect to the
        remote volttron instance.

        :param main_agent: the agent that instantiated this one.
        :type VolttronCentralPlatform:
        """
        self._main_agent = main_agent

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self._log.debug("Created VCConnection")

    @RPC.export
    def publish_bacnet_props(self, proxy_identity, publish_topic, address,
                             device_id, filter=[]):
        self._log.debug('Publishing bacnet props to topic: {}'.format(
            publish_topic))
        self._main_agent.publish_bacnet_props(
            proxy_identity,
            publish_topic,
            address,
            device_id,
            filter=[])

    def publish_to_vc(self, topic, message, headers={}):
        """
        This method allows the main_agent to publish a message up to the
        volttron.central instance.

        :param topic:
        :param message:
        :param headers:
        """
        self.vip.pubsub.publish('pubsub', topic, headers, message)


    def call(self, method, *args, **kwargs):
        self._log.debug("Callilng method {} {} {}".format(method, args, kwargs))

    def is_connected(self):
        connected = self.vip.hello().get(timeout=5) is not None
        self._log.debug("is_connected returning {}".format(connected))
        return connected

    def is_peer_connected(self, peer=VOLTTRON_CENTRAL):
        connected = peer in self.vip.peerlist().get(timeout=5)
        self._log.debug("is_connected returning {}".format(connected))
        return connected    @RPC.export
    def route_to_agent_method(self, id, agent_method, params):
        """
        Calls a method on an installed agent running on the platform.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :param id:
        :param agent_method:
        :param params:
        :return:
        """
        self._log.debug("inside route_to_agent_method")
        return self._main_agent.route_request(id, agent_method, params)

    @RPC.export
    def get_vip_addresses(self):
        """
        Retrieves the vip addresses that were specified in the configuration
        file or via command line.

        :return:
        """
        return self._main_agent.get_external_vip_addresses()

    @RPC.export
    def get_instance_name(self):
        return self._main_agent.get_instance_name()

    @RPC.export
    def start_agent(self, agent_uuid):
        """
        Calls start_agent method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :param agent_uuid:
        :return:
        """
        self._main_agent.start_agent(agent_uuid)

    @RPC.export
    def stop_agent(self, agent_uuid):
        """
        Calls stop_agent method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :param agent_uuid:
        :return:
        """
        proc_result = self._main_agent.stop_agent(agent_uuid)
        return proc_result

    @RPC.export
    def restart_agent(self, agent_uuid):
        """
        Calls restart method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :param agent_uuid:
        :return:
        """
        return self._main_agent.restart(agent_uuid)

    @RPC.export
    def agent_status(self, agent_uuid):
        """
        Calls agent_status method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :param agent_uuid:
        :return:
        """
        return self._main_agent.agent_status(agent_uuid)

    @RPC.export
    def status_agents(self):
        """
        Calls status_agents method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :return:
        """
        return self._main_agent.status_agents()

    @RPC.export
    def list_agents(self):
        """
        Calls list_agents method on the vcp main agent instance.

        .. note::

            This method only valid for installed agents not dynamic agents.

        :return:
        """
        return self._main_agent.list_agents()