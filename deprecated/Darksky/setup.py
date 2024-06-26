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


from os import path
from setuptools import setup, find_packages

MAIN_MODULE = 'agent'

# Find the agent package that contains the main module
packages = find_packages('.')
agent_package = ''

for package in find_packages():
    # Because there could be other packages such as tests
    if path.isfile(package + '/' + MAIN_MODULE + '.py') is True:
        agent_package = package
if not agent_package:
    raise RuntimeError('None of the packages under {dir} contain the file '
                       '{main_module}'.format(main_module=MAIN_MODULE + '.py',
                                              dir=path.abspath('')))

# Find the version number from the main module
agent_module = agent_package + '.' + MAIN_MODULE
# -1 not valid import level in python3
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

# Setup
setup(
    name=agent_package + 'agent',
    version=__version__,
    description="Agent for interfacing with the Darksky Weather API service",
    install_requires=['volttron'],
    packages=packages,
    package_data={'darksky': ['data/name_mapping.csv']},
    entry_points={
        'setuptools.installation': [
            'eggsecutable = ' + agent_module + ':main',
        ]
    }
)
