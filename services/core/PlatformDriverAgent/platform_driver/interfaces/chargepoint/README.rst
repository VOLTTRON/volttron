.. _Chargepoint-Driver:

Chargepoint Driver README
=========================

Version 1.0

Requirements
------------
The Chargepoint driver Python requirements can be installed by running the following in an
activated environment:

::

    pip install suds-jurko

Alternatively requirements can be installed from requirements.txt using:

::

    pip install -r requirements.txt

Write Points
------------

For any write of an attribute, it will return a read value of the attribute. This can produce some weird results.
For example, clear alarms can only be written to, not read, so a set_value call will return None. Because any write to
an attribute must go first to the Chargepoint Cloud, then propagate to the Chargepoint station, any calls to set or
clear load sheds will also take time to resolve. A write to these attributes will most likely return the previous value
before the call was accepted.

This is further explained in sections regarding the specific drivers. However, each write point is very particular in
its use cases. To set a load shed, the points allowedLoad or percentShed must be written to. These may or may not have a
port associated with them. To clear a load shed however, a value of 0 must be written to the shedLoad attribute. While
shedLoad should be associated with a port, due to API limitations, only an entire station may be cleared at a time. So if
a user wishes to only clear one port of a chargepoint station, they must subsequently reapply the loadShed to the other
point on the Chargepoint station as it will be cleared as well as the desired port.


Driver Config
-------------
The driver config dictionary must have three entries.

- stationID: This is the ID for the Chargepoint Station of the Driver.  It is in the format "1:00001"
- username: This is the username to be used for the Chargepoint API Service.
- password: This is the password to be used for the Chargepoint API Service.
- cacheExpiration: This is how many seconds any API responses will be cached. Cached responses limit traffic to
  Chargepoint API services.

CSV Config
----------

Column Values
-------------
======================= ======================================================================================
Column Header           Column Description
======================= ======================================================================================
Volttron Point Name     Point name as defined by VOLTTRON. By default, this is the same as the attribute name.
Attribute Name          Syntactically correct name of point value. This ensures correct API calls.
Port #                  If the point describes a specific port on the Chargestation, it is defined here. (Note
                        0 and an empty value are equivalent.)
Type                    Python type of the value of this point.
Units                   Description for meta-data of applicable units/values for this point.
Writable                True/False whether or not the point is read/write or read-only.
Notes                   Description of the point purpose.
Register Name           Which subclass of ChargepointRegister this point belongs to.
Starting Value          Default value for writeable points.
======================= ======================================================================================

Configurable Points
-------------------

StationRegister
---------------
All attributes here are returned from the getStations Chargepoint API call.  None of the attributes are writeable.
Note that some attributes are station level, while some are port level. Attributes that are defined as station level
cannot have a port defined. Similarly, attributes that are defined as port level MUST have a port defined.

stationID
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationID
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   ID
Writable                False
Notes                   Expected format is 1:00001
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

stationManufacturer
^^^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationManufacturer
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   Value is typically Chargepoint
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

stationModel
^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationModel
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   Value of Chargepoint station model
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

portNumber
^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          portNumber
Port #                  1 or 2
Type                    int
Units                   1 or 2
Writable                False
Notes                   Describes which port number is being referenced. Chargepoint stations typically have
                        up to two ports.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

stationName
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationName
Port #                  1 or 2 (Chargepoint defines this as a port-level attribute)
Type                    string
Units                   N/A
Writable                False
Notes                   Name of station in Chargepoint. This is for some reason defined as a port-level
                        attribute so a port must be defined to access the information.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

stationMacAddr
^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationMacAddr
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   MAC address
Writable                False
Notes                   Typical MAC address format is 1234:5678:90AB:CDEF
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

stationSerialNum
^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationSerialNum
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   ID
Writable                False
Notes                   Serial number of Chargepoint station.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Address
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Address
Port #                  N/A (Must be empty or 0)
Type                    int
Units                   N/A
Writable                False
Notes                   Address where Chargepoint station is located
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

City
^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          City
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   City where Chargepoint station is located
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

State
^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          State
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   State where Chargepoint station is located
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Country
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Country
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   Country where Chargepoint station is located
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

