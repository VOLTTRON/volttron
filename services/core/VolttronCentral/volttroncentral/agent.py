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

from datetime import datetime
import errno
import logging
import sys
import os
import os.path as p

import gevent
import requests
from requests.packages.urllib3.exceptions import NewConnectionError
from zmq.utils import jsonapi

from authenticate import Authenticate
from .resource_directory import ResourceDirectory
from .registry import PlatformRegistry, RegistryEntry

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform import jsonrpc
from volttron.platform.jsonrpc import (
    INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND,
    PARSE_ERROR, UNHANDLED_EXCEPTION, UNAUTHORIZED,
    UNABLE_TO_REGISTER_INSTANCE, DISCOVERY_ERROR,
    UNABLE_TO_UNREGISTER_INSTANCE)
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core
from volttron.platform.vip.agent.subsystems import query
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.vip.socket import encode_key
from volttron.platform.web import (DiscoveryInfo, CouldNotRegister,
                                   build_vip_address_string, DiscoveryError)

from sessions import SessionHandler

__version__ = "3.5"

utils.setup_logging()
_log = logging.getLogger(__name__)


# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))


class VolttronCentralAgent(Agent):
    """ Agent for exposing and managing many platform.agent's through a web interface.
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

        # This is a special object so only use it's identity.
        identity = kwargs.pop("identity", VOLTTRON_CENTRAL)

        super(VolttronCentralAgent, self).__init__(identity=identity,
                                                   **kwargs)

        # A resource directory that contains everything that can be looked up.
        self._resources = ResourceDirectory()
        self._registry = self._resources.platform_registry
        self._pa_agents = {}

        # An object that allows the checking of currently authenticated
        # sessions.
        self._sessions = SessionHandler(Authenticate(self._user_map))
        self.webaddress = None
        self._web_info = None

#    def _check_for_peer_platform(self):
#        """ Check the list of peers for a platform.agent
#
#        Registers the platform_peer if it hasn't been registered.
#        """
#        peers = self.vip.peerlist().get()
#        if "platform.agent" in peers:
#            if not self._peer_platform_exists:
#                _log.info("peer_platform available")
#                self._peer_platform_exists = True
#                try:
#                    entry = self._registry.get_platform_by_address(
#                        self._local_address)
#                except KeyError:
#                    assert "ipc" in self._local_address
#                    entry = PlatformRegistry.build_entry(
#                        vip_address=self._local_address, serverkey=None,
#                        discovery_address=None, is_local=True
#                    )
#                    self._registry.register(entry)
#
#        elif "platform.agent" not in peers:
#            if self._peer_platform_exists:
#                _log.info("peer_platform unavailable")
#                self._peer_platform_exists = False

    @PubSub.subscribe("pubsub", "platforms")
    def on_platoforms_message(self, peer, sender, bus,  topic, headers,
                              message):
        _log.debug('Got message: {}'.format(message))


    @RPC.export
    def get_platforms(self):
        return self._registry.get_platforms()

    @RPC.export
    def get_platform(self, platform_uuid):
        return self._registry.get_platform(platform_uuid)

    #@Core.periodic(5)
    def _auto_register_peer(self):
        if not self._peer_platform:
            peers = self.vip.peerlist().get(timeout=2)
            if 'platform.agent' in peers:
                _log.debug('Auto connecting platform.agent on vc')
                self._peer_platform = Agent()
                self._peer_platform.core.onstop.connect(
                    self._peer_platform)
                self._peer_platform.core.ondisconnected.connect(
                    lambda sender, **kwargs: _log.debug("disconnected")
                )
                self._peer_platform.core.onconnected.connect(
                    lambda sender, **kwargs: _log.debug("connected")
                )
                event = gevent.event.Event()
                gevent.spawn(self._peer_platform.core.run, event)
                event.wait(timeout=2)
                del event

    def _disconnect_peer_platform(self, sender, **kwargs):
        _log.debug("disconnecting peer_platform")
        self._peer_platform = None

    @RPC.export
    def list_platform_details(self):
        print('list_platform_details', self._registry.get_platforms())
        return self._registry.get_platforms() #[x.to_json() for x in self._registry.get_platforms()]

    @RPC.export
    def unregister_platform(self, platform_uuid):
        platform = self._registry.get_platform(platform_uuid)
        if platform:
            self._registry.unregister(platform.vip_address)
            self._store_registry()

            if platform_uuid in self._pa_agents.keys():
                pa_agent = self._pa_agents[platform_uuid]
                pa_agent.core.stop()
                del self._pa_agents[platform_uuid]

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
        pass


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
            connected_to_pa = build_agent(
                address=pa_vip_address, serverkey=pa_instance_serverkey,
                secretkey=self.core.secretkey,
                publickey=self.core.publickey
            )
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
        peers = connected_to_pa.vip.peerlist().get(timeout=1)
        if VOLTTRON_CENTRAL_PLATFORM not in peers:
            connected_to_pa.core.stop()
            return {'error': {'code': UNABLE_TO_REGISTER_INSTANCE,
                              'message': '{} not present.'.format(
                                  VOLTTRON_CENTRAL_PLATFORM)
                              }}

        # The call to manage should return a public key for that agent
        result = connected_to_pa.vip.rpc.call(
            VOLTTRON_CENTRAL_PLATFORM, 'manage', self._web_info.vip_address,
            self._web_info.serverkey, self.core.publickey).get(timeout=4)

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

        #TODO: figure out if we are local or not

        entry = PlatformRegistry.build_entry(
                    pa_vip_address, pa_instance_serverkey, discovery_address,
                    display_name, False)

        self._registry.register(entry)
        self._pa_agents[entry.platform_uuid] = connected_to_pa

        instance_name = display_name if display_name else discovery_address
        context = 'Registered instance {}'.format(instance_name)

        return {'status': 'SUCCESS', 'context': context}

    # @RPC.export
    # def register_platform(self, peer_identity, name, peer_address):
    #     '''Agents will call this to register with the platform.
    #
    #     This method is successful unless an error is raised.
    #     '''
    #     value = self._handle_register_platform(peer_address, peer_identity, name)
    #
    #     if not value:
    #         return 'Platform Unavailable'
    #
    #     return value

    def _store_registry(self):
        self._store('registry', self._registry.package())

