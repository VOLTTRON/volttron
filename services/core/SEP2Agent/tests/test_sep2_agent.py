# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
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
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
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
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

import pytest
import gevent
import requests
import time
from ..sep2.end_device import SEP2Parser

DRIVER_NAME = 'sep2'
DEVICE_ID = "097935300833"

REGISTRY_CONFIG_STRING = """Volttron Point Name,Point Name,Units,Writable,Default
b1_Md,b1_Md,NA,FALSE,NA
b1_Opt,b1_Opt,NA,FALSE,NA
b1_SN,b1_SN,NA,FALSE,NA
b1_Vr,b1_Vr,NA,FALSE,NA
b113_A,b113_A,A,FALSE,NA
b113_DCA,b113_DCA,A,FALSE,NA
b113_DCV,b113_DCV,V,FALSE,NA
b113_DCW,b113_DCW,W,FALSE,NA
b113_PF,b113_PF,%,FALSE,NA
b113_WH,b113_WH,Wh,FALSE,NA
b120_AhrRtg,b120_AhrRtg,Ah,FALSE,NA
b120_ARtg,b120_ARtg,A,FALSE,NA
b120_MaxChaRte,b120_MaxChaRte,W,FALSE,NA
b120_MaxDisChaRte,b120_MaxDisChaRte,W,FALSE,NA
b120_WHRtg,b120_WHRtg,Wh,FALSE,NA
b120_WRtg,b120_WRtg,W,FALSE,NA
b121_WMax,b121_WMax,W,FALSE,NA
b122_ActWh,b122_ActWh,Wh,FALSE,NA
b122_StorConn,b122_StorConn,NA,FALSE,NA
b124_WChaMax,b124_WChaMax,W,TRUE,NA
b403_Tmp,b403_Tmp,C,FALSE,NA
b404_DCW,b404_DCW,W,FALSE,NA
b404_DCWh,b404_DCWh,Wh,FALSE,NA
b802_LocRemCtl,b802_LocRemCtl,NA,FALSE,NA
b802_SoC,b802_SoC,%,FALSE,NA
b802_State,b802_State,NA,FALSE,NA"""

web_address = ""


@pytest.fixture(scope="module")
def agent(request, volttron_instance_module_web):
    test_agent = volttron_instance_module_web.build_agent()

    # Configure a SEP2 device in the Master Driver
    test_agent.vip.rpc.call('config.store', 'manage_delete_store', 'platform.driver').get(timeout=10)
    test_agent.vip.rpc.call('config.store', 'manage_store', 'platform.driver',
                            'devices/{}'.format(DRIVER_NAME),
                            """{
                                "driver_config": {
                                    "sfdi": "097935300833",
                                    "sep2_agent_id": "test_sep2agent"
                                },
                                "campus": "campus",
                                "building": "building",
                                "unit": "sep2",
                                "driver_type": "sep2",
                                "registry_config": "config://sep2.csv",
                                "interval": 15,
                                "timezone": "US/Pacific",
                                "heart_beat_point": "Heartbeat"
                            }""",
                            'json').get(timeout=10)
    test_agent.vip.rpc.call('config.store', 'manage_store', 'platform.driver',
                            'sep2.csv',
                            REGISTRY_CONFIG_STRING,
                            'csv').get(timeout=10)

    # Install and start a SEP2Agent
    sep2_id = volttron_instance_module_web.install_agent(agent_dir='services/core/SEP2Agent',
                                               config_file='services/core/SEP2Agent/tests/testagent.config',
                                               vip_identity='test_sep2agent',
                                               start=True)
    print('sep2 agent id: ', sep2_id)

    global web_address
    web_address = volttron_instance_module_web.bind_web_address

    def stop():
        volttron_instance_module_web.stop_agent(sep2_id)
        test_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


