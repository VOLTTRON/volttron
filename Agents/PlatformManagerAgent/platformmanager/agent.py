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
import os
import os.path as p
import uuid

from authenticate import Authenticate

from volttron.platform.agent import BaseAgent
from volttron.platform.agent.utils import jsonapi
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot'))

class ValidationException(Exception):
    pass

class LoggedIn:
    def __init__(self, authenticator):
        self.sessions = {}
        self.session_token = {}
        self.authenticator = authenticator

    def authenticate(self, username, password, ip):
        groups = self.authenticator.authenticate(username, password)
        if groups:
            token = uuid.uuid4()
            self._add_session(username, token, ip, ",".join(groups))
            return token
        return None

    def _add_session(self, user, token, ip, groups):
        self.sessions[user] = {user: user, token: token, ip: ip, groups: groups}
        self.session_token[token] = self.sessions[user]

    def check_session(self, token, ip):
        session = self.session_token.get(token)
        if not session:
            return session['ip'] == ip

        return False



class WebApi:

    def __init__(self, authenticator):
        self.sessions = LoggedIn(authenticator)

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def index(self):
        '''
        Example curl post
        curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0","method": "getAuthorization","params": {"username": "dorothy","password": "toto123"},"id": "someid"}' \
 http://127.0.0.1:8080/api/

        Successful response
             {"jsonrpc": "2.0",
              "result": "071b5022-4c35-4395-a4f0-8c32905919d8",
              "id": "someid"}
        Failed
            401 Unauthorized
'''
        print cherrypy.request.json
        if cherrypy.request.json.get('jsonrpc') != '2.0':
            raise ValidationException('Invalid jsnrpc version')
        if not cherrypy.request.json.get('method'):
            raise ValidationException('Invalid method')
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
                    'error': {'code': 401, 'message': 'Unauthorized'},
                    'id': cherrypy.request.json.get('id')}

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

class Root:
    @cherrypy.expose
    def index(self):
        return open(os.path.join(WEB_ROOT, u'index.html'))

def PlatformManagerAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, '')

    agent_id = get_config('agentid')
    server_conf = {'global': get_config('server')}
    user_map = get_config('users')

    static_conf = {
        "/": {
            "tools.staticdir.on": True,
            "tools.staticdir.dir": WEB_ROOT
        }
    }

    #poll_time = get_config('poll_time')
    #zip_code = get_config("zip")
    #key = get_config('key')

    class Agent(BaseAgent):
        """Agent for querying WeatherUndergrounds API"""

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.valid_data = False
            self.webserver = WebApi(Authenticate(user_map))

        def setup(self):
            super(Agent, self).setup()
            #cherrypy.tree.mount(self.webserver, "/", config=static_conf)
            cherrypy.tree.mount(self.webserver, "/api")
            cherrypy.tree.mount(Root(), "/", config=static_conf)
            #cherrypy.config.update(server_conf)
            #cherrypy.config.update(static_conf)
            cherrypy.engine.start()

        def finish(self):
            cherrypy.engine.stop()
            super(Agent, self).finish()


    Agent.__name__ = 'ManagedServiceAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(PlatformManagerAgent,
                       description='The managed server agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
