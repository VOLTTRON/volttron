Driver Configuration
====================
The Master Driver Agent manages all device communication. To communicate with devices you must setup and deploy the Master Driver Agent.

Configuration for each device consists of 3 parts:

* Master Driver Agent configuration file - lists all driver configuration files to load
* Driver configuration file - contains the driver configuration and device setting
* Device Register configuration file - contains the settings for each indivitual data point on the device

For each device you must create a driver configuration file, device register configuration file, and an entry in the Master Driver Agent configuration file.  

Once configured the Master Driver Agent is configured and deployed in a manner similar to any other agent (TODO: insert link to Agent deployment howto).

The Master Driver Agent along with Historian Agents replace the functionality of sMap from VOLTTRON 2.0 and thus sMap is no longer a requirement for VOLTTRON.

Master Driver Agent Configuration
---------------------------------
The Master Driver Agent configuration consists a list of device configuration files to load at startup. 

Optionally the user may stagger the start of drivers to improve scalability of the platform by using the staggered_start setting.

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

Driver Configuration File
-------------------------
Each device configuration has the following form:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},
        
        "driver_type": "bacnet",
        "registry_config":"/home/volttron-user/configs/vav.csv",
        "interval": 60,
        "heart_beat_point": "Heartbeat",
        "campus": "pnnl",
        "building": "isb1",
        "unit": "vav1"
    }

The following settings are required for all device configurations:

    - **driver_config** - Driver specific setting go here. See below for driver specific settings.
    - **driver_type** - Type of driver to use for this device. Currently VOLTTRON includes "bacnet" and "modbus" drivers and a testing driver called "fake".
    - **registry_config** - Configuration file for registers on the device. See the documentation for specific drivers for details.

These settings are optional:
    - **interval** - Period which to scrape the device and publish the results in seconds. This defaults to 60.
    - **heart_beat_point** - Point (must exist in the registry configuration) which to toggle to indicate a heartbeat to the device. If this setting is missing the driver will not send a heart beat signal to the device. Heart beats are triggered by the Actuator Agent which must be running to use this feature.

These settings are used to create the topic that this device will be referenced by following the VOLTTRON standard of {campus}/{building}/{unit}. This will also be the topic published on when then device is periodically scraped for it's current state.

While all of the settings are optional at least one is required.
    - **campus** - Campus portion of the device topic. (Optional)
    - **building** - Building portion of the device topic. (Optional)
    - **unit** - Unit portion of the device topic. (Optional)
    - **path** - Additional topic bits after unit. Useful for specifying sub devices. (Optional)

For instance with the above example the topic used to reference this device would be

    pnnl/isb1/vav1
    
and device state publishes would start with

    devices/pnnl/isb1/vav1

Registry Configuration Files
----------------------------
Registry configuration files setup each individual point on a device. Typically this file will be in CSV format.

The following is an example of a MODBUS registry confugration file:

.. csv-table:: Catalyst 371
	:header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes
	
	CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
	CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation 
	Cool1Spd,CoolSupplyFanSpeed1,%,0.00 to 100.00 (75 default),>f,TRUE,1005,75,Fan speed on cool 1 call
	Cool2Spd,CoolSupplyFanSpeed2,%,0.00 to 100.00 (90 default),>f,TRUE,1007,90,Fan speed on Cool2 Call
	Damper,DamperSignal,%,0.00 - 100.00,>f,FALSE,1023,,Output to the economizer damper
	DaTemp,DischargeAirTemperature,F,(-)39.99 to 248.00,>f,FALSE,1009,,Discharge air reading
	ESMEconMin,ESMDamperMinPosition,%,0.00 to 100.00 (5 default),>f,TRUE,1013,5,Minimum damper poistion during the energy savings mode
	FanPower,SupplyFanPower, kW,0.00 to 100.00,>f,FALSE,1015,,Fan power from drive
	FanSpeed,SupplyFanSpeed,%,0.00 to 100.00,>f,FALSE,1003,,Fan speed from drive

