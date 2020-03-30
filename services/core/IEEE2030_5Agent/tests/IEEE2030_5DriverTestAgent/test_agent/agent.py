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

import gevent
import logging
import requests
import sys

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

_log = logging.getLogger(__name__)
utils.setup_logging()

__version__ = '1.0'

CYCLE_TIME = 3         # Seconds between sets of get_point/set_point calls

ALL_POINTS = [
    'b1_Md',
    'b1_Opt',
    'b1_SN',
    'b1_Vr',
    'b113_A',
    'b113_DCA',
    'b113_DCV',
    'b113_DCW',
    'b113_PF',
    'b113_WH',
    'b120_AhrRtg',
    'b120_ARtg',
    'b120_MaxChaRte',
    'b120_MaxDisChaRte',
    'b120_WHRtg',
    'b120_WRtg',
    'b121_WMax',
    'b122_ActWh',
    'b122_StorConn',
    'b124_WChaMax',
    'b403_Tmp',
    'b404_DCW',
    'b404_DCWh',
    'b802_LocRemCtl',
    'b802_SoC',
    'b802_State']

DEVICE_INFORMATION = """<DeviceInformation xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <functionsImplemented>0145</functionsImplemented>
    <lFDI>5509D69F8B353595206AD71B47E27906318EA367</lFDI>
    <mfDate>1388566800</mfDate>
    <mfHwVer>MF-HW: 1.0.0</mfHwVer>
    <mfID>37250</mfID>
    <mfInfo>Mf Information</mfInfo>
    <mfModel>Mf Model</mfModel>
    <mfSerNum>1234567890</mfSerNum>
    <primaryPower>2</primaryPower>
    <secondaryPower>0</secondaryPower>
    <swActTime>1416107035</swActTime>
    <swVer>9bc8e7b_modified</swVer>
</DeviceInformation>
"""

DER_SETTINGS = """<DERSettings xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <setGradW>55000</setGradW>
    <setMaxChargeRate>
        <multiplier>1</multiplier>
        <value>2</value>
    </setMaxChargeRate>
    <setMaxDischargeRate>
        <multiplier>3</multiplier>
        <value>4</value>
    </setMaxDischargeRate>
    <setMaxW>
        <multiplier>1</multiplier>
        <value>1</value>
    </setMaxW>
    <setStorConnect>true</setStorConnect>
    <updatedTime>1416307137</updatedTime>
</DERSettings>"""

DER_STATUS = """<DERStatus xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <readingTime>1416270124</readingTime>
    <stateOfChargeStatus>
        <dateTime>1416270124</dateTime>
        <value>777</value>
    </stateOfChargeStatus>
    <inverterStatus>
        <dateTime>1416270124</dateTime>
        <value>777</value>
    </inverterStatus>
    <storConnectStatus>
        <dateTime>1416270124</dateTime>
        <value>777</value>
    </storConnectStatus>
    <localControlModeStatus>
        <dateTime>1416270124</dateTime>
        <value>777</value>
    </localControlModeStatus>
</DERStatus>"""

DER_AVAILABILITY = """<DERAvailability xmlns="http://zigbee.org/sep">
    <availabilityDuration>55036</availabilityDuration>
    <maxChargeDuration>3</maxChargeDuration>
    <readingTime>1416304442</readingTime>
    <reserveChargePercent>10000</reserveChargePercent>
    <reservePercent>10000</reservePercent>
    <statWAvail>
        <multiplier>1</multiplier>
        <value>1</value>
    </statWAvail>
</DERAvailability>"""

DER_CAPABILITY = """<DERCapability xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modesSupported>01</modesSupported>
    <rtgAh>
        <multiplier>1</multiplier>
        <value>35</value>
    </rtgAh>
    <rtgA>
        <multiplier>1</multiplier>
        <value>33</value>
    </rtgA>
    <rtgMaxChargeRate>
        <multiplier>1</multiplier>
        <value>22</value>
    </rtgMaxChargeRate>
    <rtgMaxDischargeRate>
        <multiplier>1</multiplier>
        <value>1</value>
    </rtgMaxDischargeRate>
    <rtgMinPF>
        <multiplier>1</multiplier>
        <value>1</value>
    </rtgMinPF>
    <rtgW>
        <multiplier>1</multiplier>
        <value>1</value>
    </rtgW>
    <rtgWh>
        <multiplier>1</multiplier>
        <value>123</value>
    </rtgWh>
    <type>85</type>
</DERCapability>"""

