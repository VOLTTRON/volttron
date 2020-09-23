.. _IEEE2030_5-Driver:

================================
IEEE 2030.5 Driver Configuration
================================

Communicating with IEEE 2030.5 devices requires that the IEEE 2030.5 Agent is configured and running.
All device communication happens through this agent. For information about the IEEE 2030.5 Agent,
please see :ref:`IEEE 2030.5 Agent <IEEE2030_5-Agent>` docs.


Driver Config
=============

There are two arguments for the `driver_config` section of the IEEE 2030.5 device configuration file:

    - **sfdi** - Short-form device ID of the IEEE 2030.5 device.
    - **ieee2030_5_agent_id** - ID of VOLTTRON's IEEE 2030.5 agent.

Here is a sample IEEE 2030.5 device configuration file:

.. code-block:: json

    {
        "driver_config": {
            "sfdi": "097935300833",
            "IEEE2030_5_agent_id": "iee2030_5agent"
        },
        "campus": "campus",
        "building": "building",
        "unit": "IEEE2030_5",
        "driver_type": "ieee2030_5",
        "registry_config": "config://ieee2030_5.csv",
        "interval": 15,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat"
    }

A sample IEEE 2030.5 driver configuration file can be found in the VOLTTRON repository
in ``services/core/MasterDriverAgent/example_configurations/test_ieee2030_5_1.config``.

Registry Configuration File
===========================

For a description of IEEE 2030.5 registry values, see :ref:`IEEE2030_5-Agent`.

A sample IEEE 2030.5 registry configuration file can be found in the VOLTTRON repository
in ``services/core/MasterDriverAgent/example_configurations/ieee2030_5.csv``.

View the :ref:`IEEE 2030.5 agent specification document <IEEE2030_5-Specification>` to learn more about IEEE 2030.5 and
the IEEE 2030.5 agent and driver.
