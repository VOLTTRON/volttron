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

import gevent
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttron.platform import get_address
from volttron.platform.keystore import KeyStore
from argparse import ArgumentParser, RawTextHelpFormatter
import os
import glob

description = """
Updates the contents of the Master Driver configuration store with a set of
configurations in a directory. This is designed to work with the output of
the update_master_driver_config.py script.

The script expects the target directory to have the following files and directories:

config              #The main configuration file
registry_configs    #A directory with all registry files in CSV format.
devices             #A directory with subdirectories and/or device configuration files.

The path to a device configuration file in the devices directory will be
used to created the name of the configuration in the store and therefore
 the topic that will associated with the device.

For example:

A device configuration with the path "devices/campus/building/my_device" will
be named "devices/campus/building/my_device" when added to the Master Driver
configuration store.

All other files and directories are ignored.

The VOLTTRON platform must be running in order for this script to work.

Any errors in the configurations will cause the process to stop with an error.

By default this will delete the old master driver configuration store before
adding new configurations.
"""

def install_configs(input_directory, keep=False):
    os.chdir(input_directory)

    keystore = KeyStore()
    agent = Agent(address=get_address(), identity="master_driver_update_agent",
                  publickey=keystore.public, secretkey=keystore.secret,
                  enable_store=False)

    event = gevent.event.Event()
    gevent.spawn(agent.core.run, event)
    event.wait()

    if not keep:
        print "Deleting old Master Driver store"
        agent.vip.rpc.call(CONFIGURATION_STORE,
                           'manage_delete_store',
                           PLATFORM_DRIVER).get(timeout=10)

    with open("config") as f:
        print "Storing main configuration"
        agent.vip.rpc.call(CONFIGURATION_STORE,
                           'manage_store',
                           PLATFORM_DRIVER,
                           'config',
                           f.read(),
                           config_type="json").get(timeout=10)


    for name in glob.iglob("registry_configs/*"):
        with open(name) as f:
            print "Storing configuration:", name
            agent.vip.rpc.call(CONFIGURATION_STORE,
                               'manage_store',
                               PLATFORM_DRIVER,
                               name,
                               f.read(),
                               config_type="csv").get(timeout=10)

    for dir_path, _, files in os.walk("devices"):
        for file_name in files:
            name = os.path.join(dir_path, file_name)
            with open(name) as f:
                print "Storing configuration:", name
                agent.vip.rpc.call(CONFIGURATION_STORE,
                                   'manage_store',
                                   PLATFORM_DRIVER,
                                   name,
                                   f.read(),
                                   config_type="json").get(timeout=10)

if __name__ == "__main__":
    parser = ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)


    parser.add_argument('input_directory',
                        help='The input directory.')

    parser.add_argument('--keep-old', action="store_true",
                        help="Do not remove existing device driver and registry files from the Master Driver configuration store.")


    args = parser.parse_args()
    install_configs(args.input_directory, args.keep_old)
