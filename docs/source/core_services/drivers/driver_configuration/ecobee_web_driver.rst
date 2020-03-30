Ecobee Driver
=============

The Ecobee driver is an implementation of a VOLTTRON driver frame work Interface.
An instance of a VOLTTRON Interface serves as an interface between the VOLTTRON
Master Driver agent and some device. In the case of the Ecobee driver, the
interface is responsible for providing a way for the Master Driver to retrieve
data from and set values for thermostats configured for a user using the Ecobee
remote API (https://www.ecobee.com/home/developer/api/introduction/index.shtml)

Configuration
-------------

The Ecobee driver uses two configuration files, similar to many other VOLTTRON
agents.

This is an example driver configuration:

::

    {
        "driver_config": {"ACCESS_TOKEN": "<Ecobee Access Token>",
                          "API_KEY":"<User Ecobee API key>",
                          "REFRESH_TOKEN":"<Ecobee Auth Refresh Token>",
                          "AUTHORIZATION_CODE":"<Ecobee Application Authorization Code>",
                          "PIN": "<Ecobee Application Authorization Code>",
                          "DEVICE_ID": <User Ecobee thermostat serial number>,
                          "GROUP_ID": "<Arbitrary string identifier for all devices included in remote API data>",
                          "PROXY_IDENTITY": "platform.httpproxy",
                          "config_name": "devices/ecobee"},
        "driver_type": "ecobee",
        "registry_config":"config://ecobee.csv",
        "interval": 180,
        "timezone": "UTC"
    }

The driver configuration works as follows:

    driver_config: this section specifies values used by the driver agent during
    operation.

        ACCESS_TOKEN - This is the access token provided by Ecobee. If the user
        does not initially have this value, it can be left as an empty string and
        fetched by the driver later.

        API_KEY - This is the User's API key. This must be obtained by the user from
        the Ecobee web UI and provided in this part of the configuration. Notes
        on how to do this will be provided below.

        REFRESH_TOKEN - This is the access token provided by Ecobee. If the user
        does not initially have this value, it can be left as an empty string and
        fetched by the driver later.

        AUTHORIZATION_CODE - This is the access token provided by Ecobee. If the user
        does not initially have this value, it can be left as an empty string and
        fetched by the driver later.

        PIN - This pin is provided by the Ecobee API when requesting a new
        authorization code. The driver will obtain a new authorization code and pin
        for the driver's user, however the user is responsible for validating the
        authorization code using the pin. Notes on how to do this will be provided
        below.

        DEVICE_ID - This is the device number of the Ecobee thermostat the driver
        is responsible for operating. This must be obtained by the user from the
        Ecobee web UI. Notes on how to do this will be provided below.

        GROUP_ID - This is an arbitrary string used to specify groups of thermostats.
        For the purposes of the Ecobee driver, it is recommended that a group correspond
        to the list of thermostats operated under a single user account (as Ecobee
        provides data foor all thermostats on a user's account with a data request).
        If only one user is running Ecobee drivers on a platform, this value can be
        left at the default, but it should contain some string in any case.

        PROXY_IDENTITY - This should match the string provided as the identity when
        installing the HTTP Proxy agent. failure to provide a matching identity
        will result in the platform being unable to send requests to the HTTP Proxy
        agent, which is required to be running for the Ecobee driver's operations.

        CONFIG_NAME - This should directly match the device topic used in the
        installation of the Ecobee driver (see Installation below).

    driver_type: This value should match the name of the python file which contains
    the interface class implementation for the ecobee driver. This should not change
    if the user has not changed the name of that Python file.

    registry_config: This should match the path to the registry configuration file
    specified during installation (see Installation below).

    interval: This should specify the time in seconds between publishes to the
    message bus by the Master Driver for the Ecobee driver (Note: the user can
    specify an interval for the Ecobee driver which is shorter than 180 seconds,
    however Ecobee API data is only updated at 180 second intervals, so old data
    will be published if a scrape occurs between updates.)

    timezone: Timezone to use for timestamps.

Registry Configuration
----------------------

This file specifies the behavior of "registers" in Ecobee API data. While
the API does not have registers in the sense that a PLC may, this way of doing
things allows the user to hone in on specific values, and makes the driver
highly configurable (and therefore resilient to changes made by Ecobee).

It is likely that more points may be added to obtain additional data, but
barring implementation changes by Ecobee it is unlikely that the values in this
configuration will need to change substantially, as most thermostats provide the
same range of data in a similar format.

This is an example registry configuration:

    Point Name,Volttron Point Name,Units,Type,Writable,Readable,Default Value,Notes
    fanMinOnTime,fanMinOnTime,seconds,setting,True,True,,
    hvacMode,hvacMode,seconds,setting,True,True,,
    humidity,humidity,%,setting,False,True,,
    coolHoldTemp,coolHoldTemp,degF,hold,True,False,,
    heatHoldTemp,heatHoldTemp,degF,hold,True,False,,
    desiredCool,desiredCool,degF,hold,False,True,,
    desiredHeat,desiredHeat,degF,hold,False,True,,
    actualTemperature,actualTemperature,degF,hold,False,True,,

This configuration works as follows:

    Point Name - Name of a point as it appears in Ecobee response data (example
    below)

    Volttron Point Name - Name of a point as a user would like it to be displayed
    in Volttron

    Units - Unit of measurement specified by remote API

    Type - The Ecobee driver registry configuration supports "setting" and "hold"
    register types, based on how the data is represented in Ecobee response data (
    example below)

    Writable - Whether or not the point is able to be written to. This may be
    determined by what Ecobee allows, and by the operation of Ecobee's API (to set
    an Ecobee cool/heat hold, cool/HoldTemp is used, but to read other data points
    are used and therefore are not writable; this is a quirk of Ecobee's API)

    Readable - Whether or not the point is able to be read as specified. This may be
    determined by what Ecobee allows, and by the operation of Ecobee's API
    (to set an Ecobee cool/heat hold, cool/HoldTemp is used, however the requested
    hold values are represented as desiredCool/Heat in Ecobee's response data; this
    is a quirk of Ecobee's API)

    Default Value - Used to send device defaults to the Ecobee API, this is optional.

    Notes - Any user specified notes, this is optional

---
Explanation on the quirks of Ecobee's readable/writable points, visit:
https://www.ecobee.com/home/developer/api/documentation/v1/functions/SetHold.shtml
---

Installation
------------

These are the most basic installation steps for the Ecobee driver. This guide
assumes the user is in the VOLTTRON_ROOT directory, the VOLTTRON platform has
been installed and bootstrapped per the  instructions in the VOLTTRON README,
and that the HTTP Proxy agent has been installed using the installation
instructions above.

First, the driver's Python file must be placed in the Master Driver's interfaces
directory (services/core/MasterDriverAgent/master_driver/interfaces). Failure
to place the file into this directory will cause the MasterDriver to be unable
to find the Ecobee interface.

    After putting the file in place:

    1. If the platform has not been started:

        ./start-volttron

    2. If the environment has not been activated - you should see (volttron) next to <user>@<host> in your terminal window

        . env/bin/activate

    3. If the HTTP Proxy has not yet been installed and started:

        python scripts/install-agent.py -s services/core/HTTPProxy -i <proxy_identity from Ecobee driver config>

        vctl start <HTTP Proxy Agent uuid or identity>

    4. Install a Master Driver if one is not yet installed

        python scripts/install-agent.py -s services/core/MasterDriverAgent -c <master driver configuration file>

    5. Load the driver configuration into the configuration store ("vctl config list platform.driver" can be used to show installed configurations)

        vctl config store platform.driver <device topic (mentioned in driver configuration section)> <path to driver configuration>

    6. Load the driver's registry configuration into the configuration store

        vctl config store platform.driver <registry configuration path from driver configuration> <path to registry configuration file>

    7. Start the master driver

        vctl start platform.driver

At this point, the master driver will start, configure the driver agent, and
data should start to publish on the publish interval. If the authentication code
provided in the configuration file (as above) is out of date, a new
authentication code will be obtained by the driver. This will require the user
enter the pin (found in the volttron logs) into the MyApps section of the Ecobee
web UI. Failure to do so within 60 seconds will result in the driver being unable
to get Ecobee data. Instructions on how to enter the pin will be included below.


This text can be found in the logs to specify the pin:

::

     WARNING: ***********************************************************
    2020-03-02 11:02:41,913 (master_driveragent-4.0 23053) master_driver.interfaces.ecobee WARNING: Please authorize your ecobee developer app with PIN code <code>.
    Go to https://www.ecobee.com/consumerportal /index.html, click My Apps, Add application, Enter Pin and click Authorize.
    2020-03-02 11:02:41,913 (master_driveragent-4.0 23053) master_driver.interfaces.ecobee WARNING: ***********************************************************


Ecobee Driver Usage
-------------------

At the configured interval, the master driver will publish a JSON object
with data obtained from Ecobee based on the provided configuration files.

The following is an example publish:

::

    'Status': [''],
      'Vacations': [{'coolHoldTemp': 780,
                     'coolRelativeTemp': 0,
                     'drRampUpTemp': 0,
                     'drRampUpTime': 3600,
                     'dutyCyclePercentage': 255,
                     'endDate': '2020-03-29',
                     'endTime': '08:00:00',
                     'fan': 'auto',
                     'fanMinOnTime': 0,
                     'heatHoldTemp': 660,
                     'heatRelativeTemp': 0,
                     'holdClimateRef': '',
                     'isCoolOff': False,
                     'isHeatOff': False,
                     'isOccupied': False,
                     'isOptional': True,
                     'isTemperatureAbsolute': True,
                     'isTemperatureRelative': False,
                     'linkRef': '',
                     'name': 'Skiing',
                     'occupiedSensorActive': False,
                     'running': False,
                     'startDate': '2020-03-15',
                     'startTime': '20:00:00',
                     'type': 'vacation',
                     'unoccupiedSensorActive': False,
                     'vent': 'off',
                     'ventilatorMinOnTime': 5}],
      'actualTemperature': 720,
      'desiredCool': 734,
      'desiredHeat': 707,
      'fanMinOnTime': 0,
      'humidity': '36',
      'hvacMode': 'off'},
     {'Programs': {'type': 'custom', 'tz': 'UTC', 'units': None},
      'Status': {'type': 'list', 'tz': 'UTC', 'units': None},
      'Vacations': {'type': 'custom', 'tz': 'UTC', 'units': None},
      'actualTemperature': {'type': 'integer', 'tz': 'UTC', 'units': 'degF'},
      'coolHoldTemp': {'type': 'integer', 'tz': 'UTC', 'units': 'degF'},
      'desiredCool': {'type': 'integer', 'tz': 'UTC', 'units': 'degF'},
      'desiredHeat': {'type': 'integer',S 'tz': 'UTC', 'units': 'degF'},
      'fanMinOnTime': {'type': 'integer', 'tz': 'UTC', 'units': 'seconds'},
      'heatHoldTemp': {'type': 'integer', 'tz': 'UTC', 'units': 'degF'},
      'humidity': {'type': 'integer', 'tz': 'UTC', 'units': '%'},
      'hvacMode': {'type': 'bool', 'tz': 'UTC', 'units': 'seconds'}}]

Individual points can be obtained via JSON RPC on the VOLTTRON Platform.
In an agent:

    self.vip.rpc.call("platform.driver", "get_point", <device topic>, <kwargs>)

Set_point
---------

To set points using the Ecobee driver, it is recommended to use the actuator
agent. Explanations of the actuation can be found in the VOLTTRON readthedocs
and example agent code can be found in the CsvDriverAgent (
examples/CSVDriver/CsvDriverAgent/agent.py)

Setting values for Vacations and Programs requires understanding Vacation and
Program object structure for Ecobee.

Documentation for Vacation structure can be found here:
https://www.ecobee.com/home/developer/api/documentation/v1/functions/CreateVacation.shtml

Documentation for Program structure can be found here:
https://www.ecobee.com/home/developer/api/examples/ex11.shtml

When using set_point for vacation, the user may specify True for the delete
keyword to remove an existing vacation. If deleting a vacation, the value
parameter should specify the name of a vacation to delete.

When using set_point for program, specifying a program structure will create a
new program. Otherwise, if the user has not specified resume_all, Ecobee will
resume the next program on the program stack. If resume_all, Ecobee will resume
all programs on the program stack.

For all other points, the corresponding integer, string, boolean, etc. value may
be sent.

Additional Instructions
=======================

Getting API Key
---------------

Instructions for finding your API key can be found here:
https://www.ecobee.com/home/developer/api/examples/ex1.shtml Under the Example
1 header.

Authenicating the Ecobee Driver using the PIN can be found at the same link
under Example 1 step 1 subheader.

Finding Device Identifier
-------------------------


To find your Ecobee thermostat's device identifier:

    1. Log into the Ecobee customer portal.
    2. From the Home screen click "About My Ecobee"
    3. The thermostat identifier is the serial number listed on the About screen
