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
        "publish_depth_first_all": true,
        "group_offset_interval": 0.0
    }

* **driver_scrape_interval** - Sets the interval between devices scrapes. Defaults to 0.02 or 50 devices per second. Useful for when the platform scrapes too many devices at once resulting in failed scrapes.
* **group_offset_interval** - Sets the interval between when groups of devices are scraped. Has no effect if all devices are in the same group.

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
        "heart_beat_point": "heartbeat",
        "group": 0
    }

The following settings are required for all device configurations:

    - **driver_config** - Driver specific setting go here. See below for driver specific settings.
    - **driver_type** - Type of driver to use for this device: bacnet, modbus, fake, etc.
    - **registry_config** - Reference to a configuration file in the configuration store for registers
      on the device. See the `Registry Configuration File`_
      and `Adding Device Configurations to the Configuration Store`_ sections below.

These settings are optional:

    - **interval** - Period which to scrape the device and publish the results in seconds. Defaults to 60 seconds.
    - **heart_beat_point** - A Point which to toggle to indicate a heartbeat to the device. A point with this Volttron Point Name must exist in the registry. If this setting is missing the driver will not send a heart beat signal to the device. Heart beats are triggered by the Actuator Agent which must be running to use this feature.
    - **group** - Group this device belongs to. Defaults to 0

These settings are used to create the topic that this device will be referenced by following the VOLTTRON convention of {campus}/{building}/{unit}. This will also be the topic published on, when the device is periodically scraped for it's current state.

The topic used to reference the device is derived from the name of the device configuration in the store. See the  `Adding Device Configurations to the Configuration Store`_ section.

Device Grouping
...............

Devices may be placed into groups to separate them logically when they are scraped. This is done by setting the `group` in the device configuration. `group` is a number greater than or equal to 0.
Only number of devices in the same group and the `group_offset_interval` are considered when determining when to scrape a device.

This is useful in two cases. First, if you need to ensure that certain devices are scraped in close proximity to each other you can put them in their own group.
If this causes devices to be scraped too quickly the groups can be separated out time wise using the `group_offset_interval` setting.
Second, you may scrape devices on different networks in parallel for performance. For instance BACnet devices behind a single MSTP router need to be scraped slowly and serially, but devices behind different routers may be scraped in parallel. Grouping devices by router will do this automatically.

The `group_offset_interval` is applied by multiplying it by the `group` number. If you intent to use `group_offset_interval` only use consecutive `group` values that start with 0.


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
