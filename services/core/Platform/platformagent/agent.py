# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
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

from __future__ import absolute_import, print_function
import base64
from datetime import datetime
import gevent
import gevent.event
import logging
import sys
import requests
import os
import os.path as p
import re
import shutil
import tempfile
import uuid

import psutil

import gevent
from zmq.utils import jsonapi
from volttron.platform.vip.agent import *

from volttron.platform import vip, jsonrpc, control
from volttron.platform.control import Connection
from volttron.platform.agent import utils

from volttron.platform.jsonrpc import (INTERNAL_ERROR, INVALID_PARAMS,
                                       INVALID_REQUEST, METHOD_NOT_FOUND,
                                       PARSE_ERROR, UNHANDLED_EXCEPTION)

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'

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
    kwargs.pop('identity',None)

    class PlatformAgent(Agent):

        def __init__(self, vc_vip_address=vc_vip_address,
                     vc_vip_identity=vc_vip_address, **kwargs):
            super(PlatformAgent, self).__init__(**kwargs)
            self.vc_vip_identity = vc_vip_identity
            self.vc_vip_address = vc_vip_address

            _log.info('my identity {} address: {}'.format(self.core.identity,
                                                      self.core.address))
            # a list of registered managers of this platform.
            self._managers = set()
            self._managers_reachable = {}
            self._services = {}
            self._settings = {}
            self._load_settings()
            self._agent_configurations = {}
            self._sibling_cache = {}
            self._vip_channels = {}

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
                _log.debug('Exception '+ e.message)
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


        @RPC.export
        def set_setting(self, key, value):
            _log.debug("Setting key: {} to value: {}".format(key, value))
            self._settings[key] = value
            self._store_settings()


        @RPC.export
        def get_setting(self, key):
            _log.debug('Retrieveing key: {}'.format(key))
            return self._settings.get(key, None)

        @Core.periodic(period=15, wait=30)
        def write_status(self):
            historian_present = False

            try:
                ping = self.vip.ping('platform.historian', 'awake?').get(timeout=2)
                historian_present = True
            except Unreachable:
                _log.warning('platform.historian unavailable no logging of data will occur.')
                return
            _log.debug('publishing data')
            base_topic = 'datalogger/log/platform/status'
            cpu = base_topic + '/cpu'
            virtual_memory = base_topic + "/virtual_memory"
            disk_partitions = base_topic + "/disk_partiions"

            points = {}

            for k, v in psutil.cpu_times_percent().__dict__.items():
                points['times_percent/' + k] = {'Readings': v,
                                                'Units': 'double'}

            points['percent'] = {'Readings': psutil.cpu_percent(),
                                 'Units': 'double'}

            message = jsonapi.dumps(points)
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=cpu,
                                    message=points)

        @RPC.export
        def publish_to_peers(self, topic, message, headers = None):
            spawned = []
            _log.debug("Should publish to peers: "+str(self._sibling_cache))
            for key, item in self._sibling_cache.items():
                for peer_address in item:
                    try:
#                         agent = Agent(address=peer_address)

#                         event = gevent.event.Event()
#                         gevent.spawn(agent.core.run, event)
#                         event.wait()
                        agent = self._get_rpc_agent(peer_address)
                        _log.debug("about to publish to peers: {}".format(agent.core.identity))
#                         agent.vip.publish()
                        agent.vip.pubsub.publish(peer='pubsub',headers=headers,
                                        topic=topic,
                                        message=message)

                    except Unreachable:
                        _log.error("Count not publish to peer: {}".
                                   format(peer_address))

        #TODO: Make configurable
        @Core.periodic(30)
        def update_sibling_address_cache(self):
            _log.debug('update_sibling_address_cache '+str(self._managers))
            for manager in self._managers:
                try:
#                     _log.debug("Manager",manager)
#                     _log.debug(manager[0],manager[1])
                    #TODO: #14 Go through manager addresses until one works. For now just use first.
                    agent = self._get_rpc_agent(manager[0][0])
#                     agent = Agent(address=manager[0])
                    result = agent.vip.rpc.call(manager[1],"list_platform_details").get(timeout=10)
