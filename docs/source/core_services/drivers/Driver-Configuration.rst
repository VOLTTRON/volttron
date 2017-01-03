.. _Driver-Configuration:

====================
Driver Configuration
====================
The Master Driver Agent manages all device communication. To communicate with devices you must setup and deploy the Master Driver Agent.

Configuration for each device consists of 3 parts:

* Master Driver Agent configuration file - lists all driver configuration files to load
* Driver configuration file - contains the general driver configuration and device settings
* Device Register configuration file - contains the settings for each individual data point on the device

For each device, you must create a driver configuration file, device register configuration file, and an entry in the Master Driver Agent configuration file.

Once configured, the Master Driver Agent is :ref:`configured and deployed <test-agent-deployment>` in a manner similar to any other agent.

The Master Driver Agent along with Historian Agents replace the functionality of sMap from VOLTTRON 2.0 and thus sMap is no longer a requirement for VOLTTRON.

.. _MasterDriverConfig:
Master Driver Agent Configuration
---------------------------------
The Master Driver Agent configuration consists of general settings for all devices. The default values of the master driver should be sufficient for most users.
The user may optionally change the interval between device scrapes with the driver_scrape_interval.

The following example sets the driver_scrape_interval to 0.05 seconds or 20 devices per second:

.. code-block:: json

    {
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false,
        "publish_depth_first_all": true
    }
    
* **driver_scrape_interval** - Sets the interval between devices scrapes. Defaults to 0.02 or 50 devices per second. Useful for when the platform scrapes too many devices at once resulting in failed scrapes.

In order to improve the scalability of the platform unneeded device state publishes for all devices can be turned off.
All of the following setting are optional and default to `True`.

* **publish_depth_first_all** - Enable "depth first" publish of all points to a single topic for all devices.
* **publish_breadth_first_all** - Enable "breadth first" publish of all points to a single topic for all devices.
* **publish_depth_first** - Enable "depth first" device state publishes for each register on the device for all devices.
* **publish_breadth_first** - Enable "breadth first" device state publishes for each register on the device for all devices.

An example master driver configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/master-driver.agent``.

.. _driver-configuration-file:
Driver Configuration File
-------------------------

.. note::

    The terms `register` and `point` are used interchangeably in the documentation and
    in the configuration setting names. They have the same meaning.

Each device configuration has the following form:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},
        "driver_type": "bacnet",
        "registry_config":"config://registry_configs/vav.csv",
        "interval": 60,
        "heart_beat_point": "heartbeat"
    }

The following settings are required for all device configurations:

    - **driver_config** - Driver specific setting go here. See below for driver specific settings.
    - **driver_type** - Type of driver to use for this device. Currently VOLTTRON includes "bacnet" and "modbus" drivers and a testing driver called "fake".
    - **registry_config** - Reference to a configuration file in the configuration store for registers on the device. See the `Registry Configuration File`_ and `Adding Device Configurations to the Configuration Store`_ sections below.

These settings are optional:

    - **interval** - Period which to scrape the device and publish the results in seconds. Defaults to 60 seconds.
    - **heart_beat_point** - A Point which to toggle to indicate a heartbeat to the device. A point with this Volttron Point Name must exist in the registry. If this setting is missing the driver will not send a heart beat signal to the device. Heart beats are triggered by the Actuator Agent which must be running to use this feature.

These settings are used to create the topic that this device will be referenced by following the VOLTTRON convention of {campus}/{building}/{unit}. This will also be the topic published on, when the device is periodically scraped for it's current state.

The topic used to reference the device is derived from the name of the device configuration in the store. See the  `Adding Device Configurations to the Configuration Store`_ section.


Registry Configuration File
---------------------------
Registry configuration files setup each individual point on a device. Typically this file will be in CSV format, but the exact format is driver specific. See the section for a particular driver for the registry configuration format.

The following is a simple example of a MODBUS registry configuration file:

.. csv-table:: Catalyst 371
    :header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes

    CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
    CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation
    HeatCall2,HeatCall2,On / Off,on/off,BOOL,FALSE,1114,,Status indicator of heating stage 2 need

.. _config-store:

=======================================================
Adding Device Configurations to the Configuration Store
=======================================================

Configurations are added to the Configuration Store using the command line `volttron-ctl config store platform.driver <name> <file name> <file type>`.

