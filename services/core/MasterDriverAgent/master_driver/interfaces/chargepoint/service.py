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

import suds.client
import suds.wsse
import logging

logger = logging.getLogger('chargepoint')

SERVICE_WSDL_URL = "https://webservices.chargepoint.com/cp_api_5.0.wsdl"

CPAPI_SUCCESS = '100'

XMPP_EVENTS = [
    'station_charging_session_start',
    'station_charging_session_stop',
    'station_charging_session_update'
]


class CPAPIException(Exception):
    """Generic Chargepoint API Exception.

    :param response_code: Exception code.
    :param response_text: Exception description.
    """

    def __init__(self, response_code, response_text):
        self._responseCode = response_code
        self._responseText = response_text

    def __str__(self):
        return '{0} : {1}'.format(self._responseCode, self._responseText)


class CPOrganization(object):
    """Represents an organization within the ChargePoint network.

    :param cpn_id: Chargepoint Network ID.
    :param organization_id: Chargepoint Org ID.
    :param name:
    """

    def __init__(self, cpn_id, organization_id, name="Unknown"):
        self._cpn_id = cpn_id
        self._organization_id = organization_id
        self._name = name

    def orgID(self):
        """Returns Chargepoint orgID

        :return orgID: 'cpn_id:organization_id'.
        """
        return '{0}:{1}'.format(self._cpn_id, self._organization_id)


class CPGroupManager(object):
    """Manger for a Chargepoint group and its stations.

    :param cps: Chargepoint Service object.
    :param group: CPStationGroup object.
    :param stations: List of CPStation objects belonging to the CPStationGroup.
    """

    def __init__(self, cps, group, stations):
        self._cps = cps
        self._group = group
        self._stations = stations

    def refreshGroupStationData(self):
        """For all stations belonging to group, refresh load data."""

        stationData = self._cps.getLoad(sgID=self._group.id)
        for data in stationData:
            for station in self._stations:
                if station.id == data.stationID:
                    station._data['stationLoadData'] = data


class CPStationGroup(object):
    """Wrapper around the getStationGroups() return by Chargepoint API.

    :param cps: Chargepoint Service object.
    :param groupsdata: Returned from Chargepoint API. Defined below.

    (groupsdata){
        sgID = 00001
        orgID = "1:ORG00001"
        sgName = "Main St Garage"
        organizationName = "My Organization Name"
        stationData[] =
            (stationData){
                stationID = "1:00001"
                Geo =
                    (geoData){
                        Lat = "12.345678901234567"
                        Long = "-123.456789012345678"
                    }
            },
            ...
    }

    :property id: sgID
    :property name: sgName
    :property organization: CPOrganization __str__ representation
    :property station_ids: List of IDs for stations in belonging to the group
    """

    def __init__(self, cps, groupsdata):
        self._cps = cps
        self._groupsdata = groupsdata

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.id)

    @property
    def id(self):
        return self._groupsdata.sgID

    @property
    def name(self):
        return self._groupsdata.sgName

    @property
    def organization(self):
        cpn_id, organization_id = self._groupsdata.orgID.split(":")
        return CPOrganization(cpn_id, organization_id, self._groupsdata.organizationName)

    @property
    def station_ids(self):
        return [s.stationID for s in self._groupsdata.stationData]


