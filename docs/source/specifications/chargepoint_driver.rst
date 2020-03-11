.. _Chargepoint-Driver:

Chargepoint API Driver
======================

Spec Version 1.1

`ChargePoint <http://www.chargepoint.com>`_ operates the largest independently owned EV charging network in the US.
It sells charge stations to businesses and provides a web application to manage and report on these chargestations.
Chargepoint offers a `Web Services API <https://na.chargepoint.com/UI/downloads/en/ChargePoint_Web_Services_API_Guide_Ver4.1_Rev4.pdf>`_
that its customers may use to develop applications that integrate with the chargepoint network devices.

The Chargepoint API Driver for VOLTTRON will enable real-time monitoring and control of Chargepoint EVSEs within
the VOLTTRON platform by creating a standard VOLTTRON device driver on top of the Chargepoint Web Services API.
Each port on each managed chargestation will look like a standard VOLTTRON device, monitored and controlled through
the VOLTTRON device driver interface.


Driver Scope & Functions
------------------------

This driver will enable VOLTTRON to support the following use cases with Chargepoint EVSEs:

    - Monitoring of chargestation status, load and energy consumption
    - Demand charge reduction
    - Time shifted charging
    - Demand response program participation

The data and functionality to be made available through the driver interface will be implemented using the
following Chargepoint web services:


================================ ====================================================================
API Method Name                   Key Data/Function Provided
================================ ====================================================================
getStationStatus                  Port status: AVAILABLE, INUSE, UNREACHABLE, UNKNOWN
shedLoad                          Limit station power by percent or max load for some time period.
clearShedState                    Clear all shed state and allow normal charging
getLoad                           Port load in Kw, shedState, allowedLoad, percentShed
getAlarms                         Only the last alarm will be available.
clearAlarms                       Clear all alarms.
getStationRights                  Name of station rights profile, eg. 'network_manager'
getChargingSessionData            Energy used in last session, start/end timestamps
getStations                       Returns description/address/nameplate of chargestation.
================================ ====================================================================

The Chargepoint Driver will implement version 5.0 Rev 7 of the Chargepoint API.  While the developer's guide
is not yet publicly available, the WSDL Schema is.
*Note: Station Reservation API has been removed from the 5.0 version of the API.*

WSDL for this API is located here:

    https://webservices.chargepoint.com/cp_api_5.0.wsdl


Mapping VOLTTRON Device Interface to Chargepoint APIs
-----------------------------------------------------

The VOLTTRON driver interface represents a single device as a list of registers accessed through a simple get_point/
set_point API.  In contrast, the Chargepoint web services for real-time monitoring and control are spread across
eight distinct APIs that return hierarchical XML.  The Chargepoint driver is the adaptor that will make a suite
of web services look like a single VOLTTRON device.



Device Mapping
^^^^^^^^^^^^^^

The chargepoint driver will map a single VOLTTRON device (a driver instance) to one chargestation. Since
a chargestation can have multiple ports, each with their own set of telemetry, the registry will include a port
index column on attributes that are specific to a port.  This will allow deployments to use an indexing convention
that has been followed with other drivers. (See Registry Configuration for more details)

Requirements
------------

The chargepoint driver requires at least one additional python library and has its own ``requirements.txt``.
Make sure to run

::

    pip install -r <chargepoint driver path>/requirements.txt

before using this driver.

Driver Configuration
--------------------

Each device must be configured with its own Driver Configuration File.  The Driver Configuration must reference
the Registry Configuration File, defining the set of points that will be available from the device.  For
chargestation devices, the ``driver_config`` entry of the Driver Configuration file will need to contain all
parameters required by the web service API:


======================= ==========================================================================
Parameter               Purpose
======================= ==========================================================================
username                 Credentials established through Chargepoint account
password
stationID                Unique station ID assigned by chargepoint
======================= ==========================================================================

The ``driver_type`` must be ``chargepoint``

 A sample driver configuration file for a single device, looks like this:

.. code-block:: json

    {
        "driver_config": {
            "username"   : "1b905c936af141b98f9b0f816087f3605a30c1df1d07f146281b151",
            "password"   : "**Put your chargepoint API passqword here**",
            "stationID"  : "1:34003",
        },
        "driver_type": "chargepoint",
        "registry_config":"config://chargepoint.csv",
        "interval": 60,
        "heart_beat_point": "heartbeat"
    }



