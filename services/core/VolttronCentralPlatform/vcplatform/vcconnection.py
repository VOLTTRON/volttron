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

    def publish_to_vc(self, topic, message=None, headers={}):
        """
        This method allows the main_agent to publish a message up to the
        volttron.central instance.

        :param topic:
        :param message:
        :param headers:
        """
        self.vip.pubsub.publish('pubsub', topic, headers, message)

    @RPC.export
    def start_bacnet_scan(self, iam_topic, proxy_identity, low_device_id=None,
                          high_device_id=None, target_address=None,
                          scan_length=5):
        """
        Starts a bacnet scan using the the named proxy_identity as the callee.


        :param iam_topic:
        :param proxy_identity:
        :param low_device_id:
        :param high_device_id:
        :param target_address:
        :param scan_length:
        :return:
        """
        self._main_agent.start_bacnet_scan(iam_topic=iam_topic,
                                           proxy_identity=proxy_identity,
                                           low_device_id=low_device_id,
                                           high_device_id=high_device_id,
                                           target_address=target_address,
                                           scan_length=scan_length)


    @RPC.export
    def get_instance_uuid(self):
        """
        Retrieve the instance uuid for the vcp agent's instance.

        :return:
        """
        return self._main_agent.get_instance_uuid()

    @RPC.export
    def get_health(self):
        """
        Retrieve the health of the vcp agent.

        :return:
        """
        return self._main_agent.vip.health.get_status()

    @RPC.export
    def start_agent(self, agent_uuid):
        """
        Start an agent that is already present on the vcp instance.

        :param agent_uuid:
        :return:
        """
        return self._main_agent.start_agent(agent_uuid)

    @RPC.export
    def stop_agent(self, agent_uuid):
        """
        Stop an agent already running on the vcp instance.

        :param agent_uuid:
        :return:
        """
        return self._main_agent.start_agent(agent_uuid)

    @RPC.export
    def restart(self, agent_uuid):
        """
        Performs the stop and start operations on the vcp instance for an agent.

        :param agent_uuid:
        :return:
        """
        stop_result = self.stop_agent(agent_uuid)
        start_result = self.start_agent(agent_uuid)

        return (stop_result, start_result)

    @RPC.export
    def agent_status(self, agent_uuid):
        """
        Retrieves the status of a particular agent executing on the vcp
        instance.  The agent does not have to be executing in order to receive
        it's status.

        :param agent_uuid:
        :return:
        """
        return self._main_agent.agent_status(agent_uuid)

    @RPC.export
    def status_agents(self):
        """
        Return all of the installed agents' statuses for the vcp instance.

        :return:
        """
        return self._main_agent.status_agents()


    @RPC.export
    def get_devices(self):
        """
        Retrieves configuration entries from the config store that begin with
        'devices'.

        :return: dictionary of devices.
        """
        self._log.debug("Getting devices in vcconnection.py")
        return self._main_agent.get_devices()

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

    @RPC.export
    def store_agent_config(self, agent_identity, config_name, raw_contents,
                           config_type='raw'):
        """
        Store an agent configuration on the volttron instance associated with
        this agent.

        :param agent_identity:
        :param config_name:
        :param raw_contents:
        :param config_type:
        :return: None
        """
        return self._main_agent.store_agent_config(agent_identity, config_name,
                                            raw_contents, config_type)

    @RPC.export
    def list_agent_configs(self, agent_identity):
        """
        List the agent configuration files stored on the volttron instance
        associated with this agent.

        :param agent_identity: Agent identity to retrieve configuration from.
        :return: A list of the configuration names.
        """
        return self._main_agent.list_agent_configs(agent_identity)

    @RPC.export
    def get_agent_config(self, agent_identity, config_name, raw=True):
        """
        Retrieve the configuration from the config store of the passed agent
        identity.

        :param agent_identity:
        :param config_name:
        :param raw:
        :return: The stored configuration.
        """
        return self._main_agent.get_agent_config(agent_identity, config_name,
                                                 raw)

    @RPC.export
    def subscribe_to_vcp(self, prefix, prefix_on_vc):
        """
        Allows volttron.central to listen to the message bus on vcp instance.

        :param prefix: The prefix to listen for.
        """
        self._log.info("VC subscribing to prefix: {}".format(prefix))
        self._log.info("VCP will publish to {} on VC".format(prefix_on_vc))

        def subscription_wrapper(peer, sender, bus, topic, headers,
                                 message):
            # We only publish up to vc for things that aren't forwarded.
            if 'X-Forwarded' in headers:
                return

            self._log.debug("publishing to VC topic: {}".format(
                prefix_on_vc + topic
            ))
            # Prepend the specified prefix to the topic that was passed
            # to the method
            self.publish_to_vc(prefix_on_vc+topic, message, headers)

        # Use the main agent to do the subscription on.
        self._main_agent.vip.pubsub.subscribe('pubsub',
                                              prefix,
                                              subscription_wrapper)

    @RPC.export
    def call(self, platform_method, *args, **kwargs):
        return self._main_agent.call(platform_method, *args, **kwargs)

    def is_connected(self):
        connected = self.vip.hello().get(timeout=5) is not None
        self._log.debug("is_connected returning {}".format(connected))
        return connected

    def is_peer_connected(self, peer=VOLTTRON_CENTRAL):
        connected = peer in self.vip.peerlist().get(timeout=5)
        self._log.debug("is_connected returning {}".format(connected))
        return connected

    @RPC.export
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

    @RPC.export
    def install_agent(self, local_wheel_file):
        """
        Installs
        :param local_wheel_file:
        :return:
        """
        return self._main_agent.install_agent
