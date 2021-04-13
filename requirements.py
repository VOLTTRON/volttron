# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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


extras_require = {   'crate': ['crate==0.26.0'],
    'databases': [   'mysql-connector-python-rf==2.2.2',
                     'bson==0.5.7',
                     'pymongo==3.7.2',
                     'crate==0.26.0',
                     'influxdb==5.3.1',
                     'psycopg2-binary==2.8.6'],
    'documentation': [   'mock==4.0.3',
                         'Sphinx==3.5.1',
                         'sphinx-rtd-theme==0.5.1',
                         'sphinx==3.3.0',
                         'm2r2==0.2.7'],
    'drivers': [   'pymodbus==2.5.0',
                   'bacpypes==0.16.7',
                   'modbus-tk==1.1.2',
                   'pyserial==3.5'],
    'influxdb': ['influxdb==5.3.1'],
    'market': ['numpy==1.19.5', 'transitions==0.8.7'],
    'mongo': ['bson==0.5.7pymongo==3.7.2'],
    'mysql': ['mysql-connector-python-rf==2.2.2'],
    'pandas': ['numpy==1.19.5', 'pandas==1.1.5'],
    'postgres': ['psycopg2-binary==2.8.6'],
    'testing': [   'mock==4.0.3',
                   'pytest==6.2.2',
                   'pytest-timeout==1.4.2',
                   'websocket-client==0.58.0',
                   'deepdiff==5.2.3',
                   'docker==4.4.4'],
    'weather': ['Pint==0.16.1'],
    'web': [   'ws4py==0.5.1',
               'PyJWT==1.7.1',
               'Jinja2==2.11.3',
               'passlib==1.7.4',
               'argon2-cffi==20.1.0',
               'Werkzeug==1.0.1']}


install_requires = [
    'gevent==20.6.1',
    'greenlet==0.4.16',
    'grequests==0.6.0',
    'idna<3,>=2.5',
    'requests==2.23.0',
    'ply==3.11',
    'psutil==5.8.0',
    'python-dateutil==2.8.1',
    'pytz==2021.1',
    'PyYAML==5.4.1',
    'pyzmq==22.0.3',
    'setuptools==39.0.1',
    'tzlocal==2.1',
    'pyOpenSSL==19.0.0',
    'cryptography==2.3',
    'watchdog-gevent==0.1.1',
    'wheel==0.30']

option_requirements = [('pyzmq==22.0.3', ['--zmq=bundled'])]


