.. _Fake-Driver:

===========
Fake Driver
===========

The FakeDriver is included as a way to quickly see data published to the message bus in a format
that mimics what a true Driver would produce.  This is an extremely simple implementation of the
:ref:`VOLTTRON driver framework <Driver-Framework>`.


Fake Device Driver Configuration
================================

This driver does not connect to any actual device and instead produces random and or pre-configured values.


Driver Config
-------------

There are no arguments for the `driver_config` section of the device configuration file. The `driver_config` entry must
still be present and should be left blank.

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

A sample fake device configuration file can be found in the VOLTTRON repository in
`examples/configurations/drivers/fake.config`

Fake Device Registry Configuration File
---------------------------------------

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row
configures a point on the device.

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this
      point.  For instance, if the `Volttron Point Name` is `HeatCall1` (and using the example device configuration
      above) then an agent would use `pnnl/isb2/hvac1/HeatCall1` to refer to the point when using the RPC interface of
      the actuator agent.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either `TRUE` or `FALSE`. Determines if the point can be written to.  Only points labeled `TRUE`
      can be written to through the ActuatorAgent.  Points labeled `TRUE` incorrectly will cause an error to be returned
      when an agent attempts to write to the point.


The following columns are optional:

    - **Starting Value** - Initial value for the point.  If the point is reverted it will change back to this value.  By
      default, points will start with a random value (1-100).
    - **Type** - Value type for the point.  Defaults to "string".  Valid types are:

        * string
        * integer
        * float
        * boolean

Any additional columns will be ignored.  It is common practice to include a `Point Name` or `Reference Point Name` to
include the device documentation's name for the point and `Notes` and `Unit Details` for additional information
about a point.  Please note that there is nothing in the driver that will enforce anything specified in the
`Unit Details` column.

.. csv-table:: BACnet
        :header: Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes

        Heartbeat,On/Off,On/Off,TRUE,0,boolean,Point for heartbeat toggle
        OutsideAirTemperature1,F,-100 to 300,FALSE,50,float,CO2 Reading 0.00-2000.0 ppm
        SampleWritableFloat1,PPM,10.00 (default),TRUE,10,float,Setpoint to enable demand control ventilation
        SampleLong1,Enumeration,1 through 13,FALSE,50,int,Status indicator of service switch
        SampleWritableShort1,%,0.00 to 100.00 (20 default),TRUE,20,int,Minimum damper position during the standard mode
        SampleBool1,On / Off,on/off,FALSE,TRUE,boolean,Status indicator of cooling stage 1
        SampleWritableBool1,On / Off,on/off,TRUE,TRUE,boolean,Status indicator

A sample fake registry configuration file can be found
`here <https://raw.githubusercontent.com/VOLTTRON/volttron/c57569bd9e71eb32afefe8687201d674651913ed/examples/configurations/drivers/fake.csv>`_
or in the VOLTTRON repository in ``examples/configurations/drivers/fake.csv``


.. _Fake-Driver-Install:

Installation
============

Installing a Fake driver in the :ref:`Platform Driver Agent <Platform-Driver>` requires adding copies of the device
configuration and registry configuration files to the Platform Driver's :ref:`configuration store <Configuration-Store>`

- Create a config directory (if one doesn't already exist) inside your Volttron repository:

.. code-block:: bash

    mkdir config

All local config files will be worked on here.

- Copy over the example config file and registry config file from the VOLTTRON repository:

.. code-block:: bash

    cp examples/configurations/drivers/fake.config config/
    cp examples/configurations/drivers/fake.csv config/

- Edit the driver config `fake.config` for the paths on your system:

.. code-block:: json

    {
        "driver_config": {},
        "registry_config": "config://fake.csv",
        "interval": 5,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat",
        "driver_type": "fakedriver",
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false
   	}

- Create a copy of the Platform Driver config from the VOLTTRON repository:

.. code-block:: bash

    cp examples/configurations/drivers/platform-driver.agent config/fake-platform-driver.config

- Add fake.csv and fake.config to the :ref:`configuration store <Configuration-Store>`:

.. code-block:: bash

    vctl config store platform.driver devices/campus/building/fake config/fake.config
    vcfl config store platform.driver fake.csv config/fake.csv --csv

- Edit `fake-platform-driver.config` to reflect paths on your system

.. code-block:: json

    {
        "driver_scrape_interval": 0.05
    }

- Use the scripts/install-agent.py script to install the Platform Driver agent:

.. code-block:: bash

    python scripts/install-agent.py -s services/core/PlatformDriverAgent -c config/fake-platform-driver.config

- If you have a :ref:`Listener Agent<Listener-Agent>` already installed, you should start seeing data being published to
  the bus.
