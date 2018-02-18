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

import json
import pytest
import gevent
from gevent import pywsgi

from volttron.platform import get_services_core
from volttrontesting.utils.utils import get_rand_http_address
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER

server_addr = get_rand_http_address()
no_scheme = server_addr[7:]
ip, port = no_scheme.split(':')

TEST_MAC_ID = '0xffffffffffffffff'
driver_config_string = json.dumps({
    "driver_config": {
        "username": "",
        "password": "",
        "macid": TEST_MAC_ID,
        "address": server_addr + "/cgi-bin/post_manager"
    },
    "campus": "campus",
    "building": "building",
    "unit": "eagle",
    "driver_type": "rainforesteagle",
    "registry_config": "config://eagle.json",
    "interval": 10,
    "timezone": "US/Pacific"
})

register_config_string = json.dumps([
    "NetworkStatus",
    "InstantaneousDemand",
    "PriceCluster",
    "SummationDelivered",
    "SummationReceived",
    "PeakDelivered",
    "PeakReceived"
])

command_network_status = '<Command>\
<Name>get_network_status</Name>\
<Format>JSON</Format>\
</Command>'

response_network_status = json.dumps({
    u'NetworkStatus': {
        u'Status': u'Connected', # This is the value we'll check
        u'ShortAddr': u'0x5272',
        u'DeviceMacId': u'0xffffffffffffffff',
        u'Protocol':
        u'Zigbee',
        u'CoordMacId': u'0xffffffffffffffff',
        u'ExtPanId': u'0x0000000000000000',
        u'LinkStrength': u'0x64',
        u'Channel': u'17'
    }
})

command_instantaneous_demand = '<Command>\
<Name>get_instantaneous_demand</Name>\
<MacId>{}</MacId>\
<Format>JSON</Format>\
</Command>'.format(TEST_MAC_ID)

response_instantaneous_demand = json.dumps({
    u'InstantaneousDemand': {
        u'DeviceMacId': u'0xffffffffffffffff',
        u'Divisor': u'0x0000000a', # 10
        u'TimeStamp': u'0x00000000',
        u'MeterMacId': u'0xffffffffffffffff',
        u'Multiplier': u'0x00000001', # 1
        u'DigitsRight': u'0x00',
        u'DigitsLeft': u'0x00',
        u'SuppressLeadingZero': u'N',
        u'Demand': u'0x000040' # 64
    }
})

command_price_cluster = '<Command>\
<Name>get_price</Name>\
<MacId>{}</MacId>\
<Format>JSON</Format>\
</Command>'.format(TEST_MAC_ID)

response_price_cluster = json.dumps({
    u'PriceCluster': {
        u'DeviceMacId': u'0xffffffffffffffff',
        u'MeterMacId': u'0xffffffffffffffff',
        u'Price': u'0x00000040', # 64
        u'TrailingDigits': u'0x02', # 2
        u'Tier': u'0',
        u'Currency': u'0xffff',
        u'StartTime': u'0xffffffff',
        u'TimeStamp': u'0xffffffff',
        u'Duration': u'0xffff'
    }
})

command_current_summation = '<Command>\
<Name>get_current_summation</Name>\
<MacId>{}</MacId>\
<Format>JSON</Format>\
</Command>'.format(TEST_MAC_ID)

response_current_summation = json.dumps({
    u'CurrentSummation': {
        u'DeviceMacId': u'0xffffffffffffffff',
        u'Divisor': u'0x00000000',
        u'TimeStamp': u'0x00000000',
        u'MeterMacId': u'0xffffffffffffffff',
        u'Multiplier': u'0x00000000',
        u'DigitsRight': u'0x00',
        u'DigitsLeft': u'0x00',
        u'SuppressLeadingZero': u'N',
        u'SummationReceived': u'0x00000000',
        u'SummationDelivered': u'0x00000000'
    }
})

command_demand_peaks = '<Command>\
<Name>get_demand_peaks</Name>\
<Format>JSON</Format>\
</Command>'

response_demand_peaks = json.dumps({
    u'DemandPeaks': {
        u'PeakReceived': u'-2.000000',
        u'DeviceMacId': u'0xffffffffffffffff',
        u'PeakDelivered': u'5.000000'
    }
})

response_dict = {
    command_network_status:       response_network_status,
    command_instantaneous_demand: response_instantaneous_demand,
    command_price_cluster:        response_price_cluster,
    command_current_summation:    response_current_summation,
    command_demand_peaks:         response_demand_peaks
}


def handle(env, start_response):
    try:
        length = env['CONTENT_LENGTH']
        data = env['wsgi.input']
        data = data.read(length)
        data = data.replace(' ', '')
    except KeyError:
        data = None

    start_response('200 OK', [('Content-Type', 'text/html')])
    return response_dict[data]

    return handle


@pytest.fixture(scope='module')
def agent(volttron_instance1):
    agent = volttron_instance1.build_agent()
    # Clean out master driver configurations.
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_delete_store',
                       PLATFORM_DRIVER).get(timeout=10)

    #Add test configurations.
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       PLATFORM_DRIVER,
                       "devices/campus/building/unit",
                       driver_config_string,
                       "json").get(timeout=10)

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_store',
                       PLATFORM_DRIVER,
                       "eagle.json",
                       register_config_string,
                       "json").get(timeout=10)

    master_uuid = volttron_instance1.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    server = pywsgi.WSGIServer((ip, int(port)), handle)
    server.start()

    yield agent

    volttron_instance1.stop_agent(master_uuid)
    agent.core.stop()
    server.stop()


def test_NetworkStatus(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'NetworkStatus').get(timeout=10)
    assert point == 'Connected'


def test_InstantaneousDemand(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'InstantaneousDemand').get(timeout=10)
    assert point == 6.4


def test_PriceCluster(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'PriceCluster').get(timeout=10)
    assert point == 0.64


def test_SummationDelivered(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'SummationDelivered').get(timeout=10)
    assert point == 0.0


def test_SummationReceived(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'SummationReceived').get(timeout=10)
    assert point == 0.0


def test_PeakDelivered(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'PeakDelivered').get(timeout=10)
    assert point == 5.0


def test_PeakReceived(agent):
    point = agent.vip.rpc.call(PLATFORM_DRIVER,
                               'get_point',
                               'campus/building/unit',
                               'PeakReceived').get(timeout=10)
    assert point == -2.0
