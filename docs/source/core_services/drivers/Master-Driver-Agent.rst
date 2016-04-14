Master Driver Agent
=====

Introduction
------------

The Master Driver Agent is linchpin for communicating with devices in
VOLTTRON. It replaces the functionality of sMap from Volttron 2.0 and
separates device communication from the process recording device data in
a database. Recording device data to a database is now handled by a
`Historian Agent <Historian-Agent>`__.

The Master Driver Agent is configured and deployed in a manner similar
to any other agent (TODO: insert link to Agent deployment howto).

Configuration
-------------

The configuration consists a list of device configuration files to load
at startup. Optionally the user may stagger the start of drivers to
improve scalability of the platform by using the staggered\_start
setting.

::

    {
        "driver_config_list": [
               "/home/volttron-user/configs/test_bacnet1.config",  
               "/home/volttron-user/configs/test_bacnet2.config",
               "/home/volttron-user/configs/test_modbus1.config"
        ],
        "staggered_start": 30.0
    }

-  **staggered\_start** - Spread the scraping and publishing of device
   data over approximately N seconds. Useful for working with many
   devices and the platform scrapes too many devices too quickly
   resulting in failed scrapes.

Each device configuration has the following form:

::

    {
        "driver_config": {"device_address": "<IP ADDRESS>"},
        "campus": "campus",
        "building": "building",
        "unit": "modbus1",
        "driver_type": "modbus",
        "registry_config":"/home/volttron-user/configs/catalyst371.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "Heartbeat"
    }

-  **driver\_config** - Driver specific setting go here. See the
   documentation for specific drivers for details.
-  **campus** - Campus portion of the device topic. (Optional, at least
   one must be specified, all device topics must be unique)
-  **building** - Building portion of the device topic. (Optional)
-  **unit** - Unit portion of the device topic. (Optional)
-  **path** - Additional topic bits after unit. Useful for specifying
   sub devices. (Optional)
-  **driver\_type** - Type of driver to use for this device.
-  **registry\_config** - Configuration file for registers on the
   device. See the documentation for specific drivers for details.
-  **interval** - Period which to scrape the device and publish the
   results.
-  **heart\_beat\_point** - Point (must exist in the registry) which to
   toggle to indicate a heartbeat to the device.

See Also
~~~~~~~~

-  `BACnet Driver <BACnet-Driver>`__
-  `Modbus Drivers <Modbus-Driver>`__

