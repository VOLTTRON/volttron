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
import datetime
import hashlib
import logging
import re
import shutil
import sys
import tempfile
import urlparse
from copy import deepcopy

import gevent
import gevent.event
import psutil
import requests
from volttron.platform import get_home
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.agent.utils import (
    get_aware_utc_now, format_timestamp, parse_timestamp_string)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS)
from volttron.platform.messaging.health import Status, \
    GOOD_STATUS, BAD_STATUS
from volttron.platform.messaging.topics import (LOGGER, PLATFORM_VCP_DEVICES,
                                                PLATFORM)
from volttron.platform.vip.agent import *
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.utils.persistance import load_create_store

__version__ = '3.5.4'

utils.setup_logging()
_log = logging.getLogger(__name__)


class NotManagedError(StandardError):
    """ Raised if vcp cannot connect to the vc trying to manage it.

    Some examples of this could be if the serverkey is not valid, if the
    tcp address is invalid, if the http address is invalid.

    Other examples could be permissions issues from auth.
    """
    pass


class VolttronCentralPlatform(Agent):
    __name__ = 'VolttronCentralPlatform'

    def __init__(self, config_path, **kwargs):
        super(VolttronCentralPlatform, self).__init__(**kwargs)

        self._local_instance_name = None
        self._local_instance_uuid = None
        self._local_serverkey = None
        self._local_bind_web_address = None
        self._external_addresses = None

        self._volttron_central_reconnect_interval = 5
        self._volttron_central_http_address = None
        self._volttron_central_tcp_address = None
        self._volttron_central_ipc_address = None
        self._volttron_central_serverkey = None
        self._volttron_central_publickey = None

        self._volttron_central_connection = None
        self._control_connection = None

        settings_path = os.path.join(get_home(), "data/vcp.settings")
        self._settings = load_create_store(settings_path)
        config = utils.load_config(config_path)
        self.reconfigure(**config)

        # Flag set after the platform has a guaranteed connection to the router.
        self._agent_started = False
        self._is_registering = False
        self._is_registered = False
        self._was_unmanaged = False

        self._devices = {}
        self._device_topic_hashes = {}

        self._topic_replace_map = {}

        # Default publish interval to 20 seconds.
        self._stats_publish_interval = 20
        self._stats_publisher = None
        if config.get('stats-publish-interval') is None:
            config['stats-publish-interval'] = self._stats_publish_interval
        if self._settings.get('instance-uuid'):
            config['instance-uuid'] = self._settings.get('instance-uuid')
        if config.get('volttron-central-reconnect-interval') is None:
            config['volttron-central-reconnect-interval'] = \
                self._volttron_central_reconnect_interval
        self._topic_replace_list = config.get("topic_replace_list", [])
        self.reconfigure(**config)

        # This is scheduled after first call to the reconnect function
        self._scheduled_connection_event = None

    @RPC.export
    def reconfigure(self, **kwargs):
        instance_name = kwargs.get('instance-name')
        instance_uuid = kwargs.get('instance-uuid')
        vc_address = kwargs.get('volttron-central-address')
        vc_serverkey = kwargs.get('volttron-central-serverkey')
        new_publish_interval = kwargs.get('stats-publish-interval')
        reconnect_interval = kwargs.get('volttron-central-reconnect-interval')

        if instance_name:
            self._local_instance_name = instance_name

        if instance_uuid:
            self._local_instance_uuid = instance_uuid

        if reconnect_interval:
            self._volttron_central_reconnect_interval = reconnect_interval

        if vc_address:
            parsed = urlparse.urlparse(vc_address)
            if parsed.scheme in ('http', 'https'):
                self._volttron_central_http_address = vc_address
            elif parsed.scheme == 'tcp':
                self._volttron_central_tcp_address = vc_address
            elif parsed.scheme == 'ipc':
                self._volttron_central_ipc_address = vc_address
            else:
                raise ValueError('Invalid volttron central address.')

        if vc_serverkey:
            if self._volttron_central_tcp_address:
                self._volttron_central_serverkey = vc_serverkey
            else:
                raise ValueError('Invalid volttron central tcp address.')

        if new_publish_interval is not None:
            if int(self._stats_publish_interval) < 20:
                raise ValueError(
                    "stats publishing must be greater than 20 seconds.")
            self._stats_publish_interval = new_publish_interval
            self._start_stats_publisher()

    def _periodic_attempt_registration(self):
        if not self._started:
            _log.error('NOT STARTED!')
            return
        if self._scheduled_connection_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._scheduled_connection_event.cancel()

        try:
            vc = self._vc_connection()
            if vc is None:
                _log.debug("vc not connected")
                return

            if not self._is_registering and not self._is_registered and \
                    not self._was_unmanaged:
                _log.debug("Starting the registration process from vcp.")
                _log.debug("Instance is named: {}".format(
                    self._local_instance_name
                ))
                _log.debug('vc.address is: {}'.format(vc.address))
                if vc.address.startswith('ipc'):
                    self._vc_connection().call(
                        "register_instance",
                        address=self.core.address,
                        display_name=self._local_instance_name,
                        serverkey=self._local_serverkey,
                        vcpagentkey=self.core.publickey
                    )
                else:
                    self._vc_connection().call(
                        "register_instance",
                        address=self._external_addresses[0],
                        display_name=self._local_instance_name,
                        serverkey=self._local_serverkey,
                        vcpagentkey=self.core.publickey
                    )
            else:
                _log.debug(
                    "is registering: {}, is_registered: {}, was unmanaged {}"
                        .format(
                            self._is_registering, self._is_registered,
                            self._was_unmanaged
                ))
        except Unreachable as e:
            _log.error("Couldn't connect to volttron.central. {}".format(
                self._volttron_central_tcp_address
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
                seconds=self._volttron_central_reconnect_interval)

            self._scheduled_connection_event = self.core.schedule(
                next_update_time, self._periodic_attempt_registration)

    def _vc_connection(self):
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

        assert self._agent_started, "cannot be called before onstart signal"

        if self._volttron_central_connection:
            # if connected return the connection.
            if self._volttron_central_connection.is_connected(5):
                _log.debug('Returning connection')
                return self._volttron_central_connection

            _log.debug("Resetting connection as the peer wasn't responding.")
            # reset the connection so we can try it again below.
            self._volttron_central_connection.kill()
            self._volttron_central_connection = None

        # First check to see if there is a peer with a volttron.central
        # identity, if there is use it as the manager of the platform.
        peers = self.vip.peerlist().get(timeout=5)
        if VOLTTRON_CENTRAL in peers:
            _log.debug('VC is a local peer.')
            self._volttron_central_connection = Connection(
                self.core.address, VOLTTRON_CENTRAL
            )
            if self._volttron_central_connection.is_connected() and \
                    self._volttron_central_connection.is_peer_connected():
                _log.debug("Connection has been established to local peer.")
            return self._volttron_central_connection

        # If we have an http address for volttron central, but haven't
        # looked up the address yet, then look up and set the address from
        # volttron central discovery.
        if self._volttron_central_http_address is not None and \
                        self._volttron_central_tcp_address is None and \
                        self._volttron_central_serverkey is None:

            _log.debug('Using discovery to lookup tcp connection')

            response = requests.get(
                "{}/discovery/".format(self._volttron_central_http_address)
            )

            if response.ok:
                jsonresp = response.json()
                entry = AuthEntry(credentials="/.*/",
                                  capabilities=['manager']
                                  #,
                                  #address=jsonresp['vip-address']
                                  )
                authfile = AuthFile(get_home() + "/auth.json")
                authfile.add(entry, overwrite=True)
                self._volttron_central_tcp_address = jsonresp['vip-address']
                self._volttron_central_serverkey = jsonresp['serverkey']

        # First see if we are able to connect via tcp with the serverkey.
        if self._volttron_central_tcp_address is not None and \
                self._volttron_central_serverkey is not None:
            _log.debug('Connecting to volttron central using tcp.')

            vc_conn = Connection(
                address=self._volttron_central_tcp_address,
                peer=VOLTTRON_CENTRAL,
                serverkey=self._volttron_central_serverkey,
                publickey=self.core.publickey,
                secretkey=self.core.secretkey
            )

            if not vc_conn.is_connected(5):
                raise ValueError(
                    "Unable to connect to remote platform")

            if not vc_conn.is_peer_connected(5):
                raise ValueError(
                    "Peer: {} unavailable on remote platform.".format(
                        VOLTTRON_CENTRAL))

            #TODO Only add a single time for this address.
            if self._volttron_central_publickey:
                # Add the vcpublickey to the auth file.
                entry = AuthEntry(
                    credentials= self._volttron_central_publickey,
                    capabilities=['manager'])
                authfile = AuthFile()
                authfile.add(entry, overwrite=True)

            self._volttron_central_connection = vc_conn

            return self._volttron_central_connection

        # Next see if we have a valid ipc address (Not Local though)
        if self._volttron_central_ipc_address is not None:
            self._volttron_central_connection = Connection(
                address=self._volttron_central_ipc_address,
                peer=VOLTTRON_CENTRAL
            )

            return self._volttron_central_connection

    @Core.receiver('onstart')
    def _started(self, sender, **kwargs):

        # Created a link to the control agent on this platform.
        self._control_connection = Connection(address=self.core.address,
                                              peer='control')

        _log.debug('Querying router for addresses and serverkey.')
        q = Query(self.core)

        self._external_addresses = q.query('addresses').get(timeout=2)
        _log.debug('External addresses are: {}'.format(
            self._external_addresses))

        self._local_serverkey = q.query('serverkey').get(timeout=2)
        _log.debug('serverkey is: {}'.format(self._local_serverkey))

        vc_http_address = q.query('volttron-central-address').get(timeout=2)
        _log.debug('vc address is {}'.format(vc_http_address))

        self._local_instance_name = q.query('instance-name').get(timeout=2)
        _log.debug('instance-name is {}'.format(self._local_instance_name))

        if vc_http_address is not None:
            parsed = urlparse.urlparse(vc_http_address)
            if parsed.scheme in ('https', 'http'):
                self._volttron_central_http_address = vc_http_address
            elif parsed.scheme == 'ipc':
                self._volttron_central_ipc_address = vc_http_address
            elif parsed.scheme == 'tcp':
                self._volttron_central_tcp_address = vc_http_address
                vc_serverkey = q.query('volttron-central-serverkey').get(
                    timeout=2
                )
                if vc_serverkey is None:
                    raise ValueError(
                        'volttron-central-serverkey is not set with tcp address'
                    )
                self._volttron_central_serverkey = vc_serverkey
            else:
                raise ValueError(
                    'invalid scheme for volttron-central-address'
                )

        self._agent_started = True

        _log.debug('Starting the period registration attempts.')
        # Start the process of attempting registration with a VOLTTRON central.
        self._periodic_attempt_registration()

        try:
            _log.debug('Starting stats publisher.')
            self._start_stats_publisher()
        except ValueError as e:
            _log.error(e)

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
    def get_instance_uuid(self):
        return self._local_instance_uuid

    @RPC.export
    def get_manager_key(self):
        return self._volttron_central_publickey

    @RPC.export
    def manage(self, address, vcserverkey=None, vcpublickey=None):
        """ Allows the `VolttronCentralPlatform` to be managed.

        From the web perspective this should be after the user has specified
        that a user has blessed an agent to be able to be managed.

        When the user enters a discovery address in `VolttronCentral` it is
        implied that the user wants to manage a platform.

        :returns publickey of the `VolttronCentralPlatform`
        """
        _log.info('Manage request from address: {} serverkey: {}'.format(
            address, vcserverkey))

        self._was_unmanaged = False

        parsed = urlparse.urlparse(address)
        same_address = False
        if parsed.scheme == 'ipc':
            if self._volttron_central_ipc_address == address:
                same_address = True
            self._volttron_central_ipc_address = address
        elif parsed.scheme == 'tcp':
            _log.debug('Found tcp scheme adding AuthEntry')
            if self._volttron_central_tcp_address == address:
                same_address = True
            self._volttron_central_tcp_address = address
            self._volttron_central_serverkey = vcserverkey

            # Add the vcpublickey to the auth file.
            entry = AuthEntry(
                credentials=vcpublickey,
                capabilities=['manager'])  # , address=parsedaddress.hostname)
            authfile = AuthFile()
            authfile.add(entry)

        else:
            raise AttributeError('Invalid scheme in address')

        if self._vc_connection() is not None:
            self._is_registered = True
            self._is_registering = False
            _log.debug("Returning publickey from manage function.")
            return self.core.publickey

        raise NotManagedError("Could not connect to specified volttron central")

    @RPC.export
    def unmanage(self):
        self._is_registering = False
        self._is_registered = False
        self._was_unmanaged = True

    @RPC.export
    # @RPC.allow("manager") #TODO: uncomment allow decorator
    def list_agents(self):
        """ List the agents that are installed on the platform.

        Note this only lists the agents that are actually installed on the
        instance.

        :return: A list of agents.
        """
        return self._get_agent_list()

    @RPC.export
    # @RPC.allow("can_manage")
    def start_agent(self, agent_uuid):
        self._control_connection.call("start_agent", agent_uuid)

    @RPC.export
    # @RPC.allow("can_manage")
    def stop_agent(self, agent_uuid):
        proc_result = self._control_connection.call("stop_agent", agent_uuid)

    @RPC.export
    # @RPC.allow("can_manage")
    def restart_agent(self, agent_uuid):
        self._control_connection.call("restart_agent", agent_uuid)
        gevent.sleep(0.2)
        return self.agent_status(agent_uuid)

    @RPC.export
    def agent_status(self, agent_uuid):
        return self._control_connection.call("agent_status", agent_uuid)

    @RPC.export
    def status_agents(self):
        return self._control_connection.call('status_agents')

    @RPC.export
    def get_device(self, topic):
        _log.debug('Get device for topic: {}'.format(topic))
        return self._devices.get(topic)

    @PubSub.subscribe('pubsub', 'devices')
    def _on_device_message(self, peer, sender, bus, topic, headers, message):
        # only deal with agents that have not been forwarded.
        if headers.get('X-Forwarded', None):
            return

        # only listen to the ending all message.
        if not re.match('.*/all$', topic):
            return

        topicsplit = topic.split('/')

        # For devices we use everything between devices/../all as a unique
        # key for determining the last time it was seen.
        key = '/'.join(topicsplit[1: -1])

        anon_topic = self._topic_replace_map.get(key)
        publish_time_utc = format_timestamp(get_aware_utc_now())

        if not anon_topic:
            anon_topic = key

            for sr in self._topic_replace_list:
                _log.debug(
                    'anon replacing {}->{}'.format(sr['from'], sr['to']))
                anon_topic = anon_topic.replace(sr['from'],
                                                sr['to'])
            _log.debug('anon after replacing {}'.format(anon_topic))
            _log.debug('Anon topic is: {}'.format(anon_topic))
            self._topic_replace_map[key] = anon_topic
            _log.debug('Only anon topics are being listed.')

        hashable = anon_topic + str(message[0].keys())
        _log.debug('Hashable is: {}'.format(hashable))
        md5 = hashlib.md5(hashable)
        # self._md5hasher.update(hashable)
        hashed = md5.hexdigest()

        self._device_topic_hashes[hashed] = anon_topic
        self._devices[anon_topic] = {
            'points': message[0].keys(),
            'last_published_utc': publish_time_utc,
            'md5hash': hashed
        }

        vc = self._vc_connection()
        if vc is not None:
            message = dict(md5hash=hashed, last_publish_utc=publish_time_utc)

            if self._local_instance_uuid is not None:
                vcp_topic = PLATFORM_VCP_DEVICES(
                    platform_uuid=self._local_instance_uuid,
                    topic=anon_topic
                )
                vc.publish(vcp_topic.format(), message=message)
            else:
                local_topic = PLATFORM(
                    subtopic="devices/{}".format(anon_topic))
                self.vip.pubsub.publish("pubsub", local_topic, message=message)

            _log.debug('Devices: {} Hashes: {} Platform: {}'.format(
                len(self._devices), self._device_topic_hashes,
                self._local_instance_name))

    @RPC.export
    def get_devices(self):
        cp = deepcopy(self._devices)
        foundbad = False

        for k, v in cp.items():
            dt = parse_timestamp_string(v['last_published_utc'])
            dtnow = get_aware_utc_now()
            if dt+datetime.timedelta(minutes=5) < dtnow:
                v['health'] = Status.build(
                    BAD_STATUS,
                    'Too long between publishes for {}'.format(k)).as_dict()
                foundbad = True
            else:
                v['health'] = Status.build(GOOD_STATUS).as_dict()

        if len(cp):
            if foundbad:
                self.vip.health.set_status(
                    BAD_STATUS,
                    'At least one device has not published in 5 minutes')
            else:
                self.vip.health.set_status(
                    GOOD_STATUS,
                    'All devices publishing normally.'
                )
        return cp

    @RPC.export
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
                                 self._control_connection.call(method)]}

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
                status = self._control_connection.call(method, uuid)
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
                # find the identity of the agent so we can call it by name.
                identity = self._control_connection.call('agent_vip_identity', agent_uuid)
                if params:
                    if isinstance(params, list):
                        result = self.vip.rpc.call(identity, agent_method, *params).get(timeout=30)
                    else:
                        result = self.vip.rpc.call(identity, agent_method, **params).get(timeout=30)
                else:
                    result = self.vip.rpc.call(identity, agent_method).get(timeout=30)

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
                uuid = self.vip.rpc.call('control', 'install_agent_local', path).get()

            except Exception as e:
                results.append({'error': str(e)})
                _log.error("EXCEPTION: " + str(e))
            else:
                results.append({'uuid': uuid})

        shutil.rmtree(tmpdir, ignore_errors=True)

        return results

    @RPC.export
    def list_agent_methods(self, method, params, id, agent_uuid):
        return jsonrpc.json_error(ident=id, code=INTERNAL_ERROR,
                                  message='Not implemented')

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
            vc = self._vc_connection()
            if vc is not None and vc.is_connected() and vc_topic is not None:
                vc.publish(vc_topic.format(), message=points)
        except Exception as e:
            _log.info("status not written to volttron central.")
        self.vip.pubsub.publish(peer='pubsub', topic=local_topic.format(),
                                message=points)

    @Core.receiver('onstop')
    def _stoping(self, sender, **kwargs):
        if self._volttron_central_connection is not None:
            self._volttron_central_connection.kill()
            self._volttron_central_connection = None
        if self._control_connection is not None:
            self._control_connection.kill()
            self._control_connection = None
        self._is_registered = False
        self._is_registering = False

    def _get_agent_list(self):
        """ Retrieve a list of agents on the platform.

        Each entry in the list

        :return: list: A list of agent data.
        """

        agents = self._control_connection.call("list_agents")
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
                identity = self.vip.rpc.call('control', 'agent_vip_identity',
                                             a['uuid']).get(timeout=30)
                try:
                    status = self.vip.rpc.call(identity,
                                               'health.get_status').get(timeout=5)
                    uuid_to_status[a['uuid']]['health'] = status
                except gevent.Timeout:
                    _log.error("Couldn't get health from {} uuid: {}".format(
                        identity, a['uuid']
                    ))
                except Unreachable:
                    _log.error("Couldn't reach agent identity {} uuid: {}".format(
                        identity, a['uuid']
                    ))
        for a in agents:
            if a['uuid'] in uuid_to_status.keys():
                _log.debug('UPDATING STATUS OF: {}'.format(a['uuid']))
                a.update(uuid_to_status[a['uuid']])
        return agents


def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    # utils.vip_main(platform_agent)
    utils.vip_main(VolttronCentralPlatform, identity = VOLTTRON_CENTRAL_PLATFORM)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
