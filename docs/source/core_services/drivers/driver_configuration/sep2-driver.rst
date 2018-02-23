.. _SEP2-Driver-Config:
SEP2 Driver Configuration
-------------------------

Communicating with SEP2 devices requires that the SEP2 Agent is configured and running.
All device communication happens through this agent. For information about the SEP2 Agent,
please see :ref:`SEP-2`.

driver_config
*************

There are two arguments for the "driver_config" section of the SEP2 device configuration file:

    - **sfdi** - Short-form device ID of the SEP2 device.
    - **sep2_agent_id** - ID of VOLTTRON's SEP2 agent.

Here is a sample SEP2 device configuration file:

.. code-block:: json

    {
        "driver_config": {
            "sfdi": "097935300833",
            "sep2_agent_id": "sep2agent"
        },
        "campus": "campus",
        "building": "building",
        "unit": "sep2",
        "driver_type": "sep2",
        "registry_config": "config://sep2.csv",
        "interval": 15,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat"
    }

A sample SEP2 driver configuration file can be found in the VOLTTRON repository
in ``services/core/MasterDriverAgent/example_configurations/test_sep2_1.config``.

.. _SEP2-Driver:
SEP2 Registry Configuration File
********************************

For a description of SEP2 registry values, see :ref:`SEP-2`.

A sample SEP2 registry configuration file can be found in the VOLTTRON repository
in ``services/core/MasterDriverAgent/example_configurations/sep2.csv``.
