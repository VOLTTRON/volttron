# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of the United States Government. Neither the
# United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any
# jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product, process, or service by trade name,
# trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions
# of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency
# thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY under
# Contract DE-AC05-76RL01830
# }}}

import requests
import sys
import json
authentication=None


def do_rpc(method, params=None ):
    global authentication
    url_root = 'http://localhost:8080/jsonrpc'


    json_package = {
        'jsonrpc': '2.0',
        'id': '2503402',
        'method':method,
    }

    if authentication:
        json_package['authorization'] = authentication

    if params:
        json_package['params'] = params

    data = json.dumps(json_package)

    return requests.post(url_root, data=json.dumps(json_package))

def get_dict(text):
    return json.loads(text)

def inspect_agent(platform_uuid, agent_uuid):
    method = "platforms.uuid.{}.agents.uuid.{}.inspect".format(platform_uuid,
                                                       agent_uuid)
    return do_rpc(method)

def list_agents(platform_uuid):
    method = "platforms.uuid.{}.list_agents".format(platform_uuid)
    return do_rpc(method)

def inspect_method(platform_uuid, agent_uuid, method):
    method = "platforms.uuid.{}.agents.uuid.{}.{}.inspect".format(platform_uuid,
                                                                  agent_uuid,
                                                                  method)
    return do_rpc(method)

def exec_method(platform_uuid, agent_uuid, method, params):
    method = "platforms.uuid.{}.agents.uuid.{}.{}".format(platform_uuid,
                                                                  agent_uuid,
                                                                  method)
    return do_rpc(method, params)

def register_platform(address, identity):
    print "Registering platform platform"
    return do_rpc('register_platform', {'address': address,
                                        'identity': identity});

def register_instance(discovery_address):
    print "Registering platform instance"
    return do_rpc(
        'register_instance', {'discovery_address': discovery_address})


if __name__ == '__main__':
    response = do_rpc("get_authorization", {'username': 'admin',
                                           'password': 'admin'})

    response = register_instance("127.0.0.2:8080")
    if response.ok:
        success = response.json()['result']
        if success:
            print('default platform registered')
        else:
            print("default platform not registered correctly")
            sys.exit(0)
    else:
        print('Getting platforms unsuccessful')
        sys.exit(0)

    response = do_rpc("list_platforms")
    platforms = None
    if response.ok:
        platforms = json.loads(response.text)['result']
        print('Platforms retrieved')
    else:
        print('Getting platforms unsuccessful')
        sys.exit(0)


    if len(platforms) > 0:
        for p in platforms:
            print(p)

            response = list_agents(p['uuid'])
            if response.ok:
                print("RESPONSE WAS: "+response.text)

                agents = json.loads(response.text)['result']

                for a in agents:
                    print('agents name {name}'.format(**a))
                    if 'hello' in a['name']: # hello agent only
                        print("routing to: ", p['uuid'])
                        print('agent uuid: ', a['uuid'])
                        response = inspect_agent(p['uuid'], a['uuid'])

                        print("INSPECT RESPONSE {}".format(response))
                        print("INSPECT RESPONSE {}".format(response.text))

                        methods = json.loads(response.text)

                        response = inspect_method(p['uuid'], a['uuid'], 'sayHello')
                        print("RESPONSE WAS: "+response.text)

                        response = exec_method(p['uuid'], a['uuid'], 'sayHello', {'name': 'Ralphie'})
                        print("RESPONSE WAS: "+response.text)

                        if response.ok:
                            print("RESPONSE WAS: "+response.text)
                            methods = json.loads(response.text)['result']
                            print('Methods received for {}'.format(p['uuid']))

                            print(methods)
                        else:
                            print('Getting methods unsuccessful')
                            sys.exit(0)


            else:
                print('Listing agents unsuccessful')
                sys.exit(0)





