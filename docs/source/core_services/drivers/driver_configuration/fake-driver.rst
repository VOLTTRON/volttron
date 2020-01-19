.. _Fake-Driver:
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
