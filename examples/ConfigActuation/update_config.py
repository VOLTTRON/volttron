# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

"""Script for adding or updating a JSON file in an agent's
:ref:`configuration store <VOLTTRON-Configuration-Store>`.

Add an integer, float, or string value in the top level dictionary
of a configuration file.

If the file does not exist it will be created with the given name.
"""

import argparse
import json

from volttron.platform import get_address
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
        config = json.loads(config)
        config[key] = value

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       vip_id,
                       filename,
                       json.dumps(config),
                       'json').get(timeout=10)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