API Plans & Access Rights
^^^^^^^^^^^^^^^^^^^^^^^^^

Chargepoint offers API plans that vary in available features and access rights.  Some of the API calls
to be implemented here are not available across all plans.  Furthermore, the attributes returned in response
to an API call may be limited by the API plan and access rights associated with the userid.  Runtime
exceptions related to plans and access rights will generate DriverInterfaceError exceptions.  These can be
avoided by using a registry configuration that does not include APIs or attributes that are not
available to the <username>.


Registry Configuration
----------------------

The registry file defines the individual points that will be exposed by the Chargepoint driver.  It should only
reference points that will actually be used since each point is potentially an additional web service call.  The driver
will be smart and limit API calls to those that are required to satisfy the points found in the CSV.

Naming of points will conform to the conventions established by the Chargepoint Web services API whenever possible.
Note that Chargepoint naming conventions are camel-cased with no spaces or hyphens.  Multi-word names start
with a lowercase letter.  Single word names start uppercase.

The available registry entries for each API method name are shown below along with a description of any
notable behavior associated with that register.  Following that is a sample of the
associated XML returned by the API.


getStationStatus
^^^^^^^^^^^^^^^^

The getStationStatus query returns information for all ports on the chargestation.

.. note::

    In all the registry entries shown below, the **Attribute Name** column defines the unique name within the
    chargepoint driver that must be used to reference this particular attribute and associated API. The
    **VOLTTRON point name** usually matches the **Attribute Name** in these examples but may be changed during deployment.


.. csv-table:: getStationStatus
    :header: Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes

    Status,Status,StationStatusRegister,1,string,,,FALSE,"AVAILABLE, INUSE, UNREACHABLE, UNKNOWN "
    Status.TimeStamp,TimeStamp,StationStatusRegister,1,datetime,,,FALSE,Timestamp of the last communication between the station and ChargePoint

Sample XML returned by getStationStatus.

.. code-block:: xml

    <ns1:getStationStatusResponse xmlns:ns1="urn:dictionary:com.chargepoint.webservices">
        <responseCode>100</responseCode>
        <responseText>API input request executed successfully.</responseText>
        <stationData>
            <stationID>1:33923</stationID>
            <Port>
                <portNumber>1</portNumber>
                <Status>AVAILABLE</Status>
                <TimeStamp>2016-11-07T19:19:19Z</TimeStamp>
            </Port>
            <Port>
                <portNumber>2</portNumber>
                <Status>INUSE</Status>
                <TimeStamp>2016-11-07T19:19:19Z</TimeStamp>
            </Port>
        </stationData>
        <moreFlag>0</moreFlag>
    </ns1:getStationStatusResponse>


getLoad, shedLoad, clearShedState
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Reading any of these values will return the result of a call to getLoad.  Writing shedState=True will call
shedLoad and pass the last written value of allowedLoad or percentShed.  The API allows only one of these
two values to be provided.  Writing to allowedLoad will simultaneously set percentShed to None and vice
versa.

.. csv-table:: getLoad, shedLoad, clearShedState
    :header: Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes

    shedState,shedState,LoadRegister,1,integer,0 or 1,0,TRUE,True when load shed limits are in place
    portLoad,portLoad,LoadRegister,1,float,kw,,FALSE,Load in kw
    allowedLoad,allowedLoad,LoadRegister,1,float,kw,,TRUE,Allowed load in kw when shedState is True
    percentShed,percentShed,LoadRegister,1,integer,percent,,TRUE,Percent of max power shed when shedState is True

Sample XML returned by getLoad

