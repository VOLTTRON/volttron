# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

