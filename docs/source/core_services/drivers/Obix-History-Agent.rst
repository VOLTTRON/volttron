.. _Obix-history:

Obix History Agent
------------------

The Obix History Agent captures data history data from an Obix RESTful interface and publishes
it to the message bus like a driver for capture by agents and historians. The Agent will setup
its queries to ensure that data is only publishes once. For points queried for the first time
it will go back in time and publish old data as configured. 

The data will be colated into device all publishs automatically and will use a timestamp in the
header based on the timestamps reported by the Obix interface. The publishes will be made in chronological order.

Units data is automatically read from the device.

For sending commands to devices see :ref:`Obix-config`.

Agent Configuration
*******************

There are three arguments for the **driver_config** section of the device configuration file:

    - **url** - URL of the interface.
    - **username** - User name for site..
    - **password** - Password for username.
    - **check_interval** - How often to check for new data on each point.
    - **path_prefix** - Path prefix for all publishes.
    - **register_config** - Registry configuration file.
    - **default_last_read** - Time, in hours, to go back and retrieve data for a point for the first time.

Here is an example device configuration file:

.. code-block:: json

    {
      "url": "http://example.com/obix/histories/EXAMPLE/",
      "username": "username",
      "password": "password",
      # Interval to query interface for updates in minutes.
      # History points are only published if new data is available
      # config points are gathered and published at this interval.
      "check_interval": 15,
      # Path prefix for all publishes
      "path_prefix": "devices/obix/history/",
      "register_config": "config://registry_config.csv",
      "default_last_read": 12
    }

A sample Obix configuration file can be found in the VOLTTRON repository in ``services/core/ObixHistoryPublish/config``

Registry Configuration File
***************************

Similar to a driver the Obix History Agent requires a registry file to select the points to publish.

The registry configuration file is a `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ file. Each row configures a point on the device.

The following columns are required for each row:

    - **Device Name** - Name of the device to associate with this point.
    - **Volttron Point Name** - The Volttron Point name to use when publishing this value.
    - **Obix Name** - Name of the point on the obix interface. Escaping of spaces and dashes for use with the interface is handled internaly.

Any additional columns will be ignored. It is common practice to include a **Notes** or **Unit Details** for additional information about a point.

The following is an example of a Obix History Agent registry confugration file:

.. csv-table:: Obix
        :header: Device Name,Volttron Point Name,Obix Name

        device1,Local Outside Dry Bulb,Local Outside Dry Bulb
        device2,CG-1 Gas Flow F-2,CG-1 Gas Flow F-2
        device2,Cog Plant Gas Flow F-1,Cog Plant Gas Flow F-1
        device2,Boiler Plant Hourly Gas Usage,Boiler Plant Hourly Gas Usage
        device3,CG-1 Water Flow H-1,CG-1 Water Flow H-1

A sample Obix History Agent configuration can be found in the VOLTTRON repository in ``services/core/ObixHistoryPublish/registry_config.csv``

.. _Obix-History-AutoConfiguration:
Automatic Obix Configuration File Creation
******************************************
A script that will automatically create both a device and register
configuration file for a site is located in the repository at ``scripts/obix/get_obix_history_config.py``.

The utility is invoked with the command:

    ``python get_obix_history_config.py <url> <registry_file> <driver_file> -u <username> -p <password> -d <device name>``

If either the registry_file or driver_file is omitted the script will output those files to stdout.

If either the username or password options are left out the script will ask for them on the command line before proceeding.

The device name option specifies a default device for every point in the configuration.

The registry file produced by this script assumes that the `Volttron Point Name` and the `Obix Name` have the same value.
Also, it is assumed that all points should be read only. Users are expected to fix this as appropriate.