postalCode
^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          postalCode
Port #                  N/A (Must be empty or 0)
Type                    int
Units                   N/A
Writable                False
Notes                   Postal Code where Chargepoint station is located
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Lat
^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Lat
Port #                  1 or 2 (Chargepoint defines geographic location as a port-level attribute)
Type                    float
Units                   Latitudinal coordinates
Writable                False
Notes                   Latitude of Chargepoint station. This is for some reason defined as a port-level
                        attribute so a port must be defined to access the information.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Long
^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Long
Port #                  1 or 2 (Chargepoint defines geographic location as a port-level attribute)
Type                    float
Units                   Longitudinal coordinates
Writable                False
Notes                   Longitude of Chargepoint station. This is for some reason defined as a port-level
                        attribute so a port must be defined to access the information.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Reservable
^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Reservable
Port #                  1 or 2
Type                    bool
Units                   True or False
Writable                False
Notes                   Flag indicating whether the charging port can be reserved through Chargepoint
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Level
^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Level
Port #                  1 or 2
Type                    string
Units                   L1, L2, L3
Writable                False
Notes                   Level of the charging port. This is for US stations only. Outside of the US, use Mode.
                        If Level is defined, Mode will most likely not be.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Mode
^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Mode
Port #                  1 or 2
Type                    int
Units                   1, 2, 3
Writable                False
Notes                   Mode of the charging port. This is for outside the US only. US stations, use Level. If
                        mode is defined, Level will most likely not be.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Voltage
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Voltage
Port #                  1 or 2
Type                    float
Units                   Volts
Writable                False
Notes                   Configured voltage for the charging port
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Current
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Current
Port #                  1 or 2
Type                    float
Units                   Amps
Writable                False
Notes                   Configured current for the charging port
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Power
^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Power
Port #                  1 or 2
Type                    float
Units                   kW
Writable                False
Notes                   Configured power for the charging port
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Connector
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Connector
Port #                  1 or 2
Type                    string
Units                   N/A
Writable                False
Notes                   Type of connector that the charging port uses
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

numPorts
^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          numPorts
Port #                  N/A (Must be empty or 0)
Type                    int
Units                   Number
Writable                False
Notes                   Number of ports configured for a charging station. This is almost always 2.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Type
^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Type
Port #                  N/A (Must be empty or 0)
Type                    int
Units                   Enum
Writable                False
Notes                   Either None, 1, 2, or 3. Indicating Session, Hourly, or kWh style pricing.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

startTime
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          startTime
Port #                  N/A (Must be empty or 0)
Type                    datetime
Units                   timestamp
Writable                False
Notes                   Time pricing session started
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

endTime
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          endTime
Port #                  N/A (Must be empty or 0)
Type                    datetime
Units                   timestamp
Writable                False
Notes                   Time pricing session ended
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

minPrice
^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          minPrice
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Minimum price charged for a session
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

maxPrice
^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          maxPrice
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Maximum price charged for a session
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

unitPricePerHour
^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          unitPricePerHour
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Hourly price of a charging session. If this kind of pricing is not configured, this
                        attribute will not be defined.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

unitPricePerSession
^^^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          unitPricePerSession
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Session price of a charging session. If this kind of pricing is not configured, this
                        attribute will not be defined.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

unitPricePerKWh
^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          unitPricePerKWh
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Price per kWh used in a charging session. If this kind of pricing is not configured,
                        this attribute will not be defined.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

unitPriceForFirst
^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          unitPriceForFirst
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Hourly price for first portion of timed charging. If this kind of pricing is not
                        configured, this attribute will not be defined.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

unitPricePerHourThereafter
^^^^^^^^^^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          unitPricePerHourThereafter
Port #                  N/A (Must be empty or 0)
Type                    float
Units                   Currency
Writable                False
Notes                   Hourly price for second portion of timed charging. If this kind of pricing is not
                        configured, this attribute will not be defined.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

sessionTime
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          sessionTime
Port #                  N/A (Must be empty or 0)
Type                    time
Units                   Amount of time
Writable                False
Notes                   Amount of time a charging session is allowed to be active.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