#    def _handle_register_platform(self, address, identity=None, agentid='platform.agent'):
#        _log.debug('Registering platform identity {} at vip address {} with name {}'
#                   .format(identity, address, agentid))
#        agent = self._get_rpc_agent(address)
#
#        if not identity:
#            identity = 'platform.agent'
#
#        result = agent.vip.rpc.call(identity, "manage",
#                                    address=self._external_addresses,
#                                    identity=self.core.identity)
#        if result.get(timeout=10):
#            node = self._registry.register(address, identity, agentid)
#
#            if node:
#                self._store_registry()
#            return node
#
#        return False
#
#    def _get_rpc_agent(self, address):
#        if address == self.core.address:
#            agent = self
#        elif address not in self._vip_channels:
#            agent = Agent(address=address)
#            gevent.spawn(agent.core.run).join(0)
#            self._vip_channels[address] = agent
#
#        else:
#            agent = self._vip_channels[address]
#        return agent

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        if not os.environ.get('VOLTTRON_HOME', None):
            raise ValueError('VOLTTRON_HOME environment must be set!')

        db_path = os.path.join(os.environ.get('VOLTTRON_HOME'),
                               'data/volttron.central')
        db_dir  = os.path.dirname(db_path)
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

            if rpcdata.method == 'get_authorization':
                args = {'username': rpcdata.params['username'],
                        'password': rpcdata.params['password'],
                        'ip': env['REMOTE_ADDR']}
                sess = self._sessions.authenticate(**args)
                if not sess:
                    _log.info('Invalid username/password for {}'.format(rpcdata.params['username']))
                    return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                              "Invalid username/password specified.")
                _log.info('Session created for {}'.format(rpcdata.params['username']))
                return jsonrpc.json_result(rpcdata.id, sess)

            token = rpcdata.authorization
            ip = env['REMOTE_ADDR']

            if not self._sessions.check_session(token, ip):
                _log.debug("Session Check Failed for Token: {}".format(token))
                return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                          "Invalid authentication token")
            _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))

            result_or_error = self.route_request(
                    rpcdata.id, rpcdata.method, rpcdata.params)

        except AssertionError:
            return jsonapi.dumps(jsonrpc.json_error(
                'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data)))

        _log.debug("RETURNING: {}".format(self._get_jsonrpc_response(
            rpcdata.id, result_or_error)))
        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

    def _get_jsonrpc_response(self, id, result_or_error):
        if 'error' in result_or_error:
            error = result_or_error['error']
            return jsonrpc.json_error(id, error['code'], error['message'])
        return jsonrpc.json_result(id, result_or_error)

    def _get_agents(self, platform_uuid):
        platform = self.get_platform(platform_uuid)
        connected_to_pa = self._pa_agents[platform_uuid] #TODO: get from registry

        agents = connected_to_pa.vip.rpc.call(
                'platform.agent', 'list_agents').get(timeout=2)

        for a in agents:
            if "platformagent" in a['name'] or \
                            "volttroncentral" in a['name']:
                a['vc_can_start'] = False
                a['vc_can_stop'] = False
                a['vc_can_restart'] = True
            else:
                a['vc_can_start'] = True
                a['vc_can_stop'] = True
                a['vc_can_restart'] = True

        _log.debug('Agents returned: {}'.format(agents))
        return agents

    @Core.receiver('onstart')
    def _starting(self, sender, **kwargs):
        '''This event is triggered when the platform is ready for the agent
        '''
        self.vip.heartbeat.start_with_period(10)

        q = query.Query(self.core)
        self._external_addresses = q.query('addresses').get(timeout=10)

        #TODO: Use all addresses for fallback, #114
        _log.debug("external addresses are: {}".format(
            self._external_addresses
        ))
        self._local_address = q.query('local_address').get(timeout=10)
        _log.debug('Local address is? {}'.format(self._local_address))
        _log.debug('Registering jsonrpc and /.* routes')
        self.vip.rpc.call('volttron.web', 'register_agent_route',
                          r'^/jsonrpc.*',
                          self.core.identity,
                          'jsonrpc').get(timeout=5)

        self.vip.rpc.call('volttron.web', 'register_path_route',
                          r'^/.*', self._webroot).get(timeout=5)

        self.webaddress = self.vip.rpc.call(
            'volttron.web', 'get_bind_web_address').get(timeout=5)

        assert self.core.publickey
        assert self.core.secretkey
        self._web_info = DiscoveryInfo.request_discovery_info(self.webaddress)

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

    @Core.receiver('onstop')
    def finish(self, sender, **kwargs):
        self.vip.rpc.call('volttron.web', 'unregister_all_agent_routes',
                          self.core.identity).get(timeout=5)

    def _handle_list_platforms(self):
        return [{'uuid': x.platform_uuid,
                 'name': x.display_name}
                for x in self._registry.get_platforms()]

    def route_request(self, id, method, params):
        '''Route request to either a registered platform or handle here.'''
        _log.debug('inside route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        if method == 'register_instance':
            if isinstance(params, list):
                return self._register_instance(*params)
            else:
                return self._register_instance(**params)
        elif method == 'list_platforms':
            return self._handle_list_platforms()
        elif method == 'unregister_platform':
            return self.unregister_platform(params['platform_uuid'])

        fields = method.split('.')
        if len(fields) < 3:
            return err('Unknown method {}'.format(method))
        platform_uuid = fields[2]
        platform = self._registry.get_platform(platform_uuid)
        if not platform:
            return err('Unknown platform {}'.format(platform_uuid))
        platform_method = '.'.join(fields[3:])
        agent = self._pa_agents[platform_uuid] #TODO: get from registry
        return agent.vip.rpc.call(
                'platform.agent', 'route_request', id, platform_method,
                params).get(timeout=10)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(VolttronCentralAgent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
