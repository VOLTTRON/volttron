.. _Platform-Driver:

===============
Platform Driver
===============

The Platform Driver agent is a special purpose agent a user can install on the platform to manage communication of
the platform with devices.  The Master driver features a number of endpoints for collecting data and sending control
signals using the message bus and automatically publishes data to the bus on a specified interval.


How does it work?
=================

The Platform Driver creates a number of driver instances based on the contents of its config store; for each
combination of driver configuration, registry configuration and other referenced config files, a driver instance is
created by the Platform Driver.  When configuration files are removed, the corresponding driver instance is removed by the
Platform Driver.

Drivers are special-purpose agents for device communication, and unlike most agents, run
as separate threads under the Platform Driver (typically agents are spawned as their own process).  While running, the
driver periodically "scrapes" device data and publishes the scrape to the message bus, as well as handling ad-hoc data
collection and control signalling commands issued from the Platform Driver.  The actual commands are issued to devices by
the driver's "Interface" class.

An Interface class is a Python class which serves as the interface between the driver and the device.  The Interface
does this by implementing a set of well-defined actions using the communication paradigms and protocols used by the
device.  For devices such as BACnet and Modbus devices, interfaces wrap certain protocol functions in Python code to be
used by the driver.  In other cases, interfaces interact with web-API's, etc.


Device/Driver Communication
---------------------------

Device communication with the Platform Driver typically occurs using the following steps:

#. Platform agents and the user's agents communicate between themselves and the message bus using publish/subscribe or
   JSON-RPC
#. The user's agent sends a JSON-RPC request to the Platform Driver to `get_point`
#. And/Or the user's agent sends a JSON-RPC request to the Actuator to `set_point`
#. The Platform Driver forwards the request to the driver instance specified in the request
#. The device driver communicates with the end device
#. The end device returns a response to the driver indicating its current status
#. The driver publishes the device's response to the message bus using a publish

For more in-depth descriptions and coverage of atypical scenarios, read up on
:ref:`the driver communication patterns <Driver_Communication>`.


.. _Platform-Driver-Configuration:

Configuration and Installation
==============================

Configuration for each device consists of 3 parts:

* Platform Driver Agent configuration file - lists all driver configuration files to load
* Driver configuration file - contains the general driver configuration and device settings
* Device Register configuration file - contains the settings for each individual data point on the device

For each device, you must create a driver configuration file, device register configuration file, and an entry in the
Platform Driver Agent configuration file.

Once configured, the Platform Driver Agent is configured and deployed in a manner similar to any other agent:

.. code-block:: bash

    python scripts/install-agent.py -s services/core/PlatformDriverAgent -c <platform driver config file>


Requirements
------------

VOLTTRON drivers operated by the platform driver may have additional requirements for installation.
Required libraries:

::

    BACnet driver - bacpypes
    Modbus driver - pymodbus
    Modbus_TK driver - modbus-tk
    DNP3 and IEEE 2030.5 drivers - pydnp3

The easiest way to install the requirements for drivers included in the VOLTTRON repository is to use ``bootstrap.py``
(see :ref:`platform installation for more detail <Platform-Installation>`)


Platform Driver Configuration
=============================

The Platform Driver Agent configuration consists of general settings for all devices. The default values of the Master
Driver should be sufficient for most users.  The user may optionally change the interval between device scrapes with the
driver_scrape_interval.

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

* **driver_scrape_interval** - Sets the interval between devices scrapes. Defaults to 0.02 or 50 devices per second.
  Useful for when the platform scrapes too many devices at once resulting in failed scrapes.
* **group_offset_interval** - Sets the interval between when groups of devices are scraped. Has no effect if all devices
  are in the same group.

In order to improve the scalability of the platform unneeded device state publishes for all devices can be turned off.
All of the following setting are optional and default to `True`.

* **publish_depth_first_all** - Enable "depth first" publish of all points to a single topic for all devices.
* **publish_breadth_first_all** - Enable "breadth first" publish of all points to a single topic for all devices.
* **publish_depth_first** - Enable "depth first" device state publishes for each register on the device for all devices.
* **publish_breadth_first** - Enable "breadth first" device state publishes for each register on the device for all
  devices.

An example platform driver configuration file can be found in the VOLTTRON repository in
`services/core/PlatformDriverAgent/platform-driver.agent`.


.. _Driver-Configuration-File:

Driver Configuration File
-------------------------

.. note::

    The terms `register` and `point` are used interchangeably in the documentation and in the configuration setting
    names.  They have the same meaning in the context of VOLTTRON drivers.

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
      on the device. See the `Registry-Configuration-File`_ section below or
      and the :ref:`Adding Device Configurations to the Configuration Store <Adding-Devices-To-Config-Store>` section in
      the driver framework docs.

