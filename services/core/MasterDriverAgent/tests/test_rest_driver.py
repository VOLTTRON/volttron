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

import pytest
import gevent
from gevent import pywsgi
import os
import json

from volttrontesting.utils.utils import get_rand_http_address

server_addr = get_rand_http_address()
no_scheme = server_addr[7:]
ip, port = no_scheme.split(':')
point = 'forty two'

driver_config_dict_string = """{
    "driver_config": {"device_address": "%s"},
    "driver_type": "restful",
    "registry_config": "config://restful.csv",
    "interval": 20,
    "timezone": "UTC"
}""" % server_addr

restful_csv_string = """Point Name,Volttron Point Name,Units,Writable,Notes,Default
test_point,test_point,Units,True,Test point,forty two"""


# return the global point value no matter what is requested
def handle(env, start_response):
    global point

    if env['REQUEST_METHOD'] == 'POST':
        data = env['wsgi.input']
        length = env['CONTENT_LENGTH']
        point = data.read(length)

    start_response('200 OK', [('Content-Type', 'text/html')])
    return point


@pytest.fixture(scope='module')
def agent(request, volttron_instance1):
    agent = volttron_instance1.build_agent()
    # Clean out master driver configurations.
    agent.vip.rpc.call('config.store',
                       'manage_delete_store',
                       'platform.driver').get(timeout=10)

    #Add test configurations.
    agent.vip.rpc.call('config.store',
                       'manage_store',
                       'platform.driver',
                       "devices/campus/building/unit",
                       driver_config_dict_string,
                       "json").get(timeout=10)

    agent.vip.rpc.call('config.store',
                       'manage_store',
                       'platform.driver',
                       "restful.csv",
                       restful_csv_string,
                       "csv").get(timeout=10)

    master_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    server = pywsgi.WSGIServer((ip, int(port)), handle)
    server.start()

    def stop():
        volttron_instance1.stop_agent(master_uuid)
        agent.core.stop()
        server.stop()

    request.addfinalizer(stop)
    return agent


def test_restful_get(agent):
    point = agent.vip.rpc.call('platform.driver',
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)

    assert point == 'forty two'


def test_restful_set(agent):
    # set point
    point = agent.vip.rpc.call('platform.driver',
                               'set_point',
                               'campus/building/unit',
                               'test_point',
                               '42').get(timeout=10)
    assert point == '42'

    # get point
    point = agent.vip.rpc.call('platform.driver',
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)
    assert point == '42'


def test_restful_revert(agent):
    # set point
    point = agent.vip.rpc.call('platform.driver',
                               'set_point',
                               'campus/building/unit',
                               'test_point',
                               '42').get(timeout=10)
    assert point == '42'

    # revert point
    point = agent.vip.rpc.call('platform.driver',
                               'revert_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)

    # get point
    point = agent.vip.rpc.call('platform.driver',
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)
    assert point == 'forty two'
