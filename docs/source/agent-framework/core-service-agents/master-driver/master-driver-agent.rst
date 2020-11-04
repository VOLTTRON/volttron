.. _Master-Driver-Agent:

===================
Master Driver Agent
===================

The Master Driver Agent manages all device communication.  To communicate with devices you must setup and deploy the
Master Driver Agent.  For more information on the Master Driver Agent's operations, read about the
:ref:`Master Driver <Master-Driver>` in the driver framework docs.


.. _Master-Driver-Config:

Configuring the Master Driver
=============================

The Master Driver like all other agents, requires a configuration file (described in brief below).  Once the user
has copied the example or created their own config, the Master Driver Agent is deployed in a manner similar to any other
agent:

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

.. code-block:: bash

   python bootstrap.py --drivers


Master Driver Agent Configuration
---------------------------------

The Master Driver Agent configuration consists of general settings for all devices. The default values of the Master
Driver should be sufficient for most users.

.. code-block:: json

    {
        "driver_scrape_interval": 0.05,
        "publish_breadth_first_all": false,
        "publish_depth_first": false,
        "publish_breadth_first": false
    }


The example master driver configuration file above can be found in the VOLTTRON repository in
`services/core/MasterDriverAgent/master-driver.agent`.

For information on configuring the Master Driver with devices, including creating driver configs and using the config
store, please read ref`configuration <Master-Driver-Configuration>` the section in the Driver Framework docs.


.. toctree::

   global-override-specification
