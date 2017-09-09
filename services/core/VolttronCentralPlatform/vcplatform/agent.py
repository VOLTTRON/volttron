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
import string
import sys
import tempfile
import urlparse

import gevent
import gevent.event
import psutil

from volttron.platform.messaging.health import GOOD_STATUS
from volttron.platform.messaging.health import Status
from .vcconnection import VCConnection

from volttron.platform import jsonrpc
from volttron.platform.agent.utils import (get_utc_seconds_from_epoch,
                                           format_timestamp, normalize_identity)
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, CONTROL, CONFIGURATION_STORE)
from volttron.platform.agent.utils import (get_aware_utc_now)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS)
from volttron.platform.messaging import topics
from volttron.platform.messaging.topics import (LOGGER, )
from volttron.platform.vip.agent import (Agent, Core, RPC, PubSub, Unreachable)
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.web import DiscoveryInfo, DiscoveryError
from .bacnet_proxy_reader import BACnetReader

__version__ = '4.5.2'

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


def vcp_init(config_path, **kwargs):
    """
    The vcp_init method is used to parse the configuration file and provide
    relatively good defaults for all of the configuration options for the
    `pyclass::vcplatform.VolttronCentralPlatform`.

    :param config_path:
    :param kwargs:
    :return: An instance of the `pyclass::vcplatform.VolttronCentralPlatform`
    """

    config = utils.load_config(config_path)

    reconnect_interval = config.get(
        'volttron-central-reconnect-interval', 5)
    vc_address = config.get('volttron-central-address')
    vc_serverkey = config.get('volttron-central-serverkey')
    instance_name = config.get('instance-name')
    stats_publish_interval = config.get('stats-publish-interval', 30)
    # Interval to wait before publishing the status of the devices on this
    # instance up to volttron central
    device_status_interval = config.get('device-status-interval', 60)
    topic_replace_map = config.get('topic-replace-map', {})

    return VolttronCentralPlatform(reconnect_interval=reconnect_interval,
                                   vc_address=vc_address,
                                   vc_serverkey=vc_serverkey,
                                   instance_name=instance_name,
                                   stats_publish_interval=stats_publish_interval,
                                   topic_replace_map=topic_replace_map,
                                   device_status_interval=device_status_interval,
                                   **kwargs)



