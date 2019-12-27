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

import time
import pytest
import gevent
import requests

from volttron.platform import get_services_core

DRIVER_NAME = 'sep2'
DEVICE_ID = "097935300833"

TEST_CONFIG = {
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
b113_A,MirrorMeterReading,PhaseCurrentAvg,NA,FALSE,NA
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

ASSERTED_VALUES = {
    'b1_Md': 'Mf Model',
    'b1_SN': '097935300833',
    'b1_Vr': 'MF-HW: 1.0.0',
    'b113_A': '24.0',
    'b113_DCA': '125.0',
    'b113_DCV': '125.0',
    'b113_DCW': '125.0',
    'b113_PF': '126.0',
    'b113_WH': '127.0',
    'b120_AhrRtg': '350.0',
    'b120_ARtg': '330.0',
    'b120_MaxChaRte': '220.0',
    'b120_MaxDisChaRte': '10.0',
    'b120_WHRtg': '1230.0',
    'b120_WRtg': '10.0',
    'b121_WMax': '20.0',
    'b122_ActWh': '128.0',
    'b122_StorConn': '777',
    'b124_WChaMax': '10.0',
    'b403_Tmp': '128000.0',
    'b404_DCW': '3000.0',
    'b404_DCWh': '305.755555556',
    'b802_LocRemCtl': '777',
    'b802_SoC': '777',
    'b802_State': '7.77'}

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

    # Install and start a MasterDriverAgent
    md_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                       config_file={},
                                                       start=True)
    print('master driver agent id: ', md_id)

    # Install and start a SEP2Agent
    sep2_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("SEP2Agent"),
                                                         config_file=TEST_CONFIG,
                                                         vip_identity='test_sep2agent',
                                                         start=True)
    print('sep2 agent id: ', sep2_id)

    global web_address
    web_address = volttron_instance_module_web.bind_web_address

    def stop():
        volttron_instance_module_web.stop_agent(md_id)
        volttron_instance_module_web.stop_agent(sep2_id)
        test_agent.core.stop()

    gevent.sleep(10)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


class TestSEP2Driver:
    """Regression tests for the SEP2 driver."""

    def test_all_points(self, agent):
        self.put_sep2_data('edev/0/di', 'edev.di')                  # device_information
        self.put_sep2_data('edev/0/der/1/derg', 'der.derg')         # der_settings
        self.put_sep2_data('edev/0/der/1/ders', 'der.ders')         # der_status
        self.put_sep2_data('edev/0/der/1/dera', 'der.dera')         # der_availability
        self.put_sep2_data('edev/0/der/1/dercap', 'der.dercap')     # der_capabililty
        self.put_sep2_data('edev/0/ps', 'edev.ps')                  # power_status
        self.put_sep2_data('mup', 'mup.mup')                        # mup
        self.put_sep2_data('mup/0', 'mup.mup2')                     # mup (update)
        self.put_sep2_data('mup/0', 'mup.mmr')                      # mmr

        # Wait a few seconds to allow the HTTP requests to be processed (asynchronously?)
        time.sleep(5)

        # Set the one settable point, the dispatched power value, and test that it comes back on a get_point
        dispatch_point_name = 'b124_WChaMax'
        dispatched_value = ASSERTED_VALUES[dispatch_point_name]
        self.set_point(agent, dispatch_point_name, dispatched_value)
        assert self.get_point(agent, dispatch_point_name) == dispatched_value

        # Test that each point has the test value that was posted to it
        for point_name, expected_value in ASSERTED_VALUES.items():
            assert self.get_point(agent, point_name) == expected_value

    @staticmethod
    def get_point(test_agent, point_name):
        return test_agent.vip.rpc.call('platform.driver', 'get_point', DRIVER_NAME, point_name).get(timeout=10)

    @staticmethod
    def set_point(test_agent, point_name, value):
        return test_agent.vip.rpc.call('platform.driver', 'set_point', DRIVER_NAME, point_name, value).get(timeout=10)

    @staticmethod
    def put_sep2_data(sep2_resource_name, sep2_filename):
        """
            PUT data for a SEP2 resource, using the contents of an XML file in the current directory.

        @param sep2_resource_name: The distinguishing part of the name of the SEP2 resource as it appears in the URL.
        @param sep2_filename: The distinguishing part of the SEP2 sample data file name.
        """
        url = '{}/dcap/{}'.format(web_address, sep2_resource_name)
        headers = {'content-type': 'application/sep+xml'}
        requests.post(url,
                      data=open(get_services_core("SEP2Agent/tests/{}.PUT.xml".format(sep2_filename)), 'rb'),
                      headers=headers)
