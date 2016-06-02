.. _Driver-Configuration:
<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
====================
Driver Configuration
====================
The Master Driver Agent manages all device communication. To communicate with devices you must setup and deploy the Master Driver Agent.

Configuration for each device consists of 3 parts:

* Master Driver Agent configuration file - lists all driver configuration files to load
* Driver configuration file - contains the general driver configuration and device settings
* Device Register configuration file - contains the settings for each individual data point on the device

For each device you must create a driver configuration file, device register configuration file, and an entry in the Master Driver Agent configuration file.  

Once configured the Master Driver Agent is configured and deployed in a manner similar to any other agent (TODO: insert link to Agent deployment howto).

The Master Driver Agent along with Historian Agents replace the functionality of sMap from VOLTTRON 2.0 and thus sMap is no longer a requirement for VOLTTRON.

.. _MasterDriverConfig:
Master Driver Agent Configuration
---------------------------------
The Master Driver Agent configuration consists of a list of device configuration files to load at startup. 
The user may optionally stagger the start of drivers to improve scalability of the platform by using the staggered_start setting.

The following example loads three driver configuration files:

.. code-block:: json

    {
        "driver_config_list": [
               "/home/volttron-user/configs/test_bacnet1.config",  
               "/home/volttron-user/configs/test_bacnet2.config",
               "/home/volttron-user/configs/test_modbus1.config"
        ],
        "staggered_start": 30.0
    }
    

* **driver_config_list** - A list of driver configuration files to load at startup.

* **staggered_start** - Spread the scraping and publishing of device data over approximately N seconds. Useful for when the platform scrapes too many devices at once resulting in failed scrapes.

An example master driver configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/master-driver.agent>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/master-driver.agent``.

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
        "registry_config":"/home/volttron-user/configs/vav.csv",
        "interval": 60,
        "campus": "pnnl",
        "building": "isb1",
        "unit": "vav1",
        "heart_beat_point": "heatbeat"
    }

The following settings are required for all device configurations:

    - **driver_config** - Driver specific setting go here. See below for driver specific settings.
    - **driver_type** - Type of driver to use for this device. Currently VOLTTRON includes "bacnet" and "modbus" drivers and a testing driver called "fake".
    - **registry_config** - Registry configuration file for registers on the device. See the `Registry Configuration File`_ section below.

These settings are optional:

    - **interval** - Period which to scrape the device and publish the results in seconds. Defaults to 60 seconds.
    - **heart_beat_point** - A Point which to toggle to indicate a heartbeat to the device. A point with this Volttron Point Name must exist in the registry. If this setting is missing the driver will not send a heart beat signal to the device. Heart beats are triggered by the Actuator Agent which must be running to use this feature.

These settings are used to create the topic that this device will be referenced by following the VOLTTRON convention of {campus}/{building}/{unit}. This will also be the topic published on when then device is periodically scraped for it's current state.

While all of the settings are optional at least one is required:

    - **campus** - Campus portion of the device topic. (Optional)
    - **building** - Building portion of the device topic. (Optional)
    - **unit** - Unit portion of the device topic. (Optional)
    - **path** - Additional topic bits after unit. Useful for specifying sub devices. (Optional)

For instance with the above example the topic used to reference this device when 
making an RPC call would be

    ``pnnl/isb1/vav1``


Device State Publishes
**********************

By default the value of each register on a device is published 4 different ways when the device state is published.
Consider the following settings in a Driver Configuration File:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},

        "driver_type": "bacnet",
        "registry_config":"/home/volttron-user/configs/vav.csv",
        "campus": "pnnl",
        "building": "isb1",
        "unit": "vav1",
    }

In the `vav.csv` file is a register with the name ``temperature``. For these examples
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

Also these two publishes happen once for all registers:

    A "depth first" publish to the topic ``devices/pnnl/isb1/vav1/all``
    with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

    A "breadth first" publish to the topic ``devices/all/vav1/isb1/pnnl``
    with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

Scalability Settings
********************

In order to improve the scalability of the platform unneeded device state publishes for a device can be turned off.
All of the following setting are optional and default to `True`:

    - **publish_depth_first_all** - Enable device state publishes to the topic
      ``devices/<campus>/<building>/<unit>/<path>/all``
    - **publish_breadth_first_all** - Enable device state publishes to the topic
      ``devices/all/<path>/<unit>/<building>/<campus>``
    - **publish_depth_first** - Enable device state publishes to the topic
      ``devices/<campus>/<building>/<unit>/<path>/<point_name>`` for each register on the device.
    - **publish_breadth_first** - Enable device state publishes to the topic
      ``devices/all/<path>/<unit>/<building>/<campus>`` for each register on the device.

It is common practice to set **publish_breadth_first_all**, **publish_depth_first**, and
**publish_breadth_first** to `False` unless they are specifically needed by an agent running on
the platform.


.. note::

    All Historian Agents require **publish_depth_first_all** to be set to `True` in order to capture data.

