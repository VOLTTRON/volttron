.. _MODBUS-config:

Modbus Driver Configuration
---------------------------
VOLTTRON's modbus driver supports the Modbus over TCP/IP protocol only. For Modbus RTU support,
see VOLTTRON's modbus-tk driver.

Requirements
------------
The Modbus driver requires the pymodbus package. This package can be installed in an
activated environment with:

::

    pip install pymodbus

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

A sample MODBUS configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/modbus.config``


.. _MODBUS-Driver:

Modbus Registry Configuration File
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
    - **Mixed Endian** - (Optional) Either "TRUE" or "FALSE". For mixed endian values. This will reverse the order of the MODBUS registers that make up this point before parsing the value or writing it out to the device. Has no effect on bit values.

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
