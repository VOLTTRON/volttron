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

import cherrypy
import datetime
import json
import logging
import sys
import requests
import threading
import os
import os.path as p
import uuid

import tornado
import tornado.ioloop
import tornado.web
from tornado.web import url


from authenticate import Authenticate
from manager import Manager

from volttron.platform.agent.utils import jsonapi, isapipe
from volttron.platform.agent import utils

from volttron.platform import vip, jsonrpc
from volttron.platform.control import Connection
from volttron.platform.agent.vipagent import RPCAgent, periodic, onevent, jsonapi, export
from volttron.platform.agent import utils

from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                                       UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)
WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))

class PlatformRegistry:

    def __init__(self, stale=5*60):
        pass

class SessionHandler:
    def __init__(self, authenticator):
        self._sessions = {}
        self._session_tokens = {}
        self._authenticator = authenticator

    def authenticate(self, username, password, ip):
        groups = self.authenticator.authenticate(username, password)
        if groups:
            token = uuid.uuid4()
            self._add_session(username, token, ip, ",".join(groups))
            return token
        return None

    def _add_session(self, user, token, ip, groups):
        self.sessions[user] = {'user': user, 'token': token, 'ip': ip, 'groups': groups}
        self.session_token[token] = self.sessions[user]

    def check_session(self, token, ip):
        session = self.session_token.get(uuid.UUID(token))
        if session:
            return session['ip'] == ip

        return False

class ManagerWebApplication(tornado.web.Application):
    def __init__(self, session_handler, manager_agent, handlers=None,
                 default_host="", transforms=None, **settings):
        super(ManagerWebApplication, self).__init__(handlers, default_host,
                                                    transforms, **settings)
        self.sessions = session_handler
        self.manager_agent = manager_agent


class ManagerRequestHandler(tornado.web.RequestHandler):

    def get(self):
        print("Get")
        self.write("Woot")

    def post(self):
        print("Post")
        self.write("Post woot")

class ValidationException(Exception):
    pass

class WebApi:

    def __init__(self, authenticator):
        self.sessions = LoggedIn(authenticator)
        self.manager = Manager()

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.allow(methods=['POST'])
    def twoway(self):
        '''You can call it like:
        curl -X POST -H "Content-Type: application/json" \
          -d '{"foo":123,"bar":"baz"}' http://127.0.0.1:8080/api/twoway
        '''

        data = cherrypy.request.json
        return data.items()

def get_error_response(id, code, message, data):
    return {'jsonrpc': '2.0',
            'error': { 'code': code, 'message': message, 'data' : data},
            'id': id
            }