These settings are optional:

    - **interval** - Period which to scrape the device and publish the results in seconds. Defaults to 60 seconds.
    - **heart_beat_point** - A Point which to toggle to indicate a heartbeat to the device. A point with this ``Volttron
      Point Name`` must exist in the registry.  If this setting is missing the driver will not send a heart beat signal
      to the device.  Heart beats are triggered by the :ref:`Actuator Agent <Actuator-Agent>` which must be running to
      use this feature.
    - **group** - Group this device belongs to. Defaults to 0

These settings are used to create the topic that this device will be referenced by following the VOLTTRON convention of
``{campus}/{building}/{unit}``.  This will also be the topic published on, when the device is periodically scraped for
it's current state.

The topic used to reference the device is derived from the name of the device configuration in the store. See the
:ref:`Adding Device Configurations to the Configuration Store <Adding-Devices-To-Config-Store>` section of the driver
framework docs.


Device Grouping
^^^^^^^^^^^^^^^

Devices may be placed into groups to separate them logically when they are scraped. This is done by setting the `group`
in the device configuration. `group` is a number greater than or equal to 0.  Only number of devices in the same group
and the `group_offset_interval` are considered when determining when to scrape a device.

This is useful in two cases:

* If you need to ensure that certain devices are scraped in close proximity to each other you can put them in their own
  group.  If this causes devices to be scraped too quickly the groups can be separated out time wise using the
  `group_offset_interval` setting.
* You may scrape devices on different networks in parallel for performance.  For instance BACnet devices behind a single
  MSTP router need to be scraped slowly and serially, but devices behind different routers may be scraped in parallel.
  Grouping devices by router will do this automatically.

The `group_offset_interval` is applied by multiplying it by the `group` number. If you intend to use
`group_offset_interval` only use consecutive `group` values that start with 0.


.. _Registry-Configuration-File:

Registry Configuration File
---------------------------
Registry configuration files setup each individual point on a device. Typically this file will be in CSV format, but the
exact format is driver specific.  See the section for a particular driver for the registry configuration format.

The following is a simple example of a Modbus registry configuration file:

.. csv-table:: Catalyst 371
    :header: Reference Point Name,Volttron Point Name,Units,Units Details,Modbus Register,Writable,Point Address,Default Value,Notes

    CO2Sensor,ReturnAirCO2,PPM,0.00-2000.00,>f,FALSE,1001,,CO2 Reading 0.00-2000.0 ppm
    CO2Stpt,ReturnAirCO2Stpt,PPM,1000.00 (default),>f,TRUE,1011,1000,Setpoint to enable demand control ventilation
    HeatCall2,HeatCall2,On / Off,on/off,BOOL,FALSE,1114,,Status indicator of heating stage 2 need


.. _Adding-Devices-To-Config-Store:

Adding Device Configurations to the Configuration Store
-------------------------------------------------------

Configurations are added to the Configuration Store using the command line:

.. code-block:: bash

    volttron-ctl config store platform.driver <name> <file name> <file type>

* **name** - The name used to refer to the file from the store.
* **file name** - A file containing the contents of the configuration.
* **file type** - ``--raw``, ``--json``, or ``--csv``. Indicates the type of the file. Defaults to ``--json``.

The main configuration must have the name ``config``

Device configuration but **not** registry configurations must have a name prefixed with ``devices/``.  Scripts that
automate the process will prefix registry configurations with ``registry_configs/``, but that is not a requirement for
registry files.

The name of the device's configuration in the store is used to create the topic used to reference the device. For
instance, a configuration named `devices/PNNL/ISB1/vav1` will publish scrape results to `devices/PNNL/ISB1/vav1` and
is accessible with the Actuator Agent via `PNNL/ISB1/vav1`.

The name of a registry configuration must match the name used to refer to it in the driver configuration.  The reference
is not case sensitive.

If the Platform Driver Agent is running any changes to the configuration store will immediately affect the running devices
according to the changes.

Example
^^^^^^^

Consider the following three configuration files:  A platform driver configuration called `platform-driver.agent`, a
Modbus device configuration file called `modbus_driver.config` and corresponding Modbus registry configuration file called
`modbus_registry.csv`

To store the platform driver configuration run the command:

.. code-block:: bash

    volttron-ctl config store platform.driver config platform-driver.agent

To store the registry configuration run the command (note the ``--csv`` option):

.. code-block:: bash

    volttron-ctl config store platform.driver registry_configs/modbus_registry.csv modbus_registry.csv --csv

