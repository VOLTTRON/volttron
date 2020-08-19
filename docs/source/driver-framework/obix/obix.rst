.. _Obix-Driver:

===========
Obix Driver
===========


.. _Obix-Config:

Obix Driver Configuration
=========================

VOLTTRON's uses Obix's restful interface to facilitate communication.

This driver does *not* handle reading data from the history section of the interface.  If the user wants data published
from the management systems historical data use the :ref:`Obix History <Obix-History>` agent.


Driver Configuration
--------------------

There are three arguments for the ``driver_config`` section of the device configuration file:

    - ``url`` - URL of the Obix remote API interface
    - ``username`` - User's username for the Obix remote API
    - ``password`` - Users' password corresponding to the username

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {"url": "http://example.com/obix/config/Drivers/Obix/exports/",
                          "username": "username",
                          "password": "password"},
        "driver_type": "obix",
        "registry_config":"config://registry_configs/obix.csv",
        "interval": 	30,
        "timezone": "UTC"
    }

A sample Obix configuration file can be found in the VOLTTRON repository in
`examples/configurations/drivers/obix.config`


.. _Obix-Registry-Config:

Obix Registry Configuration File
--------------------------------

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row
configures a point on the device.

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this
      point. For instance, if the Volttron Point Name is HeatCall1 then an agent would use `<device topic>/HeatCall1`
      to refer to the point when using the RPC interface of the actuator agent.
    - **Obix Point Name** - Name of the point on the Obix interface. Escaping of spaces and dashes for use with the
      interface is handled internally.
    - **Obix Type** - One of `bool`, `int`, or `real`
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either `TRUE` or `FALSE`. Determines if the point can be written to. Only points labeled
      **TRUE** can be written to through the ActuatorAgent. This can be used to protect points that should not be
      accessed by the platform.

The following column is optional:

    - **Default Value** - The default value for the point. When the point is reverted by an agent it will change back to
      this value. If this value is missing it will revert to the last known value not set by an agent.

Any additional columns will be ignored. It is common practice to include a `Point Name` or `Reference Point Name` to
include the device documentation's name for the point and `Notes` and `Unit Details` for additional information
about a point.

The following is an example of a Obix registry configuration file:

.. csv-table:: Obix
        :header: Volttron Point Name,Obix Point Name,Obix Type,Units,Writable,Notes

        CostEL,CostEL,real,dollar,FALSE,Precision: 2
        CostELBB,CostELBB,real,dollar,FALSE,Precision: 2
        CDHEnergyHeartbeat,CDHEnergyHeartbeat,real,null,FALSE,
        ThermalFollowing,ThermalFollowing,bool,,FALSE,
        CDHTestThermFollow,CDHTestThermFollow,bool,,FALSE,
        CollegeModeFromCDH,CollegeModeFromCDH,real,null,FALSE,"Precision: 0, Min: 3.0, Max: 3.0"
        HospitalModeFromCDH,HospitalModeFromCDH,real,null,FALSE,"Precision: 0, Min: 3.0, Max: 3.0"
        HomeModeFromCDH,HomeModeFromCDH,real,null,FALSE,"Precision: 0, Min: 3.0, Max: 3.0"
        CostNG,CostNG,real,null,FALSE,Precision: 2
        CollegeBaseloadSPFromCDH,CollegeBaseloadSPFromCDH,real,kilowatt,FALSE,Precision: 0
        CollegeImportSPFromCDH,CollegeImportSPFromCDH,real,kilowatt,FALSE,Precision: 0
        HospitalImportSPFromCDH,HospitalImportSPFromCDH,real,kilowatt,FALSE,Precision: 0
        HospitalBaseloadSPFromCDH,HospitalBaseloadSPFromCDH,real,kilowatt,FALSE,Precision: 0
        HomeImportSPFromCDH,HomeImportSPFromCDH,real,kilowatt,FALSE,Precision: 0
        ThermalFollowingAlarm,ThermalFollowingAlarm,bool,,FALSE,

A sample Obix configuration can be found in the VOLTTRON repository in `examples/configurations/drivers/obix.csv`


.. _Obix-Auto-Configuration:

Automatic Obix Configuration File Creation
------------------------------------------

A script that will automatically create both a device and register configuration file for a site is located in the
repository at `scripts/obix/get_obix_driver_config.py`.

The utility is invoked with the command:

.. code-block:: bash

    python get_obix_driver_config.py <url> <registry_file> <driver_file> -u <username> -p <password>

If either the `registry_file` or `driver_file` is omitted the script will output those files to stdout.

If either the username or password arguments are left out the script will ask for them on the command line before
proceeding.

The registry file produced by this script assumes that the `Volttron Point Name` and the `Obix Point Name` have the same
value.  Also, it is assumed that all points should be read only.  Users are expected to fix this as appropriate.
