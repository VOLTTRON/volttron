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

from collections import defaultdict
import errno
import logging
import sys
import os
import os.path as p

import gevent
from abc import ABCMeta

from authenticate import Authenticate
from sessions import SessionHandler
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
    UNAVAILABLE_AGENT)
from volttron.platform.messaging.health import UNKNOWN_STATUS, Status, \
    BAD_STATUS
from .resource_directory import ResourceDirectory
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core, Unreachable
from volttron.platform.vip.agent.subsystems import query
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.web import (DiscoveryInfo, DiscoveryError)
from zmq.utils import jsonapi
from .registry import PlatformRegistry

__version__ = "3.5.3"

_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))


class Connected(object):
    __metaclass__ = ABCMeta

    @property
    def agent(self):
        raise NotImplementedError('Class must implment this property')

    def is_connected(self):
        raise NotImplementedError('Class must implment is_connected function')


class ConnectedLocalPlatform(Connected):
    def __init__(self, agent):
        super(ConnectedLocalPlatform, self).__init__()
        self._connected_agent = agent

    @property
    def agent(self):
        return self._connected_agent

    def is_connected(self):
        try:
            resp = self._connected_agent.vip.ping(
                VOLTTRON_CENTRAL_PLATFORM).get(timeout=15)
            return True
        except gevent.Timeout, Unreachable:
            _log.debug("Timeout ping address {} for agent."
                       .format(self._address))
            return False

    def disconnect(self):
        self._connected_agent = None