* **name** - The name used to refer to the file from the store.
* **file name** - A file containing the contents of the configuration.
* **file type** - `--raw`, `--json`, or `--csv`. Indicates the type of the file. Defaults to `--json`.

The main configuration must have the name `config`

Device configuration but **not** registry configurations must have a name prefixed with `devices/`. Scripts that automate the process will prefix registry configurations with `registry_configs/`, but that is not a requirement for registry files.

The name of the device's configuration in the store is used to create the topic used to reference the device. For instance, a configuration named ``devices/PNNL/ISB1/vav1`` will publish scrape results to ``devices/PNNL/ISB1/vav1`` and is accessible with the Actuator Agent via ``PNNL/ISB1/vav1``.

The name of a registry configuration must match the name used to refer to it in the driver configuration. The reference is not case sensitive.

If the Master Driver Agent is running any changes to the configuration store will immediately affect the running devices according to the changes.

Consider the following three configuration files:

A master driver configuration called `master-driver.agent`:

.. code-block:: json

    {
        "driver_scrape_interval": 0.05
    }

A MODBUS device configuration file called `modbus1.config`:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.2",
                          "port": 502,
                          "slave_id": 5},
        "driver_type": "modbus",
        "registry_config":"config://registry_configs/hvac.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A MODBUS registry configuration file called `catalyst371.csv`:

.. csv-table:: catalyst371.csv
    :header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes

    CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
    CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation
    HeatCall2,HeatCall2,On / Off,on/off,BOOL,FALSE,1114,,Status indicator of heating stage 2 need

To store the master driver configuration run the command

``volttron-ctl config store platform.driver config master-driver.agent``

To store the registry configuration run the command (note the --csv option)

``volttron-ctl config store platform.driver registry_configs/hvac.csv catalyst371.csv --csv``

Note the name ``registry_configs/hvac.csv`` matches the configuration reference in the file ``modbus1.config``.

To store the driver configuration run the command

``volttron-ctl config store platform.driver devices/my_campus/my_building/hvac1 modbus1.config``


Converting Old Style Configuration
----------------------------------

The new Master Driver no longer supports the old style of device configuration. The old ``device_list`` setting is ignored.

To simplify updating to the new format ``scripts/update_master_driver_config.py`` is provide to automatically update to the new configuration format.

With the platform running run:

``python scripts/update_master_driver_config.py <old configuration> <output>``

**old_configuration** is the main configuration file in the old format. The script automatically modifies the driver files to create references to CSV files and adds the CSV files with the appropriate name.

**output** is the target output directory.

If the ``--keep-old`` switch is used the old configurations in the output directory (if any) will not be deleted before new configurations are created. Matching names will still be overwritten.

The output from ``scripts/update_master_driver_config.py`` can be automatically added to the configuration store
for the Master Driver agent with ``scripts/install_master_driver_configs.py``.

Creating and naming configuration files in the form needed by ``scripts/install_master_driver_configs.py``
can speed up the process of changing and updating a large number of configurations. See the ``--help``
message for ``scripts/install_master_driver_configs.py`` for more details.

Device State Publishes
----------------------

By default, the value of each register on a device is published 4 different ways when the device state is published.
Consider the following settings in a driver configuration stored under the name ``devices/pnnl/isb1/vav1``:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},

        "driver_type": "bacnet",
        "registry_config":"config://registry_configs/vav.csv",
    }

In the ``vav.csv`` file is a register with the name ``temperature``. For these examples
the current value of the register on the device happens to be 75.2 and the meta data
is

.. code-block:: python

    {"units": "F"}

When the driver publishes the device state the following 2 things will be published for this register:

    A "depth first" publish to the topic ``devices/pnnl/isb1/vav1/temperature``
    with the following message:

        .. code-block:: python

            [75.2, {"units": "F"}]

    A "breadth first" publish to the topic ``devices/temperature/vav1/isb1/pnnl``
    with the following message:

        .. code-block:: python

            [75.2, {"units": "F"}]

    These publishes can be turned off by setting `publish_depth_first` and `publish_breadth_first` to `false` respectively.

Also these two publishes happen once for all registers:

    A "depth first" publish to the topic ``devices/pnnl/isb1/vav1/all``
    with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

    A "breadth first" publish to the topic ``devices/all/vav1/isb1/pnnl``
    with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

    These publishes can be turned off by setting `publish_depth_first_all` and `publish_breadth_first_all` to `false` respectively.

