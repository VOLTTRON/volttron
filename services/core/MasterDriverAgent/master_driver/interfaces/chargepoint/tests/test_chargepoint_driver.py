# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, SLAC National Laboratory / Kisensum Inc.
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
import os
import pytest
import gevent

from volttron.platform import get_services_core

DRIVER1_CONFIG_STRING = """{
    "driver_config": {
        "stationID" : "1:34003",
        "username" : "9d44ba0be5fe6b6628e50af1335d4fcf5743a6f3c63ee1464051443",
        "password" : "%s",
        "cacheExpiration" : 40
    },
    "campus": "campus",
    "building": "building",
    "unit": "station_001_01",
    "driver_type": "chargepoint",
    "registry_config":"config://chargepoint.csv",
    "interval": 5,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}"""

DRIVER2_CONFIG_STRING = """{
    "driver_config": {
        "stationID" : "1:34033",
        "username" : "9d44ba0be5fe6b6628e50af1335d4fcf5743a6f3c63ee1464051443",
        "password" : "%s",
        "cacheExpiration" : 40
    },
    "campus": "campus",
    "building": "building",
    "unit": "station_001_02",
    "driver_type": "chargepoint",
    "registry_config":"config://chargepoint.csv",
    "interval": 5,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}"""

# This registry configuration is for a two-port charge station
REGISTRY_CONFIG_STRING = """Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes
stationID,stationID,StationRegister,,string,Format similar to 1:00001,,FALSE,
stationManufacturer,stationManufacturer,StationRegister,,string,String,,FALSE,
stationModel,stationModel,StationRegister,,string,String,,FALSE,
portNumber,portNumber,StationRegister,1,string,Integer,,FALSE,
portNumber2,portNumber,StationRegister,2,string,Integer,,FALSE,
stationName,stationName,StationRegister,1,string,String,,FALSE,
stationName2,stationName,StationRegister,2,string,String,,FALSE,
stationMacAddr,stationMacAddr,StationRegister,,string,String (colon separated mac address),,FALSE,
stationSerialNum,stationSerialNum,StationRegister,,string,String,,FALSE,
Address,Address,StationRegister,,string,String,,FALSE,
City,City,StationRegister,,string,String,,FALSE,
State,State,StationRegister,,string,String,,FALSE,
Country,Country,StationRegister,,string,String,,FALSE,
postalCode,postalCode,StationRegister,,string,US Postal code,,FALSE,
Lat,Lat,StationRegister,1,float,Latitude Coordinate,,FALSE,
Lat2,Lat,StationRegister,2,float,Latitude Coordinate,,FALSE,
Long,Long,StationRegister,1,float,Longitude Coordinate,,FALSE,
Long2,Long,StationRegister,2,float,Longitude Coordinate,,FALSE,
Reservable,Reservable,StationRegister,1,bool,T/F,,FALSE,
Level,Level,StationRegister,1,string,"L1, L2, L3",,FALSE,
Level2,Level,StationRegister,2,string,"L1, L2, L3",,FALSE,
Mode,Mode,StationRegister,1,int,"1,2,3",,FALSE,
Mode2,Mode,StationRegister,2,int,"1,2,3",,FALSE,
Voltage,Voltage,StationRegister,1,float,Configured Voltage,,FALSE,
Voltage2,Voltage,StationRegister,2,float,Configured Voltage,,FALSE,
Current,Current,StationRegister,1,float,Configured Current,,FALSE,
Current2,Current,StationRegister,2,float,Configured Current,,FALSE,
Power,Power,StationRegister,1,float,Configured Power,,FALSE,Power supported (kW).
Power2,Power,StationRegister,2,float,Configured Power,,FALSE,Power supported (kW).
numPorts,numPorts,StationRegister,,int,Integer,,FALSE,Number of Ports
Type,Type,StationRegister,,int,Integer or None,,FALSE,
startTime,startTime,StationRegister,,datetime,Datetime,,FALSE,
endTime,endTime,StationRegister,,datetime,Datetime,,FALSE,
minPrice,minPrice,StationRegister,,float,Dollar Amount,,FALSE,
maxPrice,maxPrice,StationRegister,,float,Dollar Amount,,FALSE,
unitPricePerHour,unitPricePerHour,StationRegister,,float,Dollar Amount,,FALSE,
unitPricePerSession,unitPricePerSession,StationRegister,,float,Dollar Amount,,FALSE,
unitPricePerKWh,unitPricePerKWh,StationRegister,,float,Dollar Amount,,FALSE,
unitPriceForFirst,unitPriceForFirst,StationRegister,,float,Dollar Amount,,FALSE,
unitPricePerHourThereafter,unitPricePerHourThereafter,StationRegister,,float,Dollar Amount,,FALSE,
sessionTime,sessionTime,StationRegister,,datetime,,,FALSE,
Description,Description,StationRegister,1,string,String,,FALSE,
Description2,Description,StationRegister,2,string,String,,FALSE,
mainPhone,mainPhone,StationRegister,,string,Phone Number,,FALSE,
orgID,orgID,StationRegister,,string,,,FALSE,
organizationName,organizationName,StationRegister,,string,,,FALSE,
sgID,sgID,StationRegister,,string,,,FALSE,
sgName,sgName,StationRegister,,string,,,FALSE,
currencyCode,currencyCode,StationRegister,,string,,,FALSE,
Status,Status,StationStatusRegister,1,string,,,FALSE,"AVAILABLE, INUSE, UNREACHABLE, UNKNOWN "
Status2,Status,StationStatusRegister,2,string,,,FALSE,"AVAILABLE, INUSE, UNREACHABLE, UNKNOWN "
Status.TimeStamp,TimeStamp,StationStatusRegister,1,datetime,,,FALSE,Timestamp of the last communication between the station and ChargePoint
Status2.TimeStamp,TimeStamp,StationStatusRegister,2,datetime,,,FALSE,Timestamp of the last communication between the station and ChargePoint
Connector,Connector,StationRegister,1,string,,,FALSE,"Connector type. For example: NEMA 5-20R, J1772, ALFENL3, "
Connector2,Connector,StationRegister,2,string,,,FALSE,"Connector type. For example: NEMA 5-20R, J1772, ALFENL3, "
shedState,shedState,LoadRegister,1,integer,0 or 1,0,TRUE,True when load shed limits are in place
portLoad,portLoad,LoadRegister,1,float,kw,,FALSE,Load in kw
allowedLoad,allowedLoad,LoadRegister,,float,kw,,TRUE,Allowed load in kw when shedState is True
percentShed,percentShed,LoadRegister,,integer,percent,,TRUE,Percent of max power shed when shedState is True
alarmType,alarmType,AlarmRegister,,string,,,FALSE,eg. 'GFCI Trip'
alarmTime,alarmTime,AlarmRegister,,datetime,,,FALSE,
clearAlarms,clearAlarms,AlarmRegister,,int,,0,TRUE,Sends the clearAlarms query when set to True
stationRightsProfile,stationRightsProfile,StationRightsRegister,,dictionary,,,FALSE,"Dictionary of sgID, rights name tuples."
sessionID,sessionID,ChargingSessionRegister,1,string,,,FALSE,
startTime,startTime,ChargingSessionRegister,1,datetime,,,FALSE,
endTime,endTime,ChargingSessionRegister,1,datetime,,,FALSE,
Energy,Energy,ChargingSessionRegister,1,float,,,FALSE,
rfidSerialNumber,rfidSerialNumber,ChargingSessionRegister,1,string,,,FALSE,
driverAccountNumber,driverAccountNumber,ChargingSessionRegister,1,string,,,FALSE,
driverName,driverName,ChargingSessionRegister,1,string,,,FALSE,"""