.. Note::

    The `registry_configs/modbus_registry.csv` argument in the above command must match the reference to the
    `registry_config` found in `modbus_driver.config`.

To store the driver configuration run the command:

.. code-block:: bash

    volttron-ctl config store platform.driver devices/my_campus/my_building/my_device modbus_config.config


Converting Old Style Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The new Platform Driver no longer supports the old style of device configuration.  The old `device_list` setting is
ignored.

To simplify updating to the new format `scripts/update_platform_driver_config.py` is provide to automatically update to
the new configuration format.

With the platform running run:

.. code-block:: bash

    python scripts/update_platform_driver_config.py <old configuration> <output>

old_configuration`` is the main configuration file in the old format. The script automatically modifies the driver
files to create references to CSV files and adds the CSV files with the appropriate name.

`output` is the target output directory.

If the ``--keep-old`` switch is used the old configurations in the output directory (if any) will not be deleted before
new configurations are created.  Matching names will still be overwritten.

The output from `scripts/update_platform_driver_config.py` can be automatically added to the configuration store
for the Platform Driver agent with `scripts/install_platform_driver_configs.py`.

Creating and naming configuration files in the form needed by `scripts/install_platform_driver_configs.py` can speed up
the process of changing and updating a large number of configurations. See the ``--help`` message for
`scripts/install_platform_driver_configs.py` for more details.


Device Scalability Settings
---------------------------

In order to improve the scalability of the platform unneeded device state publishes for a device can be turned off.
All of the following setting are optional and will override the value set in the main platform driver configuration.

    - **publish_depth_first_all** - Enable "depth first" publish of all points to a single topic.
    - **publish_breadth_first_all** - Enable "breadth first" publish of all points to a single topic.
    - **publish_depth_first** - Enable "depth first" device state publishes for each register on the device.
    - **publish_breadth_first** - Enable "breadth first" device state publishes for each register on the device.

It is common practice to set `publish_breadth_first_all`, `publish_depth_first`, and
`publish_breadth_first` to `False` unless they are specifically needed by an agent running on
the platform.


.. note::

    All Historian Agents require `publish_depth_first_all` to be set to `True` in order to capture data.


Usage
=====

After installing the Platform Driver and loading driver configs into the config store, the installed drivers begin
polling and JSON-RPC endpoints become usable.


.. _Device-State-Publish:

Polling
-------

Once running, the Platform Driver will spawn drivers using the `driver_type` parameter of the
:ref:`driver configuration <Driver-Configuration-File>` and periodically poll devices for all point data specified in
the :ref:`registry configuration <Registry-Configuration-File>` (at the interval specified by the interval parameter
of the driver configuration).

By default, the value of each register on a device is published 4 different ways when the device state is published.
Consider the following settings in a driver configuration stored under the name ``devices/pnnl/isb1/vav1``:

.. code-block:: json

    {
        "driver_config": {"device_address": "10.1.1.5",
                          "device_id": 500},

        "driver_type": "bacnet",
        "registry_config":"config://registry_configs/vav.csv",
    }

In the `vav.csv` file is a register with the name `temperature`.  For these examples the current value of the
register on the device happens to be 75.2 and the meta data is

.. code-block:: json

    {"units": "F"}

When the driver publishes the device state the following 2 things will be published for this register:

    A "depth first" publish to the topic `devices/pnnl/isb1/vav1/temperature` with the following message:

        .. code-block:: python

            [75.2, {"units": "F"}]

    A "breadth first" publish to the topic `devices/temperature/vav1/isb1/pnnl` with the following message:

        .. code-block:: python

            [75.2, {"units": "F"}]

    These publishes can be turned off by setting `publish_depth_first` and `publish_breadth_first` to `false`
    respectively.

Also these two publishes happen once for all registers:

    A "depth first" publish to the topic `devices/pnnl/isb1/vav1/all` with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

    A "breadth first" publish to the topic `devices/all/vav1/isb1/pnnl` with the following message:

        .. code-block:: python

            [{"temperature": 75.2, ...}, {"temperature":{"units": "F"}, ...}]

    These publishes can be turned off by setting `publish_depth_first_all` and `publish_breadth_first_all` to
    ``false`` respectively.


JSON-RPC Endpoints
------------------

**get_point** - Returns the value of specified device set point

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)
        - **point_name** - name of device point from registry configuration file

**set_point** - Set value on specified device set point. If global override is condition is set, raise OverrideError
  exception.

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)
        - **point_name** - name of device point from registry configuration file
        - **value** - desired value to set for point on device

    .. warning::

        It is not recommended to call the `set_point` method directly.  It is recommended to instead use the
        :ref:`Actuator <Actuator-Agent>` agent to set points on a device, using its scheduling capability.