Device Scalability Settings
---------------------------

In order to improve the scalability of the platform unneeded device state publishes for a device can be turned off.
All of the following setting are optional and will override the value set in the main master driver configuration.

    - **publish_depth_first_all** - Enable "depth first" publish of all points to a single topic.
    - **publish_breadth_first_all** - Enable "breadth first" publish of all points to a single topic.
    - **publish_depth_first** - Enable "depth first" device state publishes for each register on the device.
    - **publish_breadth_first** - Enable "breadth first" device state publishes for each register on the device.

It is common practice to set **publish_breadth_first_all**, **publish_depth_first**, and
**publish_breadth_first** to `False` unless they are specifically needed by an agent running on
the platform.


.. note::

    All Historian Agents require **publish_depth_first_all** to be set to `True` in order to capture data.



.. _MODBUS-config:
MODBUS Driver Configuration
---------------------------
Currently, VOLTTRON only supports the MODBUS over TCP/IP protocol.

driver_config
*************

There are three arguments for the **driver_config** section of the device configuration file:

    - **device_address** - IP Address of the device.
    - **port** - Port the device is listening on. Defaults to 502 which is the standard port for MODBUS devices.
    - **slave_id** - Slave ID of the device. Defaults to 0. Use 0 for no slave.

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.2",
                          "port": 502,
                          "slave_id": 5},
        "driver_type": "modbus",
        "registry_config":"config://registry_configs/hvac.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample MODBUS configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/modbus1.config``


.. _MODBUS-Driver:
MODBUS Registry Configuration File
**********************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device. 

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point. For instance, if the Volttron Point Name is HeatCall1 (and using the example device configuration above) then an agent would use ``pnnl/isb2/hvac1/HeatCall1`` to refer to the point when using the RPC interface of the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Modbus Register** - A string representing how to interpret the data register and how to read it from the device. The string takes two forms:
    
        + "BOOL" for coils and discrete inputs.
        + A format string for the Python struct module. See http://docs.python.org/2/library/struct.html for full documentation. The supplied format string must only represent one value. See the documentation of your device to determine how to interpret the registers. Some Examples:
        
            * ">f" - A big endian 32-bit floating point number.
            * "<H" - A little endian 16-bit unsigned integer.
            * ">l" - A big endian 32-bit integer.
            
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written to through the ActuatorAgent.
    - **Point Address** - Modbus address of the point. Cannot include any offset value, it must be the exact value of the address.

The following column is optional:

    - **Default Value** - The default value for the point. When the point is reverted by an agent it will change back to this value. If this value is missing it will revert to the last known value not set by an agent.

Any additional columns will be ignored. It is common practice to include a **Point Name** or **Reference Point Name** to include the device documentation's name for the point and **Notes** and **Unit Details** for additional information about a point.

The following is an example of a MODBUS registry confugration file:

.. csv-table:: Catalyst 371
        :header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes
        
        CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
        CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation 
        Cool1Spd,CoolSupplyFanSpeed1,%,0.00 to 100.00 (75 default),>f,TRUE,1005,75,Fan speed on cool 1 call
        Cool2Spd,CoolSupplyFanSpeed2,%,0.00 to 100.00 (90 default),>f,TRUE,1007,90,Fan speed on Cool2 Call
        Damper,DamperSignal,%,0.00 - 100.00,>f,FALSE,1023,,Output to the economizer damper
        DaTemp,DischargeAirTemperature,F,(-)39.99 to 248.00,>f,FALSE,1009,,Discharge air reading
        ESMEconMin,ESMDamperMinPosition,%,0.00 to 100.00 (5 default),>f,TRUE,1013,5,Minimum damper position during the energy savings mode
        FanPower,SupplyFanPower, kW,0.00 to 100.00,>f,FALSE,1015,,Fan power from drive
        FanSpeed,SupplyFanSpeed,%,0.00 to 100.00,>f,FALSE,1003,,Fan speed from drive
        HeatCall1,HeatCall1,On / Off,on/off,BOOL,FALSE,1113,,Status indicator of heating stage 1 need
        HeartBeat,heartbeat,On / Off,on/off,BOOL,FALSE,1114,,Status indicator of heating stage 2 need

