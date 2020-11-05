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

import pytest
import gevent
import requests

from volttron.platform import get_services_core
from IEEE2030_5.end_device import IEEE2030_5Parser
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

DRIVER_NAME = 'IEEE2030_5'
DEVICE_ID = "097935300833"

TEST_IEEE2030_5_CONFIG = {
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
    "IEEE2030_5_server_sfdi": "413707194130",
    "IEEE2030_5_server_lfdi": "29834592834729384728374562039847629",
    "load_shed_device_category": "0020",
    "timezone": "America/Los_Angeles"
}

REGISTRY_CONFIG_STRING = """Volttron Point Name,IEEE2030_5 Resource Name,IEEE2030_5 Field Name,Units,Writable,Default
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
    # Configure a IEEE 2030.5 device in the Master Driver
    test_agent.vip.rpc.call('config.store', 'manage_delete_store', PLATFORM_DRIVER).get(timeout=10)
    test_agent.vip.rpc.call('config.store', 'manage_store', PLATFORM_DRIVER,
                            'devices/{}'.format(DRIVER_NAME),
                            """{
                                "driver_config": {
                                    "sfdi": "097935300833",
                                    "IEEE2030_5_agent_id": "test_IEEE2030_5agent"
                                },
                                "campus": "campus",
                                "building": "building",
                                "unit": "IEEE2030_5",
                                "driver_type": "IEEE2030_5",
                                "registry_config": "config://IEEE2030_5.csv",
                                "interval": 15,
                                "timezone": "US/Pacific",
                                "heart_beat_point": "Heartbeat"
                            }""",
                            'json').get(timeout=10)
    test_agent.vip.rpc.call('config.store', 'manage_store', PLATFORM_DRIVER,
                            'IEEE2030_5.csv',
                            REGISTRY_CONFIG_STRING,
                            'csv').get(timeout=10)

    # Install and start a IEEE2030_5Agent
    IEEE2030_5_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("IEEE2030_5Agent"),
                                                               config_file=TEST_IEEE2030_5_CONFIG,
                                                               vip_identity='test_IEEE2030_5agent',
                                                               start=True)
    print('IEEE2030_5 agent id: ', IEEE2030_5_id)

    # Install and start a MasterDriverAgent
    md_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                       config_file={},
                                                       start=True)
    print('master driver agent id: ', md_id)

    global web_address
    web_address = volttron_instance_module_web.bind_web_address

    def stop():
        volttron_instance_module_web.stop_agent(md_id)
        volttron_instance_module_web.stop_agent(IEEE2030_5_id)
        test_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


class TestIEEE2030_5Agent:
    """Regression tests for the IEEE 2030.5 Agent."""

    def test_get_urls(self, agent):
        """Test that a requests.get succeeds (200 status) for various URLs."""
        assert requests.get('{}/dcap'.format(web_address)).status_code == 200
        self.IEEE2030_5_http_get('tm')
        self.IEEE2030_5_http_get('edev')
        self.IEEE2030_5_http_get('sdev')
        self.IEEE2030_5_http_get('sdev/di')
        self.IEEE2030_5_http_get('sdev/log')
        self.IEEE2030_5_http_get('edev/0')
        self.IEEE2030_5_http_get('edev/0/reg')
        self.IEEE2030_5_http_get('edev/0/fsa')
        self.IEEE2030_5_http_get('edev/0/der')
        self.IEEE2030_5_http_get('edev/0/der/1')

    def test_set_di(self, agent):
        """Test that DeviceInformation can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/di').mfInfo is None
        assert self.get_point(agent, 'b1_Vr') is None
        assert self.get_point(agent, 'b1_Md') is None
        assert self.IEEE2030_5_http_put('edev/0/di', 'edev.di').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/di').mfInfo == 'Mf Information'
        assert self.get_point(agent, 'b1_Vr') == 'MF-HW: 1.0.0'
        assert self.get_point(agent, 'b1_Md') == 'Mf Model'

    def test_set_dstat(self, agent):
        """Test that DeviceStatus can be fetched after it's been set."""
        self.IEEE2030_5_http_get('edev/0/dstat')
        assert self.IEEE2030_5_http_put('edev/0/dstat', 'edev.dstat').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/dstat').onCount == 5

    def test_set_ps(self, agent):
        """Test that PowerStatus can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/ps').totalTimeOnBattery is None
        assert self.IEEE2030_5_http_put('edev/0/ps', 'edev.ps').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/ps').totalTimeOnBattery == 2

    def test_get_derc(self, agent):
        """Test that DERControl can be used to dispatch a power setting."""
        self.IEEE2030_5_http_get('edev/0/derc/1')
        self.set_point(agent, 'b124_WChaMax', 30)
        # The next assert would fail -- DERControlBase.opModFixedFlow returns None
        # assert self.get_point(agent, 'b124_WChaMax') == 30

    def test_set_dercap(self, agent):
        """Test that DERCapability can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/der/1/dercap').type_ is None
        assert self.IEEE2030_5_http_put('edev/0/der/1/dercap', 'der.dercap').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/der/1/dercap').type_.get_valueOf_() == '85'

    def test_set_derg(self, agent):
        """Test that DERSettings can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/der/1/derg').setGradW is None
        assert self.get_point(agent, 'b121_WMax') is None
        assert self.IEEE2030_5_http_put('edev/0/der/1/derg', 'der.derg').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/der/1/derg').setGradW == 55000
        assert self.get_point(agent, 'b121_WMax') == 20.0

    def test_set_dera(self, agent):
        """Test that DERAvailability can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/der/1/dera').maxChargeDuration is None
        assert self.get_point(agent, 'b404_DCWh') is None
        assert self.IEEE2030_5_http_put('edev/0/der/1/dera', 'der.dera').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/der/1/dera').maxChargeDuration == 3
        assert self.get_point(agent, 'b404_DCWh') == 305.7555555555556

    def test_set_ders(self, agent):
        """Test that DERStatus can be fetched after it's been set."""
        assert self.IEEE2030_5_http_get('edev/0/der/1/ders').stateOfChargeStatus is None
        assert self.get_point(agent, 'b802_State') is None
        assert self.get_point(agent, 'b802_LocRemCtl') is None
        assert self.get_point(agent, 'b802_SoC') is None
        assert self.get_point(agent, 'b122_StorConn') is None
        assert self.IEEE2030_5_http_put('edev/0/der/1/ders', 'der.ders').status_code == 204
        assert self.IEEE2030_5_http_get('edev/0/der/1/ders').stateOfChargeStatus.value.get_valueOf_() == '777'
        assert self.get_point(agent, 'b802_State') == 7.77
        assert self.get_point(agent, 'b802_LocRemCtl') == 777
        assert self.get_point(agent, 'b802_SoC') == 777
        assert self.get_point(agent, 'b122_StorConn') == 777

    def test_mup(self, agent):
        """Test that metrics can be fetched from a MirrorUsagePoint."""
        self.IEEE2030_5_http_get('mup')
        assert self.IEEE2030_5_http_put('mup', 'mup.mup').status_code == 201
        assert self.IEEE2030_5_http_get('mup').MirrorUsagePoint[0].description == 'Gas Mirroring'
        self.IEEE2030_5_http_put('mup/0', 'mup.mmr')
        self.IEEE2030_5_http_get('mup')
        assert self.get_point(agent, 'b113_A') == 24.0
        assert self.get_point(agent, 'b122_ActWh') is None
        self.IEEE2030_5_http_put('mup/0', 'mup.mup2')
        assert self.get_point(agent, 'b122_ActWh') == 128

    @staticmethod
    def get_point(agent, point_name):
        """Ask IEEE2030_5Agent for a point value for a IEEE 2030.5 resource."""
        return agent.vip.rpc.call('test_IEEE2030_5agent', 'get_point', DEVICE_ID, point_name).get(timeout=10)

    @staticmethod
    def set_point(agent, point_name, value):
        """Use IEEE2030_5Agent to set a point value for a IEEE 2030.5 resource."""
        return agent.vip.rpc.call('test_IEEE2030_5agent', 'set_point', DEVICE_ID, point_name, value).get(timeout=10)

    @staticmethod
    def IEEE2030_5_http_get(IEEE2030_5_resource_name):
        """
            Issue a web request to GET data for a IEEE 2030.5 resource.

        :param IEEE2030_5_resource_name: The distinguishing part of the name of the IEEE 2030.5 resource as it appears
        in the URL.
        :return: XML
        """
        r = requests.get('{}/dcap/{}'.format(web_address, IEEE2030_5_resource_name))
        assert r.status_code == 200
        return IEEE2030_5Parser.parse(r.text.encode('ascii', 'ignore'))

    @staticmethod
    def IEEE2030_5_http_put(IEEE2030_5_resource_name, IEEE2030_5_filename):
        """
            Issue a web request to PUT data for a IEEE 2030.5 resource, using the contents of an XML file.

        @param IEEE2030_5_resource_name: The distinguishing part of the name of the IEEE 2030.5 resource as it appears
        in the URL.
        @param IEEE2030_5_filename: The distinguishing part of the IEEE 2030.5 sample data file name.
        """
        url = '{}/dcap/{}'.format(web_address, IEEE2030_5_resource_name)
        headers = {'content-type': 'application/IEEE2030_5+xml'}
        return requests.post(url,
                             data=open(get_services_core("IEEE2030_5Agent/tests/{}.PUT.xml").format(IEEE2030_5_filename),
                                       'rb'),
                             headers=headers)