class ConnectedPlatform(Connected):
    def __init__(self, address, serverkey, publickey, secretkey):
        super(ConnectedPlatform, self).__init__()
        self._address = address
        self._serverkey = serverkey
        self._publickey = publickey
        self._secretkey = secretkey
        self._connected_agent = None

    def connect(self):
        _log.info('Connecting {}'.format(self._address))
        self._connected_agent = build_agent(
            address=self._address, serverkey=self._serverkey,
            secretkey=self._secretkey, publickey=self._publickey
        )

    def disconnect(self):
        _log.info('Disconnecting {}'.format(self._address))
        if self._connected_agent:
            self._connected_agent.core.stop()
            self._connected_agent = False

    @property
    def agent(self):
        if not self.is_connected():
            self.connect()
        return self._connected_agent

    def is_connected(self):
        if self._connected_agent:
            try:
                resp = self._connected_agent.vip.ping(
                    VOLTTRON_CENTRAL_PLATFORM).get(timeout=15)
            except gevent.Timeout:
                _log.debug("Timeout ping address {} for agent."
                           .format(self._address))
                self._connected_agent = None

        return self._connected_agent


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

        # A resource directory that contains everything that can be looked up.
        self._resources = ResourceDirectory()
        self._registry = self._resources.platform_registry

        # This has a dictionary mapping the platform_uuid to an agent
        # connected to the vip-address of the registered platform.  If the
        # registered platform is None then that means we were unable to
        # connect to the platform the last time it was tried.
        self._pa_agents = {}

        # if there is a volttron central agent on this instance then this
        # will be resolved.
        self._peer_platform = None

        # An object that allows the checking of currently authenticated
        # sessions.
        self._sessions = SessionHandler(Authenticate(self._user_map))
        self.webaddress = None
        self._web_info = None

        # A flag that tels us that we are in the process of updating already.
        # This will allow us to not have multiple periodic calls at the same
        # time which could cause unpredicatable results.
        self._flag_updating_deviceregistry = False

        self._setting_store = load_create_store(
            os.path.join(os.environ['VOLTTRON_HOME'],
                         'data', 'volttron.central.settings'))

        self._request_store = load_create_store(
            os.path.join(os.environ['VOLTTRON_HOME'],
                         'data', 'volttron.central.requeststore'))

    # @Core.periodic(60)
    def _reconnect_to_platforms(self):
        """ Attempt to reconnect to all the registered platforms.
        """
        _log.info('Reconnecting to platforms')
        for entry in self._registry.get_platforms():
            try:
                conn_to_instance = None
                if entry.is_local:
                    _log.debug('connecting to vip address: {}'.format(
                        self._local_address
                    ))
                    conn_to_instance = ConnectedLocalPlatform(self)
                elif entry.platform_uuid in self._pa_agents.keys():
                    conn_to_instance = self._pa_agents.get(entry.platform_uuid)
                    try:
                        if conn_to_instance.agent.vip.peerlist.get(timeout=15):
                            pass
                    except gevent.Timeout:
                        del self._pa_agents[entry.platform_uuid]
                        conn_to_instance = None

                if not conn_to_instance:
                    _log.debug('connecting to vip address: {}'.format(
                        entry.vip_address
                    ))
                    conn_to_instance = ConnectedPlatform(
                        address=entry.vip_address,
                        serverkey=entry.serverkey,
                        publickey=self.core.publickey,
                        secretkey=self.core.secretkey
                    )

                # Subscribe to the underlying agent's pubsub bus.
                _log.debug("subscribing to platforms pubsub bus.")
                conn_to_instance.agent.vip.pubsub.subscribe(
                    "pubsub", "platforms", self._on_platforms_messsage)
                self._pa_agents[entry.platform_uuid] = conn_to_instance
                _log.debug('Configuring platform to be the correct uuid.')
                conn_to_instance.agent.vip.rpc.call(
                    VOLTTRON_CENTRAL_PLATFORM, "reconfigure",
                    platform_uuid=entry.platform_uuid).get(timeout=15)

            except (gevent.Timeout, Unreachable) as e:
                _log.error("Unreachable platform address: {}"
                           .format(entry.vip_address))
                self._pa_agents[entry.platform_uuid] = None

    @PubSub.subscribe("pubsub", "heartbeat/volttroncentralplatform")
    def _on_platform_heartbeat(self, peer, sender, bus, topic, headers,
                               message):
        _log.debug('Got Heartbeat from: {}'.format(topic))

    def _handle_pubsub_register(self, message):
        # register the platform if a local platform otherwise put it
        # in a to_register store
        required = ('serverkey', 'publickey', 'address')
        valid = True
        for p in required:
            if not p in message or not message[p]:
                _log.error('Invalid {} param not specified or invalid')
                valid = False
        # Exit loop if not valid.
        if not valid:
            _log.warn('Invalid message format for platform registration.')
            return

        _log.info('Attempting to register through pubsub address: {}'
                  .format(message['address']))

        passed_uuid = None
        if 'had_platform_uuid' in message:
            passed_uuid = message['had_platform_uuid']

            entry = self._registry.get_platform(passed_uuid)
            if not entry:
                _log.error('{} was not found as a previously registered '
                           'platform. Address: {}'
                           .format(passed_uuid, message['address']))
                return

            # Verify the platform address serverkey publickey are the
            # same.
            _log.debug('Refreshing registration for {}'
                       .format(message['address']))

        if self._local_address == message['address']:
            if passed_uuid is not None:
                _log.debug('Local platform entry attempting to re-register.')
                local_entry = self._registry.get_platform(passed_uuid)
                if passed_uuid in self._pa_agents.keys():
                    if self._pa_agents[passed_uuid]:
                        self._pa_agents[passed_uuid].disconnect()
                    del self._pa_agents[passed_uuid]
            else:
                _log.debug('Local platform entry attempting to register.')
                local_entry = PlatformRegistry.build_entry(
                    None, None, None, is_local=True, display_name='local')
                self._registry.register(local_entry)
            connected = ConnectedLocalPlatform(self)
            _log.debug('Calling manage on local vcp.')
            pubkey = connected.agent.vip.rpc.call(
                VOLTTRON_CENTRAL_PLATFORM, 'manage', self._local_address,
                self.core.publickey, self._web_info.serverkey
            )
            _log.debug('Reconfiguring platform_uuid for local vcp.')
            # Change the uuid of the agent.
            connected.agent.vip.rpc.call(
                VOLTTRON_CENTRAL_PLATFORM, 'reconfigure',
                platform_uuid=local_entry.platform_uuid)
            self._pa_agents[local_entry.platform_uuid] = connected

        else:
            _log.debug('External platform entry attempting to register.')
            # TODO use the following to store data for registering
            # platform.
            # self._request_store[message['address']] = message
            # self._request_store.sync()
            connected = ConnectedPlatform(
                address=message['address'],
                serverkey=message['serverkey'],
                publickey=self.core.publickey,
                secretkey=self.core.secretkey
            )

            _log.debug('Connecting to external vcp.')
            connected.connect()
            if not connected.is_connected():
                _log.error("Couldn't connect {} address"
                           .format(message['address']))
                return
            _log.debug('Attempting to manage {} from address {}'
                       .format(message['address'], self.core.address))
            vcp_pubkey = connected.agent.vip.rpc.call(
                VOLTTRON_CENTRAL_PLATFORM,
                'manage', address=self.core.address,
                vcserverkey=self._web_info.serverkey,
                vcpublickey=self.core.publickey
            ).get(timeout=15)

            # Check that this pubkey is the same as the one passed through
            # pubsub mechanism.
            if not vcp_pubkey == message['publickey']:
                _log.error("Publickey through pubsub doesn't match "
                           "through manage platform call. ")
                _log.error("Address {} was attempting to register."
                           .format(message['address']))
                return

            if passed_uuid:
                entry = self._registry.get_platform(passed_uuid)
            else:
                entry = PlatformRegistry.build_entry(
                    vip_address=message['address'],
                    serverkey=message['serverkey'],
                    vcp_publickey=message['publickey'],
                    is_local=False,
                    discovery_address=message.get('discovery_address'),
                    display_name=message.get('display_name')
                )
                self._registry.register(entry)

            self._pa_agents[entry.platform_uuid] = connected

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

        if not self._registry.get_platform(platform_uuid):
            _log.warn('Platform {} is not registered but sent message {}'
                      .format(platform_uuid, message))
            return

        if len(topicsplit) < 3:
            _log.warn("Invalid topic length no operation specified.")

        _log.debug('Doing operation: {}'.format(topicsplit[2]))

        self._registry.update_agent_list(platform_uuid, message)

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

        self._registry.update_performance(platform_uuid=platform_uuid,
                                          performance=stats)

    @RPC.export
    def get_platforms(self):
        """ Retrieves the platforms that have been registered with VC.

        @return:
        """
        return self._registry.get_platforms()

    @RPC.export
    def get_platform(self, platform_uuid):
        return self._registry.get_platform(platform_uuid)

    # @Core.periodic(15)
    def _auto_register_peer(self):
        """ Auto register a volttron central platform.

        This should only happen if there isn't already a peer registered and
        then only if there hasn't been a local platform registered already.
        """
        pass
        # if not self._peer_platform:
        #     for p in self._registry.get_platforms():
        #         if p.is_local:
        #             _log.debug("Reconfiguring local to use: {}".format(
        #                 p.platform_uuid))
        #             self.vip.rpc.call(
        #                 VOLTTRON_CENTRAL_PLATFORM, 'reconfigure',
        #                 platform_uuid=p.platform_uuid
        #             )
        #             return
        #
        #     peers = self.vip.peerlist().get(timeout=30)
        #     if 'platform.agent' in peers:
        #         _log.debug('Auto connecting platform.agent on vc')
        #         # the _peer_platform is set to self because we don't need
        #         # another agent to connect to the bus instead we just use
        #         # this agent.
        #         self._peer_platform = self
        #         local_entry = PlatformRegistry.build_entry(
        #             None, None, None, is_local=True, display_name='local')
        #
        #         self._registry.register(local_entry)
        #         self._pa_agents[local_entry.platform_uuid] = self
        #         _log.debug("Reconfiguring local to use: {}".format(
        #             local_entry.platform_uuid))
        #         self.vip.rpc.call(
        #             VOLTTRON_CENTRAL_PLATFORM, 'reconfigure',
        #             platform_uuid=local_entry.platform_uuid
        #         )

    def _disconnect_peer_platform(self, sender, **kwargs):
        _log.debug("disconnecting peer_platform")
        self._peer_platform = None

    @RPC.export
    def list_platform_details(self):
        _log.debug('list_platform_details {}', self._registry.get_platforms())
        return self._registry.get_platforms()

    @RPC.export
    def unregister_platform(self, platform_uuid):
        _log.debug('unregister_platform')
        platform = self._registry.get_platform(platform_uuid)
        if platform:
            self._registry.unregister(platform.vip_address)
            self._store_registry()

            if platform_uuid in self._pa_agents.keys():
                connected = self._pa_agents[platform_uuid]
                # Don't stop the local platform because that is this
                # agent.
                if not platform.is_local:
                    connected.disconnect()
                del self._pa_agents[platform_uuid]
                del connected

            if platform.is_local:
                self._peer_platform = None
            context = 'Unregistered platform {}'.format(platform_uuid)
            return {'status': 'SUCCESS', 'context': context}
        else:
            msg = 'Unable to unregistered platform {}'.format(platform_uuid)
            return {'error': {'code': UNABLE_TO_UNREGISTER_INSTANCE,
                              'message': msg}}

    @RPC.export
    def register_instance(self, discovery_address):
        """ Adds discovery_address to proposed list of agents.

        This method is called from a configured agent to hone into the
        `VolttronCentralAgent`.  An administrator must then choose to
        accept the call from this agent before the agent will be granted
        status.

        :param string: The url of the discovery_address for the platform.
        """
        _log.debug('register_instance called via RPC')
        self._register_instance(discovery_address,
                                display_name=discovery_address)

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
            connected_to_pa = ConnectedPlatform(
                address=pa_vip_address, serverkey=pa_instance_serverkey,
                secretkey=self.core.secretkey,
                publickey=self.core.publickey
            )
            connected_to_pa.connect()
            if not connected_to_pa.is_connected():
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

        _log.debug('Connected to address')
        peers = connected_to_pa.agent.vip.peerlist().get(timeout=30)
        if VOLTTRON_CENTRAL_PLATFORM not in peers:
            connected_to_pa.core.stop()
            return {'error': {'code': UNABLE_TO_REGISTER_INSTANCE,
                              'message': '{} not present.'.format(
                                  VOLTTRON_CENTRAL_PLATFORM)
                              }}

        # The call to manage should return a public key for that agent
        result = connected_to_pa.agent.vip.rpc.call(
            VOLTTRON_CENTRAL_PLATFORM, 'manage', self._web_info.vip_address,
            self._web_info.serverkey, self.core.publickey).get(timeout=30)

        # Magic number 43 is the length of a encoded public key.
        if len(result) != 43:
            return {'error': {'code': UNABLE_TO_REGISTER_INSTANCE,
                              'message': 'Invalid publickey returned from {}'
                                  .format(VOLTTRON_CENTRAL_PLATFORM)
                              }}

        # Add the pa's public key so it can connect back to us.
        auth_file = AuthFile()
        auth_entry = AuthEntry(credentials="CURVE:{}".format(result),
                               capabilities=['managing']
                               )
        auth_file.add(auth_entry)

        # TODO: figure out if we are local or not

        entry = PlatformRegistry.build_entry(
            pa_vip_address, pa_instance_serverkey, discovery_address,
            display_name, False)

        self._registry.register(entry)
        self._pa_agents[entry.platform_uuid] = connected_to_pa
        _log.debug("Adding {}".format(entry.platform_uuid))
        instance_name = display_name if display_name else discovery_address
        context = 'Registered instance {}'.format(instance_name)
        connected_to_pa.agent.vip.rpc.call(
            VOLTTRON_CENTRAL_PLATFORM, 'reconfigure',
            platform_uuid=entry.platform_uuid).get(timeout=30)

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

    @Core.receiver('onstart')
    def _starting(self, sender, **kwargs):
        """ Starting of the platform
        :param sender:
        :param kwargs:
        :return:
        """
        self.vip.heartbeat.start()

        q = query.Query(self.core)
        self._external_addresses = q.query('addresses').get(timeout=30)

        # TODO: Use all addresses for fallback, #114
        _log.debug("external addresses are: {}".format(
            self._external_addresses
        ))

        self._local_address = q.query('local_address').get(timeout=30)
        _log.debug('Local address is? {}'.format(self._local_address))
        _log.debug('Registering jsonrpc and /.* routes')

        self.vip.rpc.call(MASTER_WEB, 'register_agent_route',
                          r'^/jsonrpc.*',
                          self.core.identity,
                          'jsonrpc').get(timeout=30)

        self.vip.rpc.call(MASTER_WEB, 'register_path_route', VOLTTRON_CENTRAL,
                          r'^/.*', self._webroot).get(timeout=30)

        self.webaddress = self.vip.rpc.call(
            MASTER_WEB, 'get_bind_web_address').get(timeout=30)

        assert self.core.publickey
        assert self.core.secretkey
        assert self.webaddress
        self._web_info = DiscoveryInfo.request_discovery_info(self.webaddress)
        # Reconnect to the platforms that are in the registry.
        self._reconnect_to_platforms()

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
            v.disconnect()

        self._pa_agents.clear()

        self.vip.rpc.call(MASTER_WEB, 'unregister_all_agent_routes',
                          self.core.identity).get(timeout=30)

    @Core.periodic(10)
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

    def _handle_list_performance(self):
        _log.debug('Listing performance topics from vc')
        return [{'platform.uuid': x.platform_uuid,
                 'performance': self._registry.get_performance(
                     x.platform_uuid)
                 } for x in self._registry.get_platforms()
                if self._registry.get_performance(x.platform_uuid)]

    def _handle_list_devices(self):
        _log.debug('Listing devices from vc')
        return [{'platform.uuid': x.platform_uuid,
                 'devices': self._registry.get_devices(x.platform_uuid)}
                for x in self._registry.get_platforms()
                if self._registry.get_devices(x.platform_uuid)]

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
                health = cn.agent.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM,
                                               'get_health').get(timeout=30)
            except Unreachable:
                health = Status.build(UNKNOWN_STATUS,
                                      "Platform Agent Unreachable").as_dict()
            return health

        _log.debug(
            'Listing platforms: {}'.format(self._registry.get_platforms()))
        return [{'uuid': x.platform_uuid,
                 'name': x.display_name,
                 'health': get_status(x.platform_uuid)}
                for x in self._registry.get_platforms()]

    def _route_request(self, session_user, id, method, params):
        '''Route request to either a registered platform or handle here.'''
        _log.debug(
            'inside _route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        if method == 'register_instance':
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
                return err('Platform historian not found on volttorn central',
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
        platform = self._registry.get_platform(platform_uuid)
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
            agents = self._registry.get_agent_list(platform_uuid)

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
