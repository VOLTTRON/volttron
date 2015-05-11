# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
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

import datetime
import logging
import sys
import requests
import threading
import os
import os.path as p
import uuid

import gevent
import tornado
import tornado.ioloop
import tornado.web
from tornado.web import url

from authenticate import Authenticate

from volttron.platform.async import AsyncCall
from volttron.platform import vip, jsonrpc
from volttron.platform.agent.vipagent import (BaseAgent, RPCAgent, periodic,
                                              onevent, jsonapi, export)
from volttron.platform.agent import utils

from webserver import (ManagerWebApplication, ManagerRequestHandler,
                       SessionHandler)
from volttron.platform.control import list_agents

utils.setup_logging()
_log = logging.getLogger(__name__)
WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))


class PlatformRegistry:
    '''Container class holding registered vip platforms and services.
    '''

    def __init__(self, stale=5*60):
        self._vips = {}
        self._uuids = {}

    def get_vip_addresses(self):
        '''Returns all of the known vip addresses.
        '''
        return self._vips.keys()

    def get_platforms(self):
        '''Returns all of the registerd platforms dictionaries.
        '''
        return self._uuids.values()

    def get_platform(self, platform_uuid):
        '''Returns a platform associated with a specific uuid instance.
        '''
        return self._uuids.get(platform_uuid, None)

    def update_agent_list(self, platform_uuid, agent_list):
        '''Update the agent list node for the platform uuid that is passed.
        '''
        self._uuids[platform_uuid].agent_list = agent_list.get()

    def register(self, vip_address, vip_identity, agentid, **kwargs):
        '''Registers a platform agent with the registry.

        An agentid must be non-None or a ValueError is raised

        Keyword arguments:
        vip_address -- the registering agent's address.
        agentid     -- a human readable agent description.
        kwargs      -- additional arguments that should be stored in a
                       platform agent's record.

        returns     The registered platform node.
        '''
        if vip_address not in self._vips.keys():
            self._vips[vip_address] = {}
        node = self._vips[vip_address]
#         if vip_identity in node:
#             raise ValueError('Duplicate vip_address vip_identity for {}-{}'
#                              .format(vip_address, vip_identity))
        if agentid is None:
            raise ValueError('Invalid agentid specified')

        platform_uuid = str(uuid.uuid4())
        node[vip_identity] = {'agentid': agentid,
                              'vip_address': vip_address,
                              'vip_identity': vip_identity,
                              'uuid': platform_uuid,
                              'other': kwargs
                              }
        self._uuids[platform_uuid] = node[vip_identity]

        _log.debug('Added ({}, {}, {} to registry'.format(vip_address,
                                                          vip_identity,
                                                          agentid))
        return node[vip_identity]


