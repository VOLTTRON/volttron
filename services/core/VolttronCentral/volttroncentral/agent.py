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
import errno
import hashlib
import logging
import os
import os.path as p
import sys
from collections import defaultdict, namedtuple
from copy import deepcopy
from urlparse import urlparse

import datetime
import gevent
from volttron.platform.auth import AuthFile, AuthEntry
from zmq.utils import jsonapi

from authenticate import Authenticate
from platforms import Platforms, PlatformHandler
from sessions import SessionHandler
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.exit_codes import INVALID_CONFIGURATION_CODE
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, PLATFORM_HISTORIAN)
from volttron.platform.agent.utils import (
    get_aware_utc_now, format_timestamp)
from volttron.platform.jsonrpc import (
    INVALID_REQUEST, METHOD_NOT_FOUND,
    UNHANDLED_EXCEPTION, UNAUTHORIZED,
    DISCOVERY_ERROR,
    UNABLE_TO_UNREGISTER_INSTANCE, UNAVAILABLE_PLATFORM, INVALID_PARAMS,
    UNAVAILABLE_AGENT, INTERNAL_ERROR)
from volttron.platform.messaging.health import Status, \
    BAD_STATUS, GOOD_STATUS, UNKNOWN_STATUS
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core, Unreachable
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.web import (DiscoveryInfo, DiscoveryError)

__version__ = "4.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))

Platform = namedtuple('Platform', ['instance_name', 'serverkey', 'vip_address'])
RequiredArgs = namedtuple('RequiredArgs', ['id', 'session_user',
                                           'platform_uuid'])


