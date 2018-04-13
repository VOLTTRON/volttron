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

from os import path
import sys
import json

from setuptools import setup, find_packages

import re
VERSIONFILE="volttron/platform/__init__.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

# Requirements which must be built separately with the provided options.
option_requirements = [
    ('pyzmq>=15,<16', ['--zmq=bundled']),
]

optional_requirements = set()

# For the different keyed in options allow the command paramenter to
# install the given requirements.
if path.exists('optional_requirements.json'):
    with open('optional_requirements.json') as optional:
        data = json.load(optional)

        for arg, val in data.items():
            if arg in sys.argv:
                for req in val['packages']:
                    optional_requirements.add(req)

# Requirements in the repository which should be installed as editable.
local_requirements = [
]

# Standard requirements
requirements = [
    'gevent>=0.13,<2',
    'monotonic',
    'pymodbus>=1.2,<2',
    'setuptools',
    'simplejson>=3.3,<4',
    'wheel==0.30',
]

install_requires = (
    [req for req, _ in option_requirements] +
    [req for req, _ in local_requirements] +
    requirements +
    [req for req in optional_requirements]
)

if __name__ == '__main__':
    setup(
        name='volttron',
        version=verstr,
        description='Agent Execution Platform',
        author='Volttron Team',
        author_email='volttron@pnnl.gov',
        url='https://github.com/VOLTTRON/volttron',
        packages=find_packages('.'),
        install_requires=install_requires,
        entry_points={
            'console_scripts': [
                'volttron = volttron.platform.main:_main',
                'volttron-ctl = volttron.platform.control:_main',
                'volttron-pkg = volttron.platform.packaging:_main',
                'volttron-cfg = volttron.platform.config:_main',
                'vctl = volttron.platform.control:_main',
                'vpkg = volttron.platform.packaging:_main',
                'vcfg = volttron.platform.config:_main',
            ]
        },
        zip_safe=False,
    )
