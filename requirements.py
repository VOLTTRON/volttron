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

# These need to be importable by bootstrap.py. If we put them in
# setup.py the import may fail if setuptools in not installed
# in the global python3.
# wheel version 0.32 restructured package and removed many of the apis.
# https://github.com/pypa/wheel/issues/255
# wheel version 0.31 has removed metadata.json file
# https://github.com/pypa/wheel/issues/195
# so sticking to 0.30 for now. Could upgrade to wheel 0.31 with code changes
option_requirements = [('pip==24.0', []), ('wheel==0.30', []), ('pyzmq==26.0.2', ['--zmq=bundled'])]


install_requires = ['gevent==24.2.1',
                    'grequests==0.7.0',
                    'requests==2.31.0',
                    'idna<3,>=2.5',
                    'ply==3.11',
                    'psutil==5.9.1',
                    'python-dateutil==2.8.2',
                    'pytz==2022.1',
                    'PyYAML==6.0',
                    'setuptools>=40.0.0,<=70.0.0',
                    # tzlocal 3.0 breaks without the backports.tzinfo package on python < 3.9 https://pypi.org/project/tzlocal/3.0/
                    'tzlocal==2.1',
                    #'pyOpenSSL==19.0.0',
                    'cryptography==37.0.4',
                    'watchdog<5.0',
                    'watchdog-gevent==0.1.1',
                    'deprecated==1.2.14']

extras_require = {'crate': ['crate==0.27.1'],
                  'databases': ['mysql-connector-python==8.0.30',
                                'pymongo==4.5.0',
                                'crate==0.27.1',
                                'influxdb==5.3.1',
                                'psycopg2-binary==2.9.7'],
                  'documentation': ['mock==4.0.3',
                                    'docutils<0.18',
                                    'sphinx-rtd-theme==1.0.0',
                                    'sphinx==5.1.1',
                                    'm2r2==0.3.2',
                                    'sphinxcontrib-mermaid'],
                  'drivers': ['pymodbus==2.5.3',
                              'bacpypes==0.16.7',
                              'modbus-tk==1.1.2',
                              'pyserial==3.5'],
                  'influxdb': ['influxdb==5.3.1'],
                  'market': ['numpy==1.23.1', 'transitions==0.8.11'],
                  'mongo': ['pymongo==4.5.0'],
                  'mysql': ['mysql-connector-python==8.0.30'],
                  'pandas': ['numpy==1.23.1', 'pandas==1.4.3'],
                  'postgres': ['psycopg2-binary==2.9.7'],
                  # This is installed in bootstrap.py itself so we don't
                  # include here, though we include the version number here
                  #
                  # This will not be installed with --all flag.
                  # 'rabbitmq': ['pika==1.2.0'],
                  'testing': ['mock==4.0.3',
                              'pytest==7.1.2',
                              'pytest-timeout==2.1.0',
                              'pytest-rerunfailures==10.2',
                              'websocket-client==1.2.2',
                              'deepdiff==5.8.1',
                              'docker==5.0.3',
                              'pytest_asyncio==0.19.0',
                              'pytest_timeout==2.1.0'],
                  'weather': ['Pint==0.19.2'],
                  'yapf': ['yapf'],
                  'web': ['ws4py==0.5.1',
                          'PyJWT==1.7.1',
                          'Jinja2==3.1.2',
                          'passlib==1.7.4',
                          'argon2-cffi==21.3.0',
                          'Werkzeug==2.2.1',
                          'treelib==1.6.1'],
                  'dnp3': ['dnp3-python==0.2.3b3'],
                  'openadr': ['openleadr==0.5.30']}