A sample MODBUS registry file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/catalyst371.csv>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/catalyst371.csv``

.. _BACnet-Driver:
BACnet Driver Configuration
---------------------------
Communicating with BACnet devices requires that the BACnet Proxy Agent is configured and running. All device communication happens through this agent.

driver_config
*************

There are six arguments for the "driver_config" section of the device configuration file:

    - **device_address** - Address of the device. If the target device is behind an IP to MS/TP router then Remote Station addressing will probably be needed for the driver to find the device.
    - **device_id** - BACnet ID of the device. Used to establish a route to the device at startup. 
    - **min_priority** - (Optional) Minimum priority value allowed for this device whether specifying the priority manually or via the registry config. Violating this parameter either in the configuration or when writing to the point will result in an error. Defaults to 8.
    - **max_per_request** - (Optional) Configure driver to manually segment read requests. The driver will only grab up to the number of objects specified in this setting at most per request. This setting is primarily for scraping many points off of low resource devices that do not support segmentation. Defaults to 10000.
    - **proxy_address** - (Optional) VIP address of the BACnet proxy. Defaults to "platform.bacnet_proxy". See :ref:`bacnet-proxy-multiple-networks` for details. Unless your BACnet network has special needs you should not change this value.
    - **ping_retry_interval** - (Optional) The driver will ping the device to establish a route at startup. If the BACnet proxy is not available the driver will retry the ping at this interval until it succeeds. Defaults to 5.

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.3",
                          "device_id": 500,
                          "min_priority": 10,
                          "max_per_request": 24
                          },
        "driver_type": "bacnet",
        "registry_config":"config://registry_configs/vav.csv",
        "interval": 5,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample BACnet configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/bacnet1.config>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/bacnet1.config``

.. _BACnet-Registry-Configuration-File:
BACnet Registry Configuration File
**********************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device. 

Most of the configuration file can be generated with the ``grab_bacnet_config.py`` utility in ``scripts/bacnet``. See :doc:`BACnet-Auto-Configuration`.

Currently, the driver provides no method to access array type properties even if the members of the array are of a supported type.

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point. For instance, if the Volttron Point Name is HeatCall1 (and using the example device configuration above) then an agent would use "pnnl/isb2/hvac1/HeatCall1" to refer to the point when using the RPC interface of the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **BACnet Object Type** - A string representing what kind of BACnet standard object the point belongs to. Examples include:
    
        * analogInput
        * analogOutput
        * analogValue
        * binaryInput
        * binaryOutput
        * binaryValue
        * multiStateValue
        
    - **Property** - A string representing the name of the property belonging to the object. Usually, this will be "presentValue".
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written to through the ActuatorAgent. Points labeled "TRUE" incorrectly will cause an error to be returned when an agent attempts to write to the point.
    - **Index** - Object ID of the BACnet object.

The following column is optional:

    - **Write Priority** - BACnet priority for writing to this point. Valid values are 1-16. Missing this column or leaving the column blank will use the default priority of 16.

Any additional columns will be ignored. It is common practice to include a **Point Name** or **Reference Point Name** to include the device documentation's name for the point and **Notes** and **Unit Details**" for additional information about a point.

.. csv-table:: BACnet
	:header: Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Notes

        Building/FCB.Local Application.PH-T,PreheatTemperature,degreesFahrenheit,-50.00 to 250.00,analogInput,presentValue,FALSE,3000119,Resolution: 0.1
        Building/FCB.Local Application.RA-T,ReturnAirTemperature,degreesFahrenheit,-50.00 to 250.00,analogInput,presentValue,FALSE,3000120,Resolution: 0.1
        Building/FCB.Local Application.RA-H,ReturnAirHumidity,percentRelativeHumidity,0.00 to 100.00,analogInput,presentValue,FALSE,3000124,Resolution: 0.1
        Building/FCB.Local Application.CLG-O,CoolingValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000107,Resolution: 0.1
        Building/FCB.Local Application.MAD-O,MixedAirDamperOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000110,Resolution: 0.1
        Building/FCB.Local Application.PH-O,PreheatValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000111,Resolution: 0.1
        Building/FCB.Local Application.RH-O,ReheatValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000112,Resolution: 0.1
        Building/FCB.Local Application.SF-O,SupplyFanSpeedOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000113,Resolution: 0.1


