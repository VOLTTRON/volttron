.. _ecobee-web-driver:

*************
Ecobee Driver
*************

The Ecobee driver is an implementation of a `VOLTTRON driver framework <VOLTTRON Driver Framework>`_ Interface.
In this case, the Master Driver issues commands to the Ecobee driver to collect data from and send control signals to
`Ecobee's remote web API <https://www.ecobee.com/home/developer/api/introduction/index.shtml>`_

.. note::

    Reading the driver framework and driver configuration documentation prior to following this guide will help the user
    to understand drivers, driver communication, and driver configuration files.

This guide covers:

* Creating a driver configuration file, including finding the user's Ecobee API key and Ecobee thermostat serial number
* Creating the registry configuration file
* Installing the Master Driver and loading Ecobee driver and registry configurations
* Starting the driver and viewing Ecobee data publishes

Configuration File
##################

The Ecobee driver uses two configuration files, similar to many other VOLTTRON agents.

This is an example driver configuration:

.. code-block:: JSON

    {
        "driver_config": {
            "API_KEY": "<User Ecobee API key>",
            "DEVICE_ID": <User Ecobee thermostat serial number>
        },
        "driver_type": "ecobee",
        "registry_config":"config://ecobee.csv",
        "interval": 180,
        "timezone": "UTC"
    }

The driver configuration works as follows:

::

    driver_config- this section specifies values used by the driver agent during
    operation.

        API_KEY - This is the User's API key. This must be obtained by the user from
        the Ecobee web UI and provided in this part of the configuration. Notes
        on how to do this will be provided below.

        DEVICE_ID - This is the device number of the Ecobee thermostat the driver
        is responsible for operating. This must be obtained by the user from the
        Ecobee web UI. Notes on how to do this will be provided below.

    driver_type - This value should match the name of the python file which contains
    the interface class implementation for the ecobee driver. This should not change
    if the user has not changed the name of that Python file.

    registry_config - This should match the path to the registry configuration file
    specified during installation (see Installation below).

    interval - This should specify the time in seconds between publishes to the
    message bus by the Master Driver for the Ecobee driver (Note: the user can
    specify an interval for the Ecobee driver which is shorter than 180 seconds,
    however Ecobee API data is only updated at 180 second intervals, so old data
    will be published if a scrape occurs between updates.)

    timezone: Timezone to use for publishing timestamps. This value should match the `timezone from the Ecobee device
    <https://www.support.com/how-to/how-to-set-the-date-and-time-on-an-ecobee-thermostat-12344#:~:text=From%20the%20Thermostat,make%20changes%20to%20Time%20Format.>`_

.. note::

    Values for API_KEY and DEVICE_ID must be obtained by the user. DEVICE_ID should be added as an integer
    representation of the thermostat's serial number.

    **Getting API Key**

    Instructions for finding your API key as well as authenticating the Ecobee Driver using the PIN can be found `here
    <https://www.ecobee.com/home/developer/api/examples/ex1.shtml>`_ Under the Example 1 header.

    **Finding Device Identifier**

    To find your Ecobee thermostat's device identifier:

        1. Log into the `Ecobee customer portal <https://www.ecobee.com/consumerportal/index.html>`_
        2. From the Home screen click "About My Ecobee"
        3. The thermostat identifier is the serial number listed on the About screen


Registry Configuration
----------------------

This file specifies the behavior of "registers" in Ecobee API data.

It is likely that more points may be added to obtain additional data, but
barring implementation changes by Ecobee it is unlikely that the values in this
configuration will need to change substantially, as most thermostats provide the
same range of data in a similar format.

This is an example registry configuration:

.. csv-table::

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

::

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

For additional explanation on the quirks of Ecobee's readable/writable points, visit:
https://www.ecobee.com/home/developer/api/documentation/v1/functions/SetHold.shtml


Installation
############

These are the most basic installation steps for the Ecobee driver.

