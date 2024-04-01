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

import contextlib

from setuptools import setup, find_packages
from requirements import extras_require, install_requires

with open('volttron/platform/__init__.py') as file:
    for line in file:
        if line.startswith('__version__'):
            with contextlib.suppress(IndexError):
                exec(line)
                break
    else:
        raise RuntimeError('Unable to find version string in {}.'.format(file.name))

if __name__ == '__main__':
    setup(
        name = 'volttron',
        version = __version__,
        description = 'Agent Execution Platform',
        author = 'Volttron Team',
        author_email = 'volttron@pnnl.gov',
        url = 'https://github.com/VOLTTRON/volttron',
        packages = find_packages('.'),
        install_requires = install_requires,
        extras_require = extras_require,
        entry_points = {
            'console_scripts': [
                'volttron = volttron.platform.main:_main',
                'volttron-ctl = volttron.platform.control.control_parser:_main',
                # 'volttron-ctl = volttron.platform.control_old:_main',
                'volttron-pkg = volttron.platform.packaging:_main',
                'volttron-cfg = volttron.platform.config:_main',
                'vctl = volttron.platform.control.control_parser:_main',
                # 'vctl = volttron.platform.control_old:_main',
                'vpkg = volttron.platform.packaging:_main',
                'vcfg = volttron.platform.config:_main',
                'volttron-upgrade = volttron.platform.upgrade.upgrade_volttron:_main',
            ]
        },
        zip_safe = False,
    )
