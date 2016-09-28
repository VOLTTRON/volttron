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
    'BACpypes>0.13,<0.14',
    'gevent>=0.13,<2',
    'monotonic',
    'pymodbus>=1.2,<2',
    'setuptools',
    'simplejson>=3.3,<4',
    'wheel>=0.24,<2',
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
            ]
        },
        zip_safe=False,
    )
