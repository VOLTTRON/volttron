.. _Master-Driver-Configuration:

===================
Master Driver Agent
===================

The Master Driver Agent manages all device communication.  To communicate with devices you must setup and deploy the
Master Driver Agent.  For more information on the Master Driver Agent's operations, read about the
:ref:`Master Driver <Master-Driver>` in the driver framework docs.


.. _Master-Driver-Config:

Configuring the Master Driver
=============================

Configuration for each device consists of 3 parts:

* Master Driver Agent configuration file - lists all driver configuration files to load
* Driver configuration file - contains the general driver configuration and device settings
* Device Register configuration file - contains the settings for each individual data point on the device

For each device, you must create a driver configuration file, device register configuration file, and an entry in the
Master Driver Agent configuration file.

Once configured, the Master Driver Agent is configured and deployed in a manner similar to any other agent:

.. code-block:: bash

    python scripts/install-agent.py -s services/core/MasterDriverAgent -c <master driver config file>


Requirements
------------

VOLTTRON drivers operated by the master driver may have additional requirements for installation.
Required libraries:

::

    BACnet driver - bacpypes
    Modbus driver - pymodbus
    Modbus_TK driver - modbus-tk
    DNP3 and IEEE 2030.5 drivers - pydnp3

The easiest way to install the requirements for drivers included in the VOLTTRON repository is to use ``bootstrap.py``
(see :ref:`platform installation for more detail <Platform-Installation>`)


Master Driver Agent Configuration
---------------------------------

The Master Driver Agent configuration consists of general settings for all devices. The default values of the Master
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

An example master driver configuration file can be found in the VOLTTRON repository in
`services/core/MasterDriverAgent/master-driver.agent`.


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


.. _Device-State-Publish:

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


Device Scalability Settings
---------------------------

In order to improve the scalability of the platform unneeded device state publishes for a device can be turned off.
All of the following setting are optional and will override the value set in the main master driver configuration.

    - **publish_depth_first_all** - Enable "depth first" publish of all points to a single topic.
    - **publish_breadth_first_all** - Enable "breadth first" publish of all points to a single topic.
    - **publish_depth_first** - Enable "depth first" device state publishes for each register on the device.
    - **publish_breadth_first** - Enable "breadth first" device state publishes for each register on the device.

It is common practice to set `publish_breadth_first_all`, `publish_depth_first`, and
`publish_breadth_first` to `False` unless they are specifically needed by an agent running on
the platform.


.. note::

    All Historian Agents require `publish_depth_first_all` to be set to `True` in order to capture data.


.. _Master-Driver-Override:

Master Driver Override
======================

By default, every user is allowed write access to the devices by the master driver.  The override feature will allow the
user (for example, building administrator) to override this default behavior and enable the user to lock the write
access on the devices for a specified duration of time or indefinitely.


Set Override On
---------------

The Master Driver's ``set_override_on`` RPC method can be used to set the override condition for all drivers with topic
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

The override condition can also be toggled off based on a provided pattern using the Master Driver's
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

A list of all overridden devices can be obtained with the Master Driver's ``get_override_devices`` RPC call.

This method call has no additional parameters.

Example ``get_override_devices`` RPC call:

.. code-block:: python

    self.vip.rpc.call(PLATFORM_DRIVER, "get_override_devices")


Get Override Patterns
---------------------

A list of all patterns which have been requested for override can be obtained with the Master Driver's
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

For more information, view the :ref:`Global Override Specification <Global-Override-Specification>`


.. toctree::

   global-override-specification