@pytest.fixture(scope='module')
def agent(request, volttron_instance1):
    md_agent = volttron_instance1.build_agent()
    # Clean out master driver configurations.
    md_agent.vip.rpc.call('config.store',
                          'manage_delete_store',
                          'platform.driver').get(timeout=10)

    driver1_config = DRIVER1_CONFIG_STRING % os.environ.get('CHARGEPOINT_PASSWORD', 'Must set a password')
    driver2_config = DRIVER2_CONFIG_STRING % os.environ.get('CHARGEPOINT_PASSWORD', 'Must set a password')
    print('Driver1 config: %s' % driver1_config)

    # Add test configurations.
    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'devices/chargepoint1',
                          driver1_config,
                          'json').get(timeout=10)

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'devices/chargepoint2',
                          driver2_config,
                          'json').get(timeout=10)

    md_agent.vip.rpc.call('config.store',
                          'manage_store',
                          'platform.driver',
                          'chargepoint.csv',
                          REGISTRY_CONFIG_STRING,
                          'csv').get(timeout=10)

    master_uuid = volttron_instance1.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                                   config_file={},
                                                   start=True)
    print('agent id: ', master_uuid)
    gevent.sleep(10)  # wait for the agent to start and start the devices

    def stop():
        volttron_instance1.stop_agent(master_uuid)
        md_agent.core.stop()

    request.addfinalizer(stop)
    return md_agent


