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

import datetime
import hashlib
import logging

import gevent
from copy import deepcopy

from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now, \
    get_utc_seconds_from_epoch
from volttron.platform.messaging.health import Status, UNKNOWN_STATUS, \
    GOOD_STATUS, BAD_STATUS
from volttron.platform.vip.agent.utils import build_connection


class Platforms(object):
    """
    A class to manage the connections and interactions
    with external instances.
    """

    def __init__(self, vc):
        """
        Construct a Platforms object with the vip member
        of an agent instance of the object.

        :param vc: A reference to the VolttronCentral agent
        """
        self._vc = vc
        self._log = logging.getLogger(self.__class__.__name__)
        self._platforms = {}

    @property
    def vc(self):
        return self._vc

    def get_platform_list(self, session_user, params):
        """
        Retrieve the platform list and respond in a manner that can
        be sent back to the web service.

        The response will be formatted as follows:

        [
        ]

        :param session_user:
        :param params:
        :return: A list of dictionaries each representing a platform.
        """
        results = []
        for x in self._platforms.values():
            results.append(
                dict(uuid=x.address_hash,
                     name=x.display_name,
                     health=x.health)
            )

        return results

    def get_platform_hashes(self):
        """
        Returns a list of all the address hashes that are currently registered
        with VC.

        :return: list of str
        """
        return self._platforms.keys()

    def get_platform(self, address_hash, default=None):
        """
        Get a specific :ref:`PlatformHandler` associated with the passed
        address_hash.  If the hash is not available then the default parameter
        is returned.

        :param address_hash: string associated with a specific platform
        :param default: a default to be returned if not in the collection.
        :return: a :ref:`PlatformHandler` or default
        """
        return self._platforms.get(address_hash, default)

    def register_platform(self, address, address_type, serverkey=None,
                          display_name=None):
        """
        Allows an volttron central platform (vcp) to register with vc.  Note
        that if the address has already been used then the same
        PlatformHandler object reference will be returned to the caller.

        @param address:
            An address or resolvable domain name with port.
        @param address_type:
            A string consisting of ipc or tcp.
        @param: serverkey: str:
            The router publickey for the vcp attempting to register.
        @param: display_name: str:
            The name to be shown in volttron central.
        """
        self._log.info('Attempting registration of vcp at address: '
                  '{} display_name: {}, serverkey: {}'.format(address,
                                                              display_name,
                                                              serverkey))
        assert address_type in ('ipc', 'tcp') and \
            address[:3] in ('ipc', 'tcp'), \
            "Invalid address_type and/or address specified."

        hashed_address = PlatformHandler.address_hasher(address)
        if hashed_address not in self._platforms:
            self._log.debug('Address {} is not in platform list.'.format(address))
            platform = PlatformHandler(self, address, address_type, serverkey,
                                       display_name)
        else:
            self._log.debug(
                'Address {} is in platform list returning reference.'.format(address))
            platform = self._platforms[hashed_address]
        self._platforms[platform.address_hash] = platform
        return platform.address_hash, platform


