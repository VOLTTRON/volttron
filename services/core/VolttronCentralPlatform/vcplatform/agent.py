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

from copy import deepcopy
import datetime
import gevent.event
import logging
import json
import re
import sys
import urlparse

import gevent
import psutil
from volttron.platform.agent.utils import (
    get_aware_utc_now, format_timestamp, parse_timestamp_string)
from volttron.platform.messaging.topics import LOGGER
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *

from volttron.platform import jsonrpc
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    MASTER_WEB, VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.messaging.health import UNKNOWN_STATUS, Status, \
    GOOD_STATUS, BAD_STATUS
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       METHOD_NOT_FOUND)
from volttron.platform.web import (DiscoveryInfo, DiscoveryError)

__version__ = '3.5.1'


class CannotConnectError(StandardError):
    """ Raised if the connection parameters are not set or invalid
    """
    pass


class AlreadyManagedError(StandardError):
    """ Raised when a different volttron central tries to register.n
    """
    pass

_log = logging.getLogger(__name__)


class VolttronCentralPlatform(Agent):
    __name__ = 'PlatformAgent'

    def __init__(self, config_path, **kwargs):

        self._config = utils.load_config(config_path)
        self._vc_discovery_address = None
        self._my_discovery_address = None
        self._agent_connected_to_vc = None
        self._vc_info = None
        self._managed = False

        # This is set from the volttron central instance (NOTE:this is not
        # the same as the installed uuid on this volttron instance0).
        self._platform_uuid = None

        # A dictionary of devices that are published by the platform.
        self._devices = {}

        identity = kwargs.pop('identity', None)
        identity = VOLTTRON_CENTRAL_PLATFORM
        super(VolttronCentralPlatform, self).__init__(
            identity=identity, **kwargs)

        self._stats_publish_interval = 10
        self._stats_publisher = None

        # if not self._read_vc_info():
        #     if discovery_address:
        #         if not self._discover_vc_info():
        #             raise CannotConnectError()
        #
        #         self._store_vc_info()

        # # a list of registered managers of this platform.
        # self._managers = set()
        # self._managers_reachable = {}
        # self._services = {}
        # self._settings = {}
        # #self._load_settings()
        # self._agent_configurations = {}
        # self._sibling_cache = {}
        # self._vip_channels = {}
        # self.volttron_home = os.environ['VOLTTRON_HOME']
        #
        # # These properties are used to be able to register this platform
        # # agent with a volttron central instance.
        # self._vc_discovery_address = discovery_address
        # self._display_name = display_name
        #
        # # By default not managed by vc, but if the file is available then
        # # read and store it as an object.
        # self._vc = None
        # # This agent will hold a connection to the vc router so that we
        # # can send information to it.
        # self._agent_connected_to_vc = None
        # self._is_local_vc = False

    #
    # @Core.periodic(period=5)
    # def doingitnow(self):
    #     _log.debug("I am doing it now?")


    # def _connect_to_vc(self):
    #     addr = self._build_address_string()
    #
    #     self._agent_connected_to_vc = Agent(address=addr)
    #
    #     event = gevent.event.Event()
    #     gevent.spawn(self._agent_connected_to_vc.core.run, event)
    #     event.wait(timeout=3)
    #     del event
    #     try:
    #         peerlist = self._agent_connected_to_vc.vip.peerlist().get(timeout=3)
    #         _log.debug(peerlist)
    #     except gevent.timeout.Timeout:
    #         _log.debug('TIMEOUT DATA?')
    #         self._agent_connected_to_vc.core.stop()
    #         self._agent_connected_to_vc = None
    #         return False
    #
    #     return True

    @PubSub.subscribe('pubsub', 'devices')
    def ondevicemessage(self, peer, sender, bus, topic, headers, message):
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
        self._devices[key] = {
            'points': message[0].keys(),
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

    @RPC.export
    #@RPC.allow("manager")
    def reconfigure(self, **kwargs):
        _log.debug('Reconfiguring: {}'.format(kwargs))
        new_uuid = kwargs.get('platform_uuid')
        _log.debug('new_uuid is {}'.format(new_uuid))
        new_interval = kwargs.get('stats_publish_interval')

        if new_uuid:
            _log.debug('new_uuid is {}'.format(new_uuid))
            self._platform_uuid = new_uuid
        # if not new_uuid and not self._platform_uuid:
        #     raise ValueError('platform_uuid must be specified!')
        # elif new_uuid:
        #     self._platform_uuid = new_uuid

        if new_interval:
            if not isinstance(new_interval, int):
                raise ValueError('Invlaid interval, must be int > 20 sec.')

            self._stats_publish_interval = new_interval

            if self._stats_publisher:
                self._stats_publisher.kill()
            # The stats publisher publishes both to the local bus and the vc
            # bus the platform specific topics.
            self._stats_publisher = self.core.periodic(
                self._stats_publish_interval, self._publish_stats)



    def _publish_agent_list(self):
        _log.info('Publishing new agent list.')
        self.vip.pubsub.publish(
            topic="platforms/{}/agents".format(self.platform_uuid),
            message=self.list_agents()
        )

    @RPC.export
    def get_devices(self):
        cp = deepcopy(self._devices)
        foundbad = False
        for k, v in cp.items():
            dt = parse_timestamp_string(v['last_published_utc'])
            dtnow = get_aware_utc_now()
            if dt+datetime.timedelta(minutes=5) < dtnow:
                v['status'] = Status.build(
                    BAD_STATUS,
                    'Too long between publishes for {}'.format(k)).as_dict()
                foundbad = True
            else:
                v['status'] = Status.build(GOOD_STATUS).as_dict()

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
    def get_health(self):
        _log.debug("Getting health: {}".format(self.vip.health.get_status()))
        return Status.from_json(self.vip.health.get_status()).as_dict()

    @RPC.export
    def get_publickey(self):
        _log.debug('Returning publickey: {}'.format(self.core.publickey))
        return self.core.publickey

    @RPC.export
    def is_managed(self):
        return self._vc or 'volttron.central' in self.vip.peerlist().get()

        # @RPC.export
        # def manage_local(self):
        #     self._is_local_vc = True

        # @RPC.export
        # def manage_platform(self, vc_discovery_address):
        #     """ Starts the process of managing this platform.
        #
        #     The vc_discovery_address is an http(s) url that points to a
        #     volttron with a volttron.central agent running.
        #
        #     Upon completion of this method there will be a new entry in this
        #     volttron instance's auth.json file.  The entry will contain the
        #     public key of the volttron central instances and will have the
        #     capability of managed_by.
        #
        #
        #     Parameters
        #     ----------
        #     vc_discovery_address: string
        #         A resolvable http(s) string that a *discoverable* volttron
        #         instances is running
        #
        #     # Raises
        #     # -----
        #     # :class:`AlreadyManagedError`:
        #     #     Raised when platform is already managed by a different
        #     #     volttron central instance.
        #     # :class:`DiscoveryError`:
        #     #     Raised when the volttron central instance is unavailable or
        #     #     if the instance gives invalid data.
        #     """
        #
        #     _log.info('Request to be managed discovery address {}.'.format(
        #         vc_discovery_address
        #     ))
        #
        #     response = requests.get(vc_discovery_address)
        #
        #     if not response.ok:
        #         raise DiscoveryError(
        #             'Invalid response from vc_discovery_address.'
        #         )
        #
        #     self._vc_info = VCInfo(discovery_address=vc_discovery_address,
        #                            **(response.json()))
        #
        #     auth_file = AuthFile()
        #     auth_entry = AuthEntry(
        #         credentials="CURVE:{}".format(
        #             self._vc_info.vcpublickey),
        #         capabilities=['managed_by']
        #     )
        #     _log.debug('Storing auth_entry in auth.json')
        #     auth_file.add(auth_entry)
        #
        #     self._agent_connected_to_vc = Agent(address=self._build_address_string())
        #     event = gevent.event.Event()
        #     gevent.spawn(self._agent_connected_to_vc.core.run, event)
        #     event.wait(timeout=10)
        #     peers = self._agent_connected_to_vc.vip.peerlist().get(timeout=10)
        #     if not 'volttron.central' in peers:
        #         self._agent_connected_to_vc.core.stop()
        #         self._agent_connected_to_vc = None
        #         raise CannotConnectError('No volttron central available.')
        #
        #     _log.debug('Connected to volttron central!')


        # # Refresh the file to see if we are now managed or not.
        # if not self._vc:
        #     self._get_vc_info_from_file()
        # else:
        #     _log.info("Already registered with: {}".format(
        #         self._vc['serverkey']))
        #     if not vc_publickey == self._vc['serverkey']:
        #         err = "Attempted to register with different key: {}".format(
        #             vc_publickey
        #         )
        #         raise AlreadyManagedError(err)
        #
        # self._fetch_vc_discovery_info(uri, vc_publickey)
        #
        # # Add the can manage to the key file
        # self._append_allow_curve_key(vc_publickey, 'can_manage')
        #
        # self._agent_connected_to_vc = Agent(address=self._vc['vip-address'], serverkey=self._vc['serverkey'],
        #                        secretkey=self.core.secretkey)
        # event = gevent.event.Event()
        # gevent.spawn(self._agent_connected_to_vc.core.run, event)
        # event.wait(timeout=2)
        #
        # self.core._set_status(STATUS_GOOD, "Platform is managed" )
        #
        # return self.core.publickey

    @RPC.export
    def set_setting(self, key, value):
        _log.debug("Setting key: {} to value: {}".format(key, value))
        self._settings[key] = value
        self._store_settings()

    @RPC.export
    def get_setting(self, key):
        _log.debug('Retrieveing key: {}'.format(key))
        return self._settings.get(key, None)

    # @Core.periodic(period=15, wait=30)
    # def write_status(self):
    #
    #     # if self._platform_uuid:
    #     #     base_topic = LOGGER(subtopic="")
    #     #     'datalogger/platforms/{}/status'.format(self._platform_uuid)
    #     # else:
    #     base_topic = 'datalogger/log/platform/status'
    #     cpu = base_topic + '/cpu'
    #     points = {}
    #
    #     for k, v in psutil.cpu_times_percent().__dict__.items():
    #         points['times_percent/' + k] = {'Readings': v,
    #                                         'Units': 'double'}
    #
    #     points['percent'] = {'Readings': psutil.cpu_percent(),
    #                          'Units': 'double'}
    #
    #     self.vip.pubsub.publish(peer='pubsub',
    #                             topic=cpu,
    #                             message=points)

    @RPC.export
    def publish_to_peers(self, topic, message, headers=None):
        spawned = []
        _log.debug("Should publish to peers: " + str(self._sibling_cache))
        for key, item in self._sibling_cache.items():
            for peer_address in item:
                try:
                    #                         agent = Agent(address=peer_address)

                    #                         event = gevent.event.Event()
                    #                         gevent.spawn(agent.core.run, event)
                    #                         event.wait()
                    agent = self._get_rpc_agent(peer_address)
                    _log.debug("about to publish to peers: {}".format(
                        agent.core.identity))
                    #                         agent.vip.publish()
                    agent.vip.pubsub.publish(peer='pubsub', headers=headers,
                                             topic=topic,
                                             message=message)

                except Unreachable:
                    _log.error("Count not publish to peer: {}".
                               format(peer_address))

    # TODO: Make configurable
    # @Core.periodic(30)
    def update_sibling_address_cache(self):
        _log.debug('update_sibling_address_cache ' + str(self._managers))
        for manager in self._managers:
            try:
                #                     _log.debug("Manager",manager)
                #                     _log.debug(manager[0],manager[1])
                # TODO: #14 Go through manager addresses until one works. For now just use first.
                agent = self._get_rpc_agent(manager[0][0])
                #                     agent = Agent(address=manager[0])
                result = agent.vip.rpc.call(manager[1],
                                            "list_platform_details").get(
                    timeout=10)
                #                     _log.debug("RESULT",result)
                self._sibling_cache[manager[0]] = result

            except Unreachable:
                _log.error('Could not reach manager: {}'.format(manager))
            except StandardError as ex:
                _log.error("Unhandled Exception: " + str(ex))

    @RPC.export
    def register_service(self, vip_identity):
        # make sure that we get a ping reply
        # response = self.vip.ping(vip_identity).get(timeout=5)
        #
        # alias = vip_identity
        #
        # # make service list not include a platform.
        # if vip_identity.startswith('platform.'):
        #     alias = vip_identity[len('platform.'):]
        #
        # self._services[alias] = vip_identity
        # NOOP at present.
        pass

    # @RPC.export
    # def services(self):
    #     return self.@RPC.allow("can_manage")

    @RPC.export
    # @RPC.allow("manager") #TODO: uncomment allow decorator
    def list_agents(self):
        """ List the agents that are installed on the platform.

        Note this does not take into account agents that are connected
        with the instance, but only the ones that are installed and
        have a uuid.

        :return: A list of agents.
        """

        agents = self.vip.rpc.call("control", "list_agents").get()

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
                    'can_stop': True,
                    'can_start': True,
                    'can_restart': True,
                    'can_remove': True
                }
            }
            if pinfo:
                uuid_to_status[a['uuid']]['process_id'] = proc_info[0]
                uuid_to_status[a['uuid']]['error_code'] = proc_info[1]

            if 'volttroncentral' in name or \
                            'vcplatform' in name:
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
                                             a['uuid']).get(timeout=2)
                status = self.vip.rpc.call(identity,
                                           'health.get_status').get(timeout=2)
                uuid_to_status[a['uuid']]['health'] = Status.from_json(
                    status).as_dict()

        for a in agents:
            if a['uuid'] in uuid_to_status.keys():
                _log.debug('UPDATING STATUS OF: {}'.format(a['uuid']))
                a.update(uuid_to_status[a['uuid']])

        return agents

    @RPC.export
    # @RPC.allow("can_manage")
    def start_agent(self, agent_uuid):
        self.vip.rpc.call("control", "start_agent", agent_uuid)

    @RPC.export
    # @RPC.allow("can_manage")
    def stop_agent(self, agent_uuid):
        proc_result = self.vip.rpc.call("control", "stop_agent",
                                        agent_uuid)

    @RPC.export
    # @RPC.allow("can_manage")
    def restart_agent(self, agent_uuid):
        self.vip.rpc.call("control", "restart_agent", agent_uuid)

    @RPC.export
    def agent_status(self, agent_uuid):
        return self.vip.rpc.call("control", "agent_status",
                                 agent_uuid).get()

    @RPC.export
    def status_agents(self):
        return self.vip.rpc.call('control', 'status_agents').get()

    @RPC.export
    def route_request(self, id, method, params):
        _log.debug(
            'platform agent routing request: {}, {}'.format(id, method))

        # First handle the elements that are going to this platform
        if method == 'list_agents':
            result = self.list_agents()
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
                                 self.vip.rpc.call('control', method).get()]}

        elif method in ('agent_status', 'start_agent', 'stop_agent',
                        'remove_agent'):
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

                status = self.vip.rpc.call('control', method, uuid).get()
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
                if 'platform.historian' in self.vip.peerlist().get(timeout=2):
                    agent_method = fields[1]
                    result = self.vip.rpc.call('platform.historian',
                                               agent_method,
                                               **params).get(timeout=5)
                else:
                    result = jsonrpc.json_error(
                        id, INVALID_PARAMS, 'historian unavailable')
            else:
                agent_uuid = fields[2]
                agent_method = '.'.join(fields[3:])
                _log.debug("Calling method {} on agent {}"
                           .format(agent_method, agent_uuid))
                _log.debug("Params is: {}".format(params))

                result = self.vip.rpc.call(agent_uuid, agent_method,
                                           params).get()


                # Get the agent via their uuid.
                # Call the method on that agent.
                # result = self.vip.rpc.call('control', 'health.get_status', fields[2]).get(timeout=5)
            #            result = self.vip.rpc.call(fields[2], 'inspect').get(timeout=5)

            #            if self._services.get(fields[0], None):
            #                service_identity = self._services[fields[0]]
            #                agent_method = fields[1]
            #
            #                result = self.vip.rpc.call(service_identity, agent_method,
            #                                           **params).get()
            #
            #
            #            else:
            #
            #                result = jsonrpc.json_error(ident=id, code=METHOD_NOT_FOUND)
            #
            #                if len(fields) < 3:
            #                    result = jsonrpc.json_error(ident=id, code=METHOD_NOT_FOUND)
            #                else:
            #                    agent_uuid = fields[2]
            #                    agent_method = '.'.join(fields[3:])
            #                    _log.debug("Calling method {} on agent {}"
            #                               .format(agent_method, agent_uuid))
            #                    _log.debug("Params is: {}".format(params))
            #
            #                    result = self.vip.rpc.call(agent_uuid, agent_method,
            #                                           params).get()

        if isinstance(result, dict):
            if 'result' in result:
                return result['result']
            elif 'code' in result:
                return result['code']

        return result

    @RPC.export
    def list_agent_methods(self, method, params, id, agent_uuid):
        return jsonrpc.json_error(ident=id, code=INTERNAL_ERROR,
                                  message='Not implemented')

    @RPC.export
    def manage(self, address, vcserverkey, vcpublickey):
        """ Allows the `VolttronCentralPlatform` to be managed.

        From the web perspective this should be after the user has specified
        that a user has blessed an agent to be able to be managed.

        When the user enters a discovery address in `VolttronCentral` it is
        implied that the user wants to manage a platform.

        :returns publickey of the `VolttronCentralPlatform`
        """
        _log.info('Manage request from address: {} serverkey: {}'.format(
            address, vcserverkey))

        if self._managed:
            raise AlreadyManagedError()

        parsedaddress = urlparse.urlparse(address)
        # Attempt to connect to the passed address and serverkey.
        self._agent_connected_to_vc = build_agent(
            address=address, serverkey=vcserverkey,
            publickey=self.core.publickey, secretkey=self.core.secretkey)

        version, peer, identity = self._agent_connected_to_vc.vip.hello().get(
            timeout=2)

        # Add the vcpublickey to the auth file.
        entry = AuthEntry(
            credentials="CURVE:{}".format(vcpublickey),
            capabilities=['manager'])  # , address=parsedaddress.hostname)
        authfile = AuthFile()
        authfile.add(entry)
        self._managed = True
        return self.core.publickey

    def _publish_stats(self):
        """
        Publish the platform statistics to the local bus as well as to the
        connected volttron central.
        """
        vc_topic = None
        local_topic = LOGGER(subtopic="platform/status/cpu")
        _log.debug('Publishing platform cpu stats')
        if self._platform_uuid:

            vc_topic = LOGGER(
                subtopic="platforms/{}/status/cpu".format(
                    self._platform_uuid))
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

        self.vip.pubsub.publish(peer='pubsub',
                                topic=local_topic.format(),
                                message=points)

        # Handle from external platform
        if vc_topic and self._agent_connected_to_vc:
            self._agent_connected_to_vc.vip.pubsub.publish(
                peer='pubsub', topic=vc_topic.format(), message=points
            )
        # Handle if platform agent on same machine as vc.
        elif vc_topic and \
            self._my_discovery_address == self._vc_discovery_address:

            self.vip.pubsub.publish(peer='pubsub',
                                    topic=vc_topic.format(),
                                    message=points)
        else:
            _log.info("status not written to volttron central.")

    # def _connect_to_vc(self):
    #     """ Attempt to connect to volttorn central.
    #
    #     Creates an agent to connect to the volttron central instance.
    #     Uses the member self._vc to determine the vip_address and
    #     serverkey to use to connect to the instance.  The agent that is
    #     connecting to the volttron central instance will use the same
    #     private/public key pair as this agent.
    #
    #     This method will return true if the connection to the volttron
    #     central instance and the volttron.central peer is running on
    #     that platform (e.g. volttron.central is one of the peers).
    #
    #     :return:
    #     """
    #     if not self._vc:
    #         raise CannotConnectError('Invalid _vc variable member.')
    #
    #     if not self._agent_connected_to_vc:
    #         _log.debug("Attempting to connect to vc.")
    #         _log.debug("address: {} serverkey: {}"
    #                    .format(self._vc.vip_address,
    #                            self._vc.serverkey))
    #         _log.debug("publickey: {} secretkey: {}"
    #                    .format(self.core.publickey, self.core.secretkey))
    #         self._agent_connected_to_vc = Agent(address=self._vc.vip_address,
    #                                serverkey=self._vc.serverkey,
    #                                publickey=self.core.publickey,
    #                                secretkey=self.core.secretkey)
    #         event = gevent.event.Event()
    #         gevent.spawn(self._agent_connected_to_vc.core.run, event)
    #         event.wait(timeout=10)
    #         del event
    #
    #     connected = False
    #     if self._agent_connected_to_vc:
    #         peers = self._agent_connected_to_vc.vip.peerlist().get(timeout=10)

    # def _fetch_vc_discovery_info(self):
    #     """ Retrieves the serverkey and vip-address from the vc instance.
    #
    #     This method retrieves the discovery payload from the volttron
    #     central instance.  It then stores that information in a
    #     volttron.central file.
    #
    #     If this method succeeds the _vc member will be a VCInfo
    #     object.
    #
    #     :return:
    #     """
    #     # The variable self._vc will be loadded when the object is
    #     # created.
    #
    #     uri = "http://{}/discovery/".format(self._vc_discovery_address)
    #     res = requests.get(uri)
    #     assert res.ok
    #     _log.debug('RESPONSE: {} {}'.format(type(res.json()), res.json()))
    #     tmpvc = res.json()
    #     assert tmpvc['vip-address']
    #     assert tmpvc['serverkey']
    #
    #     self._vc = VCInfo(discovery_address=self._vc_discovery_address,
    #                       serverkey=tmpvc['serverkey'],
    #                       vip_address=tmpvc['vip-address'])
    #     _log.debug("vctmp: {}".format(self._vc))
    #     with open("volttron.central", 'w') as fout:
    #         fout.write(jsonapi.dumps(tmpvc))

    # def _get_vc_info_from_file(self):
    #     """ Loads the VOLTTRON Central keys if available.
    #
    #     :return:
    #     """
    #     # Load up the vc information.  If manage_platform is called with
    #     # different public key then there is an error.
    #     if os.path.exists("volttron.central"):
    #         with open("volttron.central",'r') as fin:
    #             vcdict = jsonapi.loads(fin.read())
    #             self._vc = VCInfo(
    #                 discovery_address=vcdict['discovery_address'],
    #                 vip_address=vcdict['vip-address'],
    #                 serverkey=vcdict['serverkey']
    #             )
    #         _log.info("vc info loaded from file.")
    #     else:
    #         self._vc = None

    # def _install_agents(self, agent_files):
    #     tmpdir = tempfile.mkdtemp()
    #     results = []
    #     for f in agent_files:
    #         try:
    #
    #             path = os.path.join(tmpdir, f['file_name'])
    #             with open(path, 'wb') as fout:
    #                 fout.write(base64.decodestring(f['file'].split('base64,')[1]))
    #
    #             agent_uuid = control._send_agent(self, 'control', path).get(timeout=15)
    #             results.append({'uuid': agent_uuid})
    #
    #         except Exception as e:
    #             results.append({'error': e.message})
    #             _log.error("EXCEPTION: "+e.message)
    #
    #     try:
    #         shutil.rmtree(tmpdir)
    #     except:
    #         pass
    #     return results

    def _store_settings(self):
        with open('platform.settings', 'wb') as f:
            f.write(jsonapi.dumps(self._settings))
            f.close()

    def _load_settings(self):
        try:
            with open('platform.settings', 'rb') as f:
                self._settings = self._settings = jsonapi.loads(f.read())
            f.close()
        except Exception as e:
            _log.debug('Exception ' + e.message)
            self._settings = {}

    def _get_rpc_agent(self, address):
        if address == self.core.address:
            agent = self
        elif address not in self._vip_channels:
            agent = Agent(address=address)
            event = gevent.event.Event()
            agent.core.onstart.connect(lambda *a, **kw: event.set(), event)
            gevent.spawn(agent.core.run)
            event.wait()
            self._vip_channels[address] = agent

        else:
            agent = self._vip_channels[address]
        return agent

    def _register_with_vc(self):
        """ Handle the process of registering with volttron central.

        In order to use this method, the platform agent must not have
        been registered and the _vc_discovery_address must have a valid
        ip address/hostname.

        :return:
        """

        if self._managed:
            raise AlreadyManagedError()
        if not self._vc_discovery_address:
            raise CannotConnectError(
                "Invalid VOLTTRON Central discovery address.")

        agent_for_vc = self._build_agent_for_vc()
        agent_for_vc.vip.rpc.call(VOLTTRON_CENTRAL, 'register_instance',
                                  self._my_discovery_address).get(timeout=10)
        self._managed = True

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        self.vip.heartbeat.start_with_period(10)
        self._auto_register_with_vc()

        # Reconfigure with the publisher.
        self.reconfigure(
            **{'stats_publish_interval': self._stats_publish_interval})

    @Core.receiver('onstop')
    def stoping(self, sender, **kwargs):
        self.vip.pubsub.publish(peer='pubsub', topic='/platform',
                                message='leaving')

    def _auto_register_with_vc(self):
        try:
            self._get_my_discovery_address()
            self._get_vc_discovery_address()
            # this is a local platform.
            if self._my_discovery_address == self._vc_discovery_address:
                return

            if not self._managed and self._vc_discovery_address:
                self._register_with_vc()
            _log.debug('Auto register compelete')
        except (DiscoveryError, gevent.Timeout, AlreadyManagedError,
                    CannotConnectError) as e:
                if self._vc_discovery_address:
                    vc_addr_string = '({})'.format(self._vc_discovery_address)
                else:
                    vc_addr_string = ''
                _log.warn(
                    'Failed to auto register platform with '
                    'Volttron Central{} (Error: {}'.format(vc_addr_string,
                                                           e.message))
    def _get_my_discovery_address(self):
        if not self._my_discovery_address:
            self._my_discovery_address = self.vip.rpc.call(
                MASTER_WEB, 'get_bind_web_address').get(timeout=10)

    def _get_vc_discovery_address(self):
        if not self._vc_discovery_address:
            self._vc_discovery_address = self.vip.rpc.call(
                MASTER_WEB, 'get_volttron_central_address').get(timeout=10)

    def _build_agent_for_vc(self):
        """Can raise DiscoveryError and gevent.Timeout"""
        response = DiscoveryInfo.request_discovery_info(
            self._vc_discovery_address)
        agent = build_agent(
            address=response.vip_address, serverkey=response.serverkey,
            secretkey=self.core.secretkey, publickey=self.core.publickey)
        return agent


def is_ip_private(vip_address):
    ip = vip_address.strip().lower().split("tcp://")[1]

    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) != None or priv_24.match(
        ip) != None or priv_20.match(ip) != None or priv_16.match(ip) != None


def find_registration_address(vip_addresses):
    # Find the address to send back to the VCentral in order of preference
    # Non-private IP (first one wins)
    # TCP address (last one wins)
    # IPC if first element is IPC it wins
    # Pull out the tcp address

    # If this is a string we have only one choice
    if vip_addresses and isinstance(vip_addresses, basestring):
        return vip_addresses
    elif vip_addresses and isinstance(vip_addresses, (list, tuple)):
        result = None
        for vip in vip_addresses:
            if result is None:
                result = vip
            if vip.startswith("tcp") and is_ip_private(vip):
                result = vip
            elif vip.startswith("tcp") and not is_ip_private(vip):
                return vip

        return result


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    # utils.vip_main(platform_agent)
    utils.vip_main(VolttronCentralPlatform)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