Description
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Description
Port #                  1 or 2 (Chargepoint defines station description as a port-level attribute)
Type                    datetime
Units                   N/A
Writable                False
Notes                   Desription of the charging station (or port). Chargepoint has this defined at the port
                        level.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

mainPhone
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          mainPhone
Port #                  N/A (Must be empty or 0)
Type                    datetime
Units                   Phone number
Writable                False
Notes                   Main support telephone number for drivers.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

orgID
^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          orgID
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   ID
Writable                False
Notes                   Organization ID within Chargepoint
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

organizationName
^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          organizationName
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   N/A
Writable                False
Notes                   Name of organization
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

sgID
^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          sgID
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   IDs
Writable                False
Notes                   List of all Chargepoint groups that the station belongs to.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

sgName
^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          sgName
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   Names
Writable                False
Notes                   List of all Chargepoint group names that the station belongs to.
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

currencyCode
^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          currencyCode
Port #                  N/A (Must be empty or 0)
Type                    string
Units                   Currency Code
Writable                False
Notes                   For the US, this is USD
Register Name           StationRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

StationStatusRegister
---------------------
All attributes here are returned from the getStationStatus Chargepoint API call. None of the attributes are
writeable. Note that all attributes are port level and MUST have a port defined.

Status
^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Status
Port #                  1 or 2
Type                    string
Units                   AVAILABLE, INUSE, UNREACHABLE, UNKNOWN
Writable                False
Notes                   Status of a given port.
Register Name           StationStatusRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

TimeStamp
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          TimeStamp
Port #                  1 or 2
Type                    datetime
Units                   Timestamp
Writable                False
Notes                   Timestamp of when the station last recorded the status of the given port.
Register Name           StationStatusRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

LoadRegister
------------
All attributes here are returned from the getLoad Chargepoint API call. Of the 4 attributes, only portLoad is
read-only. To clear any restrictions on charging, a value of 0 should be written to shedState. This will set
both allowedLoad and percentShed to None. Writing a value of 1 to shedState is not allowed. Instead, a value
should be written to either allowedLoad or percentShed.

Only one type of load shed can take place at a time. If there is a write to allowedLoad, a write of 0 to shedState
must occur before a write to percentShed will be accepted. This applies in the reverse as well: a write to shedState
must occur between a write to percentShed and a write to allowedLoad.

For allowedLoad and percentShed, a defined port is optional. If no port is defined, the
load shed (or clear) will happen at the station level. If a port is defined, the load shed will happen at the port
level. For a read of shedState to occur, it must have a defined port.  A write to shedState, regardless of port status,
will result in the shedState being cleared for the entire Chargepoint station.

shedState
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          shedState
Port #                  0, 1, or 2
Type                    int
Units                   0 or 1
Writable                True
Notes                   0 is the only value this register accepts as a write value.
Register Name           LoadRegister
Starting Value          0
======================= ======================================================================================

portLoad
^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          portLoad
Port #                  1 or 2
Type                    float
Units                   kW
Writable                False
Notes                   Current load on port.
Register Name           LoadRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

allowedLoad
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          allowedLoad
Port #                  0, 1, or 2
Type                    float
Units                   kW
Writable                True
Notes                   Max load allowed on a station (or port)
Register Name           LoadRegister
Starting Value
======================= ======================================================================================

percentShed
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          percentShed
Port #                  0, 1, or 2
Type                    float
Units                   Percent
Writable                True
Notes                   Percent of present power output to be shed. Can be defined at the station or port
                        level
Register Name           LoadRegister
Starting Value
======================= ======================================================================================

AlarmRegister
-------------
alarmType and alarmTime are returned from the getAlarms Chargepoint API call.  clearAlarms is a bit of an anomaly
as it is not a returned register in any Chargepoint API call. Any attempt to read clearAlarms will result in a
null value returned. A write value of 1 to clearAlarms will clear any alarms associated with the given Chargepoint
station.

All three registers can be defined at the port or station level. If defined at the port level, only alarms associated
with the given port will be read (or cleared). If defined at the station level, all alarms will be read (or cleared).