Registry Configuration File
---------------------------
Registry configuration files setup each individual point on a device. Typically this file will be in CSV format, but the exact format is driver specific. See the section for a particular driver for the registry configuration format.

The following is a simple example of a MODBUS registry confugration file:

.. csv-table:: Catalyst 371
    :header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes
	
    CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
    CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation 
    HeatCall2,HeatCall2,On / Off,on/off,BOOL,FALSE,1114,,Status indicator of heating stage 2 need

.. _MODBUS-config:
MODBUS Driver Configuration
---------------------------
Currently VOLTTRON only supports the MODBUS over TCP/IP protocol.

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
        "campus": "pnnl",
        "building": "isb2",
        "unit": "hvac1",
        "driver_type": "modbus",
        "registry_config":"/home/volttron-user/configs/hvac.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample MODBUS configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/modbus1.config>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/modbus1.config``


.. _MODBUS-Driver:
MODBUS Registry Configuration File
**********************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device. 

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point. For instance, if the Volttron Point Name is HeatCall1 (and using the example device configuration above) then an agent would use ``pnnl/isb2/hvac1/HeatCall1`` to refer to the point when using the RPC interface of the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Modbus Register** - A string representing how to interpret the data register and how to read it it from the device. The string takes two forms:
    
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
    - **min_priority** - (Optional) Minimum priority value allowed for this device whether specifying the prioity manually or via the registry config. Violating this parameter either in the configuration or when writing to the point will result in an error. Defaults to 8.
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
        "campus": "pnnl",
        "building": "isb2",
        "unit": "vav",
        "driver_type": "bacnet",
        "registry_config":"/home/volttron-user/configs/vav.csv",
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

Currently the driver provides no method to access array type properties even if the members of the array are of a supported type.

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
        
    - **Property** - A string representing the name of the property belonging to the object. Usually this will be "presentValue".
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written to through the ActuatorAgent. Points labeled "TRUE" incorrectly will cause an error to be returned when an agent attempts to write to the point.
    - **Index** - Object ID of the BACnet object.

The following column is optional:

    - **Write Priority** - BACnet priority for writing to this point. Valid values are 1-16. Missing this column or leaving the column blank will use the default priority of 16.

Any additional columns will be ignored. It is common practice to include a **Point Name** or **Reference Point Name** to include the device documentation's name for the point and **Notes** and **Unit Details**" for additional information about a point.

.. csv-table:: BACnet
	:header: Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Notes

        2400Stevens/FCB.Local Application.PH-T,PreheatTemperature,degreesFahrenheit,-50.00 to 250.00,analogInput,presentValue,FALSE,3000119,Resolution: 0.1
        2400Stevens/FCB.Local Application.RA-T,ReturnAirTemperature,degreesFahrenheit,-50.00 to 250.00,analogInput,presentValue,FALSE,3000120,Resolution: 0.1
        2400Stevens/FCB.Local Application.RA-H,ReturnAirHumidity,percentRelativeHumidity,0.00 to 100.00,analogInput,presentValue,FALSE,3000124,Resolution: 0.1
        2400Stevens/FCB.Local Application.CLG-O,CoolingValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000107,Resolution: 0.1
        2400Stevens/FCB.Local Application.MAD-O,MixedAirDamperOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000110,Resolution: 0.1
        2400Stevens/FCB.Local Application.PH-O,PreheatValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000111,Resolution: 0.1
        2400Stevens/FCB.Local Application.RH-O,ReheatValveOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000112,Resolution: 0.1
        2400Stevens/FCB.Local Application.SF-O,SupplyFanSpeedOutputCommand,percent,0.00 to 100.00 (default 0.0),analogOutput,presentValue,TRUE,3000113,Resolution: 0.1


A sample BACnet registry file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/bacnet.csv>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/bacnet.csv``

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
        "campus": "pnnl",
        "building": "isb2",
        "unit": "vav",
        "driver_type": "bacnet",
        "registry_config":"/home/volttron-user/configs/vav.csv",
        "interval": 5,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample fake device configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/fake.config>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/fake.config``

Fake Device Registry Configuration File
***************************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device. 

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point. For instance, if the Volttron Point Name is HeatCall1 (and using the example device configuration above) then an agent would use *pnnl/isb2/hvac1/HeatCall1* to refer to the point when using the RPC interface of the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written to through the ActuatorAgent. Points labeled "TRUE" incorrectly will cause an error to be returned when an agent attempts to write to the point.
    

The following columns are optional:

    - **Starting Value** - Initial value for the point. If the point is reverted it will change back to this value. By default points will start with a random value (1-100).
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
        SampleBool1,On / Off,on/off,FALSE,TRUE,boolean,Status indidcator of cooling stage 1
        SampleWritableBool1,On / Off,on/off,TRUE,TRUE,boolean,Status indicator


A sample fake registry configuration file can be found `here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/fake.csv>`_ or 
in the VOLTTRON repository in ``examples/configurations/drivers/fake.csv``
