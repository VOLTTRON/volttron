.. _Platform-Driver-Agent:

===================
Platform Driver Agent
===================

The Platform Driver Agent manages all device communication.  To communicate with devices you must setup and deploy the
Platform Driver Agent.  For more information on the Platform Driver Agent's operations, read about the
:ref:`Platform Driver <Platform-Driver>` in the driver framework docs.


.. _Platform-Driver-Config:

Configuring the Platform Driver
=============================

The Platform Driver requires a configuration file (described in brief below) to set global settings for all drivers.  Once
the user has copied the example or created their own config, the Platform Driver Agent is deployed with this command:

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

.. code-block:: bash

   python bootstrap.py --drivers


Platform Driver Agent Configuration
---------------------------------

The Platform Driver Agent configuration consists of general settings for all devices. Below is an example config from the
repository:

.. code-block:: json

    {
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false
    }


The example platform driver configuration file above can be found in the VOLTTRON repository in
`services/core/PlatformDriverAgent/platform-driver.agent`.

For information on configuring the Platform Driver with devices, including creating driver configs and using the config
store, please read ref`configuration <Platform-Driver-Configuration>` the section in the Driver Framework docs.


.. toctree::

   global-override-specification
