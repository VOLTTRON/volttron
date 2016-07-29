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

"""
.. _volttroncentral-agent:

The VolttronCentral(VCA) agent is used to manage remote VOLTTRON instances.
The VCA exposes a JSON-RPC based web api and a web enabled visualization
framework.  The web enabled framework is known as VOLTTRON
Central Management Console (VCMC).

In order for an instance to be able to be managed by VCMC a
:class:`vcplatform.agent.VolttronCentralPlatform` must be executing on the
instance.  If there is a :class:`vcplatform.agent.VolttronCentralPlatform`
running on the same instance as VCA it will be automatically registered as a
managed instance.  Otherwise, there are two different paths to registering an
instance with VCA.

1. Through the web api a call to the JSON-RPC method register_instance.
2. From an external platform through pub/sub.  this secondary method is
   preferred when deploying instances in the field that need to "phone home"
   to VCA after being deployed.
   
"""
import uuid
from collections import defaultdict
from copy import deepcopy
import errno
import logging
import os
import os.path as p
import sys
from urlparse import urlparse

import gevent
from abc import ABCMeta

from authenticate import Authenticate
from sessions import SessionHandler
from volttron.platform.vip.connection import Connection
from volttron.utils.persistance import load_create_store
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (
    get_aware_utc_now, format_timestamp, parse_timestamp_string)
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, MASTER_WEB,
    PLATFORM_HISTORIAN)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.jsonrpc import (
    INVALID_REQUEST, METHOD_NOT_FOUND,
    UNHANDLED_EXCEPTION, UNAUTHORIZED,
    UNABLE_TO_REGISTER_INSTANCE, DISCOVERY_ERROR,
    UNABLE_TO_UNREGISTER_INSTANCE, UNAVAILABLE_PLATFORM, INVALID_PARAMS,
    UNAVAILABLE_AGENT, json_error)
from volttron.platform.messaging.health import UNKNOWN_STATUS, Status, \
    BAD_STATUS
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core, Unreachable
from volttron.platform.vip.agent.subsystems import query
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.web import (DiscoveryInfo, DiscoveryError)
from zmq.utils import jsonapi

__version__ = "3.5.4"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))


