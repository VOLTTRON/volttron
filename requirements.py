# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

# These need to be importable by bootstrap.py. If we put them in
# setup.py the import may fail if setuptools in not installed
# in the global python3.

option_requirements = [
    ('pyzmq', ['--zmq=bundled']),
]

install_requires = [
    'gevent==20.6.1',
    'grequests',
    'requests==2.23.0',
    'ply',
    'psutil',
    'python-dateutil',
    'pytz',
    'PyYAML',
    'pyzmq',
    'setuptools',
    'tzlocal',
    'pyOpenSSL==19.0.0',
    'cryptography==2.3',
    # Cross platform way of handling changes in file/directories.
    # https://github.com/Bogdanp/watchdog_gevent
    'watchdog-gevent',
    'wheel==0.30'
]

extras_require = {
    'crate': [  # crate databases
        'crate'
    ],
    'databases': [  # Support for all known databases
        'mysql-connector-python-rf',
        'pymongo',
        'crate',
        'influxdb',
        'psycopg2-binary'
    ],
    'dnp3': [  # dnp3 agent requirements.
        'pydnp3'
    ],
    'documentation': [  # Requirements for building the documentation
        'mock',
        'mysql-connector-python-rf',
        'psutil',
        'pymongo',
        'Sphinx',
        'recommonmark',
        'sphinx-rtd-theme'
    ],
    'drivers': [
        'pymodbus',
        'bacpypes==0.16.7',
        'modbus-tk',
        'pyserial'
    ],
    'influxdb': [  # influxdb historian requirements.
        'influxdb'
    ],
    'market': [  # Requirements for the market service
        'numpy',
        'transitions',
    ],
    'mongo': [  # mongo databases
        'pymongo',
    ],
    'mysql': [  # mysql databases
        'mysql-connector-python-rf',
    ],
    'pandas': [  # numpy and pandas for applications
        'numpy',
        'pandas',
    ],
    'postgres': [  # numpy and pandas for applications
        'psycopg2-binary'
    ],
    'testing': [  # Testing infrastructure dependencies
        'mock',
        'pytest',
        'pytest-timeout',
        'websocket-client',
        # Allows us to compare nested dictionaries easily.
        'deepdiff'
    ],
    'rabbitmq': [
        'gevent-pika'
    ],
    'web': [    # Web support for launching web based agents including ssl and json web tokens.
        'ws4py',
        'PyJWT',
        'Jinja2',
        'passlib',
        'argon2-cffi',
        'Werkzeug'
    ],
    'weather': [
        'Pint'
    ],
}
