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

from volttron.platform import get_services_core
from ..sep2.end_device import SEP2Parser
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

DRIVER_NAME = 'sep2'
DEVICE_ID = "097935300833"

TEST_SEP2_CONFIG = {
    "devices": [
                    {
                        "sfdi": "097935300833",
                        "lfdi": "247bd68e3378fe57ba604e3c8bdf9e3f78a3d743",
                        "load_shed_device_category": "0200",
                        "pin_code": "130178"
                    },
                    {
                        "sfdi": "111576577659",
                        "lfdi": "2990c58a59935a7d5838c952b1a453c967341a07",
                        "load_shed_device_category": "0200",
                        "pin_code": "130178"
                    }
               ],
    "sep2_server_sfdi": "413707194130",
    "sep2_server_lfdi": "29834592834729384728374562039847629",
    "load_shed_device_category": "0020",
    "timezone": "America/Los_Angeles"
}

REGISTRY_CONFIG_STRING = """Volttron Point Name,SEP2 Resource Name,SEP2 Field Name,Units,Writable,Default
b1_Md,DeviceInformation,mfModel,NA,FALSE,NA
b1_Opt,DeviceInformation,lFDI,NA,FALSE,NA
b1_SN,DeviceInformation,sFDI,NA,FALSE,NA
b1_Vr,DeviceInformation,mfHwVer,NA,FALSE,NA
b113_A,MirrorMeterReading,PhaseCurrentAvg,A,FALSE,NA
b113_DCA,MirrorMeterReading,InstantPackCurrent,A,FALSE,NA
b113_DCV,MirrorMeterReading,LineVoltageAvg,V,FALSE,NA
b113_DCW,MirrorMeterReading,PhasePowerAvg,W,FALSE,NA
b113_PF,MirrorMeterReading,PhasePFA,%,FALSE,NA
b113_WH,MirrorMeterReading,EnergyIMP,Wh,FALSE,NA
b120_AhrRtg,DERCapability,rtgAh,Ah,FALSE,NA
b120_ARtg,DERCapability,rtgA,A,FALSE,NA
b120_MaxChaRte,DERCapability,rtgMaxChargeRate,W,FALSE,NA
b120_MaxDisChaRte,DERCapability,rtgMaxDischargeRate,W,FALSE,NA
b120_WHRtg,DERCapability,rtgWh,Wh,FALSE,NA
b120_WRtg,DERCapability,rtgW,W,FALSE,NA
b121_WMax,DERSettings,setMaxChargeRate,W,FALSE,NA
b122_ActWh,MirrorMeterReading,EnergyEXP,Wh,FALSE,NA
b122_StorConn,DERStatus,storConnectStatus,NA,FALSE,NA
b124_WChaMax,DERControl,DERControlBase.opModFixedFlow,W,TRUE,NA
b403_Tmp,MirrorMeterReading,InstantPackTemp,C,FALSE,NA
b404_DCW,PowerStatus,PEVInfo.chargingPowerNow,W,FALSE,NA
b404_DCWh,DERAvailability,SOC,Wh,FALSE,NA
b802_LocRemCtl,DERStatus,localControlModeStatus,NA,FALSE,NA
b802_SoC,DERStatus,inverterStatus,%,FALSE,NA
b802_State,DERStatus,stateOfChargeStatus,NA,FALSE,NA"""

web_address = ""


@pytest.fixture(scope="module")
def agent(request, volttron_instance_module_web):

    test_agent = volttron_instance_module_web.build_agent(identity="test_agent")
    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    volttron_instance_module_web.add_capabilities(test_agent.core.publickey, capabilities)
    # Configure a SEP2 device in the Master Driver
    test_agent.vip.rpc.call('config.store', 'manage_delete_store', PLATFORM_DRIVER).get(timeout=10)
    test_agent.vip.rpc.call('config.store', 'manage_store', PLATFORM_DRIVER,
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
    test_agent.vip.rpc.call('config.store', 'manage_store', PLATFORM_DRIVER,
                            'sep2.csv',
                            REGISTRY_CONFIG_STRING,
                            'csv').get(timeout=10)

    # Install and start a SEP2Agent
    sep2_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("SEP2Agent"),
                                                         config_file=TEST_SEP2_CONFIG,
                                                         vip_identity='test_sep2agent',
                                                         start=True)
    print('sep2 agent id: ', sep2_id)

    # Install and start a MasterDriverAgent
    md_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                       config_file={},
                                                       start=True)
    print('master driver agent id: ', md_id)

    global web_address
    web_address = volttron_instance_module_web.bind_web_address

    def stop():
        volttron_instance_module_web.stop_agent(md_id)
        volttron_instance_module_web.stop_agent(sep2_id)
        test_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