class Root:

    def __init__(self, authenticator, manager):
        self.sessions = LoggedIn(authenticator)
        self.manager = manager

    @cherrypy.expose
    def index(self):
        return open(os.path.join(WEB_ROOT, u'index.html'))

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def jsonrpc(self):
        '''
        Example curl post
        curl -X POST -H "Content-Type: application/json" \
            -d '{"jsonrpc": "2.0","method": "getAuthorization","params": {"username": "dorothy","password": "toto123"},"id": "someid"}' \
            http://127.0.0.1:8080/jsonrpc/

        Successful response
            {"jsonrpc": "2.0",
             "result": "071b5022-4c35-4395-a4f0-8c32905919d8",
             "id": "someid"}
        Failed
            401 Invalid username or password
        '''

        if cherrypy.request.json.get('jsonrpc') != '2.0':
            return get_error_response(cherrypy.request.json.get('id'), PARSE_ERROR,
                    'Invalid jsonrpc version', None)
        if not cherrypy.request.json.get('method'):
            return get_error_response(cherrypy.request.json.get('id'), METHOD_NOT_FOUND,
                    'Method not found', {'method':  cherrypy.request.json.get('method')})
        if cherrypy.request.json.get('method') == 'getAuthorization':
            if not cherrypy.request.json.get('params'):
                raise ValidationException('Invalid params')
            params = cherrypy.request.json.get('params')
            if not params.get('username'):
                raise ValidationException('Specify username')
            if not params.get('password'):
                raise ValidationException('Specify password')

            token = self.sessions.authenticate(params.get('username'),
                                   params.get('password'),
                                   cherrypy.request.remote.ip)

            if token:
                return {'jsonrpc': '2.0',
                        'result': str(token),
                        'id': cherrypy.request.json.get('id')}

            return {'jsonrpc': '2.0',
                    'error': {'code': 401,
                              'message': 'Invalid username or password'},
                    'id': cherrypy.request.json.get('id')}
        else:
            token = cherrypy.request.json.get('authorization')

            if not token:
                return {'jsonrpc': '2.0',
                        'error': {'code': 401,
                                  'message': 'Authorization required'},
                        'id': cherrypy.request.json.get('id')}

            if not self.sessions.check_session(token, cherrypy.request.remote.ip):
                return {'jsonrpc': '2.0',
                        'error': {'code': 401,
                                  'message': 'Invalid or expired authorization'},
                        'id': cherrypy.request.json.get('id')}

            method = cherrypy.request.json.get('method')
            params = cherrypy.request.json.get('params')
            id = cherrypy.request.json.get('id')

            return self.manager.dispatch(method, params, id)

        return {'jsonrpc': '2.0',
                'error': {'code': 404, 'message': 'Unknown method'},
                'id': cherrypy.request.json.get('id')}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.allow(methods=['POST'])
    def twoway(self):
        '''You can call it like:
        curl -X POST -H "Content-Type: application/json" \
          -d '{"foo":123,"bar":"baz"}' http://127.0.0.1:8080/api/twoway
        '''

        data = cherrypy.request.json
        return data.items()

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.allow(methods=['POST'])
    def listPlatforms(self):
        return manager.current_platforms()

# class Root:
#     @cherrypy.expose
#     def index(self):
#         return open(os.path.join(WEB_ROOT, u'index.html'))

def PlatformManagerAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, '')
    home = os.path.expanduser(os.path.expandvars(
        os.environ.get('VOLTTRON_HOME', '~/.volttron')))
    vip_address = 'ipc://@{}/run/vip.socket'.format(home)
    vip_identity = 'platform_manager'
    #s1 = SenderAgent('sender', vip_address=path, vip_identity='replier')

    agent_id = get_config('agentid')
    server_conf = {'global': get_config('server')}
    user_map = get_config('users')

    static_conf = {
        "/": {
            "tools.staticdir.root": WEB_ROOT
        },
        "/css": {
            "tools.staticdir.on": True,
            "tools.staticdir.dir": "css"
        },
        "/js": {
            "tools.staticdir.on": True,
            "tools.staticdir.dir": "js"
        }
    }

    hander_config = [
        (r'/jsonrpc/(.*)', ManagerRequestHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,\
            {"path": WEB_ROOT, "default_filename": "index.html"})
]
#         ,
#         (r'/css/(.*)', tornado.web.StaticFileHandler,
#                         {"path": p.join(WEB_ROOT, 'css')}),
#         (r'/js/(.*)', tornado.web.StaticFileHandler,
#                         {'path': p.join(WEB_ROOT, 'js')}),
#         (r'/', tornado.web.StaticFileHandler,
#                         {'path': p.join(WEB_ROOT, 'index.html')})




    def startWebServer(manager_agent):