class PlatformHandler(object):
    """
    This class is a wrapper around the communication between VC and a
    corresponding VCP on either this instance or another instance.
    """

    @staticmethod
    def address_hasher(address):
        """
        Hashes the passed address.

        :param address:
        :return:
        """
        return hashlib.md5(address).hexdigest()

    def __init__(self, platforms, address, address_type, serverkey=None,
                 display_name=None):
        """
        Constructs a platform and attempts to connect it up with the
        an instance containing a vcp agent.

        :param platforms: A platforms object.
        """
        self._platforms = platforms
        self._vc = self.platforms.vc
        self._address = address
        self._serverkey = serverkey
        self._display_name = display_name
        self._address_type = address_type
        self._address_hash = PlatformHandler.address_hasher(address)
        self._connection = None
        self._log = logging.getLogger(self.__class__.__name__)
        self._is_managed = False
        self._last_time_verified_connection = None
        self._event_listeners = set()
        self._health = Status.build(UNKNOWN_STATUS, "Initial Status")
        self._recheck_connection_event = None
        self._connect()
        self._recheck_connection()

    @property
    def address_hash(self):
        return self._address_hash

    @property
    def display_name(self):
        return self._display_name

    @property
    def address(self):
        return self._address

    @property
    def serverkey(self):
        return self._serverkey

    @property
    def platforms(self):
        """
        Returns a link to the object that created this handler.

        :return:
        """
        return self._platforms

    @property
    def health(self):
        """
        Returns a Status object as a dictionary.  This will be populated
        by the heartbeat from the external instance that this object is
        monitoring, unless it has been over 10 seconds since the instance
        has been reached.  In that case the health will be BAD.

        :return:
        """
        now = get_utc_seconds_from_epoch()
        if now > self._last_time_verified_connection + 10:
            self._health = Status.build(
                BAD_STATUS,
                "Platform hasn't been reached in over 10 seconds.")
        return self._health.as_dict()

    @property
    def external_vip_identity(self):
        """
        Returns the identity this object will use on the remote instance.

        :return:
        """
        return 'platform.{}'.format(self._address_hash)

    def get_agent_config_list(self, agent_identity):
        if self._is_managed:
            return self._connection.call('list_agent_configs', agent_identity)
        return []

    def get_agent_config(self, agent_identity, config_name, raw=True):
        if self._is_managed:
            try:
                return self._connection.call('get_agent_config', agent_identity,
                                             config_name, raw)
            except KeyError:
                self._log.error('Invalid configuration name: {}'.format(
                    config_name
                ))
        return ""

    def add_event_listener(self, callback):
        self._event_listeners.add(callback)

    def handle_sending_bacnet_properties(self):
        pass

    def _raise_event(self, type, data={}):
        self._log.debug('RAISING EVENT: {} {}'.format(type, data))
        for listener in self._event_listeners:
            listener(type, data)

    def _manage(self):
        """
        Attempt to call the manage function on the external instance's VCP
        agent.

        This will only happen if we have a connection and the platform.agent
        is connected.
        """
        try:
            if self._connection is not None and \
                    self._connection.is_peer_connected():
                public_address = self._vc.runtime_config['local_external_address']
                my_address = self._vc.runtime_config['local_external_address']
                self._log.debug('Calling manage with vc address: {}'.format(
                    public_address
                ))
                pk = self._connection.call('manage', my_address)
                self._raise_event("MANAGED", data=dict(
                    address=self._address,
                    address_hash=self._address_hash))

        except gevent.Timeout:
            self._log.error(
                'RPC call to manage did not return in a timely manner.')
            raise

    def _on_device_message(self, peer, sender, bus, topic, headers, message):
        self._log.debug("DEVICE MESSAGE: {}".format(message))

    def _on_platform_message(self, peer, sender, bus, topic, headers, message):
        self._log.debug('Platform message {}'.format(message))

    def _connect(self):
        """
        Connects to the remote instance.  If unsuccessful raises a
        gevent.Timeout error.
        """

        publickey = self._vc.core.publickey
        secretkey = self._vc.core.secretkey

        # First attempt to connect to the external instance.  The instance
        # doesn't have to have the VCP on it for the connection to be
        # established.  However it will need to have it on in order to
        # execute any rpc methods on it.
        try:
            self._connection = build_connection(
                identity=self.external_vip_identity,
                peer=VOLTTRON_CENTRAL_PLATFORM,
                address=self._address,
                serverkey=self._serverkey,
                publickey=publickey,
                secretkey=secretkey)
            self._raise_event("CONECTED", data=dict(
                address=self._address,
                address_hash=self._address_hash))
            self._connection.subscribe('devices', self._on_device_message)
        except gevent.Timeout:
            self._log.error("Unable to connect to instance.")
            if self._connection is not None:
                self._connection.kill()
                self._connection = None
            raise

        # If we were successful in calling manage then we can add it to
        # our list of managed platforms.
        # if pk is not None and len(pk) == 43:
        #
        #     md5 = hashlib.md5(address)
        #     address_hash = md5.hexdigest()
        #     config_name = "platforms/{}".format(address_hash)
        #     platform = None
        #     if config_name in self.vip.config.list():
        #         platform = self.vip.config.get(config_name)
        #
        #     if platform:
        #         data = platform.copy()
        #         data['serverkey'] = serverkey
        #         data['display_name'] = display_name
        #
        #     else:
        #         time_now = format_timestamp(get_aware_utc_now())
        #         data = dict(
        #             address=address, serverkey=serverkey,
        #             display_name=display_name,
        #             registered_time_utc=time_now,
        #             instance_uuid=address_hash
        #         )
        #
        #     data['health'] = connection.call('health.get_status')
        #     devices = connection.call('get_devices')
        #     data['devices'] = devices
        #
        #     status = Status.build(UNKNOWN_STATUS,
        #                           context="Not published since update")
        #     devices_health = {}
        #     for device, item in devices.items():
        #         device_no_prefix = device[len('devices/'):]
        #         devices_health[device_no_prefix] = dict(
        #             last_publish_utc=None,
        #             health=status.as_dict(),
        #             points=item.get('points', [])
        #         )
        #     data['devices_health'] = devices_health
        #
        #     self.vip.config.set(config_name, data)
        #
        #     # Hook into management socket here and send all of the data
        #     # for newly registered platforms.
        #     management_sockets = [s for s in self._websocket_endpoints
        #                           if s.endswith("management")]
        #     payload = dict(
        #         type="platform_registered",
        #         data=data
        #     )
        #     for s in management_sockets:
        #         self.vip.web.send(s, payload)
        #
        #     def ondevicemessage(peer, sender, bus, topic, headers, message):
        #         if not topic.endswith('/all'):
        #             return
        #
        #         # used in the devices structure.
        #         topic_no_all = topic[:-len('/all')]
        #
        #         # Used in the devices_health structure.
        #         no_devices_prefix = topic_no_all[len('devices/'):]
        #
        #         now_time_utc = get_aware_utc_now()
        #         last_publish_utc = format_timestamp(now_time_utc)
        #
        #         status = Status.build(GOOD_STATUS,
        #                               context="Last publish {}".format(
        #                                   last_publish_utc))
        #         self._log.debug("DEVICES MESSAGE: {}".format(message))
        #         try:
        #             data = self.vip.config.get(config_name)
        #         except KeyError:
        #             self._log.error('Invalid configuration name: {}'.format(
        #                 config_name))
        #             return
        #
        #         cp = deepcopy(data)
        #         try:
        #             device_health = cp['devices_health'][no_devices_prefix]
        #         except KeyError:
        #             self._log.warn('No device health for: {}'.format(
        #                 no_devices_prefix))
        #             device_health = cp['devices']
        #             device_health = cp['devices'][topic_no_all] = {
        #                 'points': {}}
        #             # device_health=dict(
        #             #     points=cp['devices'][topic_no_all]['points'])
        #
        #         # Build a dictionary to easily update the status of our device
        #         # health.
        #         update = dict(last_publish_utc=last_publish_utc,
        #                       health=status.as_dict())
        #         device_health.update(update)
        #         # Might need to provide protection around these three lines
        #         data = self.vip.config.get(config_name)
        #         data.update(cp)
        #         self.vip.config.set(config_name, cp)
        #
        #     # Subscribe to the vcp instance for device publishes.
        #     connection.server.vip.pubsub.subscribe('pubsub', 'devices',
        #                                            ondevicemessage)

    def _recheck_connection(self):
        """
        The recheck_connection function is scheduled to run and monitors whether
        we have a valid connection to the external instance and if the
        platform.agent is connected at the present time.
        """
        self._log.debug("Rechecking connection state.")
        if self._recheck_connection_event:
            self._recheck_connection_event.kill()

        try:
            if self._connection.is_peer_connected():
                if not self._is_managed:
                    self._manage()
                if self._last_time_verified_connection:
                    self._health.update_status(GOOD_STATUS,
                                               "Connected to platform.")
                self._last_time_verified_connection = get_utc_seconds_from_epoch()
                self._log.debug('platform.agent is connected to remote instance')
            else:
                self._is_managed = False
                self._raise_event("UNMANAGED", data=dict(
                    address=self._address,
                    address_hash=self._address_hash))
                self._log.debug(
                    'platform.agent is not connected to remote instance.')

        except gevent.Timeout:
            self._log.debug(
                'Connection has timed out attempting to connect to peers.')
            try:
                if self._connection is None:
                    self._connect()
            except gevent.Timeout:
                # Here we are going to eat the exception as it won't help us.
                # the _connect object
                pass

        # For now we are going to schedule this for 10 second periods of
        # checking for connections.
        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(
            seconds=10)

        self._scheduled_connection_event = self._vc.core.schedule(
            next_update_time, self._recheck_connection)
