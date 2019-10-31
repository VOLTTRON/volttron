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
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""Script for adding or updating a JSON file in an agent's
:ref:`configuration store <VOLTTRON-Configuration-Store>`.

Add an integer, float, or string value in the top level dictionary
of a configuration file.

If the file does not exist it will be created with the given name.
"""

import argparse

from volttron.platform import get_address, jsonapi
from volttron.platform.agent.known_identities import CONFIGURATION_STORE
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.vip.agent.utils import build_agent


def get_keys():
    """Gets keys from keystore and known-hosts store

    :returns: Keys for connecting to the platform
    :rtype: dict
    """
    hosts = KnownHostsStore()
    serverkey = hosts.serverkey(get_address())
    key_store = KeyStore()
    publickey = key_store.public
    secretkey = key_store.secret
    return {'publickey': publickey,
            'secretkey': secretkey,
            'serverkey': serverkey}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('vip_identity',
                        help='VIP Identity of the agent that owns the config')
    parser.add_argument('filename',
                        help='Name of the configstore file to edit')
    parser.add_argument('key',
                        help='Key to add or edit in the config')
    parser.add_argument('value',
                        help='int, float, or string')
    args = parser.parse_args()

    vip_id = args.vip_identity
    filename = args.filename
    key = args.key
    value = args.value

    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            pass

    agent = build_agent(**get_keys())

    files = agent.vip.rpc.call(CONFIGURATION_STORE,
                               'manage_list_configs',
                               vip_id).get(timeout=10)

    if filename not in files:
        config = {key: value}
    else:
        config = agent.vip.rpc.call(CONFIGURATION_STORE,
                                    'manage_get',
                                    vip_id,
                                    filename).get(timeout=10)
        config = jsonapi.loads(config)
        config[key] = value

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       vip_id,
                       filename,
                       jsonapi.dumps(config),
                       'json').get(timeout=10)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
