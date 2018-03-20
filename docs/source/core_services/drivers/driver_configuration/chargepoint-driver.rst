.. _Chargepoint-config:
Chargepoint Driver Configuration
--------------------------------

The chargepoint driver requires at least one additional python library and has its own ``requirements.txt``.
Make sure to run ``pip install -r <chargepoint driver path>/requirements.txt`` before using this driver.


driver_config
*************

There are three arguments for the **driver_config** section of the device configuration file:

    - **stationID** - Chargepoint ID of the station. This format is ususally '1:00001'
    - **username** - Login credentials for the Chargepoint API
    - **password** - Login credentials for the Chargepoint API

The Chargepoint login credentials are generated in the Chargepoint web portal and require
a chargepoint account with sufficient privileges.  Station IDs are also available on
the web portal.

Here is an example device configuration file:

.. code-block:: json

    {
        "driver_config": {"stationID": "3:12345",
                          "username": "4b90fc0ae5fe8b6628e50af1215d4fcf5743a6f3c63ee1464012875",
                          "password": "ebaf1a3cdfb80baf5b274bdf831e2648"},
        "driver_type": "chargepoint",
        "registry_config":"config://chargepoint.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "heartbeat"
    }

A sample Chargepoint configuration file can be found in the VOLTTRON repository in ``examples/configurations/drivers/chargepoint1.config``


.. _Chargepoint-Driver:
Chargepoint Registry Configuration File
***************************************

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device.

The following columns are required for each row:

    - **Volttron Point Name** - The name by which the platform and agents running on the platform will refer to this point.
    - **Attribute Name** - Chargepoint API attribute name. This determines the field that will be read from the API response and must be one of the allowed values.
    - **Port #** - If the point describes a specific port on the Chargestation, it is defined here. (Note 0 and an empty value are equivalent.)
    - **Type** - Python type of the point value.
    - **Units** - Used for meta data when creating point information on the historian.
    - **Writable** - Either "TRUE" or "FALSE". Determines if the point can be written to. Only points labeled TRUE can be written.
    - **Notes** - Miscellaneous notes field.
    - **Register Name** - A string representing how to interpret the data register. Acceptable values are:
        * StationRegister
        * StationStatusRegister
        * LoadRegister
        * AlarmRegister
        * StationRightsRegister
    - **Starting Value** - Default value for writeable points. Read-only points should not have a value in this column.

Detailed descriptions for all available chargepoint registers may be found in the ``README.rst`` in the
chargepoint driver directory.

A sample Chargepoint registry file can be found in the VOLTTRON repository in ``examples/configurations/drivers/chargepoint.csv``