@pytest.mark.skipif("CHARGEPOINT_PASSWORD" not in os.environ,
                    reason="Requires a valid password in driver configuration")
class TestChargepointDriver:
    """
        Regression tests for the chargepoint driver interface.
    """

    def get_point(self, agent, point_name, driver_name=None):
        """
            Issue a get_point RPC call for the named point and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param: driver_name: The driver name (default: chargepoint1).
        @return: The returned value from the RPC call.
        """
        driver = driver_name if driver_name else 'chargepoint1'
        return agent.vip.rpc.call('platform.driver', 'get_point', driver, point_name).get(timeout=10)

    def set_point(self, agent, point_name, value, driver_name=None):
        """
            Issue a set_point RPC call for the named point and value, and return the result.

        @param agent: The test Agent.
        @param point_name: The name of the point to query.
        @param value: The value to set on the point.
        @param: driver_name: The driver name (default: chargepoint1).
        @return: The returned value from the RPC call.
        """
        driver = driver_name if driver_name else 'chargepoint1'
        return agent.vip.rpc.call('platform.driver', 'set_point', driver, point_name, value).get(timeout=10)

    def test_get_station_mac_addr(self, agent):
        assert ':' in self.get_point(agent, 'stationMacAddr')

    def test_lat_long(self, agent):
        lat = self.get_point(agent, 'Lat')
        lon = self.get_point(agent, 'Long')
        print("Lat/Long: {0}, {1}".format(lat, lon))
        assert type(lat) == float
        assert type(lon) == float

    def test_set_shed_state(self, agent):
        self.set_point(agent, 'shedState', 0)
        # Wait for shedState to be cleared
        gevent.sleep(5)
        assert self.get_point(agent, 'shedState') == 0

    def test_set_allowed_load(self, agent):
        self.set_point(agent, 'allowedLoad', 5.0)
        # Reset the test environment: Clear the shed state
        self.set_point(agent, 'shedState', 0)

    def test_set_percent_shed(self, agent):
        self.set_point(agent, 'percentShed', 50)
        # Reset the test environment: Clear the shed state
        self.set_point(agent, 'shedState', 0)

    def test_clear_alarms(self, agent):
        # Clear all alarms
        self.set_point(agent, 'clearAlarms', 1)
        # Wait for alarms to be cleared
        gevent.sleep(5)
        # Verify that no alarms are present
        assert self.get_point(agent, 'alarmType') is None

    def test_get_charging_session_id(self, agent):
        assert self.get_point(agent, 'sessionID') is not None

    def test_get_status(self, agent):
        assert self.get_point(agent, 'Status') in ('AVAILABLE', 'INUSE', 'UNREACHABLE', 'UNKNOWN')

    def test_get_station_rights(self, agent):
        assert type(self.get_point(agent, 'stationRightsProfile')) == dict

    def test_two_station_ids(self, agent):
        assert self.get_point(agent, 'stationID', driver_name='chargepoint1') == '1:34003'
        assert self.get_point(agent, 'stationID', driver_name='chargepoint2') == '1:34033'

    def test_two_port_levels(self, agent):
        assert self.get_point(agent, 'Level') == 'L1'
        assert self.get_point(agent, 'Level2') == 'L2'