#         app = tornado.web.Application(handlers=hander_config, debug=True)
#         app.listen(8080) #, address)
#         tornado.ioloop.IOLoop.instance().start()

        webserver = ManagerWebApplication(
                        SessionHandler(Authenticate(user_map)),
                        manager_agent,
                        hander_config, debug=True, static_path=WEB_ROOT)
        webserver.listen(8080)
        tornado.ioloop.IOLoop.instance().start()


    def stopWebServer():
        tornado.ioloop.IOLoop.stop()

    #poll_time = get_config('poll_time')
    #zip_code = get_config("zip")
    #key = get_config('key')

    class Agent(RPCAgent):
        """Agent for querying WeatherUndergrounds API"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(vip_address, vip_identity, **kwargs)
            print("Registering (vip_address, vip_identity)\n\t", vip_address, vip_identity)
            # a list of peers that have checked in with this agent.
            self.platform_dict = {}
            self.valid_data = False
            #self.webserver = Root(Authenticate(user_map), self)

        def list_agents(self, platform):

            if platform in self.platform_dict.keys():
                return self.rpc_call(platform, "list_agents").get()
            return "PLATFORM NOT FOUND"

        @export()
        def register_platform(self, peer_identity, name, peer_address):
            print "registering ", peer_identity
            self.platform_dict[peer_identity] = {
                    'identity_params':  {'name': name, 'uuid': peer_identity},
                    'peer_address': peer_address,
                }

            self.platform_dict[peer_identity]['external'] = peer_address != vip_address

            return True


        @export()
        def unregister_platform(self, peer_identity):
            print "unregistering ", peer_identity
            del self.platform_dict[peer_identity]['identity_params']
            return 'Removed'

        @onevent("start")
        def start(self):
            threading.Thread(target=startWebServer, args=(self,)).start()
            #threading.Thread(target=startWebServer, args=(self,)).start()
            print("Web server started!")
            #startWebServer()
            #print("Web server started")
            #super(Agent, self).setup()
            #cherrypy.tree.mount(self.webserver, "/", config=static_conf)
            #cherrypy.engine.start()

        @onevent("finish")
        def finish(self):
            stopWebServer()
            print("Web server stopped")
            #cherrypy.engine.stop()


        def dispatch (self, method, params, id):
            retvalue = {"jsonrpc": "2.0", "id":id}


            if method == 'listPlatforms':
                retvalue["result"] = [x['identity_params'] for x in self.platform_dict.values()]

            else:

                fields = method.split('.')

                # must have platform.uuid.<uuid>.<somemethod> to pass through
                # here.
                if len(fields) < 3:
                    return get_error_response(id, METHOD_NOT_FOUND,
                                              'Unknown Method',
                                              'method was: ' + method)

                platform_uuid = fields[2]

                if platform_uuid not in self.platform_dict:
                    return get_error_response(id, METHOD_NOT_FOUND,
                                              'Unknown Method',
                                              'Unknown platform method was: ' + method)

                platform = self.platform_dict[platform_uuid]

                platform_method = '.'.join(fields[3:])

                # Translate external interface to internal interface.
                platform_method = platform_method.replace("listAgents", "list_agents")
                platform_method = platform_method.replace("listMethods", "list_agent_methods")
                platform_method = platform_method.replace("startAgent", "start_agent")
                platform_method = platform_method.replace("stopAgent", "stop_agent")
                platform_method = platform_method.replace("statusAgents", "status_agents")
                platform_method = platform_method.replace("statusAgent", "agent_status")

                print("calling platform: ", platform_uuid,
                      "method ", platform_method,
                      " params", params)

                platform_method = str(platform_method)

                if platform['peer_address'] == vip_address:
                    result = self.rpc_call(str(platform_uuid), 'dispatch', [platform_method, params])
                else:
                    if 'ctl' not in platform:
                        print "Connecting to ", platform['peer_address'], 'for peer', platform_uuid
                        platform['ctl'] = Connection(platform['peer_address'],
                                                 peer=platform_uuid)

                    result = platform['ctl'].call("dispatch", [platform_method, params])

                # Wait for response to come back
                import time
                while not result.ready():
                    time.sleep(1)


                retvalue['result'] = result.get()
            return retvalue


    Agent.__name__ = 'ManagedServiceAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    try:
        # If stdout is a pipe, re-open it line buffered
        if isapipe(sys.stdout):
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