.. code-block:: xml

    <ns1:getLoadResponse xmlns:ns1="urn:dictionary:com.chargepoint.webservices">
        <responseCode>100</responseCode>
        <responseText>API input request executed successfully.</responseText>
        <numStations></numStations>
        <groupName></groupName>
        <sgLoad></sgLoad>
        <stationData>
            <stationID>1:33923</stationID>
            <stationName>ALCOGARSTATIONS / ALCOPARK 8 -005</stationName><Address>165 13th St, Oakland, California,  94612, United States</Address>
            <stationLoad>3.314</stationLoad>
            <Port>
                <portNumber>1</portNumber>
                <userID></userID>
                <credentialID></credentialID>
                <shedState>0</shedState>
                <portLoad>0.000</portLoad>
                <allowedLoad>0.000</allowedLoad>
                <percentShed>0</percentShed>
            </Port>
            <Port>
                <portNumber>2</portNumber>
                <userID>664719</userID>
                <credentialID>CNCP0000481668</credentialID>
                <shedState>0</shedState>
                <portLoad>3.314</portLoad>
                <allowedLoad>0.000</allowedLoad>
                <percentShed>0</percentShed>
            </Port>
        </stationData>
    </ns1:getLoadResponse>

Sample shedLoad XML query to set the allowed load on a port to 3.0kw.

.. code-block:: xml

 <ns1:shedLoad>
      <shedQuery>
        <shedStation>
          <stationID>1:123456</stationID>
          <Ports>
            <Port>
              <portNumber>1</portNumber>
              <allowedLoadPerPort>3.0</allowedLoadPerPort>
            </Port>
          </Ports>
        </shedStation>
        <timeInterval/>
      </shedQuery>
    </ns1:shedLoad>


getAlarms, clearAlarms
^^^^^^^^^^^^^^^^^^^^^^

The getAlarms query returns a list of all alarms since last cleared.  The driver interface will only return
data for the most recent alarm, if present.  While the getAlarm query provides various station identifying
attributes, these will be made available through registers associated with the getStations API.  If an alarm is
not specific to a particular port, it will be associated with all chargestation ports and available through any
of its device instances.

Write ``True`` to clearAlarms to submit the clearAlarms query to the **chargestation**.  It will clear alarms
across all ports on that chargestation.


.. csv-table:: getAlarms, clearAlarms
    :header: Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes

    alarmType,alarmType,AlarmRegister,,string,,,FALSE,eg. 'GFCI Trip'
    alarmTime,alarmTime,AlarmRegister,,datetime,,,FALSE,
    clearAlarms,clearAlarms,AlarmRegister,,int,,0,TRUE,Sends the clearAlarms query when set to True


.. code-block:: xml

    <Alarms>
        <stationID>1:33973</stationID>
        <stationName>ALCOGARSTATIONS / ALCOPARK 8 -003</stationName>
        <stationModel>CT2100-HD-CCR</stationModel>
        <orgID>1:ORG07225</orgID>
        <organizationName>Alameda County</organizationName>
        <stationManufacturer></stationManufacturer>
        <stationSerialNum>115110013418</stationSerialNum>
        <portNumber></portNumber>
        <alarmType>Reachable</alarmType>
        <alarmTime>2016-09-26T12:19:16Z</alarmTime>
        <recordNumber>1</recordNumber>
    </Alarms>


getStationRights
^^^^^^^^^^^^^^^^

Returns the name of the stations rights profile.  A station may have multiple station rights profiles, each associated
with a different station group ID.  For this reason, the stationRightsProfile register will return a dictionary of
(sgID, name) pairs.  Since this is a chargestation level attribute, it will be returned for all ports.


.. csv-table:: getStationRights
    :header: Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes

    stationRightsProfile,stationRightsProfile,StationRightsRegister,,dictionary,,,FALSE,"Dictionary of sgID, rights name tuples."



.. code-block:: xml

    <rightsData>
        <sgID>39491</sgID>
        <sgName>AlcoPark 8</sgName>
        <stationRightsProfile>network_manager</stationRightsProfile>
        <stationData>
            <stationID>1:34003</stationID>
            <stationName>ALCOGARSTATIONS / ALCOPARK 8 -004</stationName>
            <stationSerialNum>115110013369</stationSerialNum>
            <stationMacAddr>000D:6F00:0154:F1FC</stationMacAddr>
        </stationData>
    </rightsData>
    <rightsData>
        <sgID>58279</sgID>
        <sgName>AlcoGarageStations</sgName>
        <stationRightsProfile>network_manager</stationRightsProfile>
        <stationData>
            <stationID>1:34003</stationID>
            <stationName>ALCOGARSTATIONS / ALCOPARK 8 -004</stationName>
            <stationSerialNum>115110013369</stationSerialNum>
            <stationMacAddr>000D:6F00:0154:F1FC</stationMacAddr>
        </stationData>
    </rightsData>


