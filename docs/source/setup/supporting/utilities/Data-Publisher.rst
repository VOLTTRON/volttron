.. _Data-Publisher:

==============
Data Publisher
==============

The data publisher agent allows the playback of csv data to the message
bus as if it were a device.

The first line of the csv file should begin with **Timestamp**, then enumerate
the points to be published. The point names in the csv will need to reflect how
the agent is configured. Each following line represents the state of the device
at a particular time.


Publishing from a Single Device
-------------------------------

If all the points are going to appear to have been read from a single device,
the agent can be configured with simply the device name. The point names in the
csv file do not need any prefixes.

.. code-block:: python

    "unit": "unitname"


Publishing from Multiple Devices
--------------------------------

If points need to appear to have come from multiple devices, **unit** needs to
be organized in a dictionary. Point names in the input csv need to be prefixed
with their device **or** subdevice and and an underscore i.e. `rtu4_point`
**or** `VAV13111_point`.

.. note::

   A point prefixed with a subdevice will automatically have the parent device
   added to its topic.

.. code-block :: python

    "unit": {
            "rtu4": {
                "subdevices": []
            },
            "rtu5": {
                "subdevices": [
                    "VAV13111", "VAV13112",
                    "FCU13258", "FCU13259"
            ]
        }
    }

Example Configuration
---------------------

This configuration illustrates the options available to the Data Publisher
Agent. Some options have default values and may be left out if the default
is acceptable. More sample configurations as well as input csv files can be
found from the *examples/DataPublisher* directory.

.. note::

   Using some configuration options will cause others to be ignored.
   "custom_topic" will overwrite "basetopic", "campus", and "building"

.. code-block:: python

    {
        "publisherid": "PUBLISHER",

        # The input file for where the comma delimited data is found.
        "input_file": "/path/to/csv/file/with/data.csv",

        # If has_timestamp is set then the timestamp is assumed to be in the first
        # column of the file. Defaults to 1.
        "has_timestamp": 1,

        # Only valid if hast_timestamp is set to true.  Will use the timestamp in
        # the first column of the datafile as the timestamp published on the bus.
        # Defaults to 0.
        "maintain_timestamp": 1,

        # Declare standard topic format that identifies campus, building,
        # device (unit), and subdevices (optional)
        # Basetopic can be devices, analysis, or custom base topic
        "basetopic": "devices",
        "campus": "campus1",
        "building": "building1",

        # If a custom topic is desired the entire topic must be configured.
        # e.g., "custom_topic": 'custom/topic/configuration'
        # If this variable is set it will be used instead of basetopic/campus/building
        # "custom_topic":

        # Unit can be a single string.
        "unit": {
                "rtu4": {
                    "subdevices": []
                },
                "rtu5": {
                    "subdevices": [
                        "VAV13111", "VAV13112",
                        "FCU13258", "FCU13259"
                ]
            }
        },

        # Used to map point names to units publishes
        # Keys in this dictionary are used as regular expressions
        "unittype_map": {
            ".*Temperature": "Fahrenheit",
            ".*SetPoint": "Fahrenheit",
            "OutdoorDamperSignal": "On/Off",
            "SupplyFanStatus": "On/Off",
            "CoolingCall": "On/Off",
            "SupplyFanSpeed": "RPM",
            "Damper.*": "On/Off",
            "Heating.*": "On/Off",
            "DuctStatic.*": "On/Off"
        },

        # Publish interval in seconds
        "publish_interval": 1,

        # Tell the playback to maintain the location in the file if playback stops
        # before the file ends.
        # default 0
        "remember_playback": 1,

        # Start playback from 0 even though remember playback may be set.
        # default 0
        "reset_playback": 0

        # Replay data rather than stopping after the data is completed.
        # Defaults to false
        "replay_data": true
    }
