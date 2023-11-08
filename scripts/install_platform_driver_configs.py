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

import os
import glob

from argparse import ArgumentParser, RawTextHelpFormatter
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER, PLATFORM
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent.utils import build_agent

description = """
Updates the contents of the Platform Driver configuration store with a set of
configurations in a directory. This is designed to work with the output of
the update_platform_driver_config.py script.

The script expects the target directory to have the following files and directories:

config              #The main configuration file
registry_configs    #A directory with all registry files in CSV format.
devices             #A directory with subdirectories and/or device configuration files.

The path to a device configuration file in the devices directory will be
used to created the name of the configuration in the store and therefore
 the topic that will associated with the device.

For example:

A device configuration with the path "devices/campus/building/my_device" will
be named "devices/campus/building/my_device" when added to the Platform Driver
configuration store.

All other files and directories are ignored.

The VOLTTRON platform must be running in order for this script to work.

Any errors in the configurations will cause the process to stop with an error.

By default this will delete the old platform driver configuration store before
adding new configurations.
"""


def install_configs(input_directory, keep=False):
    try:
        os.chdir(input_directory)
    except FileNotFoundError:
        print(f"'input_directory' could not be found: {input_directory}")
        return

    ks = KeyStore()
    agent = build_agent(identity=PLATFORM, publickey=ks.public, secretkey=ks.secret, enable_store=True, timeout=30)

    if not keep:
        print("Deleting old Platform Driver store")
        agent.vip.rpc.call(CONFIGURATION_STORE,
                           'delete_store',
                           PLATFORM_DRIVER).get(timeout=10)

    with open("config") as f:
        print("Storing main configuration")
        agent.vip.rpc.call(CONFIGURATION_STORE,
                           'set_config',
                           PLATFORM_DRIVER,
                           'config',
                           f.read(),
                           config_type="json").get(timeout=10)

    for name in glob.iglob("registry_configs/*"):
        with open(name) as f:
            print("Storing configuration:", name)
            agent.vip.rpc.call(CONFIGURATION_STORE,
                               'set_config',
                               PLATFORM_DRIVER,
                               name,
                               f.read(),
                               config_type="csv").get(timeout=10)

    for dir_path, _, files in os.walk("devices"):
        for file_name in files:
            name = os.path.join(dir_path, file_name)
            with open(name) as f:
                print("Storing configuration:", name)
                agent.vip.rpc.call(CONFIGURATION_STORE,
                                   'set_config',
                                   PLATFORM_DRIVER,
                                   name,
                                   f.read(),
                                   config_type="json").get(timeout=10)


if __name__ == "__main__":
    parser = ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)

    parser.add_argument('input_directory',
                        help='The input directory.')

    parser.add_argument('--keep-old', action="store_true",
                        help="Do not remove existing device driver and registry files from the Platform Driver configuration store.")

    args = parser.parse_args()
    install_configs(args.input_directory, args.keep_old)
