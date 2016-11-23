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
import re
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

__version__ = '3.6.0'

utils.setup_logging()
_log = logging.getLogger(__name__)

# After setup logging
from . bacnet_proxy_reader import BACnetReader
_log.debug('LOGGING SETUP?')


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
        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE", "DELETE"],
                                  pattern="default_config")
        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE", "DELETE"],
                                  pattern="config")
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

    def configure_main(self, config_name, action, contents):
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
        instance_id = hashlib.md5(external_addresses[0]).hexdigest()

        updates = dict(
            volttron_central_address=vc_address,
            volttron_central_serverkey=vc_serverkey,
            instance_name=instance_name,
            instance_id=instance_id,
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

        # Address hash that uniquely defines this platform in the network.
        address_hash = hashlib.md5(external_addresses[0]).hexdigest()
        self.current_config['address_hash'] = address_hash

        self.enable_registration = True
        self._periodic_attempt_registration()

    @RPC.export
    def get_public_keys(self):
        """
        RPC method to retrieve all of the public keys fo the installed agents.

        :return: A mapping of identity to publickey.
        :rtype: dict
        """
        return self.control_connection.call('get_agents_publickeys')

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

    def _reconnect_to_vc(self):
        # with self.vcl_semaphore:
        if self.volttron_central_connection is not None and \
                self.volttron_central_connection.is_connected:
            self.volttron_central_connection.kill()
            self.volttron_central_connection = None

        instance_id = self.current_config['instance_id']
        vc_address = self._volttron_central_address
        vc_serverkey = self._volttron_central_serverkey

        _log.debug('Connecting using vc: {} serverkey: {}'.format(vc_address,
                                                                  vc_serverkey))

        self.volttron_central_connection = build_connection(
            identity=instance_id, peer=VOLTTRON_CENTRAL, address=vc_address,
            serverkey=vc_serverkey, publickey=self.core.publickey,
            secretkey=self.core.secretkey
        )

        assert self.volttron_central_connection.is_connected()
        assert self.volttron_central_connection.is_peer_connected()

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

        if self._scheduled_connection_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._scheduled_connection_event.cancel()

        if not self.enable_registration:
            _log.debug('Registration of vcp is not enabled.')
            now = get_aware_utc_now()
            next_update_time = now + datetime.timedelta(
                seconds=10)

            self._scheduled_connection_event = self.core.schedule(
                next_update_time, self._periodic_attempt_registration)
            return

        try:
            vc = self.get_vc_connection()
            if vc is None:
                _log.debug("vc not connected")
                return

            if self.registration_state == RegistrationStates.NotRegistered:
                _log.debug('Not registred beginning registration process.')
                _log.debug('Retrieving publickey from vc agent.')
                vc_agent_publickey = vc.call("get_publickey")
                _log.debug('vc agent publickey is {}'.format(
                    vc_agent_publickey))
                assert vc_agent_publickey and len(vc_agent_publickey) == 43
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
            _log.error("{} found as {}".format(e, e.message))
        except gevent.Timeout as e:
            _log.error("timout occured connecting to remote platform.")
        finally:
            _log.debug('Scheduling next periodic call')
            now = get_aware_utc_now()
            next_update_time = now + datetime.timedelta(
                seconds=10)

            self._scheduled_connection_event = self.core.schedule(
                next_update_time, self._periodic_attempt_registration)

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
            conn.server.vip.health.set_status(status, context)

        self.vip.health.add_status_callback(sync_status_to_vc)

        def enable_connection_heartbeat():
            """
            Start publishing the heartbeat with the status messages.
            """
            conn = self.vc_connection
            status = self.vip.health.get_status()
            conn.server.vip.health.set_status(
                status['status'], status['context']
            )
            conn.server.vip.heartbeat.start()

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
            self.vc_connection = Connection(
                self.core.address, VOLTTRON_CENTRAL,
                publickey=self.core.publickey, secretkey=self.core.secretkey,
                identity=vcp_identity_on_vc
            )
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
        self.vc_connection = build_connection(
            identity=vcp_identity_on_vc,
            peer=VOLTTRON_CENTRAL,
            address=c.get('vc_connect_address'),
            serverkey=c.get('vc_connect_serverkey'),
            publickey=self.core.publickey,
            secretkey=self.core.secretkey
        )

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
        if not self._agent_started:
            return

        if self._stats_publisher:
            self._stats_publisher.kill()
        # The stats publisher publishes both to the local bus and the vc
        # bus the platform specific topics.
        self._stats_publisher = self.core.periodic(
            self._stats_publish_interval, self._publish_stats)

    @RPC.export
    def get_health(self):
        _log.debug("Getting health: {}".format(self.vip.health.get_status()))
        return self.vip.health.get_status()

    @RPC.export
    @RPC.allow("manager")
    def get_instance_uuid(self):
        return self.current_config.get('instance_id')

    @RPC.export
    @RPC.allow("manager")
    def get_publickey(self):
        return self.core.publickey

    @RPC.export
    @RPC.allow("manager")
    def manage(self, address):
        """ Allows the `VolttronCentralPlatform` to be managed.

        From the web perspective this should be after the user has specified
        that a user has blessed an agent to be able to be managed.

        When the user enters a discovery address in `VolttronCentral` it is
        implied that the user wants to manage a platform.

        :returns publickey of the `VolttronCentralPlatform`
        """
        _log.info('Manage request from address: {}'.format(address))

        if address != self.current_config['vc_connect_address']:
            _log.error("Managed by differeent volttron central.")
            return

        vc = self.get_vc_connection()

        if not vc.is_peer_connected():
            self.registration_state = RegistrationStates.NotRegistered
        else:
            self.registration_state = RegistrationStates.Registered

        return self.get_publickey()

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


    @RPC.export
    def start_bacnet_scan(self, iam_topic, proxy_identity, low_device_id=None,
                          high_device_id=None, target_address=None,
                          scan_length=5):
        """This function is a wrapper around the bacnet proxy scan.
        """
        if proxy_identity not in self.vip.peerlist().get(timeout=5):
            raise Unreachable("Can't reach agent identity {}".format(
                proxy_identity))
        _log.info('Starting bacnet_scan with who_is request to {}'.format(
            proxy_identity))

        def handle_iam(peer, sender, bus, topic, headers, message):
            proxy_identity = sender
            address = message['address']
            device_id = message['device_id']
            bn = BACnetReader(self.vip.rpc, proxy_identity)
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
            self.vip.pubsub.unsubscribe('pubsub', topics.BACNET_I_AM,
                                        handle_iam)

        self.vip.pubsub.subscribe('pubsub', topics.BACNET_I_AM, handle_iam)

        timestamp = get_utc_seconds_from_epoch()

        self._pub_to_vc(iam_topic, message=dict(status="STARTED IAM",
                                                timestamp=timestamp))

        self.vip.rpc.call(proxy_identity, "who_is", low_device_id=low_device_id,
                          high_device_id=high_device_id,
                          target_address=target_address).get(timeout=5.0)

        gevent.spawn_later(float(scan_length), stop_iam)

    def _pub_to_vc(self, topic_leaf, headers=None, message=None):
        vc = self.get_vc_connection()

        if not vc:
            _log.error('Platform must have connection to vc to publish {}'
                       .format(topic_leaf))
        else:
            if topic_leaf[0] == '/':
                topic_leaf = topic_leaf[1:]
            topic = "platforms/{}/{}".format(self.get_instance_uuid(),
                                             topic_leaf)
            _log.debug('Publishing to vc topic: {}'.format(topic))
            _log.debug('Publishing to vc headers: {}'.format(headers))
            _log.debug('Publishing to vc message: {}'.format(message))
            vc.publish(topic=topic, headers=headers, message=message)

    @RPC.export
    @RPC.allow("manager")
    def unmanage(self):
        pass
        # self._is_registering = False
        # self._is_registered = False
        # self._was_unmanaged = True

    @RPC.export
    @RPC.allow("manager")
    def list_agents(self):
        """
        RPC method to list the agents installed on the platform.

        :return: A list of agents.
        """

        agents = self.vip.rpc.call(CONTROL, "list_agents").get(timeout=5)
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

    @RPC.export
    @RPC.allow("manager")
    def store_agent_config(self, agent_identity, config_name, raw_contents,
                            config_type='raw'):
        self.vip.rpc.call(CONFIGURATION_STORE, "manage_store", agent_identity,
                          config_name, raw_contents, config_type)

    @RPC.export
    @RPC.allow("manager")
    def list_agent_configs(self, agent_identity):
        return self.vip.rpc.call(CONFIGURATION_STORE, "manage_list_configs",
                                 agent_identity).get(timeout=5)

    @RPC.export
    @RPC.allow("manager")
    def get_agent_config(self, agent_identity, config_name, raw=True):
        data = self.vip.rpc.call(CONFIGURATION_STORE, "manage_get",
                                 agent_identity, config_name, raw).get(timeout=5)
        return data or ""


    @RPC.export
    @RPC.allow("manager")
    def start_agent(self, agent_uuid):
        self.vip.rpc.call(CONTROL, "start_agent", agent_uuid)

    @RPC.export
    @RPC.allow("manager")
    def stop_agent(self, agent_uuid):
        proc_result = self.vip.rpc.call(CONTROL, "stop_agent", agent_uuid)

    @RPC.export
    @RPC.allow("manager")
    def restart_agent(self, agent_uuid):
        self.vip.rpc.call(CONTROL, "restart_agent", agent_uuid)
        gevent.sleep(0.2)
        return self.agent_status(agent_uuid).get(timeout=5)

    @RPC.export
    @RPC.allow("manager")
    def agent_status(self, agent_uuid):
        return self.vip.rpc.call(CONTROL, "agent_status", agent_uuid).get(timeout=5)

    @RPC.export
    @RPC.allow("manager")
    def status_agents(self):
        return self.vip.rpc.call(CONTROL, 'status_agents').get(timeout=5)

    @PubSub.subscribe('pubsub', 'devices')
    def _on_record_message(self, peer, sender, bus, topic, headers, message):
        pass

    @PubSub.subscribe('pubsub', 'devices')
    def _on_analysis_message(self, peer, sender, bus, topic, headers, message):
        pass

    @RPC.export
    @RPC.allow("manager")
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

    @RPC.export
    @RPC.allow("manager")
    def route_request(self, id, method, params):
        _log.debug(
            'platform agent routing request: {}, {}'.format(id, method))

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
            _log.debug('Params are: {}'.format(params))
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
                status = self.vip.rpc.call(CONTROL, method, uuid)
                if method == 'stop_agent' or status == None:
                    # Note we recurse here to get the agent status.
                    result = self.route_request(id, 'agent_status', uuid)
                else:
                    result = {'process_id': status[0],
                              'return_code': status[1]}
        elif method in ('install'):

            if not 'files' in params:
                result = jsonrpc.json_error(ident=id, code=INVALID_PARAMS)
            else:
                result = self._install_agents(params['files'])

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

    def _install_agents(self, agent_files):
        tmpdir = tempfile.mkdtemp()
        results = []

        for f in agent_files:
            try:
                if 'local' in f.keys():
                    path = f['file_name']
                else:
                    path = os.path.join(tmpdir, f['file_name'])
                    with open(path, 'wb') as fout:
                        fout.write(
                            base64.decodestring(f['file'].split('base64,')[1]))

                _log.debug('Calling control install agent.')
                uuid = self.vip.rpc.call(CONTROL,  'install_agent_local',
                                         path).get(timeout=30)

            except Exception as e:
                results.append({'error': str(e)})
                _log.error("EXCEPTION: " + str(e))
            else:
                results.append({'uuid': uuid})

        shutil.rmtree(tmpdir, ignore_errors=True)

        return results

    def _publish_stats(self):
        """
        Publish the platform statistics to the local bus as well as to the
        connected volttron central.
        """
        vc_topic = None
        local_topic = LOGGER(subtopic="platform/status/cpu")
        _log.debug('Publishing platform cpu stats')
        if self._local_instance_uuid is not None:

            vc_topic = LOGGER(
                subtopic="platforms/{}/status/cpu".format(
                    self._local_instance_uuid))
            _log.debug('Stats will be published to: {}'.format(
                vc_topic.format()))
        else:
            _log.debug('Platform uuid is not valid')
        points = {}

        for k, v in psutil.cpu_times_percent().__dict__.items():
            points['times_percent/' + k] = {'Readings': v,
                                            'Units': 'double'}

        points['percent'] = {'Readings': psutil.cpu_percent(),
                             'Units': 'double'}
        try:
            vc = self.get_vc_connection()
            if vc is not None and vc.is_connected() and vc_topic is not None:
                vc.publish(vc_topic.format(), message=points)
        except Exception as e:
            _log.info("status not written to volttron central.")
        self.vip.pubsub.publish(peer='pubsub', topic=local_topic.format(),
                                message=points)

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        if self.vc_connection is not None:
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
    utils.vip_main(VolttronCentralPlatform, identity=VOLTTRON_CENTRAL_PLATFORM)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
