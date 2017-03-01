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
import platform
import shutil
import sys
import tempfile
import urlparse

import gevent
import gevent.event
import psutil
from . vcconnection import VCConnection

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
from volttron.platform.vip.agent.utils import build_connection, build_agent
from volttron.platform.web import DiscoveryInfo, DiscoveryError
from . bacnet_proxy_reader import BACnetReader

__version__ = '4.0'

utils.setup_logging()
_log = logging.getLogger(__name__)


class NotManagedError(StandardError):
    """ Raised if vcp cannot connect to the vc trying to manage it.

    Some examples of this could be if the serverkey is not valid, if the
    tcp address is invalid, if the http address is invalid.

    Other examples could be permissions issues from auth.
    """
    pass


RegistrationStates = Enum('AgentStates',
                               'NotRegistered Unregistered Registered '
                               'Registering')


class VolttronCentralPlatform(Agent):
    __name__ = 'VolttronCentralPlatform'

    def __init__(self, config_path, **kwargs):
        super(VolttronCentralPlatform, self).__init__(**kwargs)

        config = utils.load_config(config_path)

        vc_reconnect_interval = config.get(
            'volttron-central-reconnect-interval', 5)
        vc_address = config.get('volttron-central-address')
        vc_serverkey = config.get('volttron-central-serverkey')
        instance_name = config.get('instance-name')
        stats_publish_interval = config.get('stats-publish-interval', 30)
        topic_replace_map = config.get('topic-replace-map', {})

        # This is scheduled after first call to the reconnect function
        self._scheduled_connection_event = None
        self._publish_bacnet_iam = False

        # default_configuration is what is specified if there isn't a "config"
        # sent in through the volttron-ctl config store command.
        self.default_config = dict(
            volttron_central_reconnect_interval=vc_reconnect_interval,
            volttron_central_address=vc_address,
            volttron_central_serverkey=vc_serverkey,
            instance_name=instance_name,
            stats_publish_interval=stats_publish_interval,
            topic_replace_map=topic_replace_map,
            local_serverkey=None,
            local_external_addresses=None
        )

        # current_config can be used an manipulated at runtime, while
        # default_config is passed to the config_store as the defaults
        self.current_config = None

        # Start using config store.
        self.vip.config.set_default("default_config", self.default_config)
        self.vip.config.subscribe(self._configure_main,
                                  actions=["NEW", "UPDATE", "DELETE"],
                                  pattern="default_config")
        # self.vip.config.subscribe(self._configure_main,
        #                           actions=["NEW", "UPDATE", "DELETE"],
        #                           pattern="config")
        # self.vip.config.subscribe(self.configure_platform,
        #                           actions=["NEW", "UPDATE", "DELETE"],
        #                           pattern="platform")

        # Allows the periodic check for registration.  It is set to true after
        # a main configuration is changed.
        self.enable_registration = False

        # A connection to the volttron central agent.
        self.vc_connection = None

        # This publickey is set during the manage rpc call.
        self.manager_publickey = None

        # The state of registration of vcp with the vc instance.
        self.registration_state = RegistrationStates.NotRegistered

        self._stats_publisher = None

        self._still_connected_event = None
        self._establish_connection_event = None

    def _configure_main(self, config_name, action, contents):
        """
        This is the main configuration point for the agent.

        :param config_name:
        :param action:
        :param contents:
        :return:
        """
        self.enable_registration = False
        # If we are updating the main configuration we need to reset the
        # connection to vc if present and initialize the state for reconnection.
        if self.vc_connection is not None:
            self.vc_connection.kill()
            self.vc_connection = None
        self.registration_state = RegistrationStates.NotRegistered

        if config_name == 'default_config':
            # we know this came from the config file that was specified
            # with the agent
            config = self.default_config.copy()

        elif config_name == 'config':
            config = self.default_config.copy()
            config.update(contents)

        else:
            _log.error('Invalid configuration name!')
            sys.exit(INVALID_CONFIGURATION_CODE)

        _log.debug('Querying router for addresses and serverkey.')
        q = Query(self.core)

        external_addresses = q.query('addresses').get(timeout=5)
        local_serverkey = q.query('serverkey').get(timeout=5)
        vc_address = q.query('volttron-central-address').get(timeout=5)
        vc_serverkey = q.query('volttron-central-serverkey').get(timeout=5)
        instance_name = q.query('instance-name').get(timeout=5)
        bind_web_address = q.query('bind-web-address').get(timeout=5)
        address_hash = hashlib.md5(external_addresses[0]).hexdigest()

        updates = dict(
            bind_web_address=bind_web_address,
            volttron_central_address=vc_address,
            volttron_central_serverkey=vc_serverkey,
            instance_name=instance_name,
            address_hash=address_hash,
            local_serverkey=local_serverkey,
            local_external_addresses=external_addresses
        )

        if config_name == 'default_config':
            for k, v in updates.items():
                if v:
                    config[k] = v
        elif config_name == 'config':
            for k, v in updates.items():
                # Only update from the platform's configuration file if the
                # value doesn't exist in the config or if it is empty.
                if k not in config:
                    config[k] = v
                elif not config[k]:
                    config[k] = v

        self.current_config = config.copy()

        vc_address = self.current_config['volttron_central_address']
        vc_serverkey = self.current_config['volttron_central_serverkey']

        if vc_address:
            parsed = urlparse.urlparse(vc_address)

            if parsed.scheme in ('http', 'https'):
                _log.debug('vc_address is {}'.format(vc_address))
                info = None
                while info is None:
                    try:
                        info = DiscoveryInfo.request_discovery_info(vc_address)
                    except DiscoveryError as e:
                        _log.error(
                            "Unable to retrieve discovery info from volttron central.")
                        gevent.sleep(10)

                self.current_config['vc_connect_address'] = info.vip_address
                self.current_config['vc_connect_serverkey'] = info.serverkey
            else:
                self.current_config['vc_connect_address'] = vc_address
                self.current_config['vc_connect_serverkey'] = vc_serverkey
        else:
            if bind_web_address:
                info = DiscoveryInfo.request_discovery_info(bind_web_address)
                # This will allow us to register with the current instance if
                # there is an http server running here.
                self.current_config['vc_connect_address'] = info.vip_address
                self.current_config['vc_connect_serverkey'] = info.serverkey

        # Address hash that uniquely defines this instance in the network.
        # Note: if there isn't a true tcp address then external_address[0] is
        # going to be the ipc address
        address_hash = hashlib.md5(external_addresses[0]).hexdigest()
        _log.debug('External hash is set using external_addresses[0] {}'.format(external_addresses[0]))
        self.current_config['address_hash'] = address_hash
        self.current_config['instance_id'] = 'vcp-{}'.format(address_hash)
        self.current_config['host'] = platform.uname()[1]

        # Connect to volttron central instance.
        self._establish_connection_to_vc()
        # self.enable_registration = True
        # self._periodic_attempt_registration()
        # self._start_stats_publisher()

    @RPC.export
    def get_external_vip_addresses(self):
        return self.current_config['local_external_addresses']

    @RPC.export
    def get_instance_name(self):
        return self.current_config['instance_name']

    @RPC.export
    def get_public_keys(self):
        """
        RPC method to retrieve all of the public keys fo the installed agents.

        :return: A mapping of identity to publickey.
        :rtype: dict
        """
        return self.control_connection.call('get_agents_publickeys')

    def call(self, platform_method, *args, **kwargs):
        return self.vip.rpc.call(platform_method, *args, **kwargs)

    def _address_type(self, address):
        """
        Parses the passed address and return it's scheme if it is one of the
        correct values otherwise throw a ValueError

        :param address: The address to be checked.
        :return: The scheme of the address
        """
        parsed_type = None
        parsed = urlparse.urlparse(address)
        if parsed.scheme not in ('http', 'https', 'ipc', 'tcp'):
            raise ValueError('Invalid volttron central address.')

        return parsed.scheme

    def _establish_connection_to_vc(self):

        if not self.current_config.get("vc_connect_address"):
            raise ValueError("vc_connect_address was not resolved properly.")

        if not self.current_config.get("vc_connect_serverkey"):
            raise ValueError("vc_connect_serverkey was not resolved properly.")

        if self._establish_connection_event is not None:
            self._establish_connection_event.cancel()

        if self.vc_connection is None:
            _log.info("Attempting to reconnect with volttron central.")
            instance_id = self.current_config['instance_id']
            # Note using the connect_address and connect_serverkey because they
            # are now resolved to the correct values based upon the different
            # ways of configuring the agent.
            vc_address = self.current_config['vc_connect_address']
            vc_serverkey =self.current_config['vc_connect_serverkey']

            try:

                self.volttron_central_connection = build_agent(
                    identity=instance_id,
                    address=vc_address,
                    serverkey=vc_serverkey,
                    publickey=self.core.publickey,
                    secretkey=self.core.secretkey,
                    agent_class=VCConnection
                )

            except gevent.Timeout:
                _log.debug("No connection to volttron central instance.")
                self.volttron_central_connection = None

                next_update_time = self._next_update_time()

                self._establish_connection_event = self.core.schedule(
                    next_update_time, self._establish_connection_to_vc)
            else:
                self.volttron_central_connection.set_main_agent(self)
                self._still_connected()

    def _still_connected(self):

        if self._still_connected_event is not None:
            self._still_connected_event.cancel()

        try:
            with gevent.Timeout(seconds=5):
                hello = self.volttron_central_connection.vip.ping(
                    b'', self.current_config['instance_id']).get()
        except gevent.Timeout:
            self.volttron_central_connection = None
            self._establish_connection_to_vc()
        else:
            next_update_time = self._next_update_time(seconds=10)

            self._still_connected_event = self.core.schedule(
                next_update_time, self._still_connected)


    def _update_vcp_config(self, external_addresses, local_serverkey,
                           vc_address, vc_serverkey, instance_name):
        assert external_addresses

        # This is how the platform will be referred to on vc.
        md5 = hashlib.md5(external_addresses[0])
        local_instance_id = md5.hexdigest()

        # If we get an http address then we need to look up the serverkey and
        # vip-address from volttorn central
        if self._address_type(vc_address) in ('http', 'https'):
            info = DiscoveryInfo.request_discovery_info(vc_address)
            assert info
            assert info.vip_address
            assert info.serverkey

            config = dict(vc_serverkey=info.serverkey,
                          vc_vip_address=info.vip_address,
                          vc_agent_publickey=None,
                          local_instance_name=instance_name,
                          local_instance_id=local_instance_id,
                          local_external_address=external_addresses[0],
                          local_serverkey=local_serverkey
                          )
        else:
            config = dict(vc_serverkey=vc_serverkey,
                          vc_vip_address=vc_address,
                          vc_agent_publickey=None,
                          local_instance_name=instance_name,
                          local_instance_id=local_instance_id,
                          local_external_address=external_addresses[0],
                          local_serverkey=local_serverkey
                          )
        # Store the config parameters in the config store for later use.
        self.vip.config.set("vc-conn-config", config)

    def _periodic_attempt_registration(self):

        _log.debug("periodic attempt to register.")
        if self._scheduled_connection_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._scheduled_connection_event.cancel()

        if not self.enable_registration:
            _log.debug('Registration of vcp is not enabled.')
            next_update_time = self._next_update_time()

            self._scheduled_connection_event = self.core.schedule(
                next_update_time, self._periodic_attempt_registration)
            return

        try:
            vc = self.get_vc_connection()
            if vc is None:
                _log.debug("vc not connected")
                return
            local_address = self.current_config.get(
                'local_external_addresses')[0]
            if not vc.call("is_registered", address=local_address):
                _log.debug("platform agent is not registered.")
                self.registration_state = RegistrationStates.NotRegistered

            if self.registration_state == RegistrationStates.NotRegistered:
                vc_agent_publickey = vc.call("get_publickey")
                _log.debug('vc agent publickey is {}'.format(
                    vc_agent_publickey))
                assert vc_agent_publickey and len(vc_agent_publickey) == 43
                authfile = AuthFile()
                # find_by_credentials returns a list.
                entries = authfile.find_by_credentials(vc_agent_publickey)
                if entries is not None and len(entries) > 0:
                    entry = entries[0]
                    if "manage" not in entry.capabilities:
                        _log.debug("Updating vc capability.")
                        entry.add_capabilities("manager")
                        authfile.add(entry, overwrite=True)
                else:
                    _log.debug('Adding vc publickey to auth')
                    entry = AuthEntry(credentials=vc_agent_publickey,
                                      capabilities=['manager'],
                                      comments="Added by VCP",
                                      user_id="vc")
                    authfile = AuthFile()
                    authfile.add(entry)

                local_address = self.current_config.get(
                    'local_external_addresses')[0]
                local_name = self.current_config.get('local_instance_name',
                                                     local_address)
                local_serverkey = self.current_config.get('local_serverkey')
                vc_address = self.current_config.get('volttron_central_address')

                _log.debug("Registering with vc from vcp.")
                _log.debug("Instance is named: {}".format(local_name))
                _log.debug("Local Address is: {}".format(local_address))
                _log.debug("VC Address is: {}".format(vc_address))

                vc.call('register_instance', address=local_address,
                        display_name=local_name, vcpserverkey=local_serverkey,
                        vcpagentkey=self.core.publickey)

            else:
                _log.debug("Current platform registration state: {}".format(
                    self.registration_state))
        except Unreachable as e:
            _log.error("Couldn't connect to volttron.central. {}".format(
                self.current_config.get('volttron_central_address')
            ))
        except ValueError as e:
            _log.error(e.message)
        except Exception as e:
            _log.error("Error: {}".format(e.args))
        except gevent.Timeout as e:
            _log.error("timout occured connecting to remote platform.")
        finally:
            _log.debug('Scheduling next periodic call')
            next_update_time = self._next_update_time()

            self._scheduled_connection_event = self.core.schedule(
                next_update_time, self._periodic_attempt_registration)

    def _next_update_time(self, seconds=10):
        """
        Based upon the current time add 'seconds' to it and return that value.
        :param seconds:
        :return: time of next update
        """
        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(
            seconds=seconds)
        return next_update_time

    def get_vc_connection(self):
        """ Attempt to connect to volttron central management console.

        The attempts will be done in the following order.

        1. if peer is vc register with it.
        2. volttron-central-tcp and serverkey
        2. volttron-central-http (looks up tcp and serverkey)
        3. volttron-central-ipc

        :param sender:
        :param kwargs:
        :return:
        """

        if self.vc_connection:
            # if connected return the connection.
            if self.vc_connection.is_connected(5) and \
                    self.vc_connection.is_peer_connected(5):
                _log.debug('Returning current connection')
                return self.vc_connection

            _log.debug("Resetting connection as the peer wasn't responding.")
            # reset the connection so we can try it again below.
            self.vc_connection.kill()
            self.vc_connection = None

        def sync_status_to_vc(status, context):
            """
            Sync the status of the current vcp object with that of the one that
            is connected to the vc instance.

            :param status:
            :param context:
            """
            conn = self.vc_connection
            conn.vip.health.set_status(status, context)

        self.vip.health.add_status_callback(sync_status_to_vc)

        def enable_connection_heartbeat():
            """
            Start publishing the heartbeat with the status messages.
            """
            conn = self.vc_connection
            status = self.vip.health.get_status()
            conn.vip.health.set_status(
                status['status'], status['context']
            )
            conn.vip.heartbeat.start()

        # We are going to use an identity of platform.address_hash for
        # connections to vc.  This should allow us unique connection as well
        # as allowing the vc to filter on the heartbeat status of the pubsub
        # message to determine context.
        vcp_identity_on_vc = 'platform.'

        # First check to see if there is a peer with a volttron.central
        # identity, if there is use it as the manager of the platform.
        peers = self.vip.peerlist().get(timeout=5)
        if VOLTTRON_CENTRAL in peers:
            _log.debug('VC is a local peer.')
            # Address hash that uniquely defines this platform in the network.
            address_hash = hashlib.md5(self.core.address).hexdigest()
            self.current_config['address_hash'] = address_hash
            vcp_identity_on_vc += address_hash
            vc_serverkey = self.current_config['volttron_connect_serverkey']
            self.vc_connection = build_agent(
                self.core.address,
                #peer=VOLTTRON_CENTRAL,
                publickey=self.core.publickey,
                secretkey=self.core.secretkey,
                serverkey=vc_serverkey,
                identity=vcp_identity_on_vc,
                agent_class=VCConnection
            )
            self.vc_connection.set_main_agent(self)
            if self.vc_connection.is_connected() and \
                    self.vc_connection.is_peer_connected():
                _log.debug("Connection has been established to local peer.")
            else:
                _log.error('Unable to connect to local peer!')
            if self.vc_connection.is_connected():
                enable_connection_heartbeat()

            return self.vc_connection

        if self.current_config.get('vc_connect_address') is None or \
                self.current_config.get('vc_connect_serverkey') is None:
            _log.warn('volttron_central_address is None in config store '
                      'and volttron.central is not a peer.')
            _log.warn('Recommend adding volttron.central address or adding a '
                      '"config" file to the config store.')
            return None

        c = self.current_config
        address_hash = c.get('address_hash')
        vcp_identity_on_vc += address_hash
        self.vc_connection = build_agent(
            identity=vcp_identity_on_vc,
            # peer=VOLTTRON_CENTRAL,
            address=c.get('vc_connect_address'),
            serverkey=c.get('vc_connect_serverkey'),
            publickey=self.core.publickey,
            secretkey=self.core.secretkey,
            agent_class=VCConnection
        )

        self.vc_connection.set_main_agent(self)
        if not self.vc_connection.is_peer_connected():
            _log.error('Peer: {} is not connected to the external platform'
                       .format(self.vc_connection.peer))
            self.vc_connection.kill()
            self.vc_connection = None
            self.registration_state = RegistrationStates.NotRegistered
            return None

        if self.vc_connection.is_connected():
            enable_connection_heartbeat()

        return self.vc_connection

    def _start_stats_publisher(self):

        if self._stats_publisher:
            self._stats_publisher.kill()

        _log.debug("Starting stats publisher.")
        stats_publish_interval = self.current_config.get(
            'stats-publish-interval', 30)
        # The stats publisher publishes both to the local bus and the vc
        # bus the platform specific topics.
        self._stats_publisher = self.core.periodic(
            stats_publish_interval, self._publish_stats)

    @RPC.export
    def get_health(self):
        _log.debug("Getting health: {}".format(self.vip.health.get_status()))
        return self.vip.health.get_status()

    def get_instance_uuid(self):
        _log.debug('ADDRESS HASH for {} is {}'.format(
            self.current_config.get('local_external_addresses')[0],
            self.current_config.get("address_hash")))
        return self.current_config.get('address_hash')

    @RPC.export
    def publish_bacnet_props(self, proxy_identity, publish_topic, address,
                             device_id, filter=[]):
        _log.debug('Publishing bacnet props to topic: {}'.format(publish_topic))

        def bacnet_response(context, results):
            _log.debug("Handling bacnet responses: RESULTS: {}".format(results))
            message = dict(results=results)
            if context is not None:
                message.update(context)

            self._pub_to_vc(publish_topic, message=message)

        bn = BACnetReader(self.vip.rpc, proxy_identity, bacnet_response)

        gevent.spawn(bn.read_device_properties, address, device_id, filter)
        gevent.sleep(0.1)

        return "PUBLISHING"

    def start_bacnet_scan(self, iam_topic, proxy_identity, low_device_id=None,
                          high_device_id=None, target_address=None,
                          scan_length=5, instance_address=None,
                          instance_serverkey=None):
        """This function is a wrapper around the bacnet proxy scan.
        """
        agent_to_use = self
        if instance_address is not None:
            agent_to_use = build_agent(address=instance_address,
                                       identity="proxy_bacnetplatform",
                                       publickey=self.core.publickey,
                                       secretkey=self.core.secretkey,
                                       serverkey=instance_serverkey)

        if proxy_identity not in agent_to_use.vip.peerlist().get(timeout=5):
            raise Unreachable("Can't reach agent identity {}".format(
                proxy_identity))
        _log.info('Starting bacnet_scan with who_is request to {}'.format(
            proxy_identity))

        def handle_iam(peer, sender, bus, topic, headers, message):
            proxy_identity = sender
            address = message['address']
            device_id = message['device_id']
            bn = BACnetReader(agent_to_use.vip.rpc, proxy_identity)
            message['device_name'] = bn.read_device_name(address, device_id)
            message['device_description'] = bn.read_device_description(
                address,
                device_id)

            self._pub_to_vc(iam_topic, message=message)

        def stop_iam():
            _log.debug('Done publishing i am responses.')
            stop_timestamp = get_utc_seconds_from_epoch()
            self._pub_to_vc(iam_topic, message=dict(
                status="FINISHED IAM",
                timestamp=stop_timestamp
            ))
            agent_to_use.vip.pubsub.unsubscribe('pubsub', topics.BACNET_I_AM,
                                        handle_iam)

        agent_to_use.vip.pubsub.subscribe('pubsub', topics.BACNET_I_AM, handle_iam)

        timestamp = get_utc_seconds_from_epoch()

        self._pub_to_vc(iam_topic, message=dict(status="STARTED IAM",
                                                timestamp=timestamp))

        agent_to_use.vip.rpc.call(proxy_identity, "who_is",
                                  low_device_id=low_device_id,
                                  high_device_id=high_device_id,
                                  target_address=target_address).get(timeout=5.0)

        gevent.spawn_later(float(scan_length), stop_iam)

    def _pub_to_vc(self, topic_leaf, headers=None, message=None):
        if self.volttron_central_connection is None:
            _log.error('Platform must have connection to vc to publish {}'
                       .format(topic_leaf))
            return

        if topic_leaf[0] == '/':
            topic_leaf = topic_leaf[1:]

        topic = "platforms/{}/{}".format(self.get_instance_uuid(),
                                         topic_leaf)
        _log.debug('Publishing to vc topic: {}'.format(topic))
        _log.debug('Publishing to vc headers: {}'.format(headers))
        _log.debug('Publishing to vc message: {}'.format(message))
        # Note because vc is a vcconnection object we are explicitly
        # saying to publish to the vc platform.
        self.volttron_central_connection.publish_to_vc(topic=topic,
                                                       headers=headers,
                                                       message=message)

    @RPC.export
    def list_agents(self):
        """
        RPC method to list the agents installed on the platform.

        :return: A list of agents.
        """

        agents = self.vip.rpc.call(CONTROL, "list_agents").get(timeout=5)
        versions = self.vip.rpc.call(CONTROL, "agent_versions").get(timeout=5)
        status_running = self.status_agents()
        uuid_to_status = {}
        # proc_info has a list of [startproc, endprox]
        for a in agents:
            pinfo = None
            is_running = False
            for uuid, name, proc_info in status_running:
                if a['uuid'] == uuid:
                    is_running = proc_info[0] > 0 and proc_info[1] == None
                    pinfo = proc_info
                    break

            uuid_to_status[a['uuid']] = {
                'is_running': is_running,
                'version': versions[a['uuid']][1],
                'process_id': None,
                'error_code': None,
                'permissions': {
                    'can_stop': is_running,
                    'can_start': not is_running,
                    'can_restart': True,
                    'can_remove': True
                }
            }

            if pinfo:
                uuid_to_status[a['uuid']]['process_id'] = proc_info[0]
                uuid_to_status[a['uuid']]['error_code'] = proc_info[1]

            if 'volttroncentral' in a['name'] or \
                            'vcplatform' in a['name']:
                uuid_to_status[a['uuid']]['permissions']['can_stop'] = False
                uuid_to_status[a['uuid']]['permissions']['can_remove'] = False

            # The default agent is stopped health looks like this.
            uuid_to_status[a['uuid']]['health'] = {
                'status': 'UNKNOWN',
                'context': None,
                'last_updated': None
            }

            if is_running:
                identity = self.vip.rpc.call(CONTROL, 'agent_vip_identity',
                                             a['uuid']).get(timeout=30)
                try:
                    status = self.vip.rpc.call(identity,
                                               'health.get_status').get(
                        timeout=5)
                    uuid_to_status[a['uuid']]['health'] = status
                except gevent.Timeout:
                    _log.error("Couldn't get health from {} uuid: {}".format(
                        identity, a['uuid']
                    ))
                except Unreachable:
                    _log.error(
                        "Couldn't reach agent identity {} uuid: {}".format(
                            identity, a['uuid']
                        ))
        for a in agents:
            if a['uuid'] in uuid_to_status.keys():
                _log.debug('UPDATING STATUS OF: {}'.format(a['uuid']))
                a.update(uuid_to_status[a['uuid']])
        return agents

    def store_agent_config(self, agent_identity, config_name, raw_contents,
                            config_type='raw'):
        _log.debug("Storeing configuration file: {}".format(config_name))
        self.vip.rpc.call(CONFIGURATION_STORE, "manage_store", agent_identity,
                          config_name, raw_contents, config_type)

    def list_agent_configs(self, agent_identity):
        return self.vip.rpc.call(CONFIGURATION_STORE, "manage_list_configs",
                                 agent_identity).get(timeout=5)

    def get_agent_config(self, agent_identity, config_name, raw=True):
        data = self.vip.rpc.call(CONFIGURATION_STORE, "manage_get",
                                 agent_identity, config_name, raw).get(timeout=5)
        return data or ""

    def start_agent(self, agent_uuid):
        self.vip.rpc.call(CONTROL, "start_agent", agent_uuid).get(timeout=5)


    def stop_agent(self, agent_uuid):
        _log.debug("Stopping agent: {}".format(agent_uuid))
        proc_result = self.vip.rpc.call(CONTROL, "stop_agent",
                                        agent_uuid).get(timeout=5)
        return proc_result

    def restart_agent(self, agent_uuid):
        self.vip.rpc.call(CONTROL, "restart_agent", agent_uuid)
        gevent.sleep(0.2)
        return self.agent_status(agent_uuid).get(timeout=5)

    def agent_status(self, agent_uuid):
        return self.vip.rpc.call(CONTROL, "agent_status", agent_uuid).get(timeout=5)

    def status_agents(self):
        _log.debug('STATUS AGENTS')
        return self.vip.rpc.call(CONTROL, 'status_agents').get(timeout=5)

    @PubSub.subscribe('pubsub', 'devices')
    def _on_record_message(self, peer, sender, bus, topic, headers, message):
        pass

    @PubSub.subscribe('pubsub', 'devices')
    def _on_analysis_message(self, peer, sender, bus, topic, headers, message):
        pass

    def get_devices(self):
        """
        RPC method for retrieving device data from the platform.

        :return:
        """

        _log.debug('Getting devices')
        config_list = self.vip.rpc.call(CONFIGURATION_STORE,
                                        'manage_list_configs',
                                        'platform.driver').get(timeout=5)

        _log.debug('Config list is: {}'.format(config_list))
        devices = defaultdict(dict)

        for cfg_name in config_list:
            # Skip as we are only looking to do devices in this call.
            if not cfg_name.startswith('devices/'):
                break

            _log.debug('Reading config store for device {}'.format(cfg_name))

            device_config = self.vip.rpc.call('config.store', 'manage_get',
                                              'platform.driver',
                                              cfg_name,
                                              raw=False).get(timeout=5)
            _log.debug('DEVICE CONFIG IS: {}'.format(device_config))

            reg_cfg_name = device_config.get(
                'registry_config')[len('config://'):]
            _log.debug('Reading registry_config file {}'.format(
                reg_cfg_name
            ))
            registry_config = self.vip.rpc.call('config.store',
                                                'manage_get', 'platform.driver',
                                                reg_cfg_name,
                                                raw=False).get(timeout=5)
            _log.debug('Registry Config: {}'.format(registry_config))

            points = []
            for pnt in registry_config:
                points.append(pnt['Volttron Point Name'])

            devices[cfg_name]['points'] = points

        _log.debug('get_devices returning {}'.format(devices))

        return devices

    def route_request(self, id, method, params):
        _log.debug(
            'platform agent routing request: {}, {}'.format(id, method))

        _log.debug(params)

        method_map = {
            'list_agents': self.list_agents,
            'get_devices': self.get_devices,
        }

        # First handle the elements that are going to this platform
        if method in method_map:
            result = method_map[method]()
        elif method == 'set_setting':
            result = self.set_setting(**params)
        elif method == 'get_setting':
            result = self.get_setting(**params)
        elif method == 'get_devices':
            result = self.get_devices()
        elif method == 'status_agents':
            _log.debug('Doing status agents')
            result = {'result': [{'name': a[1], 'uuid': a[0],
                                  'process_id': a[2][0],
                                  'return_code': a[2][1]}
                                 for a in
                                 self.vip.rpc.call(CONTROL, method).get(
                                     timeout=5)]}

        elif method in ('agent_status', 'start_agent', 'stop_agent',
                        'remove_agent', 'restart_agent'):
            _log.debug('We are trying to exectute method {}'.format(method))
            if isinstance(params, list) and len(params) != 1 or \
                            isinstance(params,
                                       dict) and 'uuid' not in params.keys():
                result = jsonrpc.json_error(ident=id, code=INVALID_PARAMS)
            else:
                if isinstance(params, list):
                    uuid = params[0]
                elif isinstance(params, str):
                    uuid = params
                else:
                    uuid = params['uuid']
                _log.debug('calling control with method: {} uuid: {}'.format(
                    method, uuid
                ))
                status = self.vip.rpc.call(CONTROL, method, uuid).get(timeout=5)
                if method == 'stop_agent' or status is None:
                    # Note we recurse here to get the agent status.
                    result = self.route_request(id, 'agent_status', uuid)
                else:
                    result = {'process_id': status[0],
                              'return_code': status[1]}
        elif method in ('install',):
            _log.debug("Attempting install!")
            if 'files' not in params:
                result = jsonrpc.json_error(
                    ident=id, code=INVALID_PARAMS,
                    message="Invalid parameter missing 'files'")
            else:
                # TODD: This should be only a single file at a time for installs
                fileargs = params.get('files')[0]
                result = self._install_agent(fileargs)

        else:

            fields = method.split('.')

            if fields[0] == 'historian':
                if 'platform.historian' in self.vip.peerlist().get(timeout=30):
                    agent_method = fields[1]
                    result = self.vip.rpc.call('platform.historian',
                                               agent_method,
                                               **params).get(timeout=45)
                else:
                    result = jsonrpc.json_error(
                        id, INVALID_PARAMS, 'historian unavailable')
            else:
                agent_uuid = fields[2]
                agent_method = '.'.join(fields[3:])
                _log.debug("Calling method {} on agent {}"
                           .format(agent_method, agent_uuid))
                _log.debug("Params is: {}".format(params))
                if agent_method in ('start_bacnet_scan', 'publish_bacnet_props'):
                    identity = params.pop("proxy_identity")
                    if agent_method == 'start_bacnet_scan':
                        result = self.start_bacnet_scan(identity, **params)
                    elif agent_method == 'publish_bacnet_props':
                        result = self.publish_bacnet_props(identity, **params)
                else:
                    # find the identity of the agent so we can call it by name.
                    identity = self.vip.rpc.call(CONTROL,
                        'agent_vip_identity', agent_uuid).get(timeout=5)
                    if params:
                        if isinstance(params, list):
                            result = self.vip.rpc.call(identity, agent_method, *params).get(timeout=30)
                        else:
                            result = self.vip.rpc.call(identity, agent_method, **params).get(timeout=30)
                    else:
                        result = self.vip.rpc.call(identity, agent_method).get(timeout=30)
                # find the identity of the agent so we can call it by name.
                identity = self.vip.rpc.call(CONTROL, 'agent_vip_identity',
                                             agent_uuid).get(timeout=5)
                if params:
                    if isinstance(params, list):
                        result = self.vip.rpc.call(identity, agent_method,
                                                   *params).get(timeout=30)
                    else:
                        result = self.vip.rpc.call(identity, agent_method,
                                                   **params).get(timeout=30)
                else:
                    result = self.vip.rpc.call(identity, agent_method).get(
                        timeout=30)

        if isinstance(result, dict):
            if 'result' in result:
                return result['result']
            elif 'code' in result:
                return result['code']
        elif result is None:
            return
        return result

    def _install_agent(self, fileargs):
        tmpdir = tempfile.mkdtemp()

        try:
            _log.debug('Installing agent FILEARGS: {}'.format(fileargs))
            vip_identity = fileargs.get('vip_identity', None)
            if 'local' in fileargs.keys():
                path = fileargs['file_name']
            else:
                path = os.path.join(tmpdir, fileargs['file_name'])

                base64_sep = 'base64,'
                if base64_sep not in fileargs['file']:
                    raise Exception('File must be base64 encoded.')

                # The start of the string representing the file is right
                # after base64,
                with open(path, 'wb') as fout:
                    fout.write(
                        base64.decodestring(
                            fileargs['file'].split(base64_sep)[1]))

            uuid = self.vip.rpc.call(CONTROL,  'install_agent_local',
                                     path, vip_identity=vip_identity
                                     ).get(timeout=30)
            result = dict(uuid=uuid)
        except Exception as e:
            err_str = "EXCEPTION: " + str(e)
            result = dict(error=dict(code=INTERNAL_ERROR,
                                     message=err_str))
        shutil.rmtree(tmpdir, ignore_errors=True)
        _log.debug('Results from install_agent are: {}'.format(result))
        return result

    def _publish_stats(self):
        """
        Publish the platform statistics to the bus.
        """

        topic = LOGGER(subtopic="platform/status/cpu")

        points = {}

        for k, v in psutil.cpu_times_percent().__dict__.items():
            points['times_percent/' + k] = {'Readings': v,
                                            'Units': 'double'}

        points['percent'] = {'Readings': psutil.cpu_percent(),
                             'Units': 'double'}
        try:
            self.vip.pubsub.publish('pubsub', topic.format(), message=points)

        except Exception as e:
            _log.warn("Failed to publish to topic {}".format(topic.format()))

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        if self.vc_connection is not None:
            _log.debug("Shutting down agent.")
            self.vc_connection.publish("platform/{}/stopping".format(
                self.get_instance_uuid()))
            gevent.sleep(1)
            try:
                self.vc_connection.kill()
            except:
                _log.error("killing vc_connection connection")
            finally:
                self.vc_connection = None

def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    # utils.vip_main(platform_agent)
    utils.vip_main(VolttronCentralPlatform, identity=VOLTTRON_CENTRAL_PLATFORM,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
