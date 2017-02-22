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

from volttron.platform import jsonrpc
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now, \
    get_utc_seconds_from_epoch
from volttron.platform.jsonrpc import INVALID_PARAMS, UNAVAILABLE_PLATFORM, \
    INTERNAL_ERROR, RemoteError
from volttron.platform.messaging.health import Status, UNKNOWN_STATUS, \
    GOOD_STATUS, BAD_STATUS
from volttron.platform.vip.agent import Unreachable
from volttron.platform.vip.agent.utils import build_connection
from zmq.utils import jsonapi


class Platforms(object):
    """
    A class to manage the connections and interactions with external instances.
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

    def add_platform(self, vip_identity):
        """
        Add a platform based upon the vip_identity to the "known list" of
        platforms.

        :param vip_identity:
        :return:
        """
        self._platforms[vip_identity] = PlatformHandler(self._vc, vip_identity)
        self._debug_platform_list()

    def disconnect_platform(self, vip_identity):
        """
        Remove a platform based upon vip_identity from the "known list" of
        platforms.

        :param vip_identity:
        :return:
        """
        del self._platforms[vip_identity]
        self._debug_platform_list()

    def get_platform_keys(self):
        """
        Get the "known list" of connected vcp platforms.  This returns a set of
        keys that are available.

        :return:
        """
        return set(self._platforms.keys())

    def _debug_platform_list(self):
        """
        Echo out the platforms that are currently "known" to the
        volttron.central instance.
        """
        self._log.debug("Currently monitoring platforms")
        for k, o in self._platforms.items():
            self._log.debug("vip: {}, identity: {}".format(o.address,
                                                           o.vip_identity))
    @property
    def vc(self):
        return self._vc

    def is_registered(self, platform_vip_identity):
        """
        Returns true if the platform is currently known.

        :type platform_vip_identity: basestring
        :rtype: Boolean
        :return: Whether the platform is known or not.
        """
        # Make sure that the platform is known.
        return platform_vip_identity in self._platforms

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
                dict(uuid=x.vip_identity,
                     name=x.display_name,
                     health=x.health)
            )

        return results

    def get_performance_list(self, session_user, params):
        """
        Retrieve a list of all of the platforms stats available.

        This function returns a list of platform status such as the following::

            [
                {
                    "topic": "datalogger/platforms/f6e675fb36989f97c3b0f25227aaf02e/status/cpu",
                    "last_published_utc": "2017-01-12T18:58:47.894296+00:00",
                    "points":
                    [
                        "times_percent/guest_nice",
                        "times_percent/system",
                        "percent",
                        "times_percent/irq",
                        "times_percent/steal",
                        "times_percent/user",
                        "times_percent/nice",
                        "times_percent/iowait",
                        "times_percent/idle",
                        "times_percent/guest",
                        "times_percent/softirq"
                    ]
                },
            ...
            ]

        :param session_user:
        :param params:
        :return: dictionary containing lookup topic and last publish time.
        """
        performances = []
        for p in self._platforms.values():
            performances.append(
                {
                    "platform.uuid": p.vip_identity,
                    "performance": p.get_stats("status/cpu")
                }
            )
        return performances

    def get_platform_hashes(self):
        """
        Returns a list of all the address hashes that are currently registered
        with VC.

        :return: list of str
        """
        return self._platforms.keys()

    def get_platform(self, vip_identity, default=None):
        """
        Get a specific :ref:`PlatformHandler` associated with the passed
        address_hash.  If the hash is not available then the default parameter
        is returned.

        :param address_hash: string associated with a specific platform
        :param default: a default to be returned if not in the collection.
        :return: a :ref:`PlatformHandler` or default
        """
        return self._platforms.get(vip_identity, default)

    def register_platform(self, address, address_type, serverkey=None,
                          display_name=None):
        """
        Allows an volttron central platform (vcp) to register with vc.  Note
        that if the address has already been used then the same
        PlatformHandler object reference will be returned to the caller.

        :param address:
            An address or resolvable domain name with port.
        :param address_type:
            A string consisting of ipc or tcp.
        :param: serverkey: str:
            The router publickey for the vcp attempting to register.
        :param: display_name: str:
            The name to be shown in volttron central.
        :returns: platform_hash and platform object as a tuple.
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

    def _on_platform_message(self,peer, sender, bus, topic, headers, message):
        self._log.debug("PLATFORM MESSAGE: {}".format(message))

    def __init__(self, vc, vip_identity):
        # This is the identity of the vcp agent connected to the
        # volttron.central instance.
        self._log = logging.getLogger(self.__class__.__name__)
        self._vip_identity = vip_identity
        self._vc = vc
        self._external_vip_addresses = self._vc.vip.rpc.call(
            peer=vip_identity,
            method='get_vip_addresses').get(timeout=30)
        self._instance_name = self._vc.vip.rpc.call(
            peer=vip_identity,
            method='get_instance_name').get(timeout=30)
        message = "Building handler for platform: {} from address: {}".format(
            self._instance_name,
            self._external_vip_addresses
        )
        self._log.info(message)

        self._vc.vip.pubsub.subscribe(
            'pubsub',
            "platforms/{}".format(self.vip_identity),
            self._on_platform_message)

        self._vc.vip.rpc.call(self.vip_identity,
                              "subscribe_to_vcp",
                              "platforms/{}".format(self.vip_identity))

    # def __init__(self, platforms, address, address_type, serverkey=None,
    #              display_name=None):
    #     """
    #     Constructs a platform and attempts to connect it up with the
    #     an instance containing a vcp agent.
    #
    #     :param platforms: A platforms object.
    #     """
    #     self._platforms = platforms
    #     self._vc = self.platforms.vc
    #     self._address = address
    #     self._serverkey = serverkey
    #     self._display_name = display_name
    #     self._address_type = address_type
    #     self._address_hash = PlatformHandler.address_hasher(address)
    #     self._connection = None
    #     self._log = logging.getLogger(self.__class__.__name__)
    #     self._is_managed = False
    #     self._last_time_verified_connection = None
    #     self._event_listeners = set()
    #     self._health = Status.build(UNKNOWN_STATUS, "Initial Status")
    #     self._recheck_connection_event = None
    #     self._connect()
    #     self._recheck_connection()

    @property
    def vip_identity(self):
        return self._vip_identity

    @property
    def display_name(self):
        return self._instance_name

    @property
    def address(self):
        return self._external_vip_addresses[0]

    @property
    def config_store_name(self):
        """
        Each platform has a specific entry for its data.  In order to get that
        entry the config store needs a config name.  This property returns the
        config store name for this platform.

        :return: config store name
        :rtype: str
        """
        return "platforms/{}".format(self.vip_identity)

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
        self._health = Status.build(
            GOOD_STATUS,
            "Platform here!"
        )
        # if now > self._last_time_verified_connection + 10:
        #     self._health = Status.build(
        #         BAD_STATUS,
        #         "Platform hasn't been reached in over 10 seconds.")
        return self._health.as_dict()

    def call(self, platform_method, *args, **kwargs):

        peer = kwargs.pop('peer', self.vip_identity)
        self._log.debug("Platform handler call peer: {} method: {}, args: {}, kwargs: {}".format(
            peer, platform_method, args, kwargs
        ))
        return self._vc.vip.rpc.call(
            peer=peer,
            method=platform_method, *args, **kwargs).get(timeout=20)

    def status_agents(self, session_user, params):
        return self.call("status_agents")

    def store_agent_config(self, session_user, params):
        required = ('agent_identity', 'config_name', 'raw_contents')
        message_id = params.pop('message_id')
        errors = []
        for r in required:
            if r not in params:
                errors.append('Missing {}'.format(r))
        config_type = params.get('config_type', None)
        if config_type:
            if config_type not in ('raw', 'json', 'csv'):
                errors.append('Invalid config_type parameter')

        if errors:
            return jsonrpc.json_error(message_id, INVALID_PARAMS,
                                      "\n".join(errors))
        try:
            self._log.debug("Calling store_agent_config on external platform.")
            self.call("store_agent_config", **params)
        except Exception as e:
            self._log.error(str(e))
            return jsonrpc.json_error(message_id, INTERNAL_ERROR,
                                      str(e))
        config_name = params.get("config_name")
        agent_identity = params.get("agent_identity")
        if config_name.startswith("devices"):
            # Since we start with devices, we assume that we are attempting
            # to save a master driver config file.
            rawdict = jsonapi.loads(params['raw_contents'])

            # if this is not a bacnet device_type then we cannot do anything
            # more than save and retrieve it from the store.
            driver_type = rawdict.get('driver_type', None)
            if driver_type is None or driver_type not in ('bacnet', 'modbus'):
                return jsonrpc.json_result(message_id, "SUCCESS")

            # Registry config starts with config://
            registry_config = rawdict['registry_config'][len('config://'):]

            try:
                self._log.debug("Retrieving registry_config for new device.")
                point_config = self.call("get_agent_config",
                                                     agent_identity,
                                                     registry_config, raw=False)
            except Exception as e:
                self._log.error(str(e))
                return jsonrpc.json_error(message_id, INTERNAL_ERROR,
                                          "Couldn't retrieve registry_config "
                                          "from connection.")
            else:
                new_device = dict(
                    device_address=rawdict['driver_config']['device_address'],
                    device_id=rawdict['driver_config']['device_id'],
                    points=[],
                    path=config_name,
                    health=Status.build(UNKNOWN_STATUS,
                                        context="Unpublished").as_dict()
                )
                points = [p['Volttron Point Name'] for p in point_config]
                new_device['points'] = points
                self._vc.send_management_message("NEW_DEVICE", new_device)

            self._log.debug('Updating device store for new device.')
            # Update the devices store for get_devices function call.
            try:
                platform_store = self._vc.vip.config.get(self.config_store_name)
            except KeyError:
                return jsonrpc.json_error(message_id,  INTERNAL_ERROR, 
                                          "Platform store doesns't exist!")
            status = Status.build(UNKNOWN_STATUS,
                                  context="Not published since update")
            device_config_name = params.get('config_name')
            device_no_prefix = device_config_name[len('devices/'):]
            devices_health = platform_store.get('devices_health', {})

            devices_health[device_no_prefix] = dict(
                last_publish_utc=None,
                health=status.as_dict(),
                points=devices_health.get("points", points)
            )
            platform_store['devices_health'] = devices_health
            self._vc.vip.config.set(self.config_store_name, platform_store)
            return jsonrpc.json_result(message_id, "SUCCESS")

    def get_agent_list(self, session_user, params):
        self._log.debug('Callling list_agents')
        agents = self.call('list_agents')

        if agents is None:
            self._log.warn('No agents found for vcp: {} ({})'.format(
                self.vip_identity, self.address
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
                self._log.debug('Permissionse for {} are {}'
                                .format(a['name'], a['permissions']))
        return agents

    def get_agent_config_list(self, session_user, params):
        agent_identity = params['agent_identity']
        return self.call('list_agent_configs', agent_identity)

    def get_agent_config(self, session_user, params):
        agent_identity = params['agent_identity']
        config_name = params['config_name']
        raw = params.get('raw', True)

        try:
            return self.call('get_agent_config', agent_identity,
                                         config_name, raw)
        except KeyError:
            self._log.error('Invalid configuration name: {}'.format(
                config_name
            ))

        return ""

    def get_devices(self, session_user, params):
        self._log.debug('handling get_devices platform: {} ({})'.format(
            self.vip_identity, self.address))

        try:
            platform_store = self._vc.vip.config.get(self.config_store_name)
        except KeyError:
            self._log.warn('Unknown platform platform_uuid specified! {}'.format(
                self.vip_identity))
        else:
            try:
                return platform_store['devices_health'].copy()
            except KeyError:
                return {}

    def get_stats(self, stat_type):
        # TODO Change so stat_type is available.
        if stat_type != 'status/cpu':
            self._log.warn('The only stats available are cpu stats currently')

        try:
            config = self._vc.vip.config.get(self.config_store_name)
            return config['stats']['status/cpu']
        except KeyError:
            self._log.warn('Performance status for {} not found'.format(
                self.config_store_name))
            return {}

    def add_event_listener(self, callback):
        self._event_listeners.add(callback)

    def route_to_agent_method(self, id, agent_method, params):
        try:
            self._log.debug('route_to_agent_method {} {}'.format(id, agent_method))
            resp = self.call('route_to_agent_method', id, agent_method,
                                         params)
            if isinstance(resp, dict):
                if 'result' not in resp and 'error' not in resp:
                    resp = jsonrpc.json_result(id, resp)
            else:
                resp = jsonrpc.json_result(id, resp)
            return resp
        except RemoteError as e:
            return jsonrpc.json_error(id, INTERNAL_ERROR,
                                      "Internal Error: {}".format(str(e)))

    def _raise_event(self, type, data={}):
        self._log.debug('RAISING EVENT: {} {}'.format(type, data))
        for listener in self._event_listeners:
            listener(type, data)

    # def _manage(self):
    #     """
    #     Attempt to call the manage function on the external instance's VCP
    #     agent.
    #
    #     This will only happen if we have a connection and the platform.agent
    #     is connected.
    #     """
    #     try:
    #         if self._connection is not None and \
    #                 self._connection.is_peer_connected():
    #             public_address = self._vc.runtime_config['local_external_address']
    #             my_address = self._vc.runtime_config['local_external_address']
    #             self._log.debug('Calling manage with vc address: {}'.format(
    #                 public_address
    #             ))
    #             pk = self._connection.call('manage', my_address)
    #             self._raise_event("MANAGED", data=dict(
    #                 address=self._address,
    #                 address_hash=self._address_hash))
    #             status = self._connection.call('health.get_status')
    #             status.pop('last_updated', None)
    #             self._health = Status.build(**status)
    #     except gevent.Timeout:
    #         self._log.error(
    #             'RPC call to manage did not return in a timely manner.')
    #         raise
    #     else:
    #         self._is_managed = True

    def _on_heartbeat(self, peer, sender, bus, topic, headers, message):
        self._log.debug("HEARTBEAT MESSAGE: {}".format(message))

    def _on_device_message(self, peer, sender, bus, topic, headers, message):
        """
        Handle device data coming from the platform represented by this
        object.

        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        """
        # Update the devices store for get_devices function call.
        try:
            platform_store = self._vc.vip.config.get(self.config_store_name)
        except KeyError:
            self._log.error("unknown config store named: {}".format(
                self.config_store_name))
        else:
            ts = format_timestamp(get_aware_utc_now())
            context = "Last received data on: {}".format(ts)
            status = Status.build(GOOD_STATUS, context=context)

            base_topic = topic[:-len('/all')]
            base_topic_no_prefix = base_topic[len('devices/'):]

            devices_health = platform_store.get('devices_health', {})

            self._log.debug(message[0])
            points = [k for k, v in message[0].items()]
            self._log.debug([k for k, v in message[0].items()])

            devices_health[base_topic_no_prefix] = dict(
                last_publish_utc=None,
                health=status.as_dict(),
                points=points
            )

            platform_store['devices_health'] = devices_health
            self._vc.vip.config.set(self.config_store_name, platform_store)
            self._vc.send_management_message(
                "DEVICE_STATUS_UPDATED", data=dict(context=context,
                                                   topic=base_topic))

    def _on_platform_stats(self, peer, sender, bus, topic, headers, message):

        # This method publishes back to the message bus at
        # datalogger/platforms/platform_hash so if it starts with platforms
        # then ignore the publish.
        if topic.startswith("datalogger/platforms"):
            return

        prefix = "datalogger/platform"
        which_stats = topic[len(prefix)+1:]
        self._log.debug("WHICH STATS: {}".format(which_stats))
        point_list = []

        for point, item in message.iteritems():
            point_list.append(point)

        # Note adding the s to the end of the prefix.
        platforms_topic = "{}/{}/{}".format(prefix+"s",
                                            self.vip_identity, which_stats)

        stat_dict = {
            'topic': platforms_topic,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        config = deepcopy(self._vc.vip.config.get(self.config_store_name))
        stats = config.get('stats')
        if not stats:
            stats = config['stats'] = {}

        stats[which_stats] = stat_dict

        self._vc.vip.config.set(self.config_store_name, config)
        self._vc.vip.pubsub.publish('pubsub', topic=platforms_topic,
                                    headers=headers, message=message)

    def _on_platform_message(self, peer, sender, bus, topic, headers, message):

        self._log.debug("MESSAGE: {}".format(message))
        point_list = []

        for point, item in message.iteritems():
            point_list.append(point)

        stats = {
            'topic': topic,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        config = deepcopy(self._vc.vip.config.get(self.config_store_name))
        config['stats_point_list'] = stats
        self._vc.vip.config.set(self.config_store_name, config)

    def _on_stats_published(self, peer, sender, bus, topic, headers, message):
        self._log.debug('STATS PUBLISHERD: {}'.format(message))

    # def _connect(self):
    #     """
    #     Connects to the remote instance.  If unsuccessful raises a
    #     gevent.Timeout error.
    #     """
    #
    #     publickey = self._vc.core.publickey
    #     secretkey = self._vc.core.secretkey
    #
    #     # First attempt to connect to the external instance.  The instance
    #     # doesn't have to have the VCP on it for the connection to be
    #     # established.  However it will need to have it on in order to
    #     # execute any rpc methods on it.
    #     try:
    #         self._connection = build_connection(
    #             identity=self.external_vip_identity,
    #             peer=VOLTTRON_CENTRAL_PLATFORM,
    #             address=self._address,
    #             serverkey=self._serverkey,
    #             publickey=publickey,
    #             secretkey=secretkey)
    #     except gevent.Timeout:
    #         self._log.error("Unable to connect to instance.")
    #         if self._connection is not None:
    #             self._connection.kill()
    #             self._connection = None
    #         raise
    #     else:
    #         self._raise_event("CONECTED", data=dict(
    #             address=self._address,
    #             address_hash=self._address_hash))
    #         self._connection.subscribe('devices', self._on_device_message)
    #         self._connection.subscribe('datalogger/platform',
    #                                    self._on_platform_stats)



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
        # if self._recheck_connection_event:
        #     self._recheck_connection_event.kill()
        #
        # try:
        #     if self._connection.is_peer_connected():
        #         if not self._is_managed:
        #             self._manage()
        #
        #         if self._last_time_verified_connection:
        #             self._health.update_status(GOOD_STATUS,
        #                                        "Connected to platform.")
        #         self._last_time_verified_connection = get_utc_seconds_from_epoch()
        #         self._log.debug('platform.agent is connected to remote instance')
        #     else:
        #         self._is_managed = False
        #         self._raise_event("UNMANAGED", data=dict(
        #             address=self._address,
        #             address_hash=self._address_hash))
        #         self._log.debug(
        #             'platform.agent is not connected to remote instance.')
        #
        # except gevent.Timeout:
        #     self._log.debug(
        #         'Connection has timed out attempting to connect to peers.')
        #     try:
        #         if self._connection is None:
        #             self._connect()
        #     except gevent.Timeout:
        #         # Here we are going to eat the exception as it won't help us.
        #         # the _connect object
        #         pass
        #
        # # For now we are going to schedule this for 10 second periods of
        # # checking for connections.
        # now = get_aware_utc_now()
        # next_update_time = now + datetime.timedelta(
        #     seconds=10)
        #
        # self._scheduled_connection_event = self._vc.core.schedule(
        #     next_update_time, self._recheck_connection)
