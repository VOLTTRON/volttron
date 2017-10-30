.. _BACnet-Driver:
BACnet Driver Configuration
---------------------------
Communicating with BACnet devices requires that the BACnet Proxy Agent is configured and running. All device communication happens through this agent.

driver_config
*************

There are seven arguments for the "driver_config" section of the device configuration file:

    - **device_address** - Address of the device. If the target device is behind an IP to MS/TP router then Remote Station addressing will probably be needed for the driver to find the device.
    - **device_id** - BACnet ID of the device. Used to establish a route to the device at startup.
    - **min_priority** - (Optional) Minimum priority value allowed for this device whether specifying the priority manually or via the registry config. Violating this parameter either in the configuration or when writing to the point will result in an error. Defaults to 8.
    - **max_per_request** - (Optional) Configure driver to manually segment read requests. The driver will only grab up to the number of objects specified in this setting at most per request. This setting is primarily for scraping many points off of low resource devices that do not support segmentation. Defaults to 10000.
    - **proxy_address** - (Optional) VIP address of the BACnet proxy. Defaults to "platform.bacnet_proxy". See :ref:`bacnet-proxy-multiple-networks` for details. Unless your BACnet network has special needs you should not change this value.
    - **ping_retry_interval** - (Optional) The driver will ping the device to establish a route at startup. If the BACnet proxy is not available the driver will retry the ping at this interval until it succeeds. Defaults to 5.
    - **use_read_multiple** - (Optional) During a scrape the driver will tell the proxy to use a ReadPropertyMultipleRequest to get data from the device. Otherwise the proxy will use multiple ReadPropertyRequest calls. If the BACnet proxy is reporting a device is rejecting requests try changing this to false for that device. Be aware that setting this to false will cause scrapes for that device to take much longer. Only change if needed. Defaults to true.

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
