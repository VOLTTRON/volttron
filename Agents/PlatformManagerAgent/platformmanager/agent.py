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
from functools import wraps, partial
import json
import logging
import sys
import requests
import threading
import os
import os.path as p
import uuid

import gevent
import greenlet
import tornado
import tornado.ioloop
import tornado.web
from tornado.web import url

from authenticate import Authenticate
from manager import Manager

from volttron.platform import vip, jsonrpc
from volttron.platform.control import Connection
from volttron.platform.agent.vipagent import RPCAgent, periodic, onevent, jsonapi, export
from volttron.platform.agent import utils
from volttron.platform.async import AsyncCall

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
    '''A handler for dealing with authentication of sessions

    The SessionHandler requires an authenticator to be handed in to this
    object in order to authenticate user.  The authenticator must implement
    an interface that expects a method called authenticate with parameters
    username and password.  The return value must be either a list of groups
    the user belongs two or None.

    If successful then the a session token is generated and added to a cache
    of validated users to be able to be checked against.  The user's ip address
    is stored with the token for further checking of authentication.
    '''
    def __init__(self, authenticator):
        self._sessions = {}
        self._session_tokens = {}
        self._authenticator = authenticator

    def authenticate(self, username, password, ip):
        '''Authenticates a user with the authenticator.

        This is the main login function for the system.
        '''
        groups = self._authenticator.authenticate(username, password)
        if groups:
            token = uuid.uuid4()
            self._add_session(username, token, ip, ",".join(groups))
            return token
        return None

    def _add_session(self, user, token, ip, groups):
        '''Add a user session to the session cache'''
        self._sessions[user] = {'user': user, 'token': token, 'ip': ip, 'groups': groups}
        self._session_tokens[token] = self._sessions[user]

    def check_session(self, token, ip):
        '''Check if a user token has been authenticated.'''
        session = self._session_tokens.get(uuid.UUID(token))
        if session:
            return session['ip'] == ip

        return False

class ManagerWebApplication(tornado.web.Application):
    '''A tornado web application wrapper class.

    This classes responsibility is to hold sessions and the agent manager
    class so that the request handler has access to these resources.

    Request handlers have access to this function through
        self.application.manager and
        self.application.sessions
    respectively.
    '''
    def __init__(self, session_handler, manager, handlers=None,
                 default_host="", transforms=None, **settings):
        super(ManagerWebApplication, self).__init__(handlers, default_host,
                                                    transforms, **settings)
        self.sessions = session_handler
        self.manager = manager

class RpcResponse:
    '''Wraps a response from rpc call in a json wrapper.'''

    def __init__(self, id, **kwargs):
        '''Initialize the response object with id and parameters.

        This method requires that either a code and message be set or a result
        be set via the kwargs.

        If code is a standard specification error then message will be set
        automatically. If message is set it will override the default message
        from the specs.

        Ex.
            RpcResponse('xwrww', code=401, message='Authorization error')
            RpcResponse('xw223', code=INVALID_PARAMS)

        '''
        self.id = id
        self.result = kwargs.get('result', None)
        self.message = kwargs.get('message', None)
        self.code = kwargs.get('code', None)

        if self.message == None and \
            self.code in (INTERNAL_ERROR, INVALID_PARAMS,
                           INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                           UNHANDLED_EXCEPTION):
            self.message = self.get_standard_error(self.code)

        # There is probably a better way to move the result up a level, however
        # this was the fastest I could think of.
        if isinstance(self.result, dict) and 'result' in self.result:
            self.result = self.result['result']

    def get_standard_error(self, code):

        if code == INTERNAL_ERROR:
            error = 'Internal JSON-RPC error'
        elif code == INVALID_PARAMS:
            error = 'Invalid method parameter(s).'
        elif code == INVALID_REQUEST:
            error = 'The JSON sent is not a valid Request object.'
        elif code == METHOD_NOT_FOUND:
            error = 'The method does not exist / is not available.'
        elif code == PARSE_ERROR:
            error = 'Invalid JSON was received by the server. '\
                    'An error occurred on the server while parsing the JSON text.'
        else:
            #UNHANDLED_EXCEPTION
            error = 'Unhandled exception happened!'

    def get_response(self):
        d = {'jsonrpc': '2.0', 'id': self.id}

        if self.code != None:
            d['error'] = {'code': self.code,
                          'message': self.message}
        else:
            d['result'] = self.result

        return d

class RpcRequest:
    PARSE_ERR = {'code': -32700, 'message': 'Parse error'}

    def was_error(self):
        '''Returns true if there is an error that was set on this object.

        The error could be set either through a parse error or through
        set_error.
        '''
        return not (self.error == None)


    def set_result(self, result):
        self.clear_err()
        self._result = result

    def __init__(self, request_body=None,
                 id=None, method=None, params = None):

        try:
            self.id = None # default for json RpcParser with parse error
            self.error = None

            if request_body:
                data = json.loads(request_body)

                if data == []:
                    self.error = INVALID_REQUEST
                    return

                if not 'method' in data:
                    self.error = METHOD_NOT_FOUND
                    return

                if not 'jsonrpc' in data or data['jsonrpc'] != '2.0':
                    self.error = PARSE_ERROR
                    return

                if not 'id' in data:
                    self.error = PARSE_ERROR
                    return

                # This is only necessary at the top level of the RpcParser stack.
                if not "authorization" in data:
                    if data['method'] != 'get_authorization':
                        self.error = 401
                        return
                if "authorization" in data:
                    self.authorization = data['authorization']
            else:
                data = {'method':method, 'id': id, 'jsonrpc': '2.0',
                        'params':params}

            self.method = data['method']
            self.jsonrpc = data['jsonrpc']
            self.id = data['id']
            if 'params' in data:
                self.params = data['params']
            else:
                self.params = []

        except:
            self.error = PARSE_ERROR