POWER_STATUS = """<PowerStatus xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <batteryStatus>0</batteryStatus>
    <changedTime>1416266598</changedTime>
    <currentPowerSource>3</currentPowerSource>
    <estimatedChargeRemaining>1</estimatedChargeRemaining>
    <estimatedTimeRemaining>0</estimatedTimeRemaining>
    <PEVInfo>
        <chargingPowerNow>
            <multiplier>0</multiplier>
            <value>3000</value>
        </chargingPowerNow>
        <energyRequestNow>
            <multiplier>0</multiplier>
            <value>6100</value>
        </energyRequestNow>
        <maxForwardPower>
            <multiplier>3</multiplier>
            <value>7</value>
        </maxForwardPower>
        <minimumChargingDuration>4337</minimumChargingDuration>
        <targetStateOfCharge>1000</targetStateOfCharge>
        <timeChargeIsNeeded>1516266598</timeChargeIsNeeded>
        <timeChargingStatusPEV>1516266598</timeChargingStatusPEV>
    </PEVInfo>
    <sessionTimeOnBattery>2</sessionTimeOnBattery>
    <totalTimeOnBattery>2</totalTimeOnBattery>
</PowerStatus>"""

MUP = """<MirrorUsagePoint xmlns="http://zigbee.org/sep">
    <mRID>0600006CC8</mRID>
    <description>Gas Mirroring</description>
    <roleFlags>13</roleFlags>
    <serviceCategoryKind>1</serviceCategoryKind>
    <status>1</status>
    <deviceLFDI>247bd68e3378fe57ba604e3c8bdf9e3f78a3d743</deviceLFDI>
    <MirrorMeterReading>
        <mRID>0700006CC8</mRID>
        <description>Cumulative Reading for Gas</description>
        <Reading>
            <value>125</value>
        </Reading>
        <ReadingType>
            <accumulationBehaviour>9</accumulationBehaviour>
            <commodity>7</commodity>
            <dataQualifier>0</dataQualifier>
            <flowDirection>1</flowDirection>
            <powerOfTenMultiplier>3</powerOfTenMultiplier>
            <uom>119</uom>
        </ReadingType>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>0800006CC8</mRID>
        <description>Interval Readings for Gas</description>
        <ReadingType>
            <accumulationBehaviour>4</accumulationBehaviour>
            <commodity>7</commodity>
            <dataQualifier>0</dataQualifier>
            <flowDirection>1</flowDirection>
            <powerOfTenMultiplier>3</powerOfTenMultiplier>
            <uom>119</uom>
        </ReadingType>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>0900006CC8</mRID>
        <description>InstantPackCurrent</description>
        <Reading>
            <value>125</value>
        </Reading>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>0900006CC8</mRID>
        <description>LineVoltageAvg</description>
        <Reading>
            <value>125</value>
        </Reading>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>0900006CC8</mRID>
        <description>PhasePowerAvg</description>
        <Reading>
            <value>125</value>
        </Reading>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>1000006CC8</mRID>
        <description>PhasePFA</description>
        <Reading>
            <value>126</value>
        </Reading>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>1100006CC8</mRID>
        <description>EnergyIMP</description>
        <Reading>
            <value>127</value>
        </Reading>
    </MirrorMeterReading>
    <MirrorMeterReading>
        <mRID>1300006CC8</mRID>
        <description>InstantPackTemp</description>
        <Reading>
            <value>128</value>
        </Reading>
        <ReadingType>
            <accumulationBehaviour>9</accumulationBehaviour>
            <commodity>7</commodity>
            <dataQualifier>0</dataQualifier>
            <flowDirection>1</flowDirection>
            <powerOfTenMultiplier>3</powerOfTenMultiplier>
            <uom>119</uom>
        </ReadingType>
    </MirrorMeterReading>
</MirrorUsagePoint>"""

MUP2 = """<MirrorUsagePoint xmlns="http://zigbee.org/sep">
    <mRID>0600006CC8</mRID>
    <description>Gas Mirroring</description>
    <roleFlags>13</roleFlags>
    <serviceCategoryKind>1</serviceCategoryKind>
    <status>1</status>
    <deviceLFDI>247bd68e3378fe57ba604e3c8bdf9e3f78a3d743</deviceLFDI>
    <MirrorMeterReading>
        <mRID>1200006CC8</mRID>
        <description>EnergyEXP</description>
        <Reading>
            <value>128</value>
        </Reading>
    </MirrorMeterReading>
</MirrorUsagePoint>"""

MMR = """<MirrorMeterReading xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <mRID>6D6D72099BBDE9156400000000009182</mRID>
    <description>PhaseCurrentAvg</description>
    <Reading subscribable="0">
        <timePeriod>
            <duration>0</duration>
            <start>2216441</start>
        </timePeriod>
        <value>24</value>
    </Reading>
    <ReadingType>
        <accumulationBehaviour>12</accumulationBehaviour>
        <commodity>0</commodity>
        <dataQualifier>12</dataQualifier>
        <flowDirection>0</flowDirection>
        <kind>0</kind>
        <phase>0</phase>
        <powerOfTenMultiplier>0</powerOfTenMultiplier>
        <uom>23</uom>
    </ReadingType>
</MirrorMeterReading>"""

