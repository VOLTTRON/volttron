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

import pytest
import gevent
from gevent import pywsgi

from volttron.platform import get_services_core
from volttrontesting.utils.utils import get_rand_http_address

from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER

server_addr = get_rand_http_address()
no_scheme = server_addr[7:]
ip, port = no_scheme.split(':')
point = b'forty two'

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
        length = int(env['CONTENT_LENGTH'])
        point = data.read(length)

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [point]


@pytest.fixture(scope='module')
def agent(request, volttron_instance):
    agent = volttron_instance.build_agent()
    # Clean out master driver configurations.
    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(agent.core.publickey, capabilities)
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_delete_store',
                       PLATFORM_DRIVER).get(timeout=10)

    #Add test configurations.
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       PLATFORM_DRIVER,
                       "devices/campus/building/unit",
                       driver_config_dict_string,
                       "json").get(timeout=10)

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       PLATFORM_DRIVER,
                       "restful.csv",
                       restful_csv_string,
                       "csv").get(timeout=10)

    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    server = pywsgi.WSGIServer((ip, int(port)), handle)
    server.start()

    def stop():
        volttron_instance.stop_agent(master_uuid)
        agent.core.stop()
        server.stop()

    request.addfinalizer(stop)
    return agent


def test_restful_get(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)

    assert point == 'forty two'


def test_restful_set(agent):
    # set point
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'set_point',
                               'campus/building/unit',
                               'test_point',
                               '42').get(timeout=10)
    assert point == '42'

    # get point
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)
    assert point == '42'


def test_restful_revert(agent):
    # set point
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'set_point',
                               'campus/building/unit',
                               'test_point',
                               '42').get(timeout=10)
    assert point == '42'

    # revert point
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'revert_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)

    # get point
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'test_point').get(timeout=10)
    assert point == 'forty two'
