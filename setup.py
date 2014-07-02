# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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
#}}}

#from distutils.core import setup
from setuptools import setup, find_packages


install_requires = [
    'avro>=1.7,<1.8',
    'BACpypes>=0.9,<0.10',
    'configobj>=4.7,<5',
    'flexible-jsonrpc',
    'gevent>=0.13,<0.14',
    'numpy>=1.8,<1.9',
    'posix-clock',
    'pymodbus>=1.2,<1.3',
    'pyOpenSSL>=0.13,<0.14',
    'python-dateutil>=2,<3',
    'pyzmq>=14.3,<14.4',
    'requests>=2.2,<2.3',
    'setuptools',
    'simplejson>=3.3,<3.4',
    'Smap==2.0.24c780d',
    'Twisted>=13,<14',
    'zope.interface>=4.0,<4.1',
    'wheel>=0.23.0',  # needed for agent mobility
]


if __name__ == '__main__':
    setup(
        name = 'volttron',
        version = '0.2',
        description = 'Agent Execution Platform',
        author = 'Volttron Team',
        author_email = 'bora@pnnl.gov',
        url = 'http://www.pnnl.gov',
        packages = find_packages('.', exclude=['*.tests']),
        install_requires = install_requires,
        package_data = {'volttron.platform': ['configspec.ini']},
        entry_points = '''
        [console_scripts]
        volttron = volttron.platform.main:_main
        volttron-ctl = volttron.platform.control:_main
        volttron-pkg = volttron.dev.control:_main

        #[volttron.platform.control.handlers]
        #run_agent = volttron.platform.commands:run_agent.handler
        #shutdown = volttron.platform.commands:shutdown.handler

        #[volttron.platform.control.commands]
        #run-agent = volttron.platform.commands:run_agent.command
        #shutdown = volttron.platform.commands:shutdown.command
        
        # Other useful commands that need implemented
        #load-agent
        #list-agents
        #run-agent
        #unload-agent
        #debug-shell

        [volttron.switchboard.directory]
        #platform = volttron.core.directory.host:HostDirectory

        [volttron.switchboard.resmon]
        platform = volttron.platform.resmon:ResourceMonitor
        
        [volttron.switchboard.aip]
        platform = volttron.platform.aip:AIPplatform


        [volttron.switchboard.auth]
        #platform = volttron.platform.auth:AuthManager
        ''',
        test_suite = 'nose.collector',
        zip_safe = False,
    )
