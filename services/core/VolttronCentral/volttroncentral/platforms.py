# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import base64
import hashlib
import logging
from collections import defaultdict

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
from volttron.platform import jsonapi


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
        encoded = base64.b64encode(vip_identity.encode('utf-8'))
        self._platforms[encoded] = PlatformHandler(self._vc, vip_identity)
        self._debug_platform_list()
        return self._platforms[encoded]

    def disconnect_platform(self, vip_identity):
        """
        Remove a platform based upon vip_identity from the "known list" of
        platforms.

        :param vip_identity:
        :return:
        """
        encoded = base64.b64encode(vip_identity.encode('utf-8'))
        del self._platforms[encoded]
        self._debug_platform_list()

    def get_platform_vip_identities(self):
        """
        Get the "known list" of connected vcp platforms.  This returns a set of
        keys that are available.

        :return:
        """
        return set([x.vip_identity for x in self._platforms.values()])

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

    def is_registered(self, platform_uuid):
        """
        Returns true if the platform is currently known.

        :type platform_vip_identity: basestring
        :rtype: Boolean
        :return: Whether the platform is known or not.
        """

        # Make sure that the platform is known.
        return platform_uuid in self._platforms

    def get_platform_list(self, session_user, params):
        """
        Retrieve the platform list and respond in a manner that can
        be sent back to the web service.

        The response will be formatted as follows:

        [
            {
                "health": {
                    "status": "GOOD",
                    "last_updated": "2017-02-24T19:18:52.723445+00:00",
                    "context": "Platform here!"
                },
                "name": "tcp://127.0.0.1:22916",
                "uuid": "vcp-f6e675fb36989f97c3b0f25227aaf02e"
            }

        ]

        :param session_user:
        :param params:
        :return: A list of dictionaries each representing a platform.
        """
        results = []
        for x in self._platforms.values():
            results.append(
                dict(uuid=base64.b64encode(x.vip_identity.encode('utf-8')),
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
                    "platform.uuid": base64.b64encode(p.vip_identity),
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
        return list(self._platforms.keys())

    def get_platform(self, platform_uuid, default=None):
        """
        Get a specific :ref:`PlatformHandler` associated with the passed
        address_hash.  If the hash is not available then the default parameter
        is returned.

        :param address_hash: string associated with a specific platform
        :param default: a default to be returned if not in the collection.
        :return: a :ref:`PlatformHandler` or default
        """
        self._debug_platform_list()
        return self._platforms.get(platform_uuid, default)

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

    def __init__(self, vc, vip_identity):

        # This is the identity of the vcp agent connected to the
        # volttron.central instance.
        self._log = logging.getLogger(self.__class__.__name__)
        self._vip_identity = vip_identity
        # References the main agent to be used to talk through to the vip
        # router.
        self._vc = vc
        # Add some logging information about the vcp platform
        self._instance_name = self.call('get_instance_name')
        self._external_vip_addresses = self.call('get_vip_addresses')

        message = "Building handler for platform: {} from address: {}".format(
            self._instance_name,
            self._external_vip_addresses
        )
        self._log.info(message)

        # Start the current devices dictionary.
        self._current_devices = defaultdict(dict)

        """
        the _current_devices structure should be what the ui uses to display
        its data. where devices/t/1/1 was the full topic this was published to.

        "t/1/1": {
            "points": [
                "Occupied"
            ],
            "health": {
                "status": "GOOD",
                "last_updated": "2017-03-02T00:38:30.347172+00:00",
                "context": "Last received data on: 2017-03-02T00:38:30.347075+00:00"
            },
            "last_publish_utc": null
        }
        """
        for k, v in self.call('get_devices').items():

            status = Status.build(UNKNOWN_STATUS,
                                  context="Unpublished").as_dict()
            self._current_devices[k]['health'] = status
            self._current_devices[k]['points'] = [p for p in v['points']]
            self._current_devices[k]['last_publish_utc'] = None

        self._platform_stats = {}

        platform_prefix = "platforms/{}/".format(self.vip_identity)

        # Setup callbacks to listen to the local bus from the vcp instance.
        #
        # Note: the platform/{}/ is prepended to the vcp_topics below for
        #   communication from the vcp in the field.
        vcp_topics = (
            # ('device_updates', self._on_device_message),
            # ('devices/update', self._on_device_message),
            # devices and status.
            # ('devices/', self._on_device_message),
            # statistics for showing performance in the ui.
            ('status', self._on_platform_stats),
            # iam and configure callbacks
            ('iam/', self._on_platform_message),
            # iam and configure callbacks
            ('configure/', self._on_platform_message)
        )

        for topic, funct in vcp_topics:
            self._vc.vip.pubsub.subscribe('pubsub',
                                          platform_prefix + topic, funct)
            self._log.info('Subscribing to {} with from vcp {}'.format(
                platform_prefix + topic, topic))

            # method will subscribe to devices/ on the collector and publish
            # the regular device topics with the prefix platform_prefix.
            self.call("subscribe_to_vcp", topic, platform_prefix)

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
        """
        Calls a method on a vcp platform.

        :param platform_method:
        :param args:
        :param kwargs:
        :return:
        """
        return self._vc.vip.rpc.call(self.vip_identity, platform_method, *args,
                                     **kwargs).get(timeout=60)

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
            self._log.error(repr(e))
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

            status = Status.build(UNKNOWN_STATUS,
                                  context="Not published since update")
            device_config_name = params.get('config_name')
            device_no_prefix = device_config_name[len('devices/'):]
            the_device = self._current_devices.get(device_no_prefix, {})

            if not the_device:
                self._current_devices[device_no_prefix] = dict(
                    last_publish_utc=None,
                    health=status.as_dict(),
                    points=points
                )
            else:
                self._current_devices[device_no_prefix]['points'] = points

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
                a['permissions'] = {
                    'can_stop': True,
                    'can_start': True,
                    'can_restart': True,
                    'can_remove': True
                }

                if a['identity'] in ('volttron.central', 'platform.agent'):
                    a['permissions']['can_stop'] = False
                    a['permissions']['can_remove'] = False

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

    def delete_agent_config(self, session_user, params):
        agent_identity = params['agent_identity']
        config_name = params['config_name']

        try:
            return self.call('delete_agent_config', agent_identity, config_name)
        except KeyError:
            self._log.error('Invalid configuration name: {}'.format(
                config_name
            ))

        return ""

    def get_devices(self, session_user, params):
        self._log.debug('handling get_devices platform: {} ({})'.format(
            self.vip_identity, self.address))
        return self.call("get_devices")
        # return self._current_devices or {}

    def get_stats(self, stat_type):
        # TODO Change so stat_type is available.
        if stat_type != 'status/cpu':
            self._log.warn('The only stats available are cpu stats currently')
            return {}

        return self._platform_stats.get(stat_type, {}).copy()

    def add_event_listener(self, callback):
        self._event_listeners.add(callback)

    def route_to_agent_method(self, id, agent_method, params):
        try:
            self._log.debug('route_to_agent_method {} {}'.format(id,
                                                                 agent_method))
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

    def _on_heartbeat(self, peer, sender, bus, topic, headers, message):
        self._log.debug("HEARTBEAT MESSAGE: {}".format(message))

    # def _on_device_message(self, peer, sender, bus, topic, headers, message):
    #     """
    #     Handle device data coming from the platform represented by this
    #     object.
    #
    #     this method only cares about the /all messages that are published to
    #     the message bus.
    #
    #     :param peer:
    #     :param sender:
    #     :param bus:
    #     :param topic:
    #     :param headers:
    #     :param message:
    #     """
    #
    #     expected_prefix = "platforms/{}/".format(self.vip_identity)
    #     self._log.debug("TOPIC WAS: {}".format(topic))
    #     self._log.debug("MESSAGE WAS: {}".format(message))
    #     self._log.debug("Expected topic: {}".format(expected_prefix))
    #     self._log.debug("Are Equal: {}".format(topic.startswith(expected_prefix)))
    #     self._log.debug("topic type: {} prefix_type: {}".format(type(topic), type(expected_prefix)))
    #     if topic is None or not topic.startswith(expected_prefix):
    #         self._log.error("INVALID DEVICE DATA FOR {}".format(self.vip_identity))
    #         return
    #
    #     if topic is None or not topic.startswith(expected_prefix):
    #         self._log.error('INVALID DEVICE TOPIC/MESSAGE DETECTED ON {}'.format(
    #             self.vip_identity
    #         ))
    #         return
    #
    #     # Update the devices store for get_devices function call
    #     if not topic.endswith('/all'):
    #         self._log.debug("Skipping publish to {}".format(topic))
    #         return
    #
    #     #
    #     topic = topic[len(expected_prefix):]
    #
    #     self._log.debug("topic: {}, message: {}".format(topic, message))
    #
    #     ts = format_timestamp(get_aware_utc_now())
    #     context = "Last received data on: {}".format(ts)
    #     status = Status.build(GOOD_STATUS, context=context)
    #
    #     base_topic = topic[:-len('/all')]
    #     base_topic_no_prefix = base_topic[len('devices/'):]
    #
    #     if base_topic_no_prefix not in self._current_devices:
    #         self._current_devices[base_topic_no_prefix] = {}
    #
    #     device_dict = self._current_devices[base_topic_no_prefix]
    #
    #     points = [k for k, v in message[0].items()]
    #
    #     device_dict['points'] = points
    #     device_dict['health'] = status.as_dict()
    #     device_dict['last_publish_utc'] = ts
    #
    #     self._vc.send_management_message(
    #         "DEVICE_STATUS_UPDATED", data=dict(context=context,
    #                                            topic=base_topic))

    def _on_platform_stats(self, peer, sender, bus, topic, headers, message):

        self._log.debug('ON PLATFORM STATUS!')
        expected_prefix = "platforms/{}/".format(self.vip_identity)

        if not topic.startswith(expected_prefix):
            self._log.warn("Unexpected topic published to stats function: {}".format(
                topic
            ))
            return

        self._log.debug("TOPIC WAS: {}".format(topic))
        self._log.debug("MESSAGE WAS: {}".format(message))
        self._log.debug("Expected topic: {}".format(expected_prefix))
        self._log.debug(
            "Are Equal: {}".format(topic.startswith(expected_prefix)))
        self._log.debug("topic type: {} prefix_type: {}".format(type(topic),
                                                                type(
                                                                    expected_prefix)))

        # Pull off the "real" topic from the prefix
        which_stats = topic[len(expected_prefix):]
        self._log.debug("WHICH STATS: {}".format(which_stats))

        prefix = "datalogger/platform"

        point_list = []

        for point, item in message.items():
            point_list.append(point)

        # Note adding the s to the end of the prefix.
        platforms_topic = "{}/{}/{}".format(prefix+"s",
                                            self.vip_identity, which_stats)

        self._platform_stats[which_stats] = {
            'topic': platforms_topic,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        self._vc.send_management_message(
            "PLATFORM_STATS_UPDATED", data=dict(
                context=self._platform_stats[which_stats],
                topic=which_stats))

        self._log.debug('Publishing to {} for ui to grab'.format(
            platforms_topic
        ))
        self._vc.vip.pubsub.publish('pubsub',
                                    topic=platforms_topic,
                                    message=message,
                                    headers=headers)

    def _on_platform_message(self,peer, sender, bus, topic, headers, message):
        """
        Callback function for vcp agent to publish to.

        Platforms that are being managed should publish to this topic with
        the agent_list and other interesting things that the volttron
        central shsould want to know.
        """
        self._log.debug('ON PLATFORM MESSAGE! {}'.format(message))
        expected_prefix = "platforms/{}/".format(self.vip_identity)

        if not topic.startswith(expected_prefix):
            self._log.warn(
                "Unexpected topic published to stats function: {}".format(
                    topic
                ))
            return

        self._log.debug("TOPIC WAS: {}".format(topic))
        self._log.debug("MESSAGE WAS: {}".format(message))
        self._log.debug("Expected topic: {}".format(expected_prefix))
        self._log.debug(
            "Are Equal: {}".format(topic.startswith(expected_prefix)))
        self._log.debug("topic type: {} prefix_type: {}".format(type(topic),
                                                                type(
                                                                    expected_prefix)))

        # Pull off the "real" topic from the prefix
        # topic = topic[len(expected_prefix):]

        topicsplit = topic.split('/')
        if len(topicsplit) < 2:
            self._log.error('Invalid topic length published to volttron central')
            return

        # Topic is platforms/<platform_uuid>/otherdata
        topicsplit = topic.split('/')

        if len(topicsplit) < 3:
            self._log.warn("Invalid topic length no operation or datatype.")
            self._log.warn("Topic was {}".format(topic))
            return

        _, platform_uuid, op_or_datatype, other = topicsplit[0], \
                                                  topicsplit[1], \
                                                  topicsplit[2], \
                                                  topicsplit[3:]

        if op_or_datatype in ('iam', 'configure'):
            if not other:
                self._log.error("Invalid response to iam or configure endpoint")
                self._log.error(
                    "the sesson token was not included in response from vcp.")
                return

            ws_endpoint = "/vc/ws/{}/{}".format(other[0], op_or_datatype)
            self._log.debug('SENDING MESSAGE TO {}'.format(ws_endpoint))
            self._vc.vip.web.send(ws_endpoint, jsonapi.dumps(message))
        else:
            self._log.debug("OP WAS: {}".format(op_or_datatype))