class VolttronCentralPlatform(Agent):

    def __init__(self, reconnect_interval, vc_address,
                 vc_serverkey, instance_name, stats_publish_interval,
                 topic_replace_map, device_status_interval, **kwargs):
        super(VolttronCentralPlatform, self).__init__(**kwargs)

        # This is scheduled after first call to the reconnect function
        self._scheduled_connection_event = None
        self._publish_bacnet_iam = False

        d = {}
        d['volttron-central-reconnect-interval'] = reconnect_interval
        d['volttron-central-address'] = vc_address
        d['volttron-central-serverkey'] = vc_serverkey
        d['instance-name'] = instance_name
        d['stats-publish-interval'] = stats_publish_interval
        d['topic-replace-map'] = topic_replace_map
        d['device-status-interval'] = device_status_interval

        # default_configuration is what is specified if there isn't a "config"
        # sent in through the volttron-ctl config store command.
        self.default_config = d

        # Start using config store.
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self._configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

        # Allows the periodic check for registration.  It is set to true after
        # a main configuration is changed.
        self.enable_registration = False

        # A connection to the volttron central agent.
        self._vc_connection = None

        # This publickey is set during the manage rpc call.
        self.manager_publickey = None

        # The state of registration of vcp with the vc instance.
        self._registration_state = RegistrationStates.NotRegistered

        self._stats_publisher = None

        self._still_connected_event = None
        self._establish_connection_event = None
        self._device_status_event = None
        self._stat_publish_event = None

        # This becomes a connection to the vc instance either specified from the
        # instance level or from the config file.
        self._vc_connection = None
        self._vc_address = None
        self._vc_serverkey = None
        self._instance_name = None
        self._local_external_address = None
        self._local_serverkey = None
        self._stats_publish_interval = None
        self._device_status_interval = None
        self._device_publishes = {}
        self._devices = {}
        # master driver config store stat time
        self._master_driver_stat_time = None

        # instance id is the vip identity of this agent on the remote platform.
        self._instance_id = None

        # where on the vc this instance will publish things
        self._publish_topic = None

        # topic_replace_map is a key value dictionary with strings to be
        # replaced with values for all topics.
        #
        self._replace_map = {}

        # This is used internally so we don't have to do replacements more
        # than one time.
        self._topic_replacement = {}

    def _retrieve_address_and_serverkey(self, discovery_address):
        info = DiscoveryInfo.request_discovery_info(discovery_address)
        return info.vip_address, info.serverkey

    def _configure(self, config_name, action, contents):
        """
        This is the main configuration point for the agent.

        :param config_name:
        :param action:
        :param contents:
        :return:
        """

        config = self.default_config.copy()
        config.update(contents)
        self.enable_registration = False

        # get the instance variables from the router.  The instance variables
        # are located in the configuration file for the local instance.
        # The query returns None if there is no value set.
        _log.debug('Querying router for addresses and serverkey.')
        q = Query(self.core)

        # qry prefix is from the query subsystem.
        qry_external_addresses = q.query('addresses').get(timeout=5)
        qry_local_serverkey = q.query('serverkey').get(timeout=5)
        qry_vc_address = q.query('volttron-central-address').get(timeout=5)
        qry_vc_serverkey = q.query('volttron-central-serverkey').get(timeout=5)
        qry_instance_name = q.query('instance-name').get(timeout=5)
        qry_bind_web_address = q.query('bind-web-address').get(timeout=5)

        cfg_vc_address = config.get("volttron-central-address")
        cfg_vc_serverkey = config.get("volttron-central-serverkey")

        try:
            a, s = self._determine_vc_address_and_serverkey(cfg_vc_address,
                                                            cfg_vc_serverkey,
                                                            qry_bind_web_address)
        except AttributeError:
            try:
                a, s = self._determine_vc_address_and_serverkey(qry_vc_address,
                                                                qry_vc_serverkey,
                                                                qry_bind_web_address)
            except AttributeError:
                error = """The global configuration contains an invalid/unavailable
reference to an volttron discovery server and there was not a configuration
for the platform agent that contains a volttron-central-agent and 
volttron-central-serverkey."""
                _log.error(error)
                return

        try:
            if not a or not s:
                _log.error("Couldn't determine server key and address")
        except NameError:
            _log.error("Couldn't determine server key and address")
            return

        # Reset the connection if necessary.  The case that we are changing
        # configuration to a new vc.
        if action == "UPDATE":
            if self._vc_connection is not None:
                self._stop_event_timers()
                self._vc_connection.core.stop()
                self._vc_connection = None

        self._topic_replacement.clear()
        self._replace_map = config['topic-replace-map']
        self._vc_address = a
        self._vc_serverkey = s
        self._registration_state = RegistrationStates.NotRegistered

        if not self._vc_address or not self._vc_serverkey:
            _log.error("vc address and serverkey could not be determined. "
                       "registration is not allowed.")
            return

        cfg_instance_name = config.get("instance-name")
        if cfg_instance_name is not None:
            self._instance_name = cfg_instance_name
        else:
            self._instance_name = qry_instance_name

        self._instance_id = 'vcp-{}'.format(normalize_identity(
            self._instance_name))

        self._publish_topic = 'platforms/{}'.format(self._instance_id)

        self._local_external_address = qry_external_addresses
        self._local_serverkey = qry_local_serverkey
        self._stats_publish_interval = config['stats-publish-interval']

        self._device_status_interval = config['device-status-interval']

        # Subscribe to devices
        self._devices = self.get_devices()
        self.vip.pubsub.subscribe('pubsub', 'devices', self._on_device_publish)

        # Begin a connection loop that will automatically attempt to reconnect
        # and publish stats to volttron central if the connection is successful.
        self._establish_connection_to_vc()

    def _stop_event_timers(self):
        if self._establish_connection_event is not None:
            self._establish_connection_event.cancel()
            self._establish_connection_event = None
        if self._stat_publish_event is not None:
            self._stat_publish_event.cancel()
            self._stat_publish_event = None
        if self._still_connected_event is not None:
            self._still_connected_event.cancel()
            self._still_connected_event = None
        if self._device_status_event is not None:
            self._device_status_event.cancel()
            self._device_status_event = None

    def _determine_vc_address_and_serverkey(self, vc_address, vc_serverkey,
                                            local_web_address):
        if vc_address is None and local_web_address is None:
            raise AttributeError("Must have local or vc address specified.")

        _log.debug("Determining vc_address and serverkey")
        _log.debug(
            "\nvc_address={}\nvc_serverkey={}\nlocal_web_address={}".format(
                vc_address, vc_serverkey, local_web_address
            ))

        if vc_address is None:
            try:
                address = local_web_address
                parsed_address = urlparse.urlparse(local_web_address)
            except AttributeError:
                _log.error("local_web_address is invalid: {}".format(
                    local_web_address))
                raise
        else:
            try:
                address = vc_address
                parsed_address = urlparse.urlparse(vc_address)
            except AttributeError:
                _log.error("vc_address invalid: {}".format(vc_address))
                raise

        if parsed_address.scheme in ('https', 'http'):
            try:
                a, s = self._retrieve_address_and_serverkey(address)
            except DiscoveryError:
                raise AttributeError(
                    "Cannot retrieve data from address: {}".format(address))
        else:
            if parsed_address.scheme not in ('tcp', 'ipc'):
                raise AttributeError("Invalid scheme detected for vc_address "
                                     "{}".format(vc_address))
            if not vc_serverkey:
                raise AttributeError("Invalid serverkey specified when "
                                     "tcp address for vc_address")
            a, s = vc_address, vc_serverkey

        return a, s

    def _update_vc_connection_params(self, updated_config,
                                     inst_bind_web_address,
                                     inst_vc_address, inst_vc_serverkey):
        """
        Updates the instance variables _vc_address and _vc_serverkey with a
        true tcp based address.  This method will look up a discovery address
        if that is what is specified.

        When this method is complete, there will either be an error or the
        _vc_address and _vc_serverkey variables will be set with "correct"
        values to connect _vc_connection.

        Note: if inst_vc_address is an http address then loop

        :param updated_config:
        :param inst_bind_web_address:
        :param inst_vc_address:
        :param inst_vc_serverkey:
        :return:
        """
        vc_address = updated_config.get('volttron-central-address')

        if vc_address is None:
            vc_address = inst_vc_address

            if vc_address is None:
                if inst_bind_web_address is not None:
                    info = DiscoveryInfo.request_discovery_info(
                        inst_bind_web_address)
                    self._vc_address = info.vip_address
                    self._vc_serverkey = info.serverkey
            else:
                parsed = urlparse.urlparse(inst_vc_address)

                if parsed.scheme in ('http', 'https'):
                    _log.debug('inst_vc_address is {}'.format(inst_vc_address))
                    info = None
                    while info is None:
                        try:
                            info = DiscoveryInfo.request_discovery_info(
                                inst_vc_address)
                        except DiscoveryError as e:
                            _log.error(
                                "Unable to retrieve discovery info from volttron central.")
                            gevent.sleep(10)

                    self._vc_address = info.vip_address
                    self._vc_serverkey = info.serverkey
                else:
                    self._vc_address = inst_vc_address
                    self._vc_serverkey = inst_vc_serverkey

    @RPC.export
    def get_external_vip_addresses(self):
        return self._local_external_address

    @RPC.export
    def get_instance_name(self):
        return self._instance_name

    @RPC.export
    def get_instance_details(self):
        return dict(
            instance_name=self._instance_name,
            instance_id=self._instance_id,
            topic_root=self._publish_topic,
            publickey=self.core.publickey,
            serverkey=self._local_serverkey,
            address=self._local_external_address
        )

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

        if not self._vc_address:
            raise ValueError("vc_address was not resolved properly.")

        if not self._vc_serverkey:
            raise ValueError("vc_serverkey was not resolved properly.")

        if self._establish_connection_event is not None:
            self._establish_connection_event.cancel()

        if self._vc_connection is None:
            _log.debug("Attempting to connect with volttron central.")
            _log.debug(
                "Serverkey is going to be: {}".format(self._vc_serverkey))

            try:

                self._vc_connection = build_agent(
                    identity=self._instance_id,
                    address=self._vc_address,
                    serverkey=self._vc_serverkey,
                    publickey=self.core.publickey,
                    secretkey=self.core.secretkey,
                    agent_class=VCConnection
                )
            except ValueError as ex:
                _log.warn("Unable to connect to volttron central due to "
                          "invalid configuration.")
                _log.warn("Value Error! {}".format(ex.message))
                self._vc_connection = None

            except gevent.Timeout:
                _log.warn("No connection to volttron central instance.")
                self._vc_connection = None

                next_update_time = self._next_update_time()

                self._establish_connection_event = self.core.schedule(
                    next_update_time, self._establish_connection_to_vc)
            else:
                self._vc_connection.set_main_agent(self)
                self._still_connected()
                self._publish_stats()
                self._publish_device_health()

    def _still_connected(self):

        if self._still_connected_event is not None:
            self._still_connected_event.cancel()

        try:
            with gevent.Timeout(seconds=5):
                hello = self._vc_connection.vip.ping(
                    b'', self._instance_id).get()
        except gevent.Timeout:
            self._vc_connection = None
            self._establish_connection_to_vc()
        except AttributeError as ae:
            self._vc_connection = None
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

            if not vc.call("is_registered",
                           address=self._local_external_address):
                _log.debug("platform agent is not registered.")
                self._registration_state = RegistrationStates.NotRegistered

            if self._registration_state == RegistrationStates.NotRegistered:
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

                vc.call('register_instance',
                        address=self._local_external_address,
                        display_name=self._instance_name,
                        vcpserverkey=self._local_serverkey,
                        vcpagentkey=self.core.publickey)

            else:
                _log.debug("Current platform registration state: {}".format(
                    self._registration_state))
        except Unreachable as e:
            _log.error("Couldn't connect to volttron.central. {}".format(
                self._vc_address
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

        if self._vc_connection:
            # if connected return the connection.
            if self._vc_connection.is_connected(5) and \
                    self._vc_connection.is_peer_connected(5):
                _log.debug('Returning current connection')
                return self._vc_connection

            _log.debug("Resetting connection as the peer wasn't responding.")
            # reset the connection so we can try it again below.
            self._vc_connection.kill()
            self._vc_connection = None

        def sync_status_to_vc(status, context):
            """
            Sync the status of the current vcp object with that of the one that
            is connected to the vc instance.

            :param status:
            :param context:
            """
            conn = self._vc_connection
            conn.vip.health.set_status(status, context)

        self.vip.health.add_status_callback(sync_status_to_vc)

        def enable_connection_heartbeat():
            """
            Start publishing the heartbeat with the status messages.
            """
            conn = self._vc_connection
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
            _log.debug('VC is a local peer, using {} as instance_id'.format(
                self._instance_id))
            self._vc_connection = build_agent(
                self.core.address,
                # peer=VOLTTRON_CENTRAL,
                publickey=self.core.publickey,
                secretkey=self.core.secretkey,
                serverkey=self._vc_serverkey,
                identity=self._instance_id,
                agent_class=VCConnection
            )
            self._vc_connection.set_main_agent(self)
            if self._vc_connection.is_connected() and \
                    self._vc_connection.is_peer_connected():
                _log.debug("Connection has been established to local peer.")
            else:
                _log.error('Unable to connect to local peer!')
            if self._vc_connection.is_connected():
                enable_connection_heartbeat()

            return self._vc_connection

        if self._vc_address is None or self._vc_serverkey is None:
            _log.warn('volttron_central_address is None in config store '
                      'and volttron.central is not a peer.')
            _log.warn('Recommend adding volttron.central address or adding a '
                      '"config" file to the config store.')
            return None

        self._vc_connection = build_agent(
            identity=vcp_identity_on_vc,
            # peer=VOLTTRON_CENTRAL,
            address=self._vc_address,
            serverkey=self._vc_serverkey,
            publickey=self.core.publickey,
            secretkey=self.core.secretkey,
            agent_class=VCConnection
        )

        self._vc_connection.set_main_agent(self)
        if not self._vc_connection.is_peer_connected():
            _log.error('Peer: {} is not connected to the external platform'
                       .format(self._vc_connection.peer))
            self._vc_connection.kill()
            self._vc_connection = None
            self._registration_state = RegistrationStates.NotRegistered
            return None

        if self._vc_connection.is_connected():
            enable_connection_heartbeat()

        return self._vc_connection

    @RPC.export
    def get_health(self):
        _log.debug("Getting health: {}".format(self.vip.health.get_status()))
        return self.vip.health.get_status()

    def get_instance_uuid(self):
        return self._instance_id

    @RPC.export
    def get_replace_map(self):
        return self._replace_map

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

        agent_to_use.vip.pubsub.subscribe('pubsub', topics.BACNET_I_AM,
                                          handle_iam)

        timestamp = get_utc_seconds_from_epoch()

        self._pub_to_vc(iam_topic, message=dict(status="STARTED IAM",
                                                timestamp=timestamp))

        agent_to_use.vip.rpc.call(proxy_identity, "who_is",
                                  low_device_id=low_device_id,
                                  high_device_id=high_device_id,
                                  target_address=target_address).get(
            timeout=5.0)

        gevent.spawn_later(float(scan_length), stop_iam)

    def _pub_to_vc(self, topic_leaf, headers=None, message=None):
        if self._vc_connection is None:
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
        self._vc_connection.publish_to_vc(topic=topic,
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
                                 agent_identity, config_name, raw).get(
            timeout=5)
        return data or ""

    def start_agent(self, agent_uuid):
        return self.vip.rpc.call(CONTROL, "start_agent", agent_uuid).get(
            timeout=5)

    def stop_agent(self, agent_uuid):
        proc_result = self.vip.rpc.call(CONTROL, "stop_agent",
                                        agent_uuid).get(timeout=5)
        return proc_result

    def restart_agent(self, agent_uuid):
        self.vip.rpc.call(CONTROL, "restart_agent", agent_uuid)
        gevent.sleep(0.2)
        return self.agent_status(agent_uuid).get(timeout=5)

    def agent_status(self, agent_uuid):
        return self.vip.rpc.call(CONTROL, "agent_status", agent_uuid).get(
            timeout=5)

    def status_agents(self):
        _log.debug('STATUS AGENTS')
        return self.vip.rpc.call(CONTROL, 'status_agents').get(timeout=5)

    def _on_device_publish(self, peer, sender, bus, topic, headers, message):
        # Update the devices store for get_devices function call
        if not topic.endswith('/all'):
            self._log.debug("Skipping publish to {}".format(topic))
            return

        _log.debug("topic: {}, message: {}".format(topic, message))

        ts = format_timestamp(get_aware_utc_now())
        context = "Last received data on: {}".format(ts)
        status = Status.build(GOOD_STATUS, context=context)

        device_topic = topic[:-len('/all')]

        if device_topic not in self._devices:
            self._devices = self.get_devices()

            if device_topic not in self._devices:
                _log.error("Unknown device was published to this address!")
                return

        device_dict = self._devices[device_topic]

        if not device_dict.get('points', None):
            points = message[0].keys() # [k for k, v in message[0].items()]
            device_dict['points'] = points

        device_dict['health'] = status.as_dict()
        device_dict['last_publish_utc'] = ts

    def _replace_topic(self, original):
        # only need to replace if we have some items in the list.
        if not self._replace_map:
            return original

        if original in self._topic_replacement:
            return self._topic_replacement

        new_value = original

        for x in self._replace_map:
            new_value = new_value.replace(x, self._replace_map[x])

        if new_value == original:
            return None

        self._topic_replacement[original] = new_value

        return new_value

    def get_devices(self):
        """
        RPC method for retrieving device data from the platform.

        :return:
        """

        md_configstore = os.path.join(
            os.environ['VOLTTRON_HOME'],
            "configuration_store/platform.driver.store"
        )

        if not os.path.exists(md_configstore):
            _log.debug("No master driver currently on this platform.")
            return {}

        statinfo = os.stat(md_configstore)

        if self._master_driver_stat_time is None or \
                        self._master_driver_stat_time != statinfo.st_mtime:
            self._master_driver_stat_time = statinfo.st_mtime

        # else no change in the md file and we have the same stat time.
        else:
            return self._devices

        _log.debug('Getting devices')
        config_list = self.vip.rpc.call(CONFIGURATION_STORE,
                                        'manage_list_configs',
                                        'platform.driver').get(timeout=5)

        _log.debug('Config list is: {}'.format(config_list))
        devices = defaultdict(dict)

        for cfg_name in config_list:
            # Skip as we are only looking to do devices in this call.
            if not cfg_name.startswith('devices/'):
                continue

            _log.debug('Reading config store for device {}'.format(cfg_name))
            anon_config_name = self._replace_topic(cfg_name)

            # Don's show the non-anonimized devices if nothing has been replaced
            # in the data.
            if anon_config_name is None:
                continue

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
                if agent_method in (
                'start_bacnet_scan', 'publish_bacnet_props'):
                    identity = params.pop("proxy_identity")
                    if agent_method == 'start_bacnet_scan':
                        result = self.start_bacnet_scan(identity, **params)
                    elif agent_method == 'publish_bacnet_props':
                        result = self.publish_bacnet_props(identity, **params)
                else:
                    # find the identity of the agent so we can call it by name.
                    identity = self.vip.rpc.call(CONTROL,
                                                 'agent_vip_identity',
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

            uuid = self.vip.rpc.call(CONTROL, 'install_agent_local',
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

    def _publish_device_health(self):
        if self._device_status_event is not None:
            self._device_status_event.cancel()

        try:
            self._vc_connection.publish_to_vc(
                "platforms/{}/device_update".format(self.get_instance_uuid()),
                message=self._device_publishes)
        finally:
            # The stats publisher publishes both to the local bus and the vc
            # bus the platform specific topics.
            next_update_time = self._next_update_time(
                seconds=self._device_status_interval)

            self._device_status_event = self.core.schedule(
                next_update_time, self._publish_device_health)



    def _publish_stats(self):
        """
        Publish the platform statistics to the bus.
        """
        if self._stat_publish_event is not None:
            self._stat_publish_event.cancel()

        topic = LOGGER(subtopic=self._publish_topic + "/status/cpu")

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
        finally:
            # The stats publisher publishes both to the local bus and the vc
            # bus the platform specific topics.
            next_update_time = self._next_update_time(
                seconds=self._stats_publish_interval)

            self._stats_publish_event = self.core.schedule(
                next_update_time, self._publish_stats)

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        if self._vc_connection is not None:
            _log.debug("Shutting down agent.")

            self._vc_connection.publish_to_vc(
                "platforms/{}/stopping".format(
                    self.get_instance_uuid()))
            gevent.sleep(1)
            try:
                self._vc_connection.core.stop(timeput=5)
            except:
                _log.error("killing _vc_connection connection")
            finally:
                self._vc_connection = None


def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    # utils.vip_main(platform_agent)
    utils.vip_main(vcp_init, identity=VOLTTRON_CENTRAL_PLATFORM,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