#                     _log.debug("RESULT",result)
                    self._sibling_cache[manager[0]] = result

                except Unreachable:
                    _log.error('Could not reach manager: {}'.format(manager))
                except StandardError as ex:
                    _log.error("Unhandled Exception: "+str(ex))




        @RPC.export
        def register_service(self, vip_identity):
            # make sure that we get a ping reply
            response = self.vip.ping(vip_identity).get(timeout=5)

            alias = vip_identity

            # make service list not include a platform.
            if vip_identity.startswith('platform.'):
                alias = vip_identity[len('platform.'):]

            self._services[alias] = vip_identity

        @RPC.export
        def services(self):
            return self._services


        @RPC.export
        def list_agents(self):
            result = self.vip.rpc.call("control", "list_agents").get()
            return result

        def _install_agents(self, agent_files):
            tmpdir = tempfile.mkdtemp()
            results = []
            for f in agent_files:
                try:

                    path = os.path.join(tmpdir, f['file_name'])
                    with open(path, 'wb') as fout:
                        fout.write(base64.decodestring(f['file'].split('base64,')[1]))

                    agent_uuid = control._send_agent(self, 'control', path).get(timeout=15)
                    results.append({'uuid': agent_uuid})

                except Exception as e:
                    results.append({'error': e.message})
                    _log.error("EXCEPTION: "+e.message)

            try:
                shutil.rmtree(tmpdir)
            except:
                pass
            return results

        @RPC.export
        def route_request(self, id, method, params):
            _log.debug('platform agent routing request: {}, {}'.format(id, method))
            _log.debug('platform agent routing request params: {}'.format(params))

            # First handle the elements that are going to this platform
            if method == 'list_agents':
                result = self.list_agents()
            elif method == 'set_setting':
                result = self.set_setting(**params)
            elif method == 'get_setting':
                result = self.get_setting(**params)
            elif method == 'status_agents':
                result = {'result': [{'name':a[1], 'uuid': a[0],
                                      'process_id': a[2][0],
                                      'return_code': a[2][1]}
                            for a in self.vip.rpc.call('control', method).get()]}

            elif method in ('agent_status', 'start_agent', 'stop_agent',
                            'remove_agent'):
                _log.debug('We are trying to exectute method {}'.format(method))
                if isinstance(params, list) and len(params) != 1 or \
                    isinstance(params, dict) and 'uuid' not in params.keys():
                    result['code'] = INVALID_PARAMS
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
                        result = {'process_id': status[0], 'return_code': status[1]}
            elif method in ('install'):

                if not 'files' in params:
                    result = {'code': INVALID_PARAMS}
                else:
                    result = self._install_agents(params['files'])

            else:

                fields = method.split('.')

                if self._services.get(fields[0], None):
                    service_identity = self._services[fields[0]]
                    agent_method = fields[1]

                    result = self.vip.rpc.call(service_identity, agent_method,
                                               **params).get()


                else:

                    result = {'code': METHOD_NOT_FOUND}

                    if len(fields) < 3:
                        result = result = {'code': METHOD_NOT_FOUND}
                    else:
                        agent_uuid = fields[2]
                        agent_method = '.'.join(fields[3:])
                        _log.debug("Calling method {} on agent {}"
                                   .format(agent_method, agent_uuid))
                        _log.debug("Params is: {}".format(params))

                        result = self.vip.rpc.call(agent_uuid, agent_method,
                                               params).get()

            if isinstance(result, dict):
                if 'result' in result:
                    return result['result']
                elif 'code' in result:
                    return result['code']

            return result

        @RPC.export
        def list_agent_methods(self, method, params, id, agent_uuid):
            return get_error_response(id, INTERNAL_ERROR, 'Not implemented')

        @RPC.export
        def manage(self, address, identity):
            key = (address, identity)
            self._managers.add(key)
            self._managers_reachable[key] = True
            return True

        @Core.receiver('onstart')
        def starting(self, sender, **kwargs):

            psutil.cpu_times_percent()
            psutil.cpu_percent()
            _, _, my_id = self.vip.hello().get(timeout=3)
            self.vip.pubsub.publish(peer='pubsub', topic='/platform',
                                    message='available')
        @Core.receiver('onstop')
        def stoping(self, sender, **kwargs):
            self.vip.pubsub.publish(peer='pubsub', topic='/platform',
                                    message='leaving')

    PlatformAgent.__name__ = 'PlatformAgent'
    return PlatformAgent(identity=vip_identity, **kwargs)


def is_ip_private(vip_address):
    ip = vip_address.strip().lower().split("tcp://")[1]

    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) != None or priv_24.match(ip) != None or priv_20.match(ip) != None or priv_16.match(ip) != None


def find_registration_address(vip_addresses):
    # Find the address to send back to the VCentral in order of preference
    # Non-private IP (first one wins)
    # TCP address (last one wins)
    # IPC if first element is IPC it wins
     #Pull out the tcp address

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
    #utils.vip_main(platform_agent)
    utils.vip_main(platform_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