getChargingSessionData
^^^^^^^^^^^^^^^^^^^^^^

Like getAlarms, this query returns a list of session data.  The driver interface implementation will make the
last session data available.

.. csv-table:: getChargingSessionData
    :header: Volttron Point Name,Attribute Name,Register Name,Port #,Type,Units,Starting Value,Writable,Notes

    sessionID,sessionID,ChargingSessionRegister,1,string,,,FALSE,
    startTime,startTime,ChargingSessionRegister,1,datetime,,,FALSE,
    endTime,endTime,ChargingSessionRegister,1,datetime,,,FALSE,
    Energy,Energy,ChargingSessionRegister,1,float,,,FALSE,
    rfidSerialNumber,rfidSerialNumber,ChargingSessionRegister,1,string,,,FALSE,
    driverAccountNumber,driverAccountNumber,ChargingSessionRegister,1,string,,,FALSE,
    driverName,driverName,ChargingSessionRegister,1,string,,,FALSE,

.. code-block:: xml

    <ChargingSessionData>
        <stationID>1:34003</stationID>
        <stationName>ALCOGARSTATIONS / ALCOPARK 8 -004</stationName>
        <portNumber>2</portNumber>
        <Address>165 13th St, Oakland, California, 94612, United States</Address>
        <City>Oakland</City>
        <State>California</State>
        <Country>United States</Country>
        <postalCode>94612</postalCode>
        <sessionID>53068029</sessionID>
        <Energy>12.120572</Energy>
        <startTime>2016-10-25T15:53:35Z</startTime>
        <endTime>2016-10-25T20:14:46Z</endTime>
        <userID>452777</userID>
        <recordNumber>1</recordNumber>
        <credentialID>490178743</credentialID>
    </ChargingSessionData>


getStations
^^^^^^^^^^^

This API call returns a complete description of the chargestation in 40 fields.  This information is essentially
static and will change infrequently.  It should not be scraped on a regular basis.  The list of attributes will be
included in the registry CSV but are only listed here:

.. code-block:: text

    stationID, stationManufacturer, stationModel, portNUmber, stationName, stationMacAddr, stationSerialNum, Address, City,
    State, Country, postalCode, Lat, Long, Reservable, Level, Mode, Connector, Voltage, Current, Power, numPorts, Type,
    startTime, endTime, minPrice, maxPrice, unitPricePerHour, unitPricePerSession, unitPricePerKWh, unitPricePerHourThereafter,
    sessionTime, Description, mainPhone, orgID, organizationName, sgID, sgName, currencyCode


Engineering Discussion
----------------------


Questions
^^^^^^^^^

    - **Allowed python-type** - We propose a register with a `python-type` of dictionary.  Is this OK?
    - **Scrape Interval** - Scrape all should not return all registers defined in the CSV, we propose fine grained control with a scrape-interval on each register. Response: ok to add extra settings to registry but don't worry about pubishing static data with every scrape
    - **Data currency** - Since devices are likely to share api calls, at least across ports, we need to think about the currency of the data and possibly allowing this to be a configurable parameter or derviced from the scrape interval. Response: add to CSV with default values if not present



Performance
^^^^^^^^^^^
Web service calls across the internet will be significantly slower than typical VOLTTRON Bacnet or Modbus devices.  It
may be prohibitively expensive for each chargepoint sub-agent instance to make individual requests on behalf of
its own EVSE+port.  We will need to examine the possibility of making a single request for all active chargestations
and sharing that information across driver instances.  This could be done through a separate agent that regularly
queries the chargepoint network and makes the data available to each sub-agent via an RPC call.


3rd Party Library Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The chargepoint driver implementation will depend on one additional 3rd part library that is not part of a standard
VOLTTRON installation:

..

    https://bitbucket.org/jurko/suds


Is there a mechanism for drivers to specify their own requirements.txt ?

Driver installation and configuration documentation can reference requirement.txt


