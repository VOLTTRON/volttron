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

"""Gets the version numbers of all agents in the services, examples, and applications directories.
Outputs to stdout in CSV format."""

import fnmatch
import os
import pprint
from distutils.version import StrictVersion
import csv
import sys
from ast import literal_eval

def get_version_from_file(file_path):
    version = None
    with open(file_path) as f:
        lines = f.readlines()
        for line in lines:
            if "__version__" in line:
                values = line.split("=")
                try:
                    version_string = literal_eval(values[1].strip())
                    version = StrictVersion(version_string)
                    break
                except IndexError:
                    pass
                except ValueError:
                    pass

    return version

def get_agent_version(agent_path):
    py_files = []
    for root, dirnames, filenames in os.walk(agent_path):
        for filename in fnmatch.filter(filenames, '*.py'):
            if "test" in filename:
                continue
            if "setup.py" in filename:
                continue
            if "__init__.py" in filename:
                continue
            py_files.append(os.path.join(root, filename))

    version = None

    for py_file in py_files:
        temp_version = get_version_from_file(py_file)
        if temp_version is None:
            continue

        if version is None:
            version = temp_version
        elif version < temp_version:
            version = temp_version

    return agent_path, version


search_dirs = ["examples", "services", "applications"]

agent_paths = []

for search_dir in search_dirs:
    for root, dirnames, filenames in os.walk(search_dir):
        for filename in fnmatch.filter(filenames, 'setup.py'):
            agent_paths.append(root)

dict_writer = csv.DictWriter(sys.stdout, ["Agent", "Version"])

agent_versions = []

for agent_path in agent_paths:
    agent_versions.append(get_agent_version(agent_path))

agent_versions.sort()

for agent_version in agent_versions:
    dict_writer.writerow({"Agent": agent_version[0], "Version": agent_version[1]})