.. note::

    This guide assumes the user is in the VOLTTRON_ROOT directory, the VOLTTRON platform has been installed and
    bootstrapped per the instructions in the VOLTTRON README.

Below are the setup instructions for the Ecobee driver.


1. If the platform has not been started:

.. code-block:: Bash

    ./start-volttron

2. Be sure that the environment has been activated - you should see (volttron) next to <user>@<host> in your terminal
window. To activate an environment, use the following command.

.. code-block:: Bash

    . env/bin/activate

3. Install a Master Driver if one is not yet installed

.. code-block:: Bash

    python scripts/install-agent.py -s services/core/MasterDriverAgent -c <master driver configuration file>

4. Load the driver configuration into the configuration store ("vctl config list platform.driver" can be used to show
   installed configurations)

.. code-block:: Bash

    vctl config store platform.driver <device topic (mentioned in driver configuration section)> <path to driver configuration>

5. Load the driver's registry configuration into the configuration store

.. code-block:: Bash

    vctl config store platform.driver <registry configuration path from driver configuration> <path to registry configuration file> --csv

6. Start the master driver

.. code-block:: Bash

    vctl start platform.driver

At this point, the master driver will start, configure the driver agent, and data should start to publish on the publish
interval.

.. note::

    If starting the driver for the first time, or if the authorization which is managed by the driver is out of date,
    the driver will perform some additional setup internally to authenticate the driver with the Ecobee API.  This stage
    will require the user enter a pin provided in the `volttron.log` file to the Ecobee web UI.  The Ecobee driver has
    a wait period of 60 seconds to allow users to enter the pin code into the Ecobee UI. Instructions for pin
    verification follow.


PIN Verification steps:
-----------------------

* Step 1 - Obtain the pin from the VOLTTRON logs. The pin is a 4 character long string in the logs flanked by 2 rows of
  asterisks

This text can be found in the logs to specify the pin:

.. code-block:: Bash

     WARNING: ***********************************************************
    2020-03-02 11:02:41,913 (master_driveragent-4.0 23053) master_driver.interfaces.ecobee WARNING: Please authorize your ecobee developer app with PIN code <code>.
    Go to https://www.ecobee.com/consumerportal /index.html, click My Apps, Add application, Enter Pin and click Authorize.
    2020-03-02 11:02:41,913 (master_driveragent-4.0 23053) master_driver.interfaces.ecobee WARNING: ***********************************************************

* Step 2 - Log into the `Ecobee UI <https://www.ecobee.com/consumerportal/index.html#/login>`_ . After logging in, the
  customer dashboard will be brought up, which features a series of panels (where the serial number was found for
  device configuration) and a "hamburger" menu.

* Step 3 - Add the application: Click the "hamburger" icon which will display a list of items in a panel that becomes
  visible on the right. Click "My Apps", then "Add application". A text form will appear, enter the pin provided in
  VOLTTRON logs here, then click "validate" and "add application.

This will complete the pin verification step.

Ecobee Driver Usage
###################

At the configured interval, the master driver will publish a JSON object
with data obtained from Ecobee based on the provided configuration files.

To view the publishes in the `volttron.log` file, install and start a ListenerAgent:

.. code-block:: Bash

    python scripts/install-agent.py -s examples/ListenerAgent

The following is an example publish:

.. code-block:: Bash

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

.. code-block:: Python

    self.vip.rpc.call("platform.driver", "get_point", <device topic>, <kwargs>)


Set_point Conventions
#####################

To set points using the Ecobee driver, it is recommended to use the actuator
agent. Explanations of the actuation can be found in the VOLTTRON readthedocs
and example agent code can be found in the CsvDriverAgent (
examples/CSVDriver/CsvDriverAgent/agent.py in the VOLTTRON repository)

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

Versioning
----------

The Ecobee driver has been tested using the May 2019 API release as well as device firmware version 4.5.73.24
