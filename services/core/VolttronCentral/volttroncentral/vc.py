# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

__version__ = "3.1"

import datetime
import errno
import logging
import sys
import os
import os.path as p

import gevent
import requests
from zmq.utils import jsonapi

from authenticate import Authenticate
from registry import PlatformRegistry

from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.vip.agent import *
from volttron.platform.vip.agent.subsystems import query
from sessions import SessionHandler

from volttron.platform.control import list_agents
from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND,
                                       PARSE_ERROR, UNHANDLED_EXCEPTION,
                                       UNAUTHORIZED)
utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))


def volttron_central_agent(config_path, **kwargs):
    '''The main entry point for the volttron central agent

    The config options requires a user_map section that should
    hold a mapping of users to their hashed passwords.  Passwords
    are currently hashed using hashlib.sha512(password).hexdigest().
    '''
    global WEB_ROOT

    config = utils.load_config(config_path)

    identity = kwargs.pop('identity', 'volttron.central')
    identity = config.get('identity', identity)

    # For debugging purposes overwrite the WEB_ROOT variable with what's
    # from the configuration file.
    WEB_ROOT = config.get('webroot', WEB_ROOT)
    if WEB_ROOT.endswith('/'):
        WEB_ROOT = WEB_ROOT[:-1]

    agent_id = config.get('agentid', 'Volttron Central')

    # Required users.
    user_map = config.get('users', None)

    if user_map is None:
        raise ValueError('users not specified within the config file.')


    class VolttronCentralAgent(Agent):
        """ Agent for exposing and managing many platform.agent's through a web interface.
        """

        def __init__(self, **kwargs):
            super(VolttronCentralAgent, self).__init__(**kwargs)
            _log.debug("Registering (address, identity) ({}, {})"
                       .format(self.core.address, self.core.identity))
            # a list of peers that have checked in with this agent.
            self.registry = PlatformRegistry()
            # An object that allows the checking of currently authenticated
            # sessions.
            self._sessions = SessionHandler(Authenticate(user_map))
            self.valid_data = False
            self.persistence_path = ''
            self._external_addresses = None
            self._vip_channels = {}


        def list_agents(self, uuid):
            platform = self.registry.get_platform(uuid)
            results = []
            if platform:
                agent = self._get_rpc_agent(platform['vip_address'])

                results = agent.vip.rpc.call(platform['vip_identity'],
                                         'list_agents').get(timeout=10)

            return results

        @RPC.export
        def list_platform_details(self):
            print('list_platform_details', self.registry._vips)
            return self.registry._vips.keys()

        @RPC.export
        def unregister_platform(self, platform_uuid):
            value = 'Failure'
            platform = self.registry.get_platform(platform_uuid)

            if platform:
                self.registry.unregister(platform['vip_address'])
                self._store_registry()
                value = 'Success'

            return value

        @RPC.export
        def register_instance(self, uri, display_name=None):
            """ Register an instance with VOLTTRON Central.

            The registration of the instance will fail in the following cases:
            - no discoverable instance at the passed uri
            - no platform.agent installed at the discoverable instance
            - is a different volttron central managing the discoverable instance.

            If the display name is not set then the display name becomes the
            same as the uri.  This will be used in the volttron central ui.

            :param uri: A ip:port for an instance of volttron.
            :param display_name:
            :return:
            """
            request_uri = "http://{}/discovery/".format(uri)
            res = requests.get(uri)
            if not res.ok:
                return 'Unreachable'




        @RPC.export
        def register_platform(self, peer_identity, name, peer_address):
            '''Agents will call this to register with the platform.

            This method is successful unless an error is raised.
            '''
            value = self._handle_register_platform(peer_address, peer_identity, name)

            if not value:
                return 'Platform Unavailable'

            return value

        def _store_registry(self):
            self._store('registry', self.registry.package())

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
                node = self.registry.register(address, identity, agentid)

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
            _log.debug('SETUP STUF NOW HERE DUDE!')
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
                self.registry.unpackage(registered)

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

            This method will only accept rpcdata.  The first time this method is
            called for a session it must be using get_authorization.  That will
            return a session token that must be included in every request
            after that.  The session is validated based upon ip address.
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


            except AssertionError:
                return jsonapi.dumps(jsonrpc.json_error('NA', INVALID_REQUEST,
                    'Invalid rpc data {}'.format(data)))

            return rpcdata

        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):
            '''This event is triggered when the platform is ready for the agent
            '''
            _log.debug('DoING STARTUP!')

            q = query.Query(self.core)
            result = q.query('addresses').get(timeout=10)

# hander_config = [
#     (r'/jsonrpc', ManagerRequestHandler),
#     (r'/jsonrpc/', ManagerRequestHandler),
#     (r'/websocket', StatusHandler),
#     (r'/websocket/', StatusHandler),
#     (r'/log', LogHandler),
#     (r'/log/', LogHandler),
#     (r"/(.*)", tornado.web.StaticFileHandler,
#      {"path": WEB_ROOT, "default_filename": "index.html"})
# ]

            #TODO: Use all addresses for fallback, #114
            self._external_addresses = (result and result[0]) or self.core.address

            _log.debug('Registering jsonrpc and /.* routes')
            self.vip.rpc.call('volttron.web', 'register_agent_route',
                            r'^/api/jsonrpc.*',
                            self.core.identity,
                            'jsonrpc').get(timeout=5)

            self.vip.rpc.call('volttron.web', 'register_path_route',
                            r'^/.*', WEB_ROOT).get(timeout=5)


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
                        for x in self.registry.get_platforms()]

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
                return RpcResponse(id=id, code=METHOD_NOT_FOUND)


            platform_uuid = fields[2]

            platform = self.registry.get_platform(platform_uuid)

            if not platform:
                return RpcResponse(id=id, code=METHOD_NOT_FOUND,
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

    VolttronCentralAgent.__name__ = 'VolttronCentralAgent'
    return VolttronCentralAgent(identity=identity, **kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(volttron_central_agent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