class VolttronCentralAgent(Agent):
    """ Agent for managing many volttron instances from a central web ui.

    During the


    """

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
        _log.info("{} constructing...".format(self.__class__.__name__))

        super(VolttronCentralAgent, self).__init__(enable_web=True, **kwargs)
        # Load the configuration into a dictionary
        config = utils.load_config(config_path)

        # Required users
        users = config.get('users', None)

        # Expose the webroot property to be customized through the config
        # file.
        webroot = config.get('webroot', DEFAULT_WEB_ROOT)
        if webroot.endswith('/'):
            webroot = webroot[:-1]

        topic_replace_list = config.get('topic-replace-list', [])

        # Create default configuration to be used in case of problems in the
        # packaged agent configuration file.
        self.default_config = dict(
            webroot=os.path.abspath(webroot),
            users=users,
            topic_replace_list=topic_replace_list
        )

        # During the configuration update/new/delete action this will be
        # updated to the current configuration.
        self.runtime_config = None

        # Start using config store.
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self.configure_main,
                                  actions=['NEW', 'UPDATE', 'DELETE'],
                                  pattern="config")

        # Use config store to update the settings of a platform's configuration.
        self.vip.config.subscribe(self.configure_platforms,
                                  actions=['NEW', 'UPDATE', 'DELETE'],
                                  pattern="platforms/*")

        # mapping from the real topic into the replacement.
        self.replaced_topic_map = {}

        # mapping from md5 hash of address to the actual connection to the
        # remote instance.
        self.vcp_connections = {}

        # Current sessions available to the
        self.web_sessions = None

        # Platform health based upon device driver publishes
        self.device_health = defaultdict(dict)

        # Used to hold scheduled reconnection event for vcp agents.
        self._vcp_reconnect_event = None

        # the registered socket endpoints so we can send out management
        # events to all the registered session.
        self._websocket_endpoints = set()

        self._platforms = Platforms(self)

        self._platform_scan_event = None
        self._connected_platforms = dict()

    @staticmethod
    def _get_next_time_seconds(seconds=10):
        now = get_aware_utc_now()
        next_time = now + datetime.timedelta(seconds=seconds)
        return next_time

    def _handle_platform_connection(self, platform_vip_identity):
        _log.debug("Handling new platform connection {}".format(
            platform_vip_identity))

        self._platforms.add_platform(platform_vip_identity)

    def _handle_platform_disconnect(self, platform_vip_identity):
        _log.debug("Handling disconnection of connection from identity: {}".format(
            platform_vip_identity
        ))
        # TODO send alert that there was a platform disconnect.
        self._platforms.disconnect_platform(platform_vip_identity)

    def _scan_for_platforms(self):
        """
        Scan the local bus for peers that start with 'vcp-'.  Handle the
        connection and disconnection events here.
        """
        if self._platform_scan_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._platform_scan_event.cancel()

        # Identities of all platform agents that are connecting to us should
        # have an identity of platform.md5hash.
        connected_platforms = set([x for x in self.vip.peerlist().get(timeout=5)
                                   if x.startswith('vcp-')])

        disconnected = self._platforms.get_platform_keys() - connected_platforms

        for vip_id in disconnected:
            self._handle_platform_disconnect(vip_id)

        not_known = connected_platforms - self._platforms.get_platform_keys()

        for vip_id in not_known:
            self._handle_platform_connection(vip_id)

        next_platform_scan = VolttronCentralAgent._get_next_time_seconds()

        # reschedule the next scan.
        self._platform_scan_event = self.core.schedule(
            next_platform_scan, self._scan_for_platforms)

    def configure_main(self, config_name, action, contents):
        """
        The main configuration for volttron central.  This is where validation
        will occur.

        Note this method is called:

            1. When the agent first starts (with the params from packaged agent
               file)
            2. When 'store' is called through the volttron-ctl config command
               line with 'config' as the name.

        Required Configuration:

        The volttron central requires a user mapping.

        :param config_name:
        :param action:
        :param contents:
        """

        _log.debug('Main config updated')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))
        if action == 'DELETE':
            # Remove the registry and keep the service running.
            self.runtime_config = None
            # Now stop the exposition of service.
        else:
            self.runtime_config = self.default_config.copy()
            self.runtime_config.update(contents)

            problems = self._validate_config_params(self.runtime_config)

            if len(problems) > 0:
                _log.error(
                    "The following configuration problems were detected!")
                for p in problems:
                    _log.error(p)
                sys.exit(INVALID_CONFIGURATION_CODE)
            else:
                _log.info('volttron central webroot is: {}'.format(
                    self.runtime_config.get('webroot')
                ))

                users = self.runtime_config.get('users')
                self.web_sessions = SessionHandler(Authenticate(users))

            _log.debug('Querying router for addresses and serverkey.')
            q = Query(self.core)

            external_addresses = q.query('addresses').get(timeout=5)
            self.runtime_config['local_external_address'] = external_addresses[0]

        self.vip.web.register_websocket(r'/vc/ws', self.open_authenticate_ws_endpoint, self._ws_closed, self._ws_received)
        self.vip.web.register_endpoint(r'/jsonrpc', self.jsonrpc)
        self.vip.web.register_path(r'^/.*', self.runtime_config.get('webroot'))

        # Start scanning for new platforms connections as well as for
        # disconnects that happen.
        self._scan_for_platforms()

        #
        # auth_file = AuthFile()
        # entry = auth_file.find_by_credentials(self.core.publickey)[0]
        # if 'manager' not in entry.capabilities:
        #     _log.debug('Adding manager capability for volttron.central to '
        #                'local instance. Publickey is {}'.format(
        #         self.core.publickey))
        #     entry.add_capabilities(['manager'])
        #     auth_file.add(entry, True)
        #     gevent.sleep(0.1)
        #
        # # We know that peers are going to be connected to this platform with the
        # # identity of platform.address_hash so we collect all of the peers that
        # # have that signature.  Then if there is a config store entry for that
        # # platform then register it.
        # platforms = [p for p in self.vip.peerlist().get(timeout=2)
        #              if p.startswith('platform')]
        # for p in platforms:
        #     try:
        #         config_name="platforms/{}".format(p.split(".")[1])
        #         platform_config = self.vip.config.get(config_name)
        #     except KeyError:
        #         _log.warn(
        #             "Couldn't reconnect to platform, missing data for "
        #             "already connected platform.")
        #     else:
        #         _log.warn("Re-registering platform: {} {}".format(
        #             platform_config['display_name'],
        #             platform_config['address']
        #         ))
        #         self._platforms.register_platform(
        #             platform_config['address'],
        #             platform_config['address_type'],
        #             platform_config['serverkey'],
        #             platform_config['display_name']
        #         )

    def configure_platforms(self, config_name, action, contents):
        _log.debug('Platform configuration updated.')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))

    def open_authenticate_ws_endpoint(self, fromip, endpoint):
        """
        Callback method from when websockets are opened.  The endpoine must
        be '/' delimited with the second to last section being the session
        of a logged in user to volttron central itself.

        :param fromip:
        :param endpoint:
            A string representing the endpoint of the websocket.
        :return:
        """
        _log.debug("OPENED ip: {} endpoint: {}".format(fromip, endpoint))
        try:
            session = endpoint.split('/')[-2]
        except IndexError:
            _log.error("Malformed endpoint. Must be delimited by '/'")
            _log.error(
                'Endpoint must have valid session in second to last position')
            return False

        if not self.web_sessions.check_session(session, fromip):
            _log.error("Authentication error for session!")
            return False

        _log.debug('Websocket allowed.')
        self._websocket_endpoints.add(endpoint)

        return True

    def _ws_closed(self, endpoint):
        _log.debug("CLOSED endpoint: {}".format(endpoint))
        try:
            self._websocket_endpoints.remove(endpoint)
        except KeyError:
            pass # This should never happen but protect against it anyways.

    def _ws_received(self, endpoint, message):
        _log.debug("RECEIVED endpoint: {} message: {}".format(endpoint,
                                                              message))

    @RPC.export
    def is_registered(self, address_hash=None, address=None):
        if address_hash is None and address is None:
            return False

        if address_hash is None:
            address_hash = PlatformHandler.address_hasher(address)

        return self._platforms.is_registered(address_hash)

    @RPC.export
    def register_instance(self, address, display_name=None, vcpserverkey=None,
                          vcpagentkey=None):
        """
        RPC Method to register an instance with volttron central.

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

        :param str address:
            The url of the address for the platform.
        :param str display_name:
            (Optional) How the instance is displayed on volttron central.  This
            will default to address if it is not specified.
        :param str vcpserverkey:
            (Optional) A server key for connecting from volttron central to the
            calling instance
        :param str vcpagentkey:
            (Optional) The public key associated with the vcp agent connecting
            to the volttron central instance.
        """
        _log.debug('register_instance called via RPC address: {}'.format(address))

        _log.debug('rpc context for register_instance is: {}'.format(
            self.vip.rpc.context.request)
        )
        _log.debug('rpc context for register_instance is: {}'.format(
            self.vip.rpc.context.vip_message)
        )

        parsed = urlparse(address)

        valid_schemes = ('http', 'https', 'tcp', 'ipc')
        if parsed.scheme not in valid_schemes:
            raise ValueError('Unknown scheme specified {} valid schemes are {}'
                             .format(parsed.scheme, valid_schemes))

        try:
            if parsed.scheme in ('http', 'https'):
                address_hash, platform = self._register_instance(
                    address, parsed.scheme, display_name=display_name)
            elif parsed.scheme == 'tcp':
                if not vcpserverkey or len(vcpserverkey) != 43:  # valid publickey length
                    raise ValueError(
                        "tcp addresses must have valid vcpserverkey provided")
                address_hash, platform = self._platforms.register_platform(
                    address, parsed.scheme, vcpserverkey, display_name)
            else: # ipc
                address_hash, platform = self._platforms.register_platform(
                    address, parsed.scheme, display_name=display_name)
        except gevent.Timeout:
            return dict(status="FAILED",
                        context="Unable to register platform instance.")
        else:
            config_name = "platforms/{}".format(address_hash)
            try:
                current_config = self.vip.config.get(config_name)
            except KeyError:
                current_config = {}
            config_store_data = dict(
                address_type=parsed.scheme, display_name=platform.display_name,
                address=platform.address, serverkey=platform.serverkey,
                unregistered=False
            )
            current_config.update(config_store_data)
            self.vip.config.set(config_name, current_config)
            return dict(status="SUCCESS", context=address_hash)

    def _periodic_reconnect_to_platforms(self):
        _log.debug('Reconnecting to external platforms.')
        if self._vcp_reconnect_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._vcp_reconnect_event.cancel()

        platforms = [x for x in self.vip.config.list()
                     if x.startswith('platforms/')]
        _log.debug('Platforms: {}'.format(platforms))
        self.send_management_message("PLATFORM_HEARTBEAT", "Checking Platforms")
        for x in platforms:
            platform = self.vip.config.get(x)
            address = platform.get('address')
            serverkey = platform.get('serverkey')
            _log.debug('Address: {} Serverkey: {}'.format(address, serverkey))
            cn = self.vcp_connections.get(platform.get('instance_uuid'))
            if cn is not None:
                if cn.is_connected() and cn.is_peer_connected():
                    _log.debug('Platform {} already connected'.format(
                        platform.get('address')))

                    continue
                elif cn.is_connected() and not cn.is_peer_connected():
                    _log.debug("Connection available, missing peer.")
                    continue

            _log.debug('Reconnecting to: {}'.format(platform.get('address')))
            try:
                cn = self._build_connection(address, serverkey)
            except gevent.Timeout:
                _log.error("Unable to reconnect to the external instances.")
                continue

            if cn is not None and cn.is_connected() and cn.is_peer_connected():
                self.vcp_connections[x] = cn
                cn.call('manage', self.runtime_config['local_external_address'])
            else:
                _log.debug('Not connected nor managed.')

        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(seconds=10)

        self._vcp_reconnect_event = self.core.schedule(
            next_update_time, self._periodic_reconnect_to_platforms)

    @PubSub.subscribe("pubsub", "heartbeat/platform")
    def _on_platform_heartbeat(self, peer, sender, bus, topic, headers,
                               message):

        self.send_management_message("PLATFORM_HEARTBEAT", {"topic": topic, "message": message})
        address_hash = topic[len("heartbeat/platforms"):]
        config_name = "platforms/{}".format(address_hash)
        if config_name not in self.vip.config.list():
            _log.warn("config unrecoginized {}".format(config_name))
            _log.warn("Unrecognized platform {} sending heartbeat".format(
                address_hash
            ))
        else:
            platform = self.vip.config.get(config_name)
            platform['health'] = message

            # Because the status is only updated on the agent when it is changed
            # and we want to have the same api for health of an agent, we are
            # explicitly overwriting the last_update field of the health to
            # reflect the time passed in the header of the message.

            try:
                if platform['health']['last_updated'] == \
                        message['last_updated']:
                    if 'Date' in headers:
                        platform['health']['last_updated'] = headers['Date']
            except KeyError:
                _log.debug('Expected first time published.')

            if 'Date' in headers:
                platform['last_seen_utc'] = headers['Date']
            self.vip.config.set(config_name, platform, True)

            self.send_management_message("PLATFORM_HEARTBEAT", platform['health'])


    @PubSub.subscribe("pubsub", "platforms")
    def _on_platforms_messsage(self, peer, sender, bus, topic, headers,
                               message):
        """ Callback function for vcp agent to publish to.

        Platforms that are being managed should publish to this topic with
        the agent_list and other interesting things that the volttron
        central shsould want to know.
        """
        topicsplit = topic.split('/')
        if len(topicsplit) < 2:
            _log.error('Invalid topic length published to volttron central')
            return

        # Topic is platforms/<platform_uuid>/otherdata
        topicsplit = topic.split('/')

        if len(topicsplit) < 3:
            _log.warn("Invalid topic length no operation or datatype.")
            return

        _, platform_uuid, op_or_datatype, other = topicsplit[0], \
                                                  topicsplit[1], \
                                                  topicsplit[2], topicsplit[3:]

        _log.warn(platform_uuid)
        _log.warn(op_or_datatype)
        _log.warn(other)
        if op_or_datatype in ('iam', 'configure'):
            if not other:
                _log.error("Invalid response to iam or configure endpoint")
                _log.error(
                    "the sesson token was not included in response from vcp.")
                return

            ws_endpoint = "/vc/ws/{}/{}".format(other[0], op_or_datatype)
            _log.debug('SENDING MESSAGE TO {}'.format(ws_endpoint))
            self.vip.web.send(ws_endpoint, jsonapi.dumps(message))

        # platform = self._registered_platforms.get(platform_uuid)
        # if platform is None:
        #     _log.warn('Platform {} is not registered but sent message {}'
        #               .format(platform_uuid, message))
        #     return
        #
        # _log.debug('Doing operation: {}'.format(op_or_datatype))
        # _log.debug('Topic was: {}'.format(topic))
        # _log.debug('Message was: {}'.format(message))
        #
        # if op_or_datatype == 'devices':
        #     md5hash = message.get('md5hash')
        #     if md5hash is None:
        #         _log.error('Invalid topic for devices datatype.  Must contain '
        #                    'md5hash in message.')
        #     if message['md5hash'] not in self._hash_to_topic:
        #         devices = platform.get("devices", {})
        #         lookup_topic = '/'.join(other)
        #         _log.debug("Lookup topic is: {}".format(lookup_topic))
        #         vcp = self._get_connection(platform_uuid)
        #         device_node = vcp.call("get_device", lookup_topic)
        #         if device_node is not None:
        #             devices[lookup_topic] = device_node
        #             self._hash_to_topic[md5hash] = lookup_topic
        #         else:
        #             _log.error("Couldn't retrive device topic {} from platform "
        #                        "{}".format(lookup_topic, platform_uuid))
        # elif op_or_datatype in ('iam', 'configure'):
        #     ws_endpoint = "/vc/ws/{}".format(op_or_datatype)
        #     self.vip.web.send(ws_endpoint, jsonapi.dumps(message))

    @PubSub.subscribe("pubsub", "datalogger/platforms")
    def _on_platform_log_message(self, peer, sender, bus, topic, headers,
                                 message):
        """ Receive message from a registered platform

        This method is called with stats from the registered platform agents.

        """
        _log.debug('Got datalogger/platforms message (topic): {}'.format(topic))
        _log.debug('Got datalogger/platforms message (message): {}'.format(
            message))

        topicsplit = topic.split('/')
        platform_hash = topicsplit[2]
        config_name = "platforms/{}".format(platform_hash)

        # For devices we use everything between devices/../all as a unique
        # key for determining the last time it was seen.
        key = '/'.join(topicsplit[:])
        uuid = topicsplit[2]

        point_list = []

        for point, item in message.iteritems():
            point_list.append(point)

        stats = {
            'topic': key,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        try:
            platform = self.vip.config.get(config_name)
        except KeyError:
            platform = {}
        platform['stats_point_list'] = stats
        self.vip.config.set(config_name, platform)

    # @RPC.export
    # def get_platforms(self):
    #     """ Retrieves the platforms that have been registered with VC.
    #
    #     @return:
    #     """
    #
    #     _log.debug("Passing platforms back: {}".format(
    #         self._registered_platforms.keys()))
    #     return self._registered_platforms.values()
    #
    # @RPC.export
    # def get_platform(self, platform_uuid):
    #     platform = self._registered_platforms.get(platform_uuid)
    #     if platform is not None:
    #         platform = deepcopy(platform)
    #
    #     return platform

    @RPC.export
    def get_publickey(self):
        """
        RPC method allowing the caller to retrieve the publickey of this agent.

        This method is available for allowing :class:`VolttronCentralPlatform`
        agents to allow this agent to be able to connect to its instance.

        :return: The publickey of this volttron central agent.
        :rtype: str
        """
        return self.core.publickey

    @RPC.export
    def unregister_platform(self, platform_uuid):
        _log.debug('unregister_platform')

        platform = self._registered_platforms.get(platform_uuid)
        if platform:
            connected = self._platform_connections.get(platform_uuid)
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
            del self._platform_connections[platform_uuid]
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

        cn_uuid = self._address_to_uuid.get(address)
        if not cn_uuid:
            raise ValueError("Can't connect to address: {}".format(
                address
            ))

        cn = self._platform_connections.get(cn_uuid)
        if cn is not None:
            if not cn.is_connected():
                cn.kill()
                cn = None

        if cn is None:
            entry = self._registered_platforms.get(cn_uuid)
            entry or _log.debug('Platform registry is empty for uuid {}'
                                .format(cn_uuid))
            assert entry

            cn = Connection(address, peer=VOLTTRON_CENTRAL_PLATFORM,
                            serverkey=entry['serverkey'],
                            secretkey=self.core.secretkey,
                            publickey=self.core.publickey)

            self._platform_connections[cn_uuid] = cn
        return cn

    def _build_connection(self, address, serverkey=None):
        """ Creates a Connection object instance if one doesn't exist for the
        passed address.

        :param address:
        :param serverkey:
        :return:
        """

        address_hash = hashlib.md5(address).hexdigest()

        cn = self.vcp_connections.get(address_hash)

        if cn is None:
            cn = Connection(address=address, serverkey=serverkey,
                            publickey=self.core.publickey,
                            secretkey=self.core.secretkey,
                            peer=VOLTTRON_CENTRAL_PLATFORM)
            _log.debug('Connection established for publickey: {}'.format(
                self.core.publickey))

        assert cn.is_connected(), "Connection unavailable for address {}"\
            .format(address)

        self.vcp_connections[address_hash] = cn
        return cn

    def _get_connection(self, platform_hash):
        cn = self.vcp_connections.get(platform_hash)

        if cn is None:
            raise ValueError('Invalid platform_hash specified {}'
                             .format(platform_hash))
        #
        # if cn is None:
        #     if self._registered_platforms.get(platform_hash) is None:
        #         raise ValueError('Invalid platform_hash specified {}'
        #                          .format(platform_hash))
        #
        #     cn = self._build_connected_agent(
        #         self._registered_platforms[platform_hash]['address']
        #     )
        #
        #     self._platform_connections[platform_hash] = cn

        return cn

    def _register_instance(self, discovery_address, display_name=None):
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
        assert pa_vip_address

        try:
            status = 'SUCCESS'
            context = 'Registered instance {}'.format(display_name)

            address_hash, platform = self._platforms.register_platform(
                address=pa_instance_serverkey,
                serverkey=pa_instance_serverkey,
                address_type=pa_vip_address[:3],
                display_name=display_name)
            platform.add_event_listener(self.send_management_message)
        except gevent.Timeout:
            _log.error("Failed to register instance.")
            self._platforms.remove_platform(address_hash)
            status = 'FAILURE'
            context = "Couldn't register address: {}".format(
                pa_vip_address)
            raise

        return address_hash, platform

    def _store_registry(self):
        self._store('registry', self._registry.package())

    def _to_jsonrpc_obj(self, jsonrpcstr):
        """ Convert data string into a JsonRpcData named tuple.

        :param object data: Either a string or a dictionary representing a json document.
        """
        return jsonrpc.JsonRpcData.parse(jsonrpcstr)

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
                                      'Invalid request method, only POST allowd'
                                      )

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))
            if rpcdata.method == 'get_authorization':
                args = {'username': rpcdata.params['username'],
                        'password': rpcdata.params['password'],
                        'ip': env['REMOTE_ADDR']}
                sess = self.web_sessions.authenticate(**args)
                if not sess:
                    _log.info('Invalid username/password for {}'.format(
                        rpcdata.params['username']))
                    return jsonrpc.json_error(
                        rpcdata.id, UNAUTHORIZED,
                        "Invalid username/password specified.")
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))
                self.vip.web.register_websocket("/vc/ws/{}/management".format(sess),
                                                self.open_authenticate_ws_endpoint,
                                                self._ws_closed,
                                                self._received_data)
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))
                
                gevent.sleep(1)
                return jsonrpc.json_result(rpcdata.id, sess)

            token = rpcdata.authorization
            ip = env['REMOTE_ADDR']
            _log.debug('REMOTE_ADDR: {}'.format(ip))
            session_user = self.web_sessions.check_session(token, ip)
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
        except Unreachable:
            return jsonrpc.json_error(
                rpcdata.id, UNAVAILABLE_PLATFORM,
                "Couldn't reach platform with method {} params: {}"
                .format(rpcdata.method, rpcdata.params)
            )
        except Exception as e:

            return jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, e
            )

        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

    def _get_jsonrpc_response(self, id, result_or_error):
        """ Wrap the response in either a json-rpc error or result.

        :param id:
        :param result_or_error:
        :return:
        """
        if isinstance(result_or_error, dict):
            if 'jsonrpc' in result_or_error:
                return result_or_error

        if result_or_error is not None and isinstance(result_or_error, dict):
            if 'error' in result_or_error:
                error = result_or_error['error']
                _log.debug("RPC RESPONSE ERROR: {}".format(error))
                return jsonrpc.json_error(id, error['code'], error['message'])
        return jsonrpc.json_result(id, result_or_error)

    def _get_agents(self, instance_uuid, groups):
        """ Retrieve the list of agents on a specific platform.

        :param instance_uuid:
        :param groups:
        :return:
        """
        _log.debug('_get_agents')
        connected_to_pa = self._platform_connections[instance_uuid]

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

    def _configure_agent(self, endpoint, message):
        _log.debug('Configure agent: {} message: {}'.format(endpoint, message))

    def _received_data(self, endpoint, message):
        print('Received from endpoint {} message: {}'.format(endpoint, message))
        self.vip.web.send(endpoint, message)

    def set_setting(self, session_user, params):
        """
        Sets or removes a setting from the config store.  If the value is None
        then the item will be removed from the store.  If there is an error in
        saving the value then a jsonrpc.json_error object is returned.

        :param session_user: Unused
        :param params: Dictionary that must contain 'key' and 'value' keys.
        :return: A 'SUCCESS' string or a jsonrpc.json_error object.
        """
        if 'key' not in params or not params['key']:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid parameter key not set')
        if 'value' not in params:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid parameter key not set')

        config_key = "settings/{}".format(params['key'])
        value = params['value']

        if value is None:
            try:
                self.vip.config.delete(config_key)
            except KeyError:
                pass
        else:
            # We handle empt string here because the config store doesn't allow
            # empty strings to be set as a config store.  I wasn't able to
            # trap the ValueError that is raised on the server side.
            if value == "":
                return jsonrpc.json_error(params['message_id'],
                                          INVALID_PARAMS,
                                          'Invalid value set (empty string?)')
            self.vip.config.set(config_key, value)

        return 'SUCCESS'

    def get_setting(self, session_user, params):
        """
        Retrieve a value from the passed setting key.  The params object must
        contain a "key" to return from the settings store.

        :param session_user: Unused
        :param params: Dictionary that must contain a 'key' key.
        :return: The value or a jsonrpc error object.
        """
        config_key = "settings/{}".format(params['key'])
        try:
            value = self.vip.config.get(config_key)
        except KeyError:
            return jsonrpc.json_error(params['message_id'],
                                      INVALID_PARAMS,
                                      'Invalid key specified')
        else:
            return value

    def get_setting_keys(self, session_user, params):
        """
        Returns a list of all of the settings keys so the caller can know
        what settings to request.

        :param session_user: Unused
        :param params: Unused
        :return: A list of settings available to the caller.
        """

        prefix = "settings/"
        keys = [x[len(prefix):] for x in self.vip.config.list()
                if x.startswith(prefix)]
        return keys or []

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        """ Clean up the  agent code before the agent is killed
        """
        pass
        # for v in self._platform_connections.values():
        #     try:
        #         if v is not None:
        #             v.kill()
        #     except AttributeError:
        #         pass
        #
        # self._platform_connections.clear()
        #
        # self.vip.rpc.call(MASTER_WEB, 'unregister_all_agent_routes',
        #                   self.core.identity).get(timeout=30)

    # #@Core.periodic(10)
    # def _update_device_registry(self):
    #     """ Updating the device registery from registered platforms.
    #
    #     :return:
    #     """
    #     try:
    #         if not self._flag_updating_deviceregistry:
    #             _log.debug("Updating device registry")
    #             self._flag_updating_deviceregistry = True
    #             self._sync_connected_platforms()
    #             unreachable = []
    #             # Loop over the connections to the registered agent platforms.
    #             for k, v in self._platform_connections.items():
    #                 _log.debug('updating for {}'.format(k))
    #                 # Only attempt update if we have a connection to the
    #                 # agent instance.
    #                 if v is not None:
    #                     try:
    #                         devices = v.agent.vip.rpc.call(
    #                             VOLTTRON_CENTRAL_PLATFORM,
    #                             'get_devices').get(timeout=30)
    #
    #                         anon_devices = defaultdict(dict)
    #
    #                         # for each device returned from the query to
    #                         # get_devices we need to anonymize the k1 in the
    #                         # anon_devices dictionary.
    #                         for k1, v1 in devices.items():
    #                             _log.debug(
    #                                 "before anon: {}, {}".format(k1, v1))
    #                             # now we need to do a search/replace on the
    #                             # self._topic_list so that the devices are
    #                             # known as the correct itme nin the tree.
    #                             anon_topic = self._topic_replace_map[k1]
    #
    #                             # if replaced has not already been replaced
    #                             if not anon_topic:
    #                                 anon_topic = k1
    #                                 for sr in self._topic_replace_list:
    #                                     anon_topic = anon_topic.replace(
    #                                         sr['from'], sr['to'])
    #
    #                                 self._topic_replace_map[k1] = anon_topic
    #
    #                             anon_devices[anon_topic] = v1
    #
    #                         _log.debug('Anon devices are: {}'.format(
    #                             anon_devices))
    #
    #                         self._registry.update_devices(k, anon_devices)
    #                     except (gevent.Timeout, Unreachable) as e:
    #                         _log.error(
    #                             'Error getting devices from platform {}'
    #                                 .format(k))
    #                         unreachable.append(k)
    #             for k in unreachable:
    #                 if self._platform_connections[k]:
    #                     self._platform_connections[k].disconnect()
    #                 del self._platform_connections[k]
    #
    #     finally:
    #         self._flag_updating_deviceregistry = False

    def _handle_bacnet_props(self, session_user, params):
        platform_uuid = params.pop('platform_uuid')
        id = params.pop('message_id')
        _log.debug('Handling bacnet_props platform: {}'.format(platform_uuid))

        configure_topic = "{}/configure".format(session_user['token'])
        ws_socket_topic = "/vc/ws/{}".format(configure_topic)

        if configure_topic not in self._websocket_endpoints:
            self.vip.web.register_websocket(ws_socket_topic,
                                            self.open_authenticate_ws_endpoint,
                                            self._ws_closed, self._ws_received)

        def start_sending_props():
            response_topic = "configure/{}".format(session_user['token'])
            # Two ways we could have handled this is to pop the identity off
            # of the params and then passed both the identity and the response
            # topic.  Or what I chose to do and to put the argument in a
            # copy of the params.
            cp = params.copy()
            cp['publish_topic'] = response_topic
            cp['device_id'] = int(cp['device_id'])
            platform = self._platforms.get_platform(platform_uuid)
            _log.debug('PARAMS: {}'.format(cp))
            platform.call("publish_bacnet_props", **cp)

        gevent.spawn_later(2, start_sending_props)

    def _handle_bacnet_scan(self, session_user, params):
        platform_uuid = params.pop('platform_uuid')
        id = params.pop('message_id')
        _log.debug('Handling bacnet_scan platform: {}'.format(platform_uuid))

        if not self._platforms.is_registered(platform_uuid):
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "Couldn't connect to platform {}".format(
                                          platform_uuid
                                      ))

        scan_length = params.pop('scan_length', 5)

        try:
            scan_length = float(scan_length)
            params['scan_length'] = scan_length
            platform = self._platforms.get_platform(platform_uuid)
            iam_topic = "{}/iam".format(session_user['token'])
            ws_socket_topic = "/vc/ws/{}".format(iam_topic)
            self.vip.web.register_websocket(ws_socket_topic,
                                            self.open_authenticate_ws_endpoint,
                                            self._ws_closed, self._ws_received)

            def start_scan():
                # We want the datatype (iam) to be second in the response so
                # we need to reposition the iam and the session id to the topic
                # that is passed to the rpc function on vcp
                iam_session_topic = "iam/{}".format(session_user['token'])
                platform.call("start_bacnet_scan", iam_session_topic, **params)

                def close_socket():
                    _log.debug('Closing bacnet scan for {}'.format(
                        platform_uuid))
                    #self.vip.web.unregister_websocket(ws_socket_topic)

                gevent.spawn_later(scan_length, close_socket)
            # By starting the scan a second later we allow the websocket
            # client to subscribe to the newly available endpoint.
            gevent.spawn_later(2, start_scan)
        except ValueError:
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "Couldn't connect to platform {}".format(
                                          platform_uuid
                                      ))
        except KeyError:
            return jsonrpc.json_error(id, UNAUTHORIZED,
                                      "Invalid user session token")

    def _enable_setup_mode(self, session_user, params):
        id = params.pop('message_id')
        if 'admin' not in session_user['groups']:
            _log.debug('Returning json_error enable_setup_mode')
            return jsonrpc.json_error(
                id, UNAUTHORIZED,
                "Admin access is required to enable setup mode")
        auth_file = AuthFile()
        entries = auth_file.find_by_credentials(".*")
        if len(entries) > 0:
            return "SUCCESS"

        entry = AuthEntry(credentials="/.*/",
                          comments="Un-Authenticated connections allowed here",
                          user_id="unknown")
        auth_file.add(entry)
        return "SUCCESS"

    def _disable_setup_mode(self, session_user, params):
        id = params.pop('message_id')
        if 'admin' not in session_user['groups']:
            _log.debug('Returning json_error disable_setup_mode')
            return jsonrpc.json_error(
                id, UNAUTHORIZED,
                "Admin access is required to disable setup mode")
        auth_file = AuthFile()
        auth_file.remove_by_credentials("/.*/")
        return "SUCCESS"

    def _handle_management_endpoint(self, session_user, params):
        ws_topic = "/vc/ws/{}/management".format(session_user.get('token'))
        self.vip.web.register_websocket(ws_topic,
                                        self.open_authenticate_ws_endpoint,
                                        self._ws_closed, self._ws_received)
        return ws_topic

    def send_management_message(self, type, data={}):
        """
        Send a message to any socket that has connected to the management
        socket.

        The payload sent to the client is like the following::

            {
                "type": "UPDATE_DEVICE_STATUS",
                "data": "this is data that was passed"
            }

        :param type:
            A string defining a unique type for sending to the websockets.
        :param data:
            An object that str can be called on.

        :type type: str
        :type data: serializable
        """
        management_sockets = [s for s in self._websocket_endpoints
                              if s.endswith("management")]
        # Nothing to send if we don't have any management sockets open.
        if len(management_sockets) <= 0:
            return

        if data is None:
            data = {}

        payload = dict(
            type=type,
            data=str(data)
        )

        payload = jsonapi.dumps(payload)
        for s in management_sockets:
            self.vip.web.send(s, payload)

    def _route_request(self, session_user, id, method, params):
        """ Handle the methods volttron central can or pass off to platforms.

        :param session_user:
            The authenticated user's session info.
        :param id:
            JSON-RPC id field.
        :param method:
        :param params:
        :return:
        """
        _log.debug(
            'inside _route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        self.send_management_message(method)

        method_split = method.split('.')
        # The last part of the jsonrpc method is the actual method to be called.
        method_check = method_split[-1]

        # These functions will be sent to a platform.agent on either this
        # instance or another.  All of these functions have the same interface
        # and can be collected into a dictionary rather than an if tree.
        platform_methods = dict(
            # bacnet related
            start_bacnet_scan=self._handle_bacnet_scan,
            publish_bacnet_props=self._handle_bacnet_props,
            # config store related
            store_agent_config="store_agent_config",
            get_agent_config="get_agent_config",
            list_agent_configs="get_agent_config_list",
            # management related

            list_agents="get_agent_list",
            get_devices="get_devices",
            status_agents="status_agents"
        )

        # These methods are specifically to be handled by the platform not any
        # agents on the platform that is why we have the length requirement.
        #
        # The jsonrpc method looks like the following
        #
        #   platform.uuid.<dynamic entry>.method_on_vcp
        if method_check in platform_methods:

            platform_uuid = None
            if isinstance(params, dict):
                platform_uuid = params.pop('platform_uuid', None)

            if platform_uuid is None:
                if method_split[0] == 'platforms' and method_split[1] == 'uuid':
                    platform_uuid = method_split[2]

            if not platform_uuid:
                return err("Invalid platform_uuid '{}' specified as parameter"
                           .format(platform_uuid),
                           INVALID_PARAMS)

            if not self._platforms.is_registered(platform_uuid):
                return err("Unknown or unavailable platform {} specified as "
                           "parameter".format(platform_uuid),
                           UNAVAILABLE_PLATFORM)

            try:
                _log.debug('Calling {} on platform {}'.format(
                    method_check, platform_uuid
                ))
                class_method = platform_methods[method_check]
                platform = self._platforms.get_platform(platform_uuid)
                # Determine whether the method to call is on the current class
                # or on the platform object.
                if isinstance(class_method, basestring):
                    method_ref = getattr(platform, class_method)
                else:
                    method_ref = class_method
                    # Put the platform_uuid in the params so it can be used
                    # inside the method
                    params['platform_uuid'] = platform_uuid

            except AttributeError or KeyError:
                return jsonrpc.json_error(id, INTERNAL_ERROR,
                                          "Attempted calling function "
                                          "{} was unavailable".format(
                                              class_method
                                          ))

            except ValueError:
                return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                          "Couldn't connect to platform "
                                          "{}".format(platform_uuid))
            else:
                # pass the id through the message_id parameter.
                if not params:
                    params = dict(message_id=id)
                else:
                    params['message_id'] = id

                # Methods will all have the signature
                #   method(session, params)
                #
                return method_ref(session_user, params)

        vc_methods = dict(
            register_management_endpoint=self._handle_management_endpoint,
            list_platforms=self._platforms.get_platform_list,
            list_performance=self._platforms.get_performance_list,

            # Settings
            set_setting=self.set_setting,
            get_setting=self.get_setting,
            get_setting_keys=self.get_setting_keys,

            # Setup mode
            enable_setup_mode=self._enable_setup_mode,
            disable_setup_mode=self._disable_setup_mode
        )


        if method in vc_methods:
            if not params:
                params = dict(message_id=id)
            else:
                params['message_id'] = id
            response = vc_methods[method](session_user, params)
            _log.debug("Response is {}".format(response))
            return response #vc_methods[method](session_user, params)

        if method == 'register_instance':
            if isinstance(params, list):
                return self._register_instance(*params)
            else:
                return self._register_instance(**params)
        elif method == 'unregister_platform':
            return self.unregister_platform(params['instance_uuid'])

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

        # This isn't known as a proper method on vc or a platform.
        if len(method_split) < 3:
            return err('Unknown method {}'.format(method))
        if method_split[0] != 'platforms' or method_split[1] != 'uuid':
            return err('Invalid format for instance must start with '
                       'platforms.uuid')
        instance_uuid = method_split[2]
        _log.debug('Instance uuid is: {}'.format(instance_uuid))
        if not self._platforms.is_registered(instance_uuid):
            return err('Unknown platform {}'.format(instance_uuid))
        platform_method = '.'.join(method_split[3:])
        _log.debug("Platform method is: {}".format(platform_method))
        platform = self._platforms.get_platform(instance_uuid)
        if not platform:
            return jsonrpc.json_error(id,
                                      UNAVAILABLE_PLATFORM,
                                      "cannot connect to platform."
                                      )

        if platform_method.startswith('install'):
            if 'admin' not in session_user['groups']:
                return jsonrpc.json_error(
                    id, UNAUTHORIZED,
                    "Admin access is required to install agents")

        return platform.route_to_agent_method(id, platform_method, params)

    def _validate_config_params(self, config):
        """
        Validate the configuration parameters of the default/updated parameters.

        This method will return a list of "problems" with the configuration.
        If there are no problems then an empty list is returned.

        :param config: Configuration parameters for the volttron central agent.
        :type config: dict
        :return: The problems if any, [] if no problems
        :rtype: list
        """
        problems = []
        webroot = config.get('webroot')
        if not webroot:
            problems.append('Invalid webroot in configuration.')
        elif not os.path.exists(webroot):
            problems.append(
                'Webroot {} does not exist on machine'.format(webroot))

        users = config.get('users')
        if not users:
            problems.append('A users node must be specified!')
        else:
            has_admin = False

            try:
                for user, item in users.items():
                    if 'password' not in item.keys():
                        problems.append('user {} must have a password!'.format(
                            user))
                    elif not item['password']:
                        problems.append('password for {} is blank!'.format(
                            user
                        ))

                    if 'groups' not in item.keys():
                        problems.append('missing groups key for user {}'.format(
                            user
                        ))
                    elif not isinstance(item['groups'], list):
                        problems.append('groups must be a list of strings.')
                    elif not item['groups']:
                        problems.append(
                            'user {} must belong to at least one group.'.format(
                                user))

                    # See if there is an adminstator present.
                    if not has_admin and isinstance(item['groups'], list):
                        has_admin = 'admin' in item['groups']
            except AttributeError:
                problems.append('invalid user node.')

            if not has_admin:
                problems.append("One user must be in the admin group.")

        return problems


def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    utils.vip_main(VolttronCentralAgent, identity=VOLTTRON_CENTRAL,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
