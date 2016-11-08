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

from volttron.platform.agent.utils import parse_json_config
from argparse import ArgumentParser
from zmq.utils import jsonapi
import os
import shutil

from pprint import pprint

def process_driver_config(config_path, csv_name_map, csv_contents):
    print "Processing config:", config_path
    with open(config_path) as f:
        device_config = parse_json_config(f.read())

    registry_config_file_name = device_config["registry_config"]

    #Sort out name collisions and add to map if needed
    if registry_config_file_name not in csv_name_map:
        print "Processing CSV:", registry_config_file_name
        base_name = registry_config_file_name.split('/')[-1]
        base_name = "registry_configs/" + base_name

        if base_name in csv_contents:
            count = 0
            new_csv_name = base_name + str(count)
            while(new_csv_name in csv_contents):
                count += 1
                new_csv_name = base_name + str(count)

            base_name = new_csv_name


        with open(registry_config_file_name) as f:
            csv_contents[base_name] = f.read()

        csv_name_map[registry_config_file_name] = base_name


    #Overwrite file name with config store reference.
    device_config["registry_config"] = "config://" + csv_name_map[registry_config_file_name]

    new_config_name = "devices"

    for topic_bit in ("campus", "building", "unit", "path"):
        topic_bit = device_config.pop(topic_bit, '')
        if topic_bit:
            new_config_name += "/" + topic_bit

    return new_config_name, device_config


def process_main_config(main_file, output_directory, keep=False):
    main_config = parse_json_config(main_file.read())
    driver_list = main_config.pop("driver_config_list")
    driver_count = len(driver_list)

    csv_name_map = {}
    csv_contents = {}

    driver_configs = {}

    for config_path in driver_list:
        new_config_name, device_config = process_driver_config(config_path, csv_name_map, csv_contents)

        if new_config_name in driver_configs:
            print "WARNING DUPLICATE DEVICES:", new_config_name, "FOUND IN", config_path

        driver_configs[new_config_name] = device_config

    staggered_start = main_config.pop('staggered_start', None)

    if staggered_start is not None:
        main_config["driver_scrape_interval"] = staggered_start / float(driver_count)

    print "New Main config:"
    pprint(main_config)
    print

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    os.chdir(output_directory)

    devices_path = "devices"
    registries_path = "registry_configs"

    if not keep:
        if os.path.exists(devices_path):
            shutil.rmtree(devices_path, ignore_errors=True)

        if os.path.exists(registries_path):
            shutil.rmtree(registries_path, ignore_errors=True)

    if not os.path.exists(devices_path):
        os.makedirs(devices_path)

    if not os.path.exists(registries_path):
        os.makedirs(registries_path)

    print "Writing 'config'"
    with open("config", "w") as f:
        f.write(jsonapi.dumps(main_config, indent=2))

    for name, contents in csv_contents.iteritems():
        print "Writing", name
        with open(name, "w") as f:
            f.write(contents)

    unique_paths = set()

    for name, config in driver_configs.iteritems():
        print "Writing", name
        dir_name = os.path.dirname(name)

        if dir_name not in unique_paths and not os.path.exists(dir_name):
            os.makedirs(dir_name)

        unique_paths.add(dir_name)

        with open(name, "w") as f:
            f.write(jsonapi.dumps(config, indent=2))



if __name__ == "__main__":
    parser = ArgumentParser(description="Update a master configuration to use the configuration store and"
                                        " writes the new configurations to disk. To automatically update the"
                                        " configurations for the Master Driver in the store use the script"
                                        " install_master_driver_configs.py on the output from this script.")

    parser.add_argument('main_configuration', type=file,
                        help='The pre-configuration store master driver configuration file')

    parser.add_argument('output_directory',
                        help='The output directory.')

    parser.add_argument('--keep-old', action="store_true",
                        help="Do not remove existing device driver and registry files from the target directory.")


    args = parser.parse_args()
    process_main_config(args.main_configuration, args.output_directory, args.keep_old)
