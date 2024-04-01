# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
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
                               'list_configs',
                               vip_id).get(timeout=10)

    if filename not in files:
        config = {key: value}
    else:
        config = agent.vip.rpc.call(CONFIGURATION_STORE,
                                    'get_config',
                                    vip_id,
                                    filename).get(timeout=10)
        config = jsonapi.loads(config)
        config[key] = value

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'set_config',
                       vip_id,
                       filename,
                       jsonapi.dumps(config),
                       'json').get(timeout=10)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