class TestSEP2Agent:
    """Regression tests for the SEP2 Agent."""

    def test_get_urls(self, agent):
        """Test that a requests.get succeeds (200 status) for various URLs."""
        assert requests.get('{}/dcap'.format(web_address)).status_code == 200
        self.sep2_http_get('tm')
        self.sep2_http_get('edev')
        self.sep2_http_get('sdev')
        self.sep2_http_get('sdev/di')
        self.sep2_http_get('sdev/log')
        self.sep2_http_get('edev/0')
        self.sep2_http_get('edev/0/reg')
        self.sep2_http_get('edev/0/fsa')
        self.sep2_http_get('edev/0/der')
        self.sep2_http_get('edev/0/der/1')

    def test_set_di(self, agent):
        """Test that DeviceInformation can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/di').mfInfo is None
        assert self.get_point(agent, 'b1_Vr') is None
        assert self.get_point(agent, 'b1_Md') is None
        assert self.sep2_http_put('edev/0/di', 'edev.di').status_code == 204
        assert self.sep2_http_get('edev/0/di').mfInfo == 'Mf Information'
        assert self.get_point(agent, 'b1_Vr') == 'MF-HW: 1.0.0'
        assert self.get_point(agent, 'b1_Md') == 'Mf Model'

    def test_set_dstat(self, agent):
        """Test that DeviceStatus can be fetched after it's been set."""
        self.sep2_http_get('edev/0/dstat')
        assert self.sep2_http_put('edev/0/dstat', 'edev.dstat').status_code == 204
        assert self.sep2_http_get('edev/0/dstat').onCount == 5

    def test_set_ps(self, agent):
        """Test that PowerStatus can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/ps').totalTimeOnBattery is None
        assert self.sep2_http_put('edev/0/ps', 'edev.ps').status_code == 204
        assert self.sep2_http_get('edev/0/ps').totalTimeOnBattery == 2

    def test_get_derc(self, agent):
        """Test that DERControl can be used to dispatch a power setting."""
        self.sep2_http_get('edev/0/derc/1')
        self.set_point(agent, 'b124_WChaMax', 30)
        # The next assert would fail -- DERControlBase.opModFixedFlow returns None
        # assert self.get_point(agent, 'b124_WChaMax') == 30

    def test_set_dercap(self, agent):
        """Test that DERCapability can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/der/1/dercap').type_ is None
        assert self.sep2_http_put('edev/0/der/1/dercap', 'der.dercap').status_code == 204
        assert self.sep2_http_get('edev/0/der/1/dercap').type_.get_valueOf_() == '85'

    def test_set_derg(self, agent):
        """Test that DERSettings can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/der/1/derg').setGradW is None
        assert self.get_point(agent, 'b121_WMax') is None
        assert self.sep2_http_put('edev/0/der/1/derg', 'der.derg').status_code == 204
        assert self.sep2_http_get('edev/0/der/1/derg').setGradW == 55000
        assert self.get_point(agent, 'b121_WMax') == 20.0

    def test_set_dera(self, agent):
        """Test that DERAvailability can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/der/1/dera').maxChargeDuration is None
        assert self.get_point(agent, 'b404_DCWh') is None
        assert self.sep2_http_put('edev/0/der/1/dera', 'der.dera').status_code == 204
        assert self.sep2_http_get('edev/0/der/1/dera').maxChargeDuration == 3
        assert self.get_point(agent, 'b404_DCWh') == 305.7555555555556

    def test_set_ders(self, agent):
        """Test that DERStatus can be fetched after it's been set."""
        assert self.sep2_http_get('edev/0/der/1/ders').stateOfChargeStatus is None
        assert self.get_point(agent, 'b802_State') is None
        assert self.get_point(agent, 'b802_LocRemCtl') is None
        assert self.get_point(agent, 'b802_SoC') is None
        assert self.get_point(agent, 'b122_StorConn') is None
        assert self.sep2_http_put('edev/0/der/1/ders', 'der.ders').status_code == 204
        assert self.sep2_http_get('edev/0/der/1/ders').stateOfChargeStatus.value.get_valueOf_() == '777'
        assert self.get_point(agent, 'b802_State') == 7.77
        assert self.get_point(agent, 'b802_LocRemCtl') == 777
        assert self.get_point(agent, 'b802_SoC') == 777
        assert self.get_point(agent, 'b122_StorConn') == 777

    def test_mup(self, agent):
        """Test that metrics can be fetched from a MirrorUsagePoint."""
        self.sep2_http_get('mup')
        assert self.sep2_http_put('mup', 'mup.mup').status_code == 201
        assert self.sep2_http_get('mup').MirrorUsagePoint[0].description == 'Gas Mirroring'
        self.sep2_http_put('mup/0', 'mup.mmr')
        self.sep2_http_get('mup')
        assert self.get_point(agent, 'b113_A') == 24.0
        assert self.get_point(agent, 'b122_ActWh') is None
        self.sep2_http_put('mup/0', 'mup.mup2')
        assert self.get_point(agent, 'b122_ActWh') == 128

    @staticmethod
    def get_point(agent, point_name):
        """Ask SEP2Agent for a point value for a SEP2 resource."""
        return agent.vip.rpc.call('test_sep2agent', 'get_point', DEVICE_ID, point_name).get(timeout=10)

    @staticmethod
    def set_point(agent, point_name, value):
        """Use SEP2Agent to set a point value for a SEP2 resource."""
        return agent.vip.rpc.call('test_sep2agent', 'set_point', DEVICE_ID, point_name, value).get(timeout=10)

    @staticmethod
    def sep2_http_get(sep2_resource_name):
        """
            Issue a web request to GET data for a SEP2 resource.

        @param sep2_resource_name: The distinguishing part of the name of the SEP2 resource as it appears in the URL.
        @return XML
        """
        r = requests.get('{}/dcap/{}'.format(web_address, sep2_resource_name))
        assert r.status_code == 200
        return SEP2Parser.parse(r.text.encode('ascii', 'ignore'))

    @staticmethod
    def sep2_http_put(sep2_resource_name, sep2_filename):
        """
            Issue a web request to PUT data for a SEP2 resource, using the contents of an XML file.

        @param sep2_resource_name: The distinguishing part of the name of the SEP2 resource as it appears in the URL.
        @param sep2_filename: The distinguishing part of the SEP2 sample data file name.
        """
        url = '{}/dcap/{}'.format(web_address, sep2_resource_name)
        headers = {'content-type': 'application/sep+xml'}
        return requests.post(url,
                             data=open(get_services_core("SEP2Agent/tests/{}.PUT.xml").format(sep2_filename), 'rb'),
                             headers=headers)