ASSERTED_VALUES = {
    'b1_Md': 'Mf Model',
    'b1_Opt': '247bd68e3378fe57ba604e3c8bdf9e3f78a3d743',
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
    'b802_SoC': '7.77',
    'b802_State': '777'}

TEST_WEB_ADDRESS = 'http://127.0.0.1:8080'
DEFAULT_DRIVER = 'IEEE2030_5_1'


class IEEE2030_5DriverTestAgent(Agent):
    """
        Test the IEEE 2030.5 driver (not a pytest regression test).

        Load a test data set by posting XML to IEEE2030_5Agent (assumed to be at port 8080 on the local host).
        Periodically send get_point for each point on the IEEE 2030.5 driver.
        Also send a set_point call to its der_control point, setting a power dispatch value.

        This agent can be installed as follows:
            export VIP_SOCKET="ipc://$VOLTTRON_HOME/run/vip.socket"
            export IEEE2030_5_TEST_ROOT=$VOLTTRON_ROOT/services/core/IEEE2030_5Agent/tests/IEEE2030_5DriverTestAgent/test_agent
            cd $VOLTTRON_ROOT
            python scripts/install-agent.py \
                -s $IEEE2030_5_TEST_ROOT \
                -i IEEE2030_5testagent \
                -c $IEEE2030_5_TEST_ROOT/IEEE2030_5drivertest.config \
                -t IEEE2030_5testagent \
                -f
    """

    def __init__(self, **kwargs):
        super(IEEE2030_5DriverTestAgent, self).__init__(**kwargs)
        self.default_config = {}
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.core.spawn(self.send_and_receive_points)

    def send_and_receive_points(self):
        self.post_test_data()
        while True:
            self.set_point('b124_WChaMax', ASSERTED_VALUES['b124_WChaMax'])
            for point_name in ALL_POINTS:
                expected_value = ASSERTED_VALUES[point_name]
                received_value = self.get_point(point_name)
                assert received_value == expected_value
            gevent.sleep(CYCLE_TIME)

    @staticmethod
    def post_test_data():
        """Post XML test data for a IEEE 2030.5 resource to the IEEE2030_5Agent."""
        headers = {'content-type': 'application/sep+xml'}
        requests.post('{}/dcap/edev/0/di'.format(TEST_WEB_ADDRESS), data=DEVICE_INFORMATION, headers=headers)
        requests.post('{}/dcap/edev/0/der/1/derg'.format(TEST_WEB_ADDRESS), data=DER_SETTINGS, headers=headers)
        requests.post('{}/dcap/edev/0/der/1/ders'.format(TEST_WEB_ADDRESS), data=DER_STATUS, headers=headers)
        requests.post('{}/dcap/edev/0/der/1/dera'.format(TEST_WEB_ADDRESS), data=DER_AVAILABILITY, headers=headers)
        requests.post('{}/dcap/edev/0/der/1/dercap'.format(TEST_WEB_ADDRESS), data=DER_CAPABILITY, headers=headers)
        requests.post('{}/dcap/edev/0/ps'.format(TEST_WEB_ADDRESS), data=POWER_STATUS, headers=headers)
        requests.post('{}/dcap/mup'.format(TEST_WEB_ADDRESS), data=MUP, headers=headers)
        requests.post('{}/dcap/mup/0'.format(TEST_WEB_ADDRESS), data=MUP2, headers=headers)
        requests.post('{}/dcap/mup/0'.format(TEST_WEB_ADDRESS), data=MMR, headers=headers)

    def get_point(self, point_name, driver_name=None):
        """Issue a get_point RPC call for the named point and return the result."""
        driver = driver_name if driver_name else DEFAULT_DRIVER
        response = self.vip.rpc.call(PLATFORM_DRIVER, 'get_point', driver, point_name).get(timeout=10)
        _log.debug('{}: Sent get_point for {}, received {}'.format(driver, point_name, response))
        return response

    def set_point(self, point_name, value, driver_name=None):
        """Issue a set_point RPC call for the named point and value, and return the result."""
        driver = driver_name if driver_name else DEFAULT_DRIVER
        self.vip.rpc.call(PLATFORM_DRIVER, 'set_point', driver, point_name, value)
        _log.debug('{}: Sent set_point for {} = {}'.format(driver, point_name, value))


def test_IEEE2030_5_agent(config_path, **kwargs):
    return IEEE2030_5DriverTestAgent(**kwargs)


def main():
    utils.vip_main(test_IEEE2030_5_agent, identity='IEEE2030_5testagent', version=__version__)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