A sample BACnet registry file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/bacnet.csv>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/bacnet.csv``




.. _Chargepoint-config:
Chargepoint Driver Configuration
--------------------------------

The chargepoint driver requires at least one additional python library and has its own ``requirements.txt``.
Make sure to run ``pip install -r <chargepoint driver path>/requirements.txt`` before using this driver.


driver_config
*************

There are three arguments for the **driver_config** section of the device configuration file:

    - **stationID** - Chargepoint ID of the station. This format is ususally '1:00001'
    - **username** - Login credentials for the Chargepoint API
    - **password** - Login credentials for the Chargepoint API

The Chargepoint login credentials are generated in the Chargepoint web portal and require
a chargepoint account with sufficient privileges.  Station IDs are also available on
the web portal.

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {"stationID": "3:12345",
                          "username": "4b90fc0ae5fe8b6628e50af1215d4fcf5743a6f3c63ee1464012875",
                          "password": "ebaf1a3cdfb80baf5b274bdf831e2648"},
        "driver_type": "chargepoint",
        "registry_config":"config://chargepoint.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample Chargepoint configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/chargepoint1.config``


.. _Chargepoint-Driver:
Chargepoint Registry Configuration File
***************************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device.

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point.
    - **Attribute Name** - Chargepoint API attribute name. This determines the field that will be read from the API response and must be one of the allowed values.
    - **Port #** - If the point describes a specific port on the Chargestation, it is defined here. (Note 0 and an empty value are equivalent.)
    - **Type** - Python type of the point value.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written.
    - **Notes** - Miscellaneous notes field.
    - **Register Name** - A string representing how to interpret the data register. Acceptable values are:
        * StationRegister
        * StationStatusRegister
        * LoadRegister
        * AlarmRegister
        * StationRightsRegister
    - **Starting Value** - Default value for writeable points. Read-only points should not have a value in this column.

Detailed descriptions for all available chargepoint registers may be found in the ``README.rst`` in the
chargepoint driver directory.

A sample Chargepoint registry file can be found in the VOLTTRON repository in ``examples/configurations/drivers/chargepoint.csv``


Fake Device Driver Configuration
--------------------------------
This driver does not connect to any actual device and instead produces random and or pre-configured values. 

driver_config
*************

There are no arguments for the "driver_config" section of the device configuration file. The driver_config entry must still be present and should be left blank

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {},
        "driver_type": "bacnet",
        "registry_config":"config://registry_configs/vav.csv",
        "interval": 5,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample fake device configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/fake.config``

Fake Device Registry Configuration File
***************************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device. 

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point. For instance, if the Volttron Point Name is HeatCall1 (and using the example device configuration above) then an agent would use *pnnl/isb2/hvac1/HeatCall1* to refer to the point when using the RPC interface of the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written to through the ActuatorAgent. Points labeled "TRUE" incorrectly will cause an error to be returned when an agent attempts to write to the point.
    

The following columns are optional:

    - **Starting Value** - Initial value for the point. If the point is reverted it will change back to this value. By default, points will start with a random value (1-100).
    - **Type** - Value type for the point. Defaults to "string". Valid types are:
    
        * string
        * integer
        * float
        * boolean

Any additional columns will be ignored. It is common practice to include a **Point Name** or **Reference Point Name** to include the device documentation's name for the point and **Notes** and **Unit Details** for additional information about a point. Please note that there is nothing in the driver that will enforce anything specified in the **Unit Details** column.

.. csv-table:: BACnet
	:header: Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes

        Heartbeat,On/Off,On/Off,TRUE,0,boolean,Point for heartbeat toggle
        OutsideAirTemperature1,F,-100 to 300,FALSE,50,float,CO2 Reading 0.00-2000.0 ppm
        SampleWritableFloat1,PPM,10.00 (default),TRUE,10,float,Setpoint to enable demand control ventilation
        SampleLong1,Enumeration,1 through 13,FALSE,50,int,Status indicator of service switch
        SampleWritableShort1,%,0.00 to 100.00 (20 default),TRUE,20,int,Minimum damper position during the standard mode
        SampleBool1,On / Off,on/off,FALSE,TRUE,boolean,Status indicator of cooling stage 1
        SampleWritableBool1,On / Off,on/off,TRUE,TRUE,boolean,Status indicator


A sample fake registry configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/fake.csv>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/fake.csv``