class CPStation(object):
    """Wrapper around the getStations() return by Chargepoint API.

    Data surrounding a Chargepoint Station can generally be categorized as static or dynamic.  Chargepoint API has two
    basic calls, getLoad and getStation, that each return station data.  getLoad returns the stationLoadData SUDS
    object, and getStation returns the stationDataExtended SUDS object.  These are each kept as separate meta-data
    parameters.

    :param cps: Chargepoint Service object.
    :param sld: stationLoadData SUDS object.
    :param sde: stationDataExtended SUDS object.

    (stationDataExtended){
        stationID = "1:00001"
        stationManufacturer = "ChargePoint"
        stationModel = "CT2100-HD-CDMA-CCR"
        stationMacAddr = "0123:4567:89AB:CDEF"
        stationSerialNum = "000000000001"
        stationActivationDate = 2016-01-01 12:23:45
        Address = "1 Main St "
        City = "Oakland"
        State = "California"
        Country = "United States"
        postalCode = "94607"
        Port[] =
            (portData){
                portNumber = "1"
                stationName = "CHARGEPOINT / MAIN 001"
                Geo =
                    (geoData){
                        Lat = "12.345678901234567"
                        Long = "-123.456789012345678"
                    }
                Description = "Use garage entrance on Main St., turn right and follow ...
                Reservable = 0
                Level = "L1"
                Connector = "NEMA 5-20R"
                Voltage = "120"
                Current = "16"
                Power = "1.920"
                estimatedCost = 0.0
            },
            (portData){
                portNumber = "2"
                stationName = "CHARGEPOINT / MAIN 001"
                Geo =
                    (geoData){
                        Lat = "12.345678901234567"
                        Long = "-123.456789012345678"
                    }
                Description = "Use garage entrance on Main St., turn right and follow ...
                Reservable = 0
                Level = "L2"
                Connector = "J1772"
                Voltage = "240"
                Current = "30"
                Power = "6.600"
                estimatedCost = 0.0
            },
        Pricing[] =
            (pricingSpecification){
                Type = "None"
                startTime = 00:00:00
                endTime = 23:59:59
                minPrice = 0.0
                maxPrice = 0.0
                unitPricePerHour = 0.0
                unitPricePerSession = 1.0
                unitPricePerKWh = 0.2
            },
        numPorts = 2
        mainPhone = "1-888-123-4567"
        currencyCode = "USD"
        orgID = "1:ORG00001"
        organizationName = "My Organization Name"
        sgID = "00001, 00002, 00003, 00004, 00005, 00006, 00007, 00008, 00009, ...
        sgName = "Main St Garage, Public Garages, California Stations, ...
    }

    (stationloaddata){
        stationID = "1:00001"
        stationName = "CHARGEPOINT / MAIN 001"
        Address = "1 Main St, Oakland, California, 94607, United States"
        stationLoad = 5.43
        Port[] =
            (stationPortData){
                portNumber = "1"
                userID = None
                credentialID = None
                shedState = 0
                portLoad = 0.0
                allowedLoad = 0.0
                percentShed = "0"
            },
            (stationPortData){
                portNumber = "2"
                credentialID = "ABC000123456"
                shedState = 0
                portLoad = 5.43
                allowedLoad = 0.0
                percentShed = "0"
            },
    }

    :property id: sde.stationID
    :property manufacturer: sde.stationManufacturer
    :property model: sde.stationModel
    :property mac: sde.stationMacAddr
    :property serial: sde.stationSerialNum
    :property activationDate: sde.stationActivationDate
    :property name: sld.stationName
    :property load: sld.stationLoad
    """

    def __init__(self, cps, sld=None, sde=None):
        self._cps = cps
        self._data = {
            'stationLoadData': sld,
            'stationDataExtended': sde
        }

    def __str__(self):
        return '{0} ({1})'.format(self.serial, self.id)

    @property
    def _sld(self):
        return self._data['stationLoadData']

    @property
    def _sde(self):
        return self._data['stationDataExtended']

    @property
    def id(self):
        return self._sde.stationID

    @property
    def manufacturer(self):
        return self._sde.stationManufacturer

    @property
    def model(self):
        return self._sde.stationModel

    @property
    def mac(self):
        return self._sde.stationMacAddr

    @property
    def serial(self):
        return self._sde.stationSerialNum

    @property
    def activationDate(self):
        return self._sde.stationActivationDate

    @property
    def name(self):
        return self._sld.stationName

    @property
    def load(self):
        return self._sld.stationLoad

    @property
    def organization(self):
        cpn_id, organization_id = self._sde.orgID.split(":")
        return CPOrganization(cpn_id, organization_id, self._sde.organizationName)

    @property
    def ports(self):
        return [CPPort(p) for p in self._sde.Port]

    def refreshStationData(self):
        self._data['stationLoadData'] = self._cps.getLoad(stationID=self.id)[0]

    def refreshStationDataExtended(self):
        self._data['stationDataExtended'] = self._cps.getStation(stationID=self.id)[0]


class CPPort(object):
    def __init__(self, data=None):
        self._data = data

    @property
    def portNumber(self):
        return self._data.portNumber

    @property
    def level(self):
        return self._data.Level

    @property
    def connector(self):
        return self._data.Connector

    @property
    def voltage(self):
        return self._data.Voltage

    @property
    def current(self):
        return self._data.Current

    @property
    def power(self):
        return self._data.Power


class CPAPIResponse(object):
    """Response object describing a chargepoint API call

    :param response: SOAP object containing the API response
    :property responseCode: API response Code.  '100' is a successful call.
    :property responseText: Short description of the designation for the API call

    :method is_successful: Returns Boolean value checking whether or not responseCode is set to '100.'
    """

    def __init__(self, response):
        self.response = response

    @property
    def responseCode(self):
        return self.response.responseCode

    @property
    def responseText(self):
        return self.response.responseText

    def is_successful(self):
        return self.responseCode == CPAPI_SUCCESS

    @staticmethod
    def is_not_found(name):
        logger.warning("{0} not found in result set.".format(name))
        return None

    @staticmethod
    def get_port_value(port_number, data, attribute):
        """Returns data for a given port

        :param port_number: Number of the port to access.
        :param data: Larger data structure to scan for Port data.
        :param attribute: Which piece of Port data to return.

        :return port_data: Accessed data for given port number and attribute. Else None.
        """
        if 'Port' in data:
            flag = True
            for port in data.Port:
                if int(port.portNumber) == port_number:
                    flag = False
                    if attribute in ['Lat', 'Long']:
                        if 'Geo' in port:
                            return CPAPIResponse.check_output(attribute, port['Geo'])
                        else:
                            logger.warning('Geo not defined for this port.')
                            return None
                    else:
                        return CPAPIResponse.check_output(attribute, port)
            if flag:
                logger.warning("Station does not have a definition for port {0}".format(port_number))
        else:
            logger.warning("Response does not have Ports defined")
            return None

    @staticmethod
    def check_output(attribute, parent_dict):
        """Helper method for get_port_value"""
        if attribute in parent_dict:
            if parent_dict[attribute] == "None":
                return None
            else:
                return parent_dict[attribute]
        else:
            logger.warning("{0} not found in Port result set.".format(attribute))
            return None

    @staticmethod
    def get_attr_from_response(name_string, response, portNum=None):
        list = []
        for item in response:
            if not portNum:
                list.append(getattr(item, name_string)
                            if name_string in item
                            else CPAPIResponse.is_not_found(name_string))
            else:
                list.append(CPAPIResponse.get_port_value(portNum, item, name_string))
        return list


class CPAPIGetAlarmsResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetAlarmsResponse, self).__init__(response)

    @property
    def alarms(self):
        if self.is_successful():
            return self.response.Alarms
        else:
            raise CPAPIException(self.responseCode, self.responseText)

    def alarmType(self, port=None):
        return CPAPIResponse.get_attr_from_response('alarmType', self.alarms, port)

    def alarmTime(self, port=None):
        return CPAPIResponse.get_attr_from_response('alarmTime', self.alarms, port)

    def clearAlarms(self, port=None):
        return CPAPIResponse.get_attr_from_response('clearAlarms', self.alarms, port)


class CPAPIGetChargingSessionsResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetChargingSessionsResponse, self).__init__(response)

    @property
    def charging_sessions(self):
        if self.is_successful():
            return self.response.ChargingSessionData
        else:
            raise CPAPIException(self.responseCode, self.responseText)

    def sessionID(self, port=None):
        return CPAPIResponse.get_attr_from_response('sessionID', self.charging_sessions, port)

    def startTime(self, port=None):
        return CPAPIResponse.get_attr_from_response('startTime', self.charging_sessions, port)

    def endTime(self, port=None):
        return CPAPIResponse.get_attr_from_response('endTime', self.charging_sessions, port)

    def Energy(self, port=None):
        return CPAPIResponse.get_attr_from_response('Energy', self.charging_sessions, port)

    def rfidSerialNumber(self, port=None):
        return CPAPIResponse.get_attr_from_response('rfidSerialNumber', self.charging_sessions, port)

    def driverAccountNumber(self, port=None):
        return CPAPIResponse.get_attr_from_response('driverAccountNumber', self.charging_sessions, port)

    def driverName(self, port=None):
        return CPAPIResponse.get_attr_from_response('driverName', self.charging_sessions, port)


class CPAPIGetStationStatusResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetStationStatusResponse, self).__init__(response)

    @property
    def status(self):
        if self.is_successful():
            return self.response.stationData
        else:
            raise CPAPIException(self.responseCode, self.responseText)

    def Status(self, port=None):
        return CPAPIResponse.get_attr_from_response('Status', self.status, port)

    def TimeStamp(self, port=None):
        return CPAPIResponse.get_attr_from_response('TimeStamp', self.status, port)


class CPAPIGetStationsResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetStationsResponse, self).__init__(response)

    @property
    def stations(self):
        if self.is_successful():
            return self.response.stationData
        else:
            raise CPAPIException(self.responseCode, self.responseText)

    def stationID(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationID', self.stations, port)

    def stationManufacturer(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationManufacturer', self.stations, port)

    def stationModel(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationModel', self.stations, port)

    def stationMacAddr(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationMacAddr', self.stations, port)

    def stationSerialNum(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationSerialNum', self.stations, port)

    def Address(self, port=None):
        return CPAPIResponse.get_attr_from_response('Address', self.stations, port)

    def City(self, port=None):
        return CPAPIResponse.get_attr_from_response('City', self.stations, port)

    def State(self, port=None):
        return CPAPIResponse.get_attr_from_response('State', self.stations, port)

    def Country(self, port=None):
        return CPAPIResponse.get_attr_from_response('Country', self.stations, port)

    def postalCode(self, port=None):
        return CPAPIResponse.get_attr_from_response('postalCode', self.stations, port)

    def numPorts(self, port=None):
        return CPAPIResponse.get_attr_from_response('numPorts', self.stations, port)

    def currencyCode(self, port=None):
        return CPAPIResponse.get_attr_from_response('currencyCode', self.stations, port)

    def orgID(self, port=None):
        return CPAPIResponse.get_attr_from_response('orgID', self.stations, port)

    def mainPhone(self, port=None):
        return CPAPIResponse.get_attr_from_response('mainPhone', self.stations, port)

    def organizationName(self, port=None):
        return CPAPIResponse.get_attr_from_response('organizationName', self.stations, port)

    def sgID(self, port=None):
        return CPAPIResponse.get_attr_from_response('sgID', self.stations, port)

    def sgName(self, port=None):
        return CPAPIResponse.get_attr_from_response('sgName', self.stations, port)

    def portNumber(self, port=None):
        return CPAPIResponse.get_attr_from_response('portNumber', self.stations, port)

    def stationName(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationName', self.stations, port)

    def Lat(self, port=None):
        return CPAPIResponse.get_attr_from_response('Lat', self.stations, port)

    def Long(self, port=None):
        return CPAPIResponse.get_attr_from_response('Long', self.stations, port)

    def Description(self, port=None):
        return CPAPIResponse.get_attr_from_response('Description', self.stations, port)

    def Reservable(self, port=None):
        return CPAPIResponse.get_attr_from_response('Reservable', self.stations, port)

    def Level(self, port=None):
        return CPAPIResponse.get_attr_from_response('Level', self.stations, port)

    def Mode(self, port=None):
        return CPAPIResponse.get_attr_from_response('Mode', self.stations, port)

    def Voltage(self, port=None):
        return CPAPIResponse.get_attr_from_response('Voltage', self.stations, port)

    def Current(self, port=None):
        return CPAPIResponse.get_attr_from_response('Current', self.stations, port)

    def Power(self, port=None):
        return CPAPIResponse.get_attr_from_response('Power', self.stations, port)

    def Connector(self, port=None):
        return CPAPIResponse.get_attr_from_response('Connector', self.stations, port)

    @staticmethod
    def pricing_helper(attribute, station):
        if 'Pricing' in station:
            return station.Pricing[0][attribute] \
                if attribute in station.Pricing[0] \
                else CPAPIResponse.is_not_found(attribute)
        else:
            logger.warning("No Pricing defined for station")
            return None

    def Type(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('Type', self.stations, port)
        else:
            return [self.pricing_helper('Type', station) for station in self.stations]

    def startTime(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('startTime', self.stations, port)
        else:
            return [self.pricing_helper('startTime', station) for station in self.stations]

    def endTime(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('endTime', self.stations, port)
        else:
            return [self.pricing_helper('endTime', station) for station in self.stations]

    def minPrice(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('minPrice', self.stations, port)
        else:
            return [self.pricing_helper('minPrice', station) for station in self.stations]

    def maxPrice(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('maxPrice', self.stations, port)
        else:
            return [self.pricing_helper('maxPrice', station) for station in self.stations]

    def unitPricePerHour(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('unitPricePerHour', self.stations, port)
        else:
            return [self.pricing_helper('unitPricePerHour', station) for station in self.stations]

    def unitPricePerSession(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('unitPricePerSession', self.stations, port)
        else:
            return [self.pricing_helper('unitPricePerSession', station) for station in self.stations]

    def unitPricePerKWh(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('unitPricePerKWh', self.stations, port)
        else:
            return [self.pricing_helper('unitPricePerKWh', station) for station in self.stations]

    def unitPriceForFirst(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('unitPriceForFirst', self.stations, port)
        else:
            return [self.pricing_helper('unitPriceForFirst', station) for station in self.stations]

    def unitPricePerHourThereafter(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('unitPricePerHourThereafter', self.stations, port)
        else:
            return [self.pricing_helper('unitPricePerHourThereafter', station) for station in self.stations]

    def sessionTime(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('sessionTime', self.stations, port)
        else:
            return [self.pricing_helper('sessionTime', station) for station in self.stations]


class CPAPIGetStationRightsResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetStationRightsResponse, self).__init__(response)

    @property
    def rights(self):
        if self.is_successful():
            return self.response.rightsData
        else:
            raise CPAPIException(self.responseCode, self.responseText)


class CPAPIGetLoadResponse(CPAPIResponse):
    def __init__(self, response):
        super(CPAPIGetLoadResponse, self).__init__(response)

    @property
    def station_data(self):
        if self.is_successful():
            return self.response.stationData
        else:
            raise CPAPIException(self.responseCode, self.responseText)

    def stationLoad(self, port=None):
        return CPAPIResponse.get_attr_from_response('stationLoad', self.station_data, port)

    def portLoad(self, port=None):
        return CPAPIResponse.get_attr_from_response('portLoad', self.station_data, port)

    def allowedLoad(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('allowedLoad', self.station_data, port)
        else:
            list = []
            for station in self.station_data:
                al = 0.0
                for port in station.Port:
                    allowed_load = self.get_port_value(int(port.portNumber), station, 'allowedLoad')
                    shed_state = self.get_port_value(int(port.portNumber), station, 'shedState')
                    if shed_state and allowed_load > al:
                        al = allowed_load
                list.append(al)
            return list

    def percentShed(self, port=None):
        if port:
            return CPAPIResponse.get_attr_from_response('percentShed', self.station_data, port)
        else:
            list = []
            for station in self.station_data:
                ps = 0.0
                for port in station.Port:
                    percent_shed = self.get_port_value(int(port.portNumber), station, 'percentShed')
                    shed_state = self.get_port_value(int(port.portNumber), station, 'shedState')
                    if shed_state and percent_shed > ps:
                        ps = percent_shed
                list.append(ps)
            return list

    def shedState(self, port=None):
        return CPAPIResponse.get_attr_from_response('shedState', self.station_data, port)


class CPService(object):
    """
        Python wrapper around the Chargepoint WebServices API.

        Current Version: 5.0
        Docs: ChargePoint_Web_Services_API_Guide_Ver4.1_Rev5.pdf
    """

    def __init__(self, username=None, password=None):
        """
            Use a default API Username/Password if nothing is provided.  These credentials are
            created on the chargepoint website: htpp://na.chargepoint.com, tab=organizations
        """
        self._username = username
        self._password = password
        self._suds_client = None

    @property
    def _client(self):
        """Initialize the SUDS client if necessary."""

        if self._suds_client is None:
            self._suds_client = suds.client.Client(SERVICE_WSDL_URL)
            # Add SOAP Security tokens
            self.set_security_token()

        return self._suds_client

    @property
    def _soap_service(self):
        return self._client.service

    def set_security_token(self):
        # Add SOAP Security tokens
        security = suds.wsse.Security()
        token = suds.wsse.UsernameToken(self._username, self._password)
        security.tokens.append(token)
        self._suds_client.set_options(wsse=security)

    def set_client(self, client):
        self._suds_client = client
        self.set_security_token()

    def clearAlarms(self, **kwargs):
        """Clears the Alarms of given group or station based on given query parameters.

        :param **kwargs: any top-level kwarg in the following query. Most frequently queried via stationID.

        Query:
            (clearAlarmsSearchQuery){
                orgID = None
                organizationName = None
                stationID = None
                stationName = None
                sgID = None
                sgName = None
                startTime = None
                endTime = None
                portNumber = None
                alarmType = None
                clearReason = None
            }

        :returns SOAP reply object.  If successful, there will be a responseCode of '100'.
        """

        searchQuery = self._client.factory.create('clearAlarmsSearchQuery')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.clearAlarms(searchQuery)
        return CPAPIResponse(response)

    def clearShedState(self, **kwargs):
        """Clears the shed state of given group or station.

        :param sgID (as kwarg): groupID of stations to clear.
        :param stationID (as kwarg): (Optional) ID of individual station to clear.  If this is used, only that station will have
        a cleared shed state, even with the use of sgID.

        :returns SOAP reply object.  If successful, there will be a responseCode of '100'.
        """

        searchQuery = self._client.factory.create('shedQueryInputData')
        if 'stationID' in kwargs.keys():
            setattr(searchQuery, 'shedStation', {'stationID': kwargs['stationID']})
        elif 'sgID' in kwargs.keys():
            setattr(searchQuery, 'shedGroup', {'sgID': kwargs['sgID']})
        else:
            raise Exception('Must have either sgID or stationID as kwarg')

        response = self._soap_service.clearShedState(searchQuery)
        return CPAPIResponse(response)

    def getAlarms(self, **kwargs):
        """Returns any active alarms matching the search query.

        :param **kwargs: any top-level kwarg in the following query.  Most frequently queried via stationID.

        Query:
            (getAlarmsSearchQuery){
                orgID = None
                organizationName = None
                stationID = None
                stationName = None
                sgID = None
                sgName = None
                startTime = None
                endTime = None
                portNumber = None
                startRecord = None
                numTransactions = None
            }

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                Alarms[] =
                    (oalarms){
                        stationID = "1:00001"
                        stationName = "CHARGEPOINT / MAIN 001"
                        stationModel = "CT2100-HD-CCR"
                        orgID = "1:ORG00001"
                        organizationName = "My Organization Name"
                        stationManufacturer = Chargepoint
                        stationSerialNum = "000000000001"
                        portNumber = None
                        alarmType = "Reachable"
                        alarmTime = 2016-12-12 12:34:56+00:00
                        recordNumber = 1
                    },
                    ...
                moreFlag = 0
            }
        """

        searchQuery = self._client.factory.create('getAlarmsSearchQuery')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getAlarms(searchQuery)

        return CPAPIGetAlarmsResponse(response)

    def getCPNInstances(self):
        """Returns ChargePoint network objects.

        Generally not useful expect that it returns the all important CPNID which is needed to construct the orgID,
        described as CPNID:CompanyID.

        For North America, the CPNID is '1'.
        """
        return self._soap_service.getCPNInstances()

    def getChargingSessionData(self, **kwargs):
        """Returns a list of charging sessions based on search query.

        Returns a list of Charging Sessions.  If there are more than 100
        records returned by the query, there will be a MoreFlag return
        value of 1.

        :param **kwargs: any top-level kwarg in the following query.  Most frequently queried via stationID.

        Query:
            (sessionSearchdata){
                stationID = None
                sessionID = None
                stationName = None
                Address = None
                City = None
                State = None
                Country = None
                postalCode = None
                Proximity = None
                proximityUnit = None
                fromTimeStamp = None
                toTimeStamp = None
                startRecord = None
                Geo =
                    (geoData){
                        Lat = None
                        Long = None
                    }
            }

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                ChargingSessionData[] =
                    (sessionSearchResultdata){
                        stationID = "1:00001"
                        stationName = "CHARGEPOINT / MAIN 001"
                        portNumber = "2"
                        Address = "1 Main St, Oakland, California, 94607, United States"
                        City = "Oakland"
                        State = "California"
                        Country = "United States"
                        postalCode = "94607"
                        sessionID = 12345678
                        Energy = 12.345678
                        startTime = 2016-01-01 01:01:01+00:00
                        endTime = 2016-01-01 12:12:02+00:00
                        userID = "123456"
                        recordNumber = 1
                        credentialID = "123456789"
                    },
                    ...
                moreFlag = 0
            }
        """

        searchQuery = self._client.factory.create('sessionSearchdata')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getChargingSessionData(searchQuery)

        return CPAPIGetChargingSessionsResponse(response)

    def getLoad(self, **kwargs):
        """Returns current load of charging station sessions.

        Returns Load on Charging stations/groups as defined by input query. If sgID is not included, many group level
        parameters will be returned as 'None.'

        :param **kwargs: sgID or stationID.

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                numStations = None
                groupName = None
                sgLoad = None
                stationData[] =
                    (stationloaddata){
                        stationID = "1:000013"
                        stationName = "CHARGEPOINT / MAIN 001"
                        Address = "1 Main St, Oakland, California, 94607, United States"
                        stationLoad = 1.1
                        Port[] =
                            (stationPortData){
                                portNumber = "1"
                                userID = None
                                credentialID = None
                                shedState = 0
                                portLoad = 0.0
                                allowedLoad = 0.0
                                percentShed = "0"
                            },
                            (stationPortData){
                                portNumber = "2"
                                userID = "123456"
                                credentialID = "123456789"
                                shedState = 0
                                portLoad = 1.1
                                allowedLoad = 0.0
                                percentShed = "0"
                            },
                    },
                    ...
             }
        """

        # @ToDo: Figure out what type of request searchQuery should be here.
        searchQuery = self._client.factory.create('stationSearchRequestExtended')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getLoad(searchQuery)
        return CPAPIGetLoadResponse(response)

    def getOrgsAndStationGroups(self, **kwargs):
        """Returns orgnaizations and their station groups.

        Get all organization and station group identifiers.

        :param **kwargs: any top-level kwarg in the following query.  Most frequently queried via stationID.

        Query:
            (getOrgsAndStationGroupsSearchQuery){
                orgID = None
                organizationName = None
                sgID = None
                sgName = None
            }

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                orgData[] =
                    (ohostdata){
                        orgID = "1:ORG00001"
                        organizationName = "My Organization Name"
                        sgData[] =
                            (sgData){
                                sgID = 00001
                                sgName = "Main St Garage"
                                parentGroupID = "0"
                            },
                            ...
                    },
                    ...
            }
        """

        searchQuery = self._client.factory.create('getOrgsAndStationGroupsSearchQuery')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getOrgsAndStationGroups(searchQuery)
        return CPAPIResponse(response)

    def getStationGroupDetails(self, sgID, *stationID):
        """Gives details for a given station group.

        :param sgID: groupID of stations to clear.
        :param stationID: (Optional) ID of individual station to clear.  If this is used, only that station will be
        returned in the stationData list.  If this parameter is given, numStations will return 1

        :returns SOAP reply object.  If successful, there will be a responseCode of '100'.

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                groupName = "My Group Name"
                numStations = 1
                stationData[] =
                    (stationGroupData){
                        stationID = "1:00001"
                        stationName = "CHARGEPOINT / MAIN 001"
                        Address = "1 Main St, Oakland, California, 94607, United States"
                    },
                    ...
             }
        """
        if not stationID:
            response = self._soap_service.getStationGroupDetails(sgID)
        else:
            response = self._soap_service.getStationGroupDetails(sgID, stationID)

        return CPAPIResponse(response)

    def getStationGroups(self, orgID):
        """Returns a list of groups and their stations belonging to an organization.

        :param orgID: Chargepoint Organization ID

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                groupData[] =
                    (groupsdata){
                        sgID = 00001
                        orgID = "1:ORG00001"
                        sgName = "Main St Garage"
                        organizationName = "My Organization Name"
                        stationData[] =
                            (stationData){
                                stationID = "1:00001"
                                Geo =
                                    (geoData){
                                        Lat = "12.345678901234567"
                                        Long = "-123.456789012345678"
                                    }
                            },
                            ...
                    },
                    ...
            }
        """

        response = self._soap_service.getStationGroups(orgID)
        return CPAPIResponse(response)

    def getStationRights(self, **kwargs):
        """Returns station rights profiles as defined by the given query parameters.

        It is worth noting that there ay be more than one rights profile for a given station.  A profile defined the
        relationship between a charge station and a group and a charge station may belong to multiple groups.

        :param **kwargs: any top-level kwarg in the following query.  Most frequently queried via stationID.

        Query:
            (stationRightsSearchRequest){
                stationID = None
                stationManufacturer = None
                stationModel = None
                stationName = None
                serialNumber = None
                Address = None
                City = None
                State = None
                Country = None
                postalCode = None
                Proximity = None
                proximityUnit = None
                Connector = None
                Voltage = None
                Current = None
                Power = None
                demoSerialNumber =
                    (serialNumberData){
                        serialNumber[] = <empty>
                    }
                Reservable = None
                Geo =
                    (geoData){
                        Lat = None
                        Long = None
                    }
                Level = None
                Mode = None
                Pricing =
                    (pricingOptions){
                        startTime = None
                        Duration = None
                        energyRequired = None
                        vehiclePower = None
                    }
                orgID = None
                organizationName = None
                sgID = None
                sgName = None
                provisionDateRange =
                    (provisionDateRange){
                        startDate = None
                        endDate = None
                    }
                currentFault = None
                portStatus = None
                adminStatus = None
                networkStatus = None
                provisionStatus = None
                startRecord = None
            }

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                rightsData[] =
                    (rightsData){
                        sgID = "00001"
                        sgName = "Main St Garage"
                        stationRightsProfile = "network_manager"
                        stationData[] =
                            (stationDataRights){
                                stationID = "1:00001"
                                stationName = "CHARGEPOINT / MAIN 001"
                                stationSerialNum = "000000000001"
                                stationMacAddr = "0123:4567:89AB:CDEF"
                            },
                            ...
                    },
                    ...
                moreFlag = 0
            }
        """

        searchQuery = self._client.factory.create('stationRightsSearchRequest')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getStationRights(searchQuery)
        return CPAPIGetStationRightsResponse(response)

    def getStationStatus(self, station):
        """Get port-level charging status for a given station

        :param station: stationID to query

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                stationData[] =
                    (oStatusdata){
                    stationID = "1:00001"
                    Port[] =
                        (portDataStatus){
                            portNumber = "1"
                            Status = "AVAILABLE"
                            TimeStamp = 2016-12-12 12:34:56+00:00
                        },
                        ...
                    },
                    ...
                moreFlag = 0
            }
        """
        response = self._soap_service.getStationStatus({'stationID': station})
        return CPAPIGetStationStatusResponse(response)

    def getStations(self, **kwargs):
        """Returns a list of Chargepoint Stations based on keyword query args

        It is worth noting that only stations the client has access to will be returned.

        :param **kwargs: any top-level kwarg in the following query.  Most frequently queried via stationID.

        Query:
            (stationSearchRequestExtended){
                stationID = None
                stationManufacturer = None
                stationModel = None
                stationName = None
                serialNumber = None
                Address = None
                City = None
                State = None
                Country = None
                postalCode = None
                Proximity = None
                proximityUnit = None
                Connector = None
                Voltage = None
                Current = None
                Power = None
                demoSerialNumber =
                    (serialNumberData){
                        serialNumber[] = <empty>
                    }
                Reservable = None
                Geo =
                    (geoData){
                        Lat = None
                        Long = None
                    }
                Level = None
                Mode = None
                Pricing =
                    (pricingOptions){
                        startTime = None
                        Duration = None
                        energyRequired = None
                        vehiclePower = None
                    }
                orgID = None
                organizationName = None
                sgID = None
                sgName = None
                stationActivationDate = None
                startRecord = None
                numStations = None
            }

        Reply:
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                stationData[] =
                    (stationDataExtended){
                        stationID = "1:00001"
                        stationManufacturer = "ChargePoint"
                        stationModel = "CT2100-HD-CCR"
                        stationMacAddr = "0123:4567:89AB:CDEF"
                        stationSerialNum = "000000000001"
                        stationActivationDate = 2016-01-01 12:23:45
                        Address = "1 Main St "
                        City = "Oakland"
                        State = "California"
                        Country = "United States"
                        postalCode = "94607"
                        Port[] =
                            (portData){
                                portNumber = "1"
                                stationName = "CHARGEPOINT / MAIN 001"
                                Geo =
                                    (geoData){
                                        Lat = "12.345678901234567"
                                        Long = "-123.456789012345678"
                                    }
                                Description = "Use garage entrance on Main St., turn right and follow ...
                                Reservable = 0
                                Level = "L1"
                                Connector = "NEMA 5-20R"
                                Voltage = "120"
                                Current = "16"
                                Power = "1.920"
                                estimatedCost = 0.0
                            },
                            ...
                        Pricing[] =
                            (pricingSpecification){
                                Type = "None"
                                startTime = 00:00:00
                                endTime = 23:59:59
                                minPrice = 0.0
                                maxPrice = 0.0
                                unitPricePerHour = 0.0
                                unitPricePerSession = 1.0
                                unitPricePerKWh = 0.2
                            },
                        numPorts = 2
                        mainPhone = "1-888-123-4567"
                        currencyCode = "USD"
                        orgID = "1:ORG00001"
                        organizationName = "My Organization Name"
                        sgID = "00001, 00002, 00003, 00004, 00005, 00006, 00007, 00008, 00009, ...
                        sgName = "Main St Garage, Public Garages, California Stations, ...
                    },
                    ...
                moreFlag = 0
            }
        """
        searchQuery = self._client.factory.create('stationSearchRequestExtended')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getStations(searchQuery)
        return CPAPIGetStationsResponse(response)

    def getUsers(self, **kwargs):
        """Returns a list of Users as defined by the given query parameters

        :param **kwargs: any top-level kwarg in the following query. Most frequently queried via userID or credentialID.

        Query:
            (getUsersSearchRequest){
                userID = None
                firstName = None
                lastName = None
                lastModifiedTimeStamp = None
                Connection =
                    (connectionDataRequest){
                        Status =
                            (connectedUserStatusTypes){
                                value = None
                            }
                        customInfo =
                            (customInfoData){
                                Key = None
                                Value = None
                            }
                    }
                managementRealm =
                    (managementRealmRequest){
                        Status =
                            (managedUserStatusTypes){
                                value = None
                            }
                        customInfo =
                            (customInfoData){
                                Key = None
                                Value = None
                            }
                    }
                credentialID = None
                startRecord = None
                numUsers = None
            }

        Reply
            (reply){
                responseCode = "100"
                responseText = "API input request executed successfully."
                users =
                    (userParams){
                        user[] =
                            (userData){
                                lastModifiedTimestamp = 2016-11-11 01:23:45+00:00
                                userID = "123456"
                                firstName = "John"
                                lastName = "Doe"
                                Connection =
                                    (connectionData){
                                        Status = "APPROVED"
                                        requestTimeStamp = 2016-11-11 01:23:45+00:00
                                        customInfos =
                                            (customInfosData){
                                                customInfo[] =
                                                    (customInfoData){
                                                        Key = "Custom Key"
                                                        Value = "Custom Value"
                                                    },
                                                    ...
                                            }
                                    }
                                managementRealm = ""
                                credentialIDs =
                                    (credentialIDsData){
                                        credentialID[] =
                                            "123456789",
                                            ...
                                    }
                                recordNumber = 1
                            },
                            ...
                        moreFlag = 0
                    }
            }
        """

        searchQuery = self._client.factory.create('getUsersSearchRequest')
        for k, v in kwargs.items():
            setattr(searchQuery, k, v)
        response = self._soap_service.getUsers(searchQuery)
        return CPAPIResponse(response)

    def shedLoad(self, **kwargs):
        """Reduce load on a Charegepoint station.

        Main functionality for reducing load on a chargepoint station. Can pass either allowedLoadPerStation OR
        percentShedPerStation, but not both (one must be None).

        :param **kwargs: Input parameters for shedding load.  One of allowedLoadPerStation and percentshedPerStation
        must be included.

        Query:
            (shedLoadQueryInputData){
                shedGroup =
                    (shedLoadGroupInputData){
                        sgID = None
                        allowedLoadPerStation = None
                        percentShedPerStation = None
                    }
                shedStation =
                    (shedLoadStationInputData){
                        stationID = None
                        allowedLoadPerStation = None
                        percentShedPerStation = None
                        Ports =
                            (Ports){
                                Port[] = <empty>
                            }
                    }
                timeInterval = None
            }

        :returns SOAP reply object.  If successful, there will be a responseCode of '100'.
        """
        searchQuery = self._client.factory.create('shedLoadQueryInputData')
        port = kwargs.pop('portNumber', None)
        query_params = {'stationID': kwargs['stationID']}
        if port:
            port_params = {'allowedLoadPerPort': kwargs.pop('allowedLoad', None),
                           'percentShedPerPort': kwargs.pop('percentShed', None),
                           'portNumber': port}
            query_params['Ports'] = {'Port': [port_params]}
        else:
            query_params['allowedLoadPerStation'] = kwargs.pop('allowedLoad', None)
            query_params['percentShedPerStation'] = kwargs.pop('percentShed', None)
        setattr(searchQuery, 'shedStation', query_params)
        response = self._soap_service.shedLoad(searchQuery)
        return CPAPIResponse(response)

    def dump_methods_and_datatypes(self):
        """Debugging tool.  Prints out the SOAP methods and datatypes."""

        print(self._client)
