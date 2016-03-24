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


import errno
import logging
import sys
import os
import os.path as p

import gevent
import requests
from zmq.utils import jsonapi

from authenticate import Authenticate
from .resource_directory import ResourceDirectory
from .registry import PlatformRegistry, RegistryEntry

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.jsonrpc import (
    INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND,
    PARSE_ERROR, UNHANDLED_EXCEPTION, UNAUTHORIZED,
    UNABLE_TO_REGISTER_INSTANCE)
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core
from volttron.platform.vip.agent.subsystems import query
from volttron.platform.vip.socket import encode_key
from volttron.platform.web import (DiscoveryInfo, CouldNotRegister,
                                   build_vip_address_string)

from sessions import SessionHandler

from volttron.platform.control import list_agents

from volttron.platform.keystore import KeyStore

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
        self.webroot = self._config.get('webroot', DEFAULT_WEB_ROOT)
        if self.webroot.endswith('/'):
            self.webroot = self.webroot[:-1]

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

        # An object that allows the checking of currently authenticated
        # sessions.
        self._sessions = SessionHandler(Authenticate(self._user_map))
        self.webaddress = None

        def _check_for_peer_platform(self):
            """ Check the list of peers for a platform.agent

            Registers the platform_peer if it hasn't been registered.
            """
            peers = self.vip.peerlist().get()
            if "platform.agent" in peers:
                if not self._peer_platform_exists:
                    _log.info("peer_platform available")
                    self._peer_platform_exists = True
                    try:
                        entry = self._registry.get_platform_by_address(
                            self._local_address)
                    except KeyError:
                        assert "ipc" in self._local_address
                        entry = PlatformRegistry.build_entry(
                            vip_address=self._local_address, serverkey=None,
                            discovery_address=None, is_local=True
                        )
                        self._registry.register(entry)

            elif "platform.agent" not in peers:
                if self._peer_platform_exists:
                    _log.info("peer_platform unavailable")
                    self._peer_platform_exists = False

        @PubSub.subscribe("pubsub", "platforms")
        def on_platoforms_message(self, peer, sender, bus,  topic, headers,
                                  message):
            _log.debug('Got message: {}'.format(message))


        @RPC.export
        def get_platforms(self):
            _log.debug('Getting platforms via rpc')
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

        def list_agents(self, uuid):
            platform = self._registry.get_platform(uuid)
            results = []
            if platform:
                agent = self._get_rpc_agent(platform['vip_address'])

                results = agent.vip.rpc.call(platform['vip_identity'],
                                             'list_agents').get(timeout=10)

            return results

        @RPC.export
        def list_platform_details(self):
            print('list_platform_details', self._registry.get_platforms())
            return self._registry.get_platforms() #[x.to_json() for x in self._registry.get_platforms()]

        @RPC.export
        def unregister_platform(self, platform_uuid):
            value = 'Failure'
            platform = self._registry.get_platform(platform_uuid)

            if platform:
                self._registry.unregister(platform['vip_address'])
                self._store_registry()
                value = 'Success'

            return value

        @RPC.export
        def register_instance(self, discovery_address, display_name=None):
            """ An rpc call to register from the platform agent.

            This method allows an external platform to register itself with
            the volttron central instance that is specified in the
            Platform agent's configuration file.

            :param discovery_address:
            :param display_name:
            :return:
            """

            info = DiscoveryInfo.get_discovery_info(discovery_address)


            #self._register_instance(discovery_address, display_name,
            #                        provisional=True)

        def _register_instance(self, discovery_address, display_name=None,
                               provisional=False):
            """ Register an instance with VOLTTRON Central.

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
            :return:
            :raises CouldNotRegister if the platform couldn't be registered.
            """

            _log.info(
                'Attempting to register name: {}\nwith address: {}'.format(
                    display_name, discovery_address))

            # Make sure that the agent is reachable.
            request_uri = "{}/discovery/".format(discovery_address)
            res = requests.get(request_uri)
            _log.debug("Requesting discovery from: {}".format(request_uri))
            if not res.ok:
                return 'Unreachable'

            tmpres = res.json()
            pa_instance_serverkey = tmpres['serverkey']
            pa_vip_address = tmpres['vip-address']

            assert pa_instance_serverkey
            _log.debug('connecting to pa_instance')
            connected_to_pa =Agent(
                address=pa_vip_address, serverkey=pa_instance_serverkey,
                secretkey=encode_key(self.core.secretkey),
                publickey=encode_key(self.core.publickey)
            )

            event = gevent.event.Event()
            gevent.spawn(connected_to_pa.core.run, event)
            event.wait(timeout=2)
            del event
            _log.debug('Connected to address')
            peers = connected_to_pa.vip.peerlist().get(timeout=1)
            assert 'platform.agent' in peers
            _log.debug("Agent connected to peers: {}".format(
                connected_to_pa.vip.peerlist().get(timeout=3)))

            result = connected_to_pa.vip.rpc.call(
                'platform.agent', 'get_publickey'
            ).get(timeout=2)
            _log.debug('RESULT: {}'.format(result))
            if not display_name:
                display_name = discovery_address

            if not result:
                raise CouldNotRegister(
                    "display_name={}, discovery_address={}".format(
                        display_name, discovery_address)
                )
            _log.debug('publickey from platform: {}'.format(result))

            # Add the pa's public key so it can connect back to us.
            auth_file = AuthFile()
            auth_entry = AuthEntry(credentials="CURVE:{}".format(result),
                                   capabilities=['is_managed']
                                   )
            auth_file.add(auth_entry)

            vc_webaddr = os.environ.get('VOLTTRON_WEB_ADDR', None)
            # # datetime_now = datetime.datetime.utcnow()
            # # _log.debug(datetime_now)
            # entry = RegistryEntry(vip_address=vip_address,
            #                       serverkey=pa_instance_serverkey,
            #                       discovery_address=web_addr,
            #                       display_name=display_name,
            #                       provisional=provisional)
            # self._registry.register(entry)
            # assert vc_webaddr
            _log.debug('Calling manage_platform from vc.')
            result = connected_to_pa.vip.rpc.call(
                'platform.agent', 'manage_platform', vc_webaddr,
                self.core.publickey

            ).get(timeout=2)

            return {}

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

        def _handle_register_platform(self, address, identity=None, agentid='platform.agent'):
            _log.debug('Registering platform identity {} at vip address {} with name {}'
                       .format(identity, address, agentid))
            agent = self._get_rpc_agent(address)

            if not identity:
                identity = 'platform.agent'

            result = agent.vip.rpc.call(identity, "manage",
                                        address=self._external_addresses,
                                        identity=self.core.identity)
            if result.get(timeout=10):
                node = self._registry.register(address, identity, agentid)

                if node:
                    self._store_registry()
                return node

            return False

        def _get_rpc_agent(self, address):
            if address == self.core.address:
                agent = self
            elif address not in self._vip_channels:
                agent = Agent(address=address)
                gevent.spawn(agent.core.run).join(0)
                self._vip_channels[address] = agent

            else:
                agent = self._vip_channels[address]
            return agent

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

        def _to_jsonrpc_obj(self, data):
            """ Convert data string into a JsonRpcData named tuple.

            :param object data: Either a string or a dictionary representing a json document.
            """
            try:
                jsonstr = jsonapi.loads(data)
            except:
                jsonstr = data

            data = jsonrpc.JsonRpcData(jsonstr.get('id', None),
                                       jsonstr.get('jsonrpc', None),
                                       jsonstr.get('method', None),
                                       jsonstr.get('params', None))

            return data

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
                jsonrpc.validate(rpcdata)

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

                _log.debug(data)
                jsondata = jsonapi.loads(data)
                token = jsondata.get('authorization', None)
                ip = env['REMOTE_ADDR']

                if not self._sessions.check_session(token, ip):
                    _log.debug("Session Check Failed for Token: {}".format(token))
                    return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                              "Invalid authentication token")
                _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))

                if rpcdata.method == 'register_instance':
                    try:
                        # internal use discovery address rather than uri
                        print("RPCDATA.PARAMS: {}".format(rpcdata.params))
                        result = self._register_instance(**rpcdata.params)
                    except CouldNotRegister as expinfo:
                        return jsonrpc.json_error(
                            rpcdata.id, UNABLE_TO_REGISTER_INSTANCE,
                            "Unable to register platform {}".format(expinfo),
                            **rpcdata.params)
                    else:
                        return jsonrpc.json_result(rpcdata.id, {
                            "status": "SUCCESS",
                            "context": "Registered instance {}".format(
                                result['display_name'])
                        })
                elif rpcdata.method == 'list_platforms':
                    return self._get_platforms_json(rpcdata.id)

            except AssertionError:
                return jsonapi.dumps(jsonrpc.json_error(
                    'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data)))

            return rpcdata

        def _get_platforms_json(self, message_id):
            """ Composes the json response for the listing of the platforms.

            :param message_id:
            :return:
            """
            platforms = []
            keys = []
            for p in self.get_platforms():
                # entry = RegistryEntry(**p)
                if p.tags['available']:
                    s = self.vip.rpc.call('platform.agent',
                                          'get_status').get(timeout=2)
                    status = s
                    can_reach = True
                else:
                    can_reach = False
                    status = {"status": "UNKNOWN",
                              "context": "Platform currently unavailable.",
                              "last_updated": None}
                agents = []
                if can_reach:
                    agents = p.tags.get('agents',
                                        self._get_agents(p.platform_uuid))
                r = {
                    'name': p.display_name,
                    'uuid': p.platform_uuid,
                    'agents': agents,
                    'devices': p.tags.get('devices', []),
                    'status': status
                }

                platforms.append(r)

            return jsonrpc.json_result(message_id, platforms)

        def _get_agents(self, platform_uuid):
            agents = self.vip.rpc.call('platform.agent',
                                       'list_agents').get(timeout=2)
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
        def starting(self, sender, **kwargs):
            '''This event is triggered when the platform is ready for the agent
            '''
            self.vip.heartbeat.start()

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
                              r'^/.*', DEFAULT_WEB_ROOT).get(timeout=5)

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
            return [{'uuid': x['uuid'],
                     'name': x['agentid']}
                    for x in self._registry.get_platforms()]

        def route_request(self, id, method, params):
            '''Route request to either a registered platform or handle here.'''
            print('inside route_request {}, {}, {}'.format(id, method, params))
            if method == 'list_platforms':
                return self._handle_list_platforms()
            elif method == 'register_platform':
                return self._handle_register_platform(**params)
            elif method == 'unregister_platform':
                return self.unregister_platform(**params)

            fields = method.split('.')

            if len(fields) < 3:
                return jsonrpc.json_error(ident=id, code=METHOD_NOT_FOUND)


            platform_uuid = fields[2]

            platform = self._registry.get_platform(platform_uuid)

            if not platform:
                return jsonrpc.json_error(ident=id, code=METHOD_NOT_FOUND,
                                          message="Unknown platform {}".format(platform_uuid))

            platform_method = '.'.join(fields[3:])

            # get an agent
            agent = self._get_rpc_agent(platform['vip_address'])

            _log.debug("calling identity {} with parameters {} {} {}"
                       .format(platform['vip_identity'],
                               id,
                               platform_method, params))
            result = agent.vip.rpc.call(platform['vip_identity'],
                                        "route_request",
                                        id, platform_method, params).get(timeout=10)


            return result



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(VolttronCentralAgent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