class TestSEP2Agent:
    """
        Regression tests for the SEP2 Agent.
    """

    def get_point(self, agent, point_name):
        return agent.vip.rpc.call('test_sep2agent', 'get_point', DEVICE_ID, point_name).get(timeout=10)

    def set_point(self, agent, point_name, value):
        return agent.vip.rpc.call('test_sep2agent', 'set_point', DEVICE_ID, point_name, value).get(timeout=10)

    def test_get_dcap(self, agent):
        url = '{}/dcap'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_tm(self, agent):
        url = '{}/dcap/tm'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_edev_list(self, agent):
        url = '{}/dcap/edev'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_sdev(self, agent):
        url = '{}/dcap/sdev'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_sdev_di(self, agent):
        url = '{}/dcap/sdev/di'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_sdev_log(self, agent):
        url = '{}/dcap/sdev/log'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_edev(self, agent):
        url = '{}/dcap/edev/0'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_edev_reg(self, agent):
        url = '{}/dcap/edev/0/reg'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_edev_fsa(self, agent):
        url = '{}/dcap/edev/0/fsa'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_set_di(self, agent):
        url = '{}/dcap/edev/0/di'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.mfInfo is None
        assert self.get_point(agent, 'b1_Vr') is None
        assert self.get_point(agent, 'b1_Md') is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('edev.di.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204
        time.sleep(5)
        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.mfInfo == 'Mf Information'
        assert self.get_point(agent, 'b1_Vr') == 'MF-HW: 1.0.0'
        assert self.get_point(agent, 'b1_Md') == 'Mf Model'

    def test_set_dstat(self, agent):
        url = '{}/dcap/edev/0/dstat'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('edev.dstat.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.onCount == 5

    def test_set_ps(self, agent):
        url = '{}/dcap/edev/0/ps'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.totalTimeOnBattery is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('edev.ps.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.totalTimeOnBattery == 2

    def test_get_der_list(self, agent):
        url = '{}/dcap/edev/0/der'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_der(self, agent):
        url = '{}/dcap/edev/0/der/1'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

    def test_get_derc(self, agent):
        url = '{}/dcap/edev/0/derc/1'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        self.set_point(agent, 'b124_WChaMax', 30)
        assert self.get_point(agent, 'b124_WChaMax') == 30

    def test_set_dercap(self, agent):
        url = '{}/dcap/edev/0/der/1/dercap'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.type_ is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('der.dercap.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.type_.get_valueOf_() == '85'

    def test_set_derg(self, agent):
        url = '{}/dcap/edev/0/der/1/derg'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.setGradW is None
        assert self.get_point(agent, 'b121_WMax') is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('der.derg.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        time.sleep(5)
        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.setGradW == 55000
        assert self.get_point(agent, 'b121_WMax') == 20.0

    def test_set_dera(self, agent):
        url = '{}/dcap/edev/0/der/1/dera'.format(web_address)
        url2 = '{}/dcap/edev/0/der/1/derg'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.maxChargeDuration is None
        assert self.get_point(agent, 'b404_DCWh') is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('der.dera.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        time.sleep(5)
        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.maxChargeDuration == 3
        r = requests.get(url2)
        assert self.get_point(agent, 'b404_DCWh') == 305.7555555555556

    def test_set_ders(self, agent):
        url = '{}/dcap/edev/0/der/1/ders'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200
        xml_data = SEP2Parser.parse(r.text.encode('ascii', 'ignore'))
        assert xml_data.stateOfChargeStatus is None
        assert self.get_point(agent, 'b802_State') is None
        assert self.get_point(agent, 'b802_LocRemCtl') is None
        assert self.get_point(agent, 'b802_SoC') is None
        assert self.get_point(agent, 'b122_StorConn') is None

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('der.ders.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 204

        time.sleep(5)
        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.stateOfChargeStatus.value.get_valueOf_() == '777'
        assert self.get_point(agent, 'b802_State') == 777
        assert self.get_point(agent, 'b802_LocRemCtl') == 777
        assert self.get_point(agent, 'b802_SoC') == 7.77
        assert self.get_point(agent, 'b122_StorConn') == 777

    def test_mup(self, agent):
        url = '{}/dcap/mup'.format(web_address)
        r = requests.get(url)
        assert r.status_code == 200

        headers = {'content-type': 'application/sep+xml'}
        r = requests.post(url, data=open('mup.mup.PUT.xml', 'rb'), headers=headers)
        assert r.status_code == 201

        r = requests.get(url)
        xml_data = SEP2Parser.parse(r.text.encode('ascii','ignore'))
        assert xml_data.MirrorUsagePoint[0].description == 'Gas Mirroring'

        url2 = '{}/dcap/mup/0'.format(web_address)
        r = requests.post(url2, data=open('mup.mmr.PUT.xml', 'rb'), headers=headers)
        r = requests.get(url)
        assert self.get_point(agent, 'b113_A') == 24.0

        assert self.get_point(agent, 'b122_ActWh') is None
        r = requests.post(url2, data=open('mup.mup2.PUT.xml', 'rb'), headers=headers)
        time.sleep(5)
        assert self.get_point(agent, 'b122_ActWh') == 128