class ManagerRequestHandler(tornado.web.RequestHandler):
    '''The main RequestHanlder for the platform manager.

    The manager only accepts posted RpcParser methods.  The manager will parse
    the request body for valid json RpcParser.  The first call to this request
    handler must be a getAuthorization request.  The call will return an
    authorization token that will be valid for the current session.  The token
    must be passed to any other calls to the handler or a 401 Unauhthorized
    code will be returned.
    '''


    def _route(self, rpcRequest):
        # this is the only method that the handler truly deals with, the
        # rest will be dispatched to the manager agent itself.
        if rpcRequest.method == 'get_authorization':
            try:
                token = self.application.sessions.authenticate(
                            rpcRequest.params['username'],
                            rpcRequest.params['password'],
                            self.request.remote_ip)
                if token:
                    rpcResponse = RpcResponse(rpcRequest.id, result=str(token))
                    #rpcRequest.set_result(str(token))
                else:
                    rpcResponse = RpcResponse(rpcRequest.id,
                                  code=401,
                                  message="invalid username or password")
            except:
                rpcResponse = RpcResponse(rpcRequest.id,
                              code=INVALID_PARAMS,
                              message='Invalid parameters to {}'.format(rpcRequest.method))


            self._response_complete((None, rpcResponse))
        else:
            # verify the user session
            if not self.application.sessions.check_session(
                            rpcRequest.authorization,
                            self.request.remote_ip):
                rpcResponse = RpcResponse(rpcRequest.id,
                                  code=401,
                                  message="Unauthorized Access")
                self._response_complete((None, rpcResponse))
            else:

                print("Calling: {}".format(rpcRequest.method))
                async_caller = self.application.manager.async_caller
                async_caller.send(self._response_complete,
                                     self.application.manager.route_request,
                                     rpcRequest.id,
                                     rpcRequest.method,
                                     rpcRequest.params)

    def _response_complete(self, data):

        if (data[0] != None):
            if isinstance(data[0], RpcResponse):
                self.write(data[0].get_response())
            else:
                self.write("Error: "+str(data[0][0])+" message: "+str(data[0][1]))
        else:
            if isinstance(data[1], RpcResponse):
                self.write(data[1].get_response())
            else:
                rpcresponse = RpcResponse(self.rpcrequest.id, result=data[1])
                self.write(rpcresponse.get_response())
        try:
            print("rpcresponse: {}".format(rpcresponse.get_response()))
        except:
            pass
        print('handling request done')
        self.finish()

    @tornado.web.asynchronous
    def post(self):
        print('handling request')
        request_body = self.request.body
        # result will be an RpcParser object  when completed
        self.rpcrequest = RpcRequest(request_body)
        print('Request_Body: {}'.format(request_body))
        print("Request is: " + str(self.rpcrequest.__dict__))
        self._route(self.rpcrequest)


def PlatformManagerAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name, fallback=''):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, fallback)
    home = os.path.expanduser(os.path.expandvars(
        os.environ.get('VOLTTRON_HOME', '~/.volttron')))
    vip_address = 'ipc://@{}/run/vip.socket'.format(home)
    vip_identity = 'platform_manager'
    #s1 = SenderAgent('sender', vip_address=path, vip_identity='replier')

    agent_id = get_config('agentid')
    server_conf = get_config('server', {})
    user_map = get_config('users')

    hander_config = [
        (r'/jsonrpc', ManagerRequestHandler),
        (r'/jsonrpc/', ManagerRequestHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,\
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

    def makeVipAgentRequest(agent_uuid, **args):
        platform['ctl'] = Connection('platform_manager')

#                                                  peer=platform_uuid)

    class Agent(RPCAgent):
        """Agent for querying WeatherUndergrounds API"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(vip_address, vip_identity, **kwargs)
            print("Registering (vip_address, vip_identity)\n\t", vip_address, vip_identity)
            # a list of peers that have checked in with this agent.
            self.platform_dict = {}
            self.valid_data = False


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
                }

            self.platform_dict[peer_identity]['external'] = peer_address != vip_address

            print("Registered: ", self.platform_dict[peer_identity])
            return True


        @export()
        def unregister_platform(self, peer_identity):
            print "unregistering ", peer_identity
            del self.platform_dict[peer_identity]['identity_params']
            return 'Removed'

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
            '''Route request to either a registered platform or handle here.
            '''

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
            if platform['peer_address'] == vip_address:
                result = self.rpc_call(str(platform_uuid), 'route_request',
                                       [id, platform_method, params]).get()
            else:
                ctl = Connection(platform['peer_address'],
                                             peer=platform_uuid)
                result = ctl.call("route_request", id, platform_method, params).get()

                if 'ctl' not in platform:
                    print "Connecting to ", platform['peer_address'], 'for peer', platform_uuid
                    platform['ctl'] = Connection(platform['peer_address'],
                                             peer=platform_uuid)

                print "Calling: {Connecting to ", platform['peer_address'], 'for peer', platform_uuid
                result = platform['ctl'].call("route_request", id, platform_method, params).get()


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
