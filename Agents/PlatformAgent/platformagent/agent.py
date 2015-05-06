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
import os
import os.path as p
import uuid

from volttron.platform import vip, jsonrpc
from volttron.platform.control import Connection
from volttron.platform.agent.vipagent import RPCAgent, periodic, onevent, jsonapi, export
from volttron.platform.agent import utils

from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
                                       UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)

def get_error_response(code, message, data=None):
    return {'jsonrpc': '2.0',
            'error': {'code': code, 'message': message, 'data': data}
            }


def platform_agent(config_path, **kwargs):
    config = utils.load_config(config_path)

    agentid = config.get('agentid', 'platform')
    agent_type = config.get('agent_type', 'platform')
    vc_vip_address = config.get('volttron_central_vip_address', None)
    vc_vip_identity = config.get('volttron_central_vip_identity',
                                 "volttron.central")
    vip_identity = config.get('vip_identity', 'platform.agent')

    if not vc_vip_address:
        raise ValueError('Invalid volttron_central_vip_address')

    class Agent(RPCAgent):

        def __init__(self, **kwargs):

            super(Agent, self).__init__(vip_identity=vip_identity, **kwargs)
            self.vip_identity = vip_identity
            self.vc_vip_identity = vc_vip_identity
            self.vc_vip_address = vc_vip_address
            self.agentid = agentid

        @export()
        def list_agents(self):
            result = self.rpc_call("control", "list_agents").get()
            return result

        @export()
        def route_request(self, id, method, params):
            _log.debug('platform agent routing request: {}, {}'.format(id, method))
            if method == 'list_agents':
                result = self.list_agents()
            elif method == 'status_agents':
                result = {'result': [{'name':a[1], 'uuid': a[0], 'process_id': a[2][0],
                          'return_code': a[2][1]}
                         for a in self.rpc_call('control', method).get()]}

            elif method in ('agent_status', 'start_agent', 'stop_agent'):
                status = self.rpc_call('control', method, params).get()
                if method == 'stop_agent' or status == None:
                    # Note we recurse here to get the agent status.
                    result = self.route_request(id, 'agent_status', params)
                else:
                    result = {'process_id': status[0], 'return_code': status[1]}

            if isinstance(result, dict):
                if 'result' in result or 'code' in result:
                    return result

            return result

        @export()
        def list_agent_methods(self, method, params, id, agent_uuid):
            return get_error_response(id, INTERNAL_ERROR, 'Not implemented')

        @onevent('setup')
        def setup(self):
            _log.debug('platform agent setup.  Connection to {} -> {}'.format(
                            self.vc_vip_address, self.vc_vip_identity))
            self._ctl = Connection(self.vc_vip_address,
                                   peer=self.vc_vip_identity)

        @onevent("start")
        def start(self):
            _log.debug('Starting service vip info: {}'.format(
                                                        str(self.__dict__)))
            _log.debug('sending call register_platform {}'.format(
                                    str((vip_identity, agentid, self.vip_address))))
            self._ctl.call("register_platform", vip_identity, agentid, self.vip_address)


        @onevent("finish")
        def stop(self):
            self._ctl.call("unregister_platform", vip_identity)

    Agent.__name__ = 'PlatformAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(platform_agent,
                       description='Agent available to manage from a remote '
                                    + 'system.',
                       no_pub_sub_socket=True,
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
