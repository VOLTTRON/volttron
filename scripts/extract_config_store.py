# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import gevent
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttron.platform import get_address
from volttron.platform.keystore import KeyStore
from argparse import ArgumentParser, RawTextHelpFormatter
import os
import errno

description = """
Extracts the contents of a config store to disk.
"""

def ensure_dir(file_path):
    #makedirs fails if we pass an empty string.
    if not file_path:
        return

    if not os.path.exists(file_path):
        try:
            os.makedirs(file_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

def get_configs(config_id, output_directory):


    keystore = KeyStore()
    agent = Agent(address=get_address(),
                  publickey=keystore.public, secretkey=keystore.secret,
                  enable_store=False)

    event = gevent.event.Event()
    gevent.spawn(agent.core.run, event)
    event.wait()

    config_list = agent.vip.rpc.call(CONFIGURATION_STORE,
                           'manage_list_configs',
                           config_id).get(timeout=10)

    if not config_list:
        print("Config store", config_id, "does not exist.")
        return

    ensure_dir(output_directory)

    os.chdir(output_directory)

    for config in config_list:
        print("Retrieving configuration", config)
        raw_config = agent.vip.rpc.call(CONFIGURATION_STORE,
                           'manage_get',
                           config_id,
                           config, raw=True).get(timeout=10)

        ensure_dir(os.path.dirname(config))

        with open(config, "w") as f:
            f.write(raw_config)



if __name__ == "__main__":
    parser = ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)

    parser.add_argument('config_id',
                        help='The ID of the config store to extract.')

    parser.add_argument('output_directory',
                        help='The output directory.')


    args = parser.parse_args()
    get_configs(args.config_id, args.output_directory)