class VolttronCentralAgent(Agent):
    """ Agent for managing many volttron instances from a central web ui.

    During the


    """
    __name__ = 'VolttronCentralAgent'

    def __init__(self, config_path, **kwargs):
        """ Creates a `VolttronCentralAgent` object to manage instances.

         Each instances that is registered must contain a running
         `VolttronCentralPlatform`.  Through this conduit the
         `VolttronCentralAgent` is able to communicate securly and
         efficiently.

        :param config_path:
        :param kwargs:
        :return:
        """
        _log.info("{} constructing...".format(self.__name__))

        # This is a special object so only use it's identity.
        identity = kwargs.pop("identity", None)
        identity = VOLTTRON_CENTRAL

        super(VolttronCentralAgent, self).__init__(identity=identity,
                                                   **kwargs)
        # Load the configuration into a dictionary
        self._config = utils.load_config(config_path)

        # Expose the webroot property to be customized through the config
        # file.
        self._webroot = self._config.get('webroot', DEFAULT_WEB_ROOT)
        if self._webroot.endswith('/'):
            self._webroot = self._webroot[:-1]
        _log.debug('The webroot is {}'.format(self._webroot))

        # Required users
        self._user_map = self._config.get('users', None)

        _log.debug("User map is: {}".format(self._user_map))
        if self._user_map is None:
            raise ValueError('users not specified within the config file.')

        # Search and replace for topics
        # The difference between the list and the map is that the list
        # specifies the search and replaces that should be done on all of the
        # incoming topics.  Once all of the search and replaces are done then
        # the mapping from the original to the final is stored in the map.
        self._topic_replace_list = self._config.get('topic_replace_list', [])
        self._topic_replace_map = defaultdict(str)
        _log.debug('Topic replace list: {}'.format(self._topic_replace_list))

        platforms_file = os.path.join(os.environ['VOLTTRON_HOME'],
                                      'data/platforms.json')
        self._registered_platforms = load_create_store(platforms_file)

        # This has a dictionary mapping the platform_uuid to an agent
        # connected to the vip-address of the registered platform.  If the
        # registered platform is None then that means we were unable to
        # connect to the platform the last time it was tried.
        self._platform_connections = {}
        self._address_to_uuid = {}

        # An object that allows the checking of currently authenticated
        # sessions.
        self._sessions = SessionHandler(Authenticate(self._user_map))
        self.webaddress = None
        self._web_info = None
        self._serverkey = None
        # A flag that tels us that we are in the process of updating already.
        # This will allow us to not have multiple periodic calls at the same
        # time which could cause unpredicatable results.
        self._flag_updating_deviceregistry = False

        # A dictionary of the connections to platforms.
        self._connections_by_address = {}
        _log.debug('Creating setting store')
        self._setting_store = load_create_store(
            os.path.join(os.environ['VOLTTRON_HOME'],
                         'data', 'volttron.central.settings'))
        _log.debug('Creating request store')
        self._request_store = load_create_store(
            os.path.join(os.environ['VOLTTRON_HOME'],
                         'data', 'volttron.central.requeststore'))

    # # @Core.periodic(60)
    # def _reconnect_to_platforms(self):
    #     """ Attempt to reconnect to all the registered platforms.
    #     """
    #     _log.info('Reconnecting to platforms')
    #     for entry in self._registry.get_platforms():
    #         try:
    #             conn_to_instance = None
    #             if entry.is_local:
    #                 _log.debug('connecting to vip address: {}'.format(
    #                     self._local_address
    #                 ))
    #                 conn_to_instance = ConnectedLocalPlatform(self)
    #             elif entry.platform_uuid in self._pa_agents.keys():
    #                 conn_to_instance = self._pa_agents.get(entry.platform_uuid)
    #                 try:
    #                     if conn_to_instance.agent.vip.peerlist.get(timeout=15):
    #                         pass
    #                 except gevent.Timeout:
    #                     del self._pa_agents[entry.platform_uuid]
    #                     conn_to_instance = None
    #
    #             if not conn_to_instance:
    #                 _log.debug('connecting to vip address: {}'.format(
    #                     entry.vip_address
    #                 ))
    #                 conn_to_instance = ConnectedPlatform(
    #                     address=entry.vip_address,
    #                     serverkey=entry.serverkey,
    #                     publickey=self.core.publickey,
    #                     secretkey=self.core.secretkey
    #                 )
    #
    #             # Subscribe to the underlying agent's pubsub bus.
    #             _log.debug("subscribing to platforms pubsub bus.")
    #             conn_to_instance.agent.vip.pubsub.subscribe(
    #                 "pubsub", "platforms", self._on_platforms_messsage)
    #             self._pa_agents[entry.platform_uuid] = conn_to_instance
    #             _log.debug('Configuring platform to be the correct uuid.')
    #             conn_to_instance.agent.vip.rpc.call(
    #                 VOLTTRON_CENTRAL_PLATFORM, "reconfigure",
    #                 platform_uuid=entry.platform_uuid).get(timeout=15)
    #
    #         except (gevent.Timeout, Unreachable) as e:
    #             _log.error("Unreachable platform address: {}"
    #                        .format(entry.vip_address))
    #             self._pa_agents[entry.platform_uuid] = None

    @PubSub.subscribe("pubsub", "heartbeat/volttroncentralplatform")
    def _on_platform_heartbeat(self, peer, sender, bus, topic, headers,
                               message):
        _log.debug('Got Heartbeat from: {}'.format(topic))

    # def _handle_pubsub_register(self, message):
    #     # register the platform if a local platform otherwise put it
    #     # in a to_register store
    #     required = ('serverkey', 'publickey', 'address')
    #     valid = True
    #     for p in required:
    #         if not p in message or not message[p]:
    #             _log.error('Invalid {} param not specified or invalid')
    #             valid = False
    #     # Exit loop if not valid.
    #     if not valid:
    #         _log.warn('Invalid message format for platform registration.')
    #         return
    #
    #     _log.info('Attempting to register through pubsub address: {}'
    #               .format(message['address']))
    #
    #     passed_uuid = None
    #     if 'had_platform_uuid' in message:
    #         passed_uuid = message['had_platform_uuid']
    #
    #         entry = self._registry.get_platform(passed_uuid)
    #         if not entry:
    #             _log.error('{} was not found as a previously registered '
    #                        'platform. Address: {}'
    #                        .format(passed_uuid, message['address']))
    #             return
    #
    #         # Verify the platform address serverkey publickey are the
    #         # same.
    #         _log.debug('Refreshing registration for {}'
    #                    .format(message['address']))
    #
    #     if self._local_address == message['address']:
    #         if passed_uuid is not None:
    #             _log.debug('Local platform entry attempting to re-register.')
    #             local_entry = self._registry.get_platform(passed_uuid)
    #             if passed_uuid in self._pa_agents.keys():
    #                 if self._pa_agents[passed_uuid]:
    #                     self._pa_agents[passed_uuid].disconnect()
    #                 del self._pa_agents[passed_uuid]
    #         else:
    #             _log.debug('Local platform entry attempting to register.')
    #             local_entry = PlatformRegistry.build_entry(
    #                 None, None, None, is_local=True, display_name='local')
    #             self._registry.register(local_entry)
    #         connected = ConnectedLocalPlatform(self)
    #         _log.debug('Calling manage on local vcp.')
    #         pubkey = connected.agent.vip.rpc.call(
    #             VOLTTRON_CENTRAL_PLATFORM, 'manage', self._local_address,
    #             self.core.publickey, self._web_info.serverkey
    #         )
    #         _log.debug('Reconfiguring platform_uuid for local vcp.')
    #         # Change the uuid of the agent.
    #         connected.agent.vip.rpc.call(
    #             VOLTTRON_CENTRAL_PLATFORM, 'reconfigure',
    #             platform_uuid=local_entry.platform_uuid)
    #         self._pa_agents[local_entry.platform_uuid] = connected
    #
    #     else:
    #         _log.debug('External platform entry attempting to register.')
    #         # TODO use the following to store data for registering
    #         # platform.
    #         # self._request_store[message['address']] = message
    #         # self._request_store.sync()
    #         connected = ConnectedPlatform(
    #             address=message['address'],
    #             serverkey=message['serverkey'],
    #             publickey=self.core.publickey,
    #             secretkey=self.core.secretkey
    #         )
    #
    #         _log.debug('Connecting to external vcp.')
    #         connected.connect()
    #         if not connected.is_connected():
    #             _log.error("Couldn't connect {} address"
    #                        .format(message['address']))
    #             return
    #         _log.debug('Attempting to manage {} from address {}'
    #                    .format(message['address'], self.core.address))
    #         vcp_pubkey = connected.agent.vip.rpc.call(
    #             VOLTTRON_CENTRAL_PLATFORM,
    #             'manage', address=self.core.address,
    #             vcserverkey=self._web_info.serverkey,
    #             vcpublickey=self.core.publickey
    #         ).get(timeout=15)
    #
    #         # Check that this pubkey is the same as the one passed through
    #         # pubsub mechanism.
    #         if not vcp_pubkey == message['publickey']:
    #             _log.error("Publickey through pubsub doesn't match "
    #                        "through manage platform call. ")
    #             _log.error("Address {} was attempting to register."
    #                        .format(message['address']))
    #             return
    #
    #         if passed_uuid:
    #             entry = self._registry.get_platform(passed_uuid)
    #         else:
    #             entry = PlatformRegistry.build_entry(
    #                 vip_address=message['address'],
    #                 serverkey=message['serverkey'],
    #                 vcp_publickey=message['publickey'],
    #                 is_local=False,
    #                 discovery_address=message.get('discovery_address'),
    #                 display_name=message.get('display_name')
    #             )
    #             self._registry.register(entry)
    #
    #         self._pa_agents[entry.platform_uuid] = connected

    @PubSub.subscribe("pubsub", "platforms")
    def _on_platforms_messsage(self, peer, sender, bus, topic, headers,
                               message):
        """ This method subscribes to the platforms topic.

        Platforms that are being managed should publish to this topic with
        the agent_list and other interesting things that the volttron
        central shsould want to know.
        """
        topicsplit = topic.split('/')
        if len(topicsplit) < 2:
            _log.error('Invalid topic length published to volttron central')
            return

        if topicsplit[1] == 'register':
            self._handle_pubsub_register(message)
            return

        if topicsplit[1] == 'unregister':
            pass

        platform_uuid = topicsplit[1]

        if len(platform_uuid) != 36:
            _log.error('Invalid platform id detected {}'
                       .format(platform_uuid))
            return

        if not self._registered_platforms.get(platform_uuid):
            _log.warn('Platform {} is not registered but sent message {}'
                      .format(platform_uuid, message))
            return

        if len(topicsplit) < 3:
            _log.warn("Invalid topic length no operation specified.")

        _log.debug('Doing operation: {}'.format(topicsplit[2]))

        #self._registry.update_agent_list(platform_uuid, message)

    @PubSub.subscribe("pubsub", "datalogger/platforms")
    def _on_platform_log_message(self, peer, sender, bus, topic, headers,
                                 message):
        """ Receive message from a registered platform

        This method is called with stats from the registered platform agents.

        """
        _log.debug('Got topic: {}'.format(topic))
        _log.debug('Got message: {}'.format(message))

        topicsplit = topic.split('/')
        platform_uuid = topicsplit[2]

        # For devices we use everything between devices/../all as a unique
        # key for determining the last time it was seen.
        key = '/'.join(topicsplit[:])
        _log.debug("key is: {}".format(key))
        uuid = topicsplit[2]

        point_list = []

        for point, item in message.iteritems():
            point_list.append(point)

        stats = {
            'topic': key,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        platform = self._registered_platforms[platform_uuid]
        platform['stats_point_list'] = stats
        self._registered_platforms[platform_uuid] = platform
        self._registered_platforms.sync()

    @RPC.export
    def get_platforms(self):
        """ Retrieves the platforms that have been registered with VC.

        @return:
        """
        _log.debug("Passing platforms back: {}".format(
            self._registered_platforms.keys()))
        return self._registered_platforms.values()

    @RPC.export
    def get_platform(self, platform_uuid):
        platform = self._registered_platforms.get(platform_uuid)
        if platform is not None:
            platform = deepcopy(platform)

        return platform

    #
    # @RPC.export
    # def list_platform_details(self):
    #     _log.debug('list_platform_details {}', self._registry.get_platforms())
    #     return self._registry.get_platforms()

    @RPC.export
    def unregister_platform(self, platform_uuid):
        _log.debug('unregister_platform')

        platform = self._registered_platforms.get(platform_uuid)
        if platform:
            connected = self._pa_agents.get(platform_uuid)
            if connected is not None:
                connected.call('unmanage')
                connected.kill()
            address = None
            for v in self._address_to_uuid.values():
                if v == platform_uuid:
                    address = v
                    break
            if address:
                del self._address_to_uuid[address]
            del self._pa_agents[platform_uuid]
            del self._registered_platforms[platform_uuid]
            self._registered_platforms.sync()
            context = 'Unregistered platform {}'.format(platform_uuid)
            return {'status': 'SUCCESS', 'context': context}
        else:
            msg = 'Unable to unregistered platform {}'.format(platform_uuid)
            return {'error': {'code': UNABLE_TO_UNREGISTER_INSTANCE,
                              'message': msg}}

    def _build_connected_agent(self, address):
        _log.debug('Building or returning connection to address: {}'.format(
            address))
        cn = self._platform_connections.get(address)
        if cn and cn.is_connected():
            return cn

        uuid = self._address_to_uuid.get(address)
        uuid or _log.debug('UUID is None from address to uuid.')
        assert uuid
        entry = self._registered_platforms.get(uuid)
        entry or _log.debug('Platform registry is empty for uuid {}'
                            .format(uuid))
        assert entry

        cn = Connection(address, peer=VOLTTRON_CENTRAL_PLATFORM,
                        serverkey=entry['serverkey'],
                        secretkey=self.core.secretkey,
                        publickey=self.core.publickey)
        return cn

    def _build_connection(self, address, serverkey=None):
        """ Creates a Connection object instance if one doesn't exist for the
        passed address.

        :param address:
        :param serverkey:
        :return:
        """
        cn = self._connections_by_address.get(address)
        if cn is not None and cn.serverkey != serverkey:
            cn.kill()
            del self._connections_by_address[address]
            cn = None

        if cn is None:
            parsed = urlparse(address)
            if parsed.scheme == 'tcp':
                cn = Connection(address=address, serverkey=serverkey,
                                publickey=self.core.publickey,
                                secretkey=self.core.secretkey,
                                peer=VOLTTRON_CENTRAL_PLATFORM)
            else:
                cn = Connection(address=address, peer=VOLTTRON_CENTRAL_PLATFORM)

        assert cn.is_connected(), "Connection unavailable for address {}"\
            .format(address)
        self._connections_by_address[address] = cn
        return cn

    def _get_connection(self, platform_uuid):
        cn = self._platform_connections.get(platform_uuid)

        if cn is None:
            if self._registered_platforms.get(platform_uuid) is None:
                raise ValueError('Invalid platform_uuid specified {}'
                                 .format(platform_uuid))

            cn = self._build_connected_agent(
                self._registered_platforms[platform_uuid]['address']
            )

            self._platform_connections[platform_uuid] = cn

        return cn

    def register_platform(self, address, serverkey=None, display_name=None):
        """ Allows an volttron central platform (vcp) to register with vc

        @param: address: str:
            An address or resolvable domain name with port.
        @param: serverkey: str:
            The router publickey for the vcp attempting to register.
        """
        _log.info('Attempting registration of vcp at address: '
                  '{} display_name: {}'.format(address, display_name))
        try:

            parsed = urlparse(address)
            _log.debug('Connecting to remote platform.agent')
            if parsed.scheme == 'tcp':
                connected = Connection(
                    address, VOLTTRON_CENTRAL_PLATFORM, serverkey=serverkey,
                    secretkey=self.core.secretkey,
                    publickey=self.core.publickey)
                _log.debug('Attempting to manage platform at {}'.format(
                    address))
                pk = connected.call(
                    'manage', self._external_addresses[0], self._serverkey,
                    self.core.publickey)
                if not display_name:
                    display_name = address
            elif parsed.scheme == 'ipc':
                if address == self.core.address:
                    _log.debug("Registering local address")
                    if not display_name:
                        display_name = "local"

                connected = Connection(
                    address, VOLTTRON_CENTRAL_PLATFORM)
                pk = connected.call('manage', self.core.address)

            assert connected is not None and connected.is_connected()
            _log.debug('Response from platform.agent was: {}'.format(pk))
            newuuid = self._address_to_uuid.get(address, str(uuid.uuid4()))
            connected.call('reconfigure', platform_uuid=newuuid)
            _log.debug('Assigning new or reused uuid: {}'.format(newuuid))
            if address in self._pa_agents.keys():
                _log.debug('Removing key to agent key')
                del self._pa_agents[address]
            self._pa_agents[address] = connected
            if not display_name:
                _log.debug(
                    "Display name now set to address since it wasn't specified")
                display_name = address
            else:
                _log.debug('Display name was passed as: {}'.format(
                    display_name))

            self._registered_platforms[newuuid] = dict(
                address=address, serverkey=serverkey, display_name=display_name,
                registered_time_utc=format_timestamp(get_aware_utc_now()),
                platform_uuid=newuuid
            )
            self._registered_platforms.sync()
        except gevent.Timeout:
            _log.error("Couldn't connect to address: {}".format(address))

    @RPC.export
    def register_instance(self, address, display_name=None, serverkey=None,
                          vcpagentkey=None):
        """ RPC Method to register an instance with volttron central.

        This method is able to accommodates both a discovery address as well
        as well as a vip address.  In both cases the ports must be included in
        the uri passed to address.  A discovery address allows the lookup of
        serverkey from the address.  If instead address is an instance address
        then the serverkey and vcpagentkey is required.  If either the serverkey
        or the vcpagentkey are not specified then a ValueError is thrown.

        .. code-block:: python
            :linenos:

            # Function call using discovery address
            agent.vip.call('volttron.central', 'register_instance',
                           'http://127.0.0.1:8080', 'platform1')

            # Function call using instance address
            agent.vip.call('volttron.central', 'register_instance',
                           'tcp://127.0.0.1:22916',
                           serverkey='EOEI_TzkyzOhjHuDPWqevWAQFaGxxU_tV1qVNZqqbBI',
                           vcpagentkey='tV1qVNZqqbBIEOEI_TzkyzOhjHuDPWqevWAQFaGxxU_')

            # Function call using instance address
            agent.vip.call('volttron.central', 'register_instance',
                           'ipc://@/home/volttron/.volttron/run/vip.socket',
                           'platform1',
                           'tV1qVNZqqbBIEOEI_TzkyzOhjHuDPWqevWAQFaGxxU_')

        :param string: address:
            The url of the address for the platform.
        :param string: display_name:
            (Optional) How the instance is displayed on volttron central.  This
            will default to address if it is not specified.
        :param string: serverkey:
            (Optional) A server key for connecting to the volttron central
        :param string: vcpagentkey:
            (Optional) The public key associated with the vcp agent connecting
            to the volttron central instance.
        """
        _log.debug('register_instance called via RPC')

        parsed = urlparse(address)

        valid_schemes = ('http', 'https', 'tcp', 'ipc')
        if parsed.scheme not in valid_schemes:
            raise ValueError('Unknown scheme specified {} valid schemes are {}'
                             .format(parsed.scheme, valid_schemes))

        if parsed.scheme in ('http', 'https'):
            self._register_instance(address,
                                    display_name=display_name)
        elif parsed.scheme == 'tcp':
            self.register_platform(address, serverkey, display_name)
        elif parsed.scheme == 'ipc':
            self.register_platform(address, display_name=display_name)

    def _handle_list_platforms(self):
        def get_status(platform_uuid):
            cn = self._pa_agents.get(platform_uuid)
            if cn is None:
                _log.debug('cn is NONE so status is BAD for uuid {}'
                           .format(platform_uuid))
                return Status.build(BAD_STATUS,
                                    "Platform Unreachable.").as_dict()
            try:
                _log.debug('TRYING TO REACH {}'.format(platform_uuid))
                health = cn.call('get_health')
            except Unreachable:
                health = Status.build(BAD_STATUS,
                                      "Platform Unreachable.").as_dict()
            return health

        _log.debug(
            'Listing platforms: {}'.format(self._registered_platforms))
        return [dict(uuid=x['platform_uuid'], name=x['display_name'],
                     health=get_status(x['platform_uuid']))
                for x in self._registered_platforms.values()]

    def _register_instance(self, discovery_address, display_name=None,
                           provisional=False):
        """ Register an instance with VOLTTRON Central based on jsonrpc.

        NOTE: This method is meant to be called from the jsonrpc method.

        The registration of the instance will fail in the following cases:
        - no discoverable instance at the passed uri
        - no platform.agent installed at the discoverable instance
        - is a different volttron central managing the discoverable
          instance.

        If the display name is not set then the display name becomes the
        same as the discovery_address.  This will be used in the
        volttron central ui.

        :param discovery_address: A ip:port for an instance of volttron
               discovery.
        :param display_name:
        :return: dictionary:
            The dictionary will hold either an error object or a result
            object.
        """

        _log.info(
            'Attempting to register name: {} with address: {}'.format(
                display_name, discovery_address))

        try:
            discovery_response = DiscoveryInfo.request_discovery_info(
                discovery_address)
        except DiscoveryError as e:
            return {
                'error': {
                    'code': DISCOVERY_ERROR, 'message': e.message
                }}

        pa_instance_serverkey = discovery_response.serverkey
        pa_vip_address = discovery_response.vip_address

        assert pa_instance_serverkey
        _log.debug('connecting to pa_instance')
        try:
            connected_to_pa = Connection(
                peer=VOLTTRON_CENTRAL_PLATFORM, address=pa_vip_address,
                serverkey=pa_instance_serverkey, secretkey=self.core.secretkey,
                publickey=self.core.publickey
            )

            if not connected_to_pa.is_connected(timeout=5):
                return {
                    'error': {
                        'code': UNABLE_TO_REGISTER_INSTANCE,
                        'message': 'Could not connect to {}'
                            .format(pa_vip_address)
                    }}
        except gevent.Timeout:
            return {
                'error': {
                    'code': UNABLE_TO_REGISTER_INSTANCE,
                    'message': 'Could not connect to {}'
                        .format(pa_vip_address)
                }}
        except Exception as ex:
            return {'error': {'code': UNHANDLED_EXCEPTION,
                              'message': ex.message
                              }}

        assert connected_to_pa
        assert connected_to_pa.is_connected()
        _log.debug('Connected to address starting to manage external platform.')

        # The call to manage should return a public key for that agent
        result = connected_to_pa.call(
            'manage', self.core.address, vcserverkey=self._serverkey,
            vcpublickey=self.core.publickey)

        _log.debug("Result of manage is {}".format(result))

        # Magic number 43 is the length of a encoded public key.
        if len(result) != 43:
            return {'error': {'code': UNABLE_TO_REGISTER_INSTANCE,
                              'message': 'Invalid publickey returned from {}'
                                  .format(VOLTTRON_CENTRAL_PLATFORM)
                              }}

        # Add the pa's public key so it can connect back to us.
        auth_file = AuthFile()
        auth_entry = AuthEntry(
            credentials="CURVE:{}".format(result), capabilities=['managing']
        )
        auth_file.add(auth_entry)
        _log.debug('Auth entry added to AuthFile')
        newuuid = self._address_to_uuid.get(pa_vip_address, str(uuid.uuid4()))

        if self._pa_agents.get(newuuid) is not None:
            self._pa_agents[newuuid].kill()
            del self._pa_agents[newuuid]

        self._registered_platforms[newuuid] = dict(
            address=pa_vip_address, serverkey=pa_instance_serverkey,
            display_name=display_name,
            registered_time_utc=format_timestamp(get_aware_utc_now()),
            platform_uuid=newuuid
        )

        self._pa_agents[newuuid] = connected_to_pa
        _log.debug("Adding {}".format(newuuid))
        instance_name = display_name if display_name else pa_vip_address
        context = 'Registered instance {}'.format(instance_name)
        connected_to_pa.call('reconfigure', platform_uuid=newuuid)

        return {'status': 'SUCCESS', 'context': context}

    def _store_registry(self):
        self._store('registry', self._registry.package())

    @Core.receiver('onsetup')
    def _setup(self, sender, **kwargs):
        if not os.environ.get('VOLTTRON_HOME', None):
            raise ValueError('VOLTTRON_HOME environment must be set!')

        db_path = os.path.join(os.environ.get('VOLTTRON_HOME'),
                               'data/volttron.central')
        db_dir = os.path.dirname(db_path)
        try:
            os.makedirs(db_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                raise
        self.persistence_path = db_path

        # Returns None if there has been no registration of any platforms.
        registered = self._load('registry')
        if registered:
            self._registry.unpackage(registered)

    def _to_jsonrpc_obj(self, jsonrpcstr):
        """ Convert data string into a JsonRpcData named tuple.

        :param object data: Either a string or a dictionary representing a json document.
        """
        return jsonrpc.JsonRpcData.parse(jsonrpcstr)

    @RPC.export
    def jsonrpc(self, env, data):
        """ The main entry point for ^jsonrpc data

        This method will only accept rpcdata.  The first time this method
        is called, per session, it must be using get_authorization.  That
        will return a session token that must be included in every
        subsequent request.  The session is tied to the ip address
        of the caller.

        :param object env: Environment dictionary for the request.
        :param object data: The JSON-RPC 2.0 method to call.
        :return object: An JSON-RPC 2.0 response.
        """
        if env['REQUEST_METHOD'].upper() != 'POST':
            return jsonrpc.json_error('NA', INVALID_REQUEST,
                                      'Invalid request method')

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))
            if rpcdata.method == 'get_authorization':
                args = {'username': rpcdata.params['username'],
                        'password': rpcdata.params['password'],
                        'ip': env['REMOTE_ADDR']}
                sess = self._sessions.authenticate(**args)
                if not sess:
                    _log.info('Invalid username/password for {}'.format(
                        rpcdata.params['username']))
                    return jsonrpc.json_error(
                        rpcdata.id, UNAUTHORIZED,
                        "Invalid username/password specified.")
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))
                return jsonrpc.json_result(rpcdata.id, sess)

            token = rpcdata.authorization
            ip = env['REMOTE_ADDR']
            _log.debug('REMOTE_ADDR: {}'.format(ip))
            session_user = self._sessions.check_session(token, ip)
            _log.debug('SESSION_USER IS: {}'.format(session_user))
            if not session_user:
                _log.debug("Session Check Failed for Token: {}".format(token))
                return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                          "Invalid authentication token")
            _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))

            # Route any other method that isn't
            result_or_error = self._route_request(session_user,
                                                  rpcdata.id, rpcdata.method,
                                                  rpcdata.params)

        except AssertionError:
            return jsonrpc.json_error(
                'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data))
        except Exception as e:

            return jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, e
            )

        _log.debug("RETURNING: {}".format(self._get_jsonrpc_response(
            rpcdata.id, result_or_error)))
        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

    def _get_jsonrpc_response(self, id, result_or_error):
        """ Wrap the response in either a json-rpc error or result.

        :param id:
        :param result_or_error:
        :return:
        """
        if 'error' in result_or_error:
            error = result_or_error['error']
            _log.debug("RPC RESPONSE ERROR: {}".format(error))
            return jsonrpc.json_error(id, error['code'], error['message'])
        return jsonrpc.json_result(id, result_or_error)

    def _get_agents(self, platform_uuid, groups):
        """ Retrieve the list of agents on a specific platform.

        :param platform_uuid:
        :param groups:
        :return:
        """
        _log.debug('_get_agents')
        connected_to_pa = self._pa_agents[platform_uuid]

        agents = connected_to_pa.agent.vip.rpc.call(
            'platform.agent', 'list_agents').get(timeout=30)

        for a in agents:
            if 'admin' in groups:
                if "platformagent" in a['name'] or \
                                "volttroncentral" in a['name']:
                    a['vc_can_start'] = False
                    a['vc_can_stop'] = False
                    a['vc_can_restart'] = True
                else:
                    a['vc_can_start'] = True
                    a['vc_can_stop'] = True
                    a['vc_can_restart'] = True
            else:
                # Handle the permissions that are not admin.
                a['vc_can_start'] = False
                a['vc_can_stop'] = False
                a['vc_can_restart'] = False

        _log.debug('Agents returned: {}'.format(agents))
        return agents

    def _setupexternal(self):
        _log.debug(self.vip.ping('', "PING ROUTER?").get(timeout=3))

    @Core.receiver('onstart')
    def _starting(self, sender, **kwargs):
        """ Starting of the platform
        :param sender:
        :param kwargs:
        :return:
        """
        _log.info('Starting: {}'.format(self.__name__))
        self.vip.heartbeat.start()
        # _log.debug(self.vip.ping('', "PING ROUTER?").get(timeout=3))
        #
        q = query.Query(self.core)
        # TODO: Use all addresses for fallback, #114
        self._external_addresses = q.query(b'addresses').get(timeout=30)
        assert self._external_addresses
        self._serverkey = q.query(b'serverkey').get(timeout=30)

        _log.debug("external addresses are: {}".format(
            self._external_addresses
        ))

        # self._local_address = q.query('local_address').get(timeout=30)
        # _log.debug('Local address is? {}'.format(self._local_address))
        _log.debug('Registering jsonrpc and /.* routes')

        self.vip.rpc.call(MASTER_WEB, 'register_agent_route',
                          r'^/jsonrpc.*',
                          self.core.identity,
                          'jsonrpc').get(timeout=10)

        self.vip.rpc.call(MASTER_WEB, 'register_path_route', VOLTTRON_CENTRAL,
                          r'^/.*', self._webroot).get(timeout=20)

        self.webaddress = self.vip.rpc.call(
            MASTER_WEB, 'get_bind_web_address').get(timeout=30)


    def __load_persist_data(self):
        persist_kv = None

        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path, 'rb') as file:
                    persist_kv = jsonapi.loads(file.read())
                    file.close()
            except Exception as err:
                _log.error("Couldn't read persistence data {}"
                           .format(err.message))

        return persist_kv

    def _store(self, key, data):

        persist = self.__load_persist_data()

        if not persist:
            persist = {}

        persist[key] = data

        with open(self.persistence_path, 'wb') as file:
            file.write(jsonapi.dumps(persist))

    def _load(self, key):
        persist = self.__load_persist_data()

        value = None

        if persist:
            value = persist.get(key, None)

        return value

    def _sync_connected_platforms(self):
        """ Sync the registry entries with the connections to vcp agents
        """
        _log.debug("len pa_agents {}".format(len(self._pa_agents)))
        pakeys = set(self._pa_agents.keys())
        _log.debug("Syncing with {}".format(pakeys))
        for p in self._registry.get_platforms():
            if p.platform_uuid in pakeys:
                pakeys.remove(p.platform_uuid)

        for k in pakeys:
            _log.debug('Removing {} from pa_agents'.format(k))
            if k in self._pa_agents.keys():
                if self._pa_agents[k]:
                    self._pa_agents[k].disconnect()
                del self._pa_agents[k]

    @Core.receiver('onstop')
    def _stopping(self, sender, **kwargs):
        """ Clean up the  agent code before the agent is killed
        """
        for v in self._pa_agents.values():
            v.kill()

        self._pa_agents.clear()

        self.vip.rpc.call(MASTER_WEB, 'unregister_all_agent_routes',
                          self.core.identity).get(timeout=30)

    #@Core.periodic(10)
    def _update_device_registry(self):
        """ Updating the device registery from registered platforms.

        :return:
        """
        try:
            if not self._flag_updating_deviceregistry:
                _log.debug("Updating device registry")
                self._flag_updating_deviceregistry = True
                self._sync_connected_platforms()
                unreachable = []
                # Loop over the connections to the registered agent platforms.
                for k, v in self._pa_agents.items():
                    _log.debug('updating for {}'.format(k))
                    # Only attempt update if we have a connection to the
                    # agent instance.
                    if v is not None:
                        try:
                            devices = v.agent.vip.rpc.call(
                                VOLTTRON_CENTRAL_PLATFORM,
                                'get_devices').get(timeout=30)

                            anon_devices = defaultdict(dict)

                            # for each device returned from the query to
                            # get_devices we need to anonymize the k1 in the
                            # anon_devices dictionary.
                            for k1, v1 in devices.items():
                                _log.debug(
                                    "before anon: {}, {}".format(k1, v1))
                                # now we need to do a search/replace on the
                                # self._topic_list so that the devices are
                                # known as the correct itme nin the tree.
                                anon_topic = self._topic_replace_map[k1]

                                # if replaced has not already been replaced
                                if not anon_topic:
                                    anon_topic = k1
                                    for sr in self._topic_replace_list:
                                        anon_topic = anon_topic.replace(
                                            sr['from'], sr['to'])

                                    self._topic_replace_map[k1] = anon_topic

                                anon_devices[anon_topic] = v1

                            _log.debug('Anon devices are: {}'.format(
                                anon_devices))

                            self._registry.update_devices(k, anon_devices)
                        except (gevent.Timeout, Unreachable) as e:
                            _log.error(
                                'Error getting devices from platform {}'
                                    .format(k))
                            unreachable.append(k)
                for k in unreachable:
                    if self._pa_agents[k]:
                        self._pa_agents[k].disconnect()
                    del self._pa_agents[k]

        finally:
            self._flag_updating_deviceregistry = False


    def _route_request(self, session_user, id, method, params):
        '''Route request to either a registered platform or handle here.'''
        _log.debug(
            'inside _route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        if method == 'register_instance':
            _log.debug('Inside register_instance')
            _log.debug('Logs {}'.format(params))
            if isinstance(params, list):
                return self._register_instance(*params)
            else:
                return self._register_instance(**params)
        elif method == 'list_deivces':
            return self._handle_list_devices()
        elif method == 'list_performance':
            return self._handle_list_performance()
        elif method == 'list_platforms':
            return self._handle_list_platforms()
        elif method == 'unregister_platform':
            return self.unregister_platform(params['platform_uuid'])
        elif method == 'get_setting':
            if 'key' not in params or not params['key']:
                return err('Invalid parameter key not set',
                           INVALID_PARAMS)
            value = self._setting_store.get(params['key'], None)
            if value is None:
                return err('Invalid key specified', INVALID_PARAMS)
            return value
        elif method == 'get_setting_keys':
            return self._setting_store.keys()
        elif method == 'set_setting':
            if 'key' not in params or not params['key']:
                return err('Invalid parameter key not set',
                           INVALID_PARAMS)
            _log.debug('VALUE: {}'.format(params))
            if 'value' not in params:
                return err('Invalid parameter value not set',
                           INVALID_PARAMS)
            # if passing None value then remove the value from the keystore
            # don't raise an error if the key isn't present in the store.
            if params['value'] is None:
                if params['key'] in self._setting_store:
                    del self._setting_store[params['key']]
            else:
                self._setting_store[params['key']] = params['value']
                self._setting_store.sync()
            return 'SUCCESS'
        elif 'historian' in method:
            has_platform_historian = PLATFORM_HISTORIAN in \
                                     self.vip.peerlist().get(timeout=30)
            if not has_platform_historian:
                return err('The VOLTTRON Central platform historian is unavailable.',
                           UNAVAILABLE_AGENT)
            _log.debug('Trapping platform.historian to vc.')
            _log.debug('has_platform_historian: {}'.format(
                has_platform_historian))
            if 'historian.query' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'query', **params).get(timeout=30)
            elif 'historian.get_topic_list' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'get_topic_list').get(timeout=30)

        fields = method.split('.')
        if len(fields) < 3:
            return err('Unknown method {}'.format(method))
        platform_uuid = fields[2]
        platform = self._registered_platforms.get(platform_uuid)
        if not platform:
            return err('Unknown platform {}'.format(platform_uuid))
        platform_method = '.'.join(fields[3:])
        _log.debug(platform_uuid)
        # Get a connection object associated with the platform uuid.
        cn = self._pa_agents.get(platform_uuid)
        if not cn:
            return jsonrpc.json_error(id,
                                      UNAVAILABLE_PLATFORM,
                                      "Cannot connect to platform."
                                      )
        _log.debug('Routing to {}'.format(VOLTTRON_CENTRAL_PLATFORM))

        if platform_method == 'install':
            if 'admin' not in session_user['groups']:
                return jsonrpc.json_error(
                    id, UNAUTHORIZED,
                    "Admin access is required to install agents")

        if platform_method == 'list_agents':
            _log.debug('Callling list_agents')
            connection = self._pa_agents.get(platform_uuid)
            agents = connection.call('list_agents')

            if agents is None:
                _log.warn('No agents found for platform_uuid {}'.format(
                    platform_uuid
                ))
                agents = []

            for a in agents:
                if 'admin' not in session_user['groups']:
                    a['permissions'] = {
                        'can_stop': False,
                        'can_start': False,
                        'can_restart': False,
                        'can_remove': False
                    }
                else:
                    _log.debug('Permissionse for {} are {}'
                               .format(a['name'], a['permissions']))
            return agents
        else:
            try:
                return cn.agent.vip.rpc.call(
                    VOLTTRON_CENTRAL_PLATFORM, 'route_request', id,
                    platform_method,
                    params).get(timeout=30)
            except (Unreachable, gevent.Timeout) as e:
                del self._pa_agents[platform_uuid]
                return err("Can't route to platform",
                           UNAVAILABLE_PLATFORM)


def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    utils.vip_main(VolttronCentralAgent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