**scrape_all** - Returns values for all set points on the specified device.

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)

**get_multiple_points** - return values corresponding to multiple points on the same device

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)
        - **point_names** - iterable of device point names from registry configuration file

**set_multiple_points** - Set values on multiple set points at once.  If global override is condition is set, raise
  OverrideError exception.

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)
        - **point_names_value** - list of tuples consisting of (point_name, value) pairs for setting a series of
          points

**heart_beat** - Send a heartbeat/keep-alive signal to all devices configured for Platform Driver

**revert_point** - Revert the set point of a device to its default state/value.  If global override is condition is
  set, raise OverrideError exception.

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)
        - **point_name** - name of device point from registry configuration file

**revert_device** - Revert all the set point values of the device to default state/values.  If global override is
  condition is set, raise OverrideError exception.

    Parameters
        - **path** - device topic string (typical format is devices/campus/building/device)

**set_override_on** - Turn on override condition on all the devices matching the specified pattern (
  :ref:`override docs <Platform-Driver-Override>`)

    Parameters
        - **pattern** - Override pattern to be applied. For example,
            - If pattern is `campus/building1/*` - Override condition is applied for all the devices under
              `campus/building1/`.
            - If pattern is `campus/building1/ahu1` - Override condition is applied for only `campus/building1/ahu1`
              The pattern matching is based on bash style filename matching semantics.
        - **duration** - Duration in seconds for the override condition to be set on the device (default 0.0,
          duration <= 0.0 imply indefinite duration)
        - **failsafe_revert** - Flag to indicate if all the devices falling under the override condition must to be
          set
          to its default state/value immediately.
        - **staggered_revert** -

**set_override_off** - Turn off override condition on all the devices matching the pattern.

    Parameters
        - **pattern** - device topic pattern for devices on which the override condition should be removed.

**get_override_devices** - Get a list of all the devices with override condition.

**clear_overrides** - Turn off override condition for all points on all devices.

**get_override_patterns** - Get a list of all override condition patterns currently set.


.. _Platform-Driver-Override:

Driver Override Condition
=========================

By default, every user is allowed write access to the devices by the platform driver.  The override feature will allow the
user (for example, building administrator) to override this default behavior and enable the user to lock the write
access on the devices for a specified duration of time or indefinitely.


Set Override On
---------------

The Platform Driver's ``set_override_on`` RPC method can be used to set the override condition for all drivers with topic
matching the provided pattern.  This can be specific devices, groups of devices, or even all configured devices.  The
pattern matching is based on bash style filename matching semantics.

Parameters:

     - pattern:  Override pattern to be applied. For example,
        * If the pattern is ``campus/building1/*`` the override condition is applied for all the devices under
          `campus/building1/`.
        * If the pattern is ``campus/building1/ahu1`` the override condition is applied for only the
          `campus/building1/ahu1` device. The pattern matching is based on bash style filename matching semantics.
     - duration:  Time duration for the override in seconds. If duration <= 0.0, it implies an indefinite duration.
     - failsafe_revert:  Flag to indicate if all the devices falling under the override condition has to be set to its
       default state/value immediately.
     - staggered_revert: If this flag is set, reverting of devices will be staggered.

Example ``set_override_on`` RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "set_override_on", <override pattern>, <override duration>)


Set Override Off
----------------

The override condition can also be toggled off based on a provided pattern using the Platform Driver's
``set_override_off`` RPC call.

Parameters:

     - pattern:  Override pattern to be applied. For example,
        * If the pattern is ``campus/building1/*`` the override condition is removed for all the devices under
          `campus/building1/`.
        * If the pattern is ``campus/building1/ahu1`` the override condition is removed for only for the
          `campus/building1/ahu1` device. The pattern matching is based on bash style filename matching semantics.

Example ``set_override_off`` RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "set_override_off", <override pattern>)


Get Override Devices
--------------------

A list of all overridden devices can be obtained with the Platform Driver's ``get_override_devices`` RPC call.

This method call has no additional parameters.

Example ``get_override_devices`` RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices")


Get Override Patterns
---------------------

A list of all patterns which have been requested for override can be obtained with the Platform Driver's
``get_override_patterns`` RPC call.

This method call has no additional parameters

Example "get_override_patterns" RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "get_override_patterns")


Clear Overrides
---------------

All overrides set by RPC calls described above can be toggled off at using a single ``clear_overrides`` RPC call.

This method call has no additional parameters

Example "clear_overrides" RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "clear_overrides")

For information on the global override feature specification, view the
:ref:`Global Override Specification <Global-Override-Specification>` doc.
