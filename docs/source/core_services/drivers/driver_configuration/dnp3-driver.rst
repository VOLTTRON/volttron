.. _DNP3-Driver-Config:
DNP3 Driver Configuration
-------------------------

VOLTTRON's DNP3 driver enables the use
of `DNP3 <https://en.wikipedia.org/wiki/DNP3>`_ (Distributed Network Protocol)
communications, reading and writing points via a DNP3 Outstation.

In order to use a DNP3 driver to read and write point data, VOLTTRON's DNP3Agent must also
be configured and running. All communication between the VOLTTRON Outstation and a
DNP3 Master happens through this DNP3Agent.
For information about the DNP3Agent, please see the :ref:`DNP3 Platform Specification <DNP3>`.

driver_config
*************

There is one argument for the "driver_config" section of the DNP3 driver configuration file:

    - **dnp3_agent_id** - ID of VOLTTRON's DNP3Agent.

Here is a sample DNP3 driver configuration file:

.. code-block:: json

    {
        "driver_config": {
            "dnp3_agent_id": "dnp3agent"
        },
        "campus": "campus",
        "building": "building",
        "unit": "dnp3",
        "driver_type": "dnp3",
        "registry_config": "config://dnp3.csv",
        "interval": 15,
        "timezone": "US/Pacific",
        "heart_beat_point": "Heartbeat"
    }

A sample DNP3 driver configuration file can be found in the VOLTTRON repository
in ``services/core/MasterDriverAgent/example_configurations/test_dnp3.config``.

.. _DNP3-Driver:
DNP3 Registry Configuration File
********************************

The driver's registry configuration file, a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file,
specifies which DNP3 points the driver will read and/or write. Each row configures a single DNP3 point.

The following columns are required for each row:

    - **Volttron Point Name** - The name used by the VOLTTRON platform and agents to refer to the point.
    - **Group** - The point's DNP3 group number.
    - **Index** - The point's index number within its DNP3 data type (which is derived from its DNP3 group number).
    - **Scaling** - A factor by which to multiply point values.
    - **Units** - Point value units.
    - **Writable** - TRUE or FALSE, indicating whether the point can be written by the driver (FALSE = read-only).

Consult the **DNP3 data dictionary** for a point's Group and Index values. Point
definitions in the data dictionary are by agreement between the DNP3 Outstation and Master.
The VOLTTRON DNP3Agent loads the data dictionary of point definitions from the JSON file
at "point_definitions_path" in the DNP3Agent's config file.

A sample data dictionary is available in ``services/core/DNP3Agent/dnp3/mesa_points.config``.

Point definitions in the DNP3 driver's registry should look something like this:

.. code-block:: csv

    Volttron Point Name,Group,Index,Scaling,Units,Writable
    DCHD.WTgt,41,65,1.0,NA,FALSE
    DCHD.WTgt-In,30,90,1.0,NA,TRUE
    DCHD.WinTms,41,66,1.0,NA,FALSE
    DCHD.RmpTms,41,67,1.0,NA,FALSE

A sample DNP3 driver registry configuration file is available
in ``services/core/MasterDriverAgent/example_configurations/dnp3.csv``.