Both alarmType and alarmTime will only return the most recent alarm associated with the Chargepoint station (or port).

For both reading or writing to these registers, if no alarms are present, Chargepoint will return a different error
code (153). In the case of register read, this will result in a None value being read, and a log message indicating
that the attribute was not found.

alarmType
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          alarmType
Port #                  0, 1, or 2
Type                    string
Units                   N/A
Writable                False
Notes                   Description of most recent alarm.
Register Name           AlarmRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

alarmTime
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          alarmTime
Port #                  0, 1, or 2
Type                    datetime
Units                   Timestamp
Writable                False
Notes                   Timestamp of most recent alarm.
Register Name           AlarmRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

clearAlarms
^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          clearAlarms
Port #                  0, 1, or 2
Type                    int
Units                   0 or 1
Writable                True
Notes                   Write a value of 1 to clear all alarms associated with the Station (or port).
Register Name           AlarmRegister
Starting Value          0
======================= ======================================================================================

StationRightsRegister
---------------------
stationRightsProfile is returned from the getStationRights Chargepoint API call. This is a unique point in that it
returns an entire dictionary. The dictionary is keyed by sgID, with one entry for every station group that the
Chargepoint station belongs to. For stations that belong to many groups, this can be quite lengthy. The value of each
key/value pair is a pythonic representation of the SOAP object describing the entire rights profile returned
from the API call. This attribute is not writeable

stationRightsProfile
^^^^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          stationRightsProfile
Port #                  N/A (Must be empty or 0)
Type                    dictionary
Units                   N/A
Writable                False
Notes                   Lengthy dictionary describing rights profiles for every group to which a station belongs.
Register Name           StationRightsRegister
Starting Value          0
======================= ======================================================================================

ChargingSessionRegister
-----------------------
All attributes here are returned from the getChargingSessionData Chargepoint API call.  None of the attributes are
writeable. This would ideally be given via port granularity, but due to current Chargepoint API restrictions, all
data points are currently limited to the most recent charging session on port 1. A port may be defined in the CSV
file, but it will be ignored.

sessionID
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          sessionID
Port #                  0, 1, or 2
Type                    string
Units                   ID
Writable                False
Notes                   ID of most recent charging session (on port 1)
Register Name           ChargingSessionRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

startTime
^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          startTime
Port #                  0, 1, or 2
Type                    datetime
Units                   Timestamp
Writable                False
Notes                   Timestamp of the start time of the most recent charging session (on port 1)
Register Name           ChargingSessionRegister
Starting Value
======================= ======================================================================================

endTime
^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          endTime
Port #                  0, 1, or 2
Type                    datetime
Units                   Timestamp
Writable                False
Notes                   Timestamp of the end time of the most recent charging session (on port 1)
Register Name           ChargingSessionRegister
Starting Value
======================= ======================================================================================

Energy
^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          Energy
Port #                  0, 1, or 2
Type                    float
Units                   kWh
Writable                False
Notes                   kWh consumed during most recent charging session (on port 1)
Register Name           ChargingSessionRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

rfidSerialNumber
^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          rfidSerialNumber
Port #                  0, 1, or 2
Type                    string
Units                   ID
Writable                False
Notes                   Serial # representing the RFID card used for the most recent charging session (on port 1). This
                        may not be applicable if a RFID card was not used.
Register Name           ChargingSessionRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

driverAccountNumber
^^^^^^^^^^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          driverAccountNumber
Port #                  0, 1, or 2
Type                    string
Units                   ID
Writable                False
Notes                   Driver Acct Number representing the driver who initiated the most recent charging session (on
                        port 1). This will not populate if access rights have not been granted.
Register Name           ChargingSessionRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================

driverName
^^^^^^^^^^
======================= ======================================================================================
Column                  Notes
======================= ======================================================================================
Attribute Name          driverName
Port #                  0, 1, or 2
Type                    string
Units                   N/A
Writable                False
Notes                   Driver name of  the driver who initiated the most recent charging session (on port 1). This
                        will not populate if access rights have not been granted.
Register Name           ChargingSessionRegister
Starting Value          N/A (Must be empty)
======================= ======================================================================================
