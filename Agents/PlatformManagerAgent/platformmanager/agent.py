# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
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

utils.setup_logging()
_log = logging.getLogger(__name__)
WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))


class PlatformRegistry:

    def __init__(self, stale=5*60):
        pass


def PlatformManagerAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name, default_value=''):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, default_value)
#     home = os.path.expanduser(os.path.expandvars(
#         os.environ.get('VOLTTRON_HOME', '~/.volttron')))
#     vip_address = 'ipc://@{}/run/vip.socket'.format(home)
    vip_identity = 'platform_manager'

    agent_id = get_config('agentid')
    server_conf = get_config('server', {})
    user_map = get_config('users')

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
        webserver = ManagerWebApplication(
                        SessionHandler(Authenticate(user_map)),
                        manager,
                        hander_config, debug=True)
        webserver.listen(server_conf.get('port', 8080), server_conf.get('host', ''))
        webserverStarted = True
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
            self.platform_dict = {}
            self.valid_data = False
            self.vip_channels = {}

        def list_agents(self, platform):

            if platform in self.platform_dict.keys():
                return self.rpc_call(platform, "list_agents").get()
            return "PLATFORM NOT FOUND"

        @export()
        def register_platform(self, peer_identity, name, peer_address):
            '''Agents will call this to register with the platform.
            '''

            self.platform_dict[peer_identity] = {
                    'identity_params':  {'name': name, 'uuid': peer_identity},
                    'peer_address': peer_address,
                    'ctl': None
                }

            self.platform_dict[peer_identity]['external'] = peer_address != self.vip_address

            _log.debug("Platform {} registered successfully"
                       .format(peer_identity))
            return True


        @export()
        def unregister_platform(self, peer_identity):
            del self.platform_dict[peer_identity]['identity_params']
            _log.debug("Platform {} unregistered successfully"
                       .format(peer_identity))
            return True

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

        def route_request (self, id, method, params):
            '''Route request to either a registered platform or handle here.'''

            if (method == 'list_platforms'):
                return [x['identity_params'] for x in self.platform_dict.values()]

            fields = method.split('.')

            if len(fields) < 3:
                return RpcResponse(id=id, code=METHOD_NOT_FOUND)


            platform_uuid = fields[2]

            if not platform_uuid in self.platform_dict:
                return RpcResponse(id=id, code=METHOD_NOT_FOUND,
                                   message="Unknown platform {}".format(platform_uuid))

            # this is the platform we need to talk with.
            platform = self.platform_dict[platform_uuid]
            # The method to route to the platform.
            platform_method = '.'.join(fields[3:])

            # Are we talking to our own vip address?
            if platform['peer_address'] == self.vip_address:
                result = self.rpc_call(str(platform_uuid), 'route_request',
                                       [id, platform_method, params]).get()
            else:

                if not platform['peer_address'] in self.vip_channels:
                    rpc = RPCAgent(platform['peer_address'])
                    gevent.spawn(rpc.run).join(0)
                    self.vip_channels[platform['peer_address']] = rpc
                else:
                    rpc = self.vip_channels[platform['peer_address']]

                result = rpc.rpc_call(platform_uuid, "route_request", [id, platform_method, params]).get(timeout=10)

            return result

    Agent.__name__ = 'ManagedServiceAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)
        '''Main method called by the eggsecutable.'''
#         utils.default_main(PlatformManagerAgent,
#                            description='The managed server agent',
#                            argv=argv)
        config = os.environ.get('AGENT_CONFIG')
        agent = PlatformManagerAgent(config_path=config)
        agent.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