def volttron_central_agent(config_path, **kwargs):
    config = utils.load_config(config_path)

    vip_identity = config.get('vip_identity', 'platform.manager')

    agent_id = config.get('agentid', 'Volttron Central')
    server_conf = config.get('server', {})
    user_map = config.get('users', None)

    if user_map is None:
        raise ValueError('users not specified within the config file.')


    hander_config = [
        (r'/jsonrpc', ManagerRequestHandler),
        (r'/jsonrpc/', ManagerRequestHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": WEB_ROOT, "default_filename": "index.html"})
    ]

    def startWebServer(manager):
        '''Starts the webserver to allow http/RpcParser calls.

        This is where the tornado IOLoop instance is officially started.  It
        does block here so one should call this within a thread or process if
        one doesn't want it to block.

        One can stop the server by calling stopWebServer or by issuing an
        IOLoop.stop() call.
        '''
        session_handler = SessionHandler(Authenticate(user_map))
        webserver = ManagerWebApplication(session_handler, manager,
                                          hander_config, debug=True)
        webserver.listen(server_conf.get('port', 8080),
                         server_conf.get('host', ''))
        tornado.ioloop.IOLoop.instance().start()

    def stopWebServer():
        '''Stops the webserver by calling IOLoop.stop
        '''
        tornado.ioloop.IOLoop.stop()

    class Agent(RPCAgent):
        """Agent for querying WeatherUndergrounds API"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(vip_identity=vip_identity, **kwargs)
            _log.debug("Registering (vip_address, vip_identity) ({}, {})"
                       .format(self.vip_address, vip_identity))
            # a list of peers that have checked in with this agent.
            self.registry = PlatformRegistry()
            self.valid_data = False
            self._vip_channels = {}

        @periodic(period=30)
        def _update_agent_list(self):
            jobs = []
            print "updating agent list"
            for p in self.registry.get_platforms():
                jobs.append(gevent.spawn(self.list_agents, uuid=p['uuid']))
            gevent.joinall(jobs, timeout=20)
            return [j.value for j in jobs]

        def list_agents(self, uuid):
            platform = self.registry.get_platform(uuid)
            results = []
            if platform:
                if platform['vip_address'] == self.vip_address:
                    rpc = self
                elif not platform['vip_address'] in self._vip_channels:
                    rpc = RPCAgent(platform['vip_address'])
                    gevent.spawn(rpc.run).join(0)
                    self._vip_channels[platform['vip_address']] = rpc
                else:
                    rpc = self._vip_channels[platform['vip_address']]



                results = rpc.rpc_call(platform['vip_identity'],
                                      'list_agents').get(timeout=10)

            return results

        @export()
        def register_platform(self, peer_identity, name, peer_address):
            '''Agents will call this to register with the platform.

            This method is successful unless an error is raised.
            '''
            platform = self.registry.register(peer_address, peer_identity,
                                              name)


#         @export()
#         def unregister_platform(self, peer_identity):
#             del self.platform_dict[peer_identity]['identity_params']
#             _log.debug("Platform {} unregistered successfully"
#                        .format(peer_identity))
#             return True

        @onevent('setup')
        def setup(self):
            print "Setting up"
            self.async_caller = AsyncCall()

        @onevent("start")
        def start(self):
            '''This event is triggered when the platform is ready for the agent
            '''
            # Start tornado in its own thread
            threading.Thread(target=startWebServer, args=(self,)).start()

        @onevent("finish")
        def finish(self):
            stopWebServer()

        def route_request(self, id, method, params):
            '''Route request to either a registered platform or handle here.'''

            if (method == 'list_platforms'):
                return [{'uuid': x['uuid'],
                         'name': x['agentid']}
                        for x in self.registry.get_platforms()]

            fields = method.split('.')

            if len(fields) < 3:
                return RpcResponse(id=id, code=METHOD_NOT_FOUND)


            platform_uuid = fields[2]

            platform = self.registry.get_platform(platform_uuid)


            if not platform:
                return RpcResponse(id=id, code=METHOD_NOT_FOUND,
                                   message="Unknown platform {}".format(platform_uuid))

            if fields[3] == 'list_agents':
                return platform.agent_list

            # The method to route to the platform.
            platform_method = '.'.join(fields[3:])



            # Are we talking to our own vip address?
            if platform['vip_address'] == self.vip_address:
                result = self.rpc_call(str(platform_uuid), 'route_request',
                                       [id, platform_method, params]).get()
            else:

                if not platform['vip_address'] in self.vip_channels:
                    rpc = RPCAgent(platform['vip_address'])
                    gevent.spawn(rpc.run).join(0)
                    self.vip_channels[platform['vip_address']] = rpc
                else:
                    rpc = self.vip_channels[platform['vip_address']]

                result = rpc.rpc_call(platform_uuid, "route_request", [id, platform_method, params]).get(timeout=10)

            return result

    Agent.__name__ = 'ManagedServiceAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(volttron_central_agent,
                       description='Volttron central agent',
                       no_pub_sub_socket=True,
                       argv=argv)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
