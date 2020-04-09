.. _DataPublisher:

=============
DataPublisher
=============

This is a simple agent that plays back data either from the config store or a CSV to the configured topic. It can also provide basic
emulation of the actuator agent for testing agents that expect to be able to set points on a device in response to device publishes.

Installation notes
------------------

In order to simulate the actuator you must install the agent with the VIP identity of `platform.actuator`.

Configuration
-------------

::

    {
        # basepath is prepended to the topic that is published to the message bus.
        "basepath": "devices/campus/building",

        # use_timestamp uses the included in the input_data if present.
        # Currently the column must be named `Timestamp`.
        "use_timestamp": true,

        # Only publish data at most once every max_data_frequency seconds.
        # Extra data is skipped.
        # The time windows are normalized from midnight.
        # ie 900 will publish one value for every 15 minute window starting from
        # midnight of when the agent was started.
        # Only used if timestamp in input file is used.
        "max_data_frequency": 900,

        # The meta data published with the device data is generated
        # by matching point names to the unittype_map.
        "unittype_map": {
            ".*Temperature": "Farenheit",
            ".*SetPoint": "Farenheit",
            "OutdoorDamperSignal": "On/Off",
            "SupplyFanStatus": "On/Off",
            "CoolingCall": "On/Off",
            "SupplyFanSpeed": "RPM",
            "Damper*.": "On/Off",
            "Heating*.": "On/Off",
            "DuctStatic*.": "On/Off"
        },
        # Path to input CSV file.
        # May also be a list of records or reference to a CSV file in the config store.
        # Large CSV files should be referenced by file name and not stored in the config store.
        # If the filename is used, the full file path is required. This can be found using
        # the `pwd` command.
        "input_data": "test.csv",
        # Publish interval in seconds
        "publish_interval": 1,

        # Tell the playback to maintain the location a the file in the config store.
        # Playback will be resumed from this point
        # at agent startup even if this setting is changed to false before restarting.
        # Saves the current line in line_marker in the DataPublishers's config store
        # as plain text.
        # default false
        "remember_playback": true,

        # Start playback from 0 even if the line_marker configuration is set a non 0 value.
        # default false
        "reset_playback": false,

        # Repeat data from the start if this flag is true.
        # Useful for data that does not include a timestamp and is played back in real time.
        "replay_data": false,

        # Allows the overriding of the default separator in the header of the csv file.
        # default is "/" if not specified.
        "topic_separator": "/"
    }

CSV File Format
---------------

The CSV file must have a single header line. The column names are appended to the
`basepath` setting in the configuration file and the resulting topic is normalized
to remove extra `/`s. The values are all treated as floating
point values and converted accordingly.  If the conversion to a float fails then that column will not be included in
all publish.

The corresponding device for each point is determined and the values are combined
together to create an `all` topic publish for each device.

If a `Timestamp` column is in the input it may be used to set the timestamp in the
header of the published data.

.. csv-table:: Publisher Data
        :header: Timestamp,centrifugal_chiller/OutsideAirTemperature,centrifugal_chiller/DischargeAirTemperatureSetPoint,fuel_cell/DischargeAirTemperature,fuel_cell/CompressorStatus,absorption_chiller/SupplyFanSpeed,absorption_chiller/SupplyFanStatus,boiler/DuctStaticPressureSetPoint,boiler/DuctStaticPressure

        2012/05/19 05:07:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:08:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:09:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:10:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:11:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:12:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:13:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:14:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:15:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:16:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:17:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:18:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:19:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:20:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:21:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:22:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:23:00,0,56,0,0,75,1,1.4,1.38
        2012/05/19 05:24:00,0,56,58.77,0,75,1,1.4,1.38
        2012/05/19 05:25:00,48.78,56,58.87,0,75,1,1.4,1.38
        2012/05/19 05:26:00,48.88,56,58.95,0,75,1,1.4,1.38
        2012/05/19 05:27:00,48.93,56,58.91,0,75,1,1.4,1.38
        2012/05/19 05:28:00,48.95,56,58.81,0,75,1,1.4,1.38
        2012/05/19 05:29:00,48.92,56,58.73,0,75,1,1.4,1.38
        2012/05/19 05:30:00,48.88,56,58.69,0,75,1,1.4,1.38
        2012/05/19 05:31:00,48.88,56,58.81,0,75,1,1.4,1.38
        2012/05/19 05:32:00,48.99,56,58.91,0,75,1,1.4,1.38
        2012/05/19 05:33:00,49.09,56,58.85,0,75,1,1.4,1.38
        2012/05/19 05:34:00,49.11,56,58.79,0,75,1,1.4,1.38
        2012/05/19 05:35:00,49.07,56,58.71,0,75,1,1.4,1.38
        2012/05/19 05:36:00,49.05,56,58.77,0,75,1,1.4,1.38
        2012/05/19 05:37:00,49.09,56,58.87,0,75,1,1.4,1.38
        2012/05/19 05:38:00,49.13,56,58.85,0,75,1,1.4,1.38
        2012/05/19 05:39:00,49.09,56,58.81,0,75,1,1.4,1.38
        2012/05/19 05:40:00,49.01,56,58.75,0,75,1,1.4,1.38
        2012/05/19 05:41:00,48.92,56,58.71,0,75,1,1.4,1.38
        2012/05/19 05:42:00,48.86,56,58.77,0,75,1,1.4,1.38
        2012/05/19 05:43:00,48.92,56,58.87,0,75,1,1.4,1.38
        2012/05/19 05:44:00,48.95,56,58.79,0,75,1,1.4,1.38
        2012/05/19 05:45:00,48.92,56,58.69,0,75,1,1.4,1.38
        2012/05/19 05:46:00,48.86,56,58.5,0,75,1,1.4,1.38
        2012/05/19 05:47:00,48.78,56,58.34,0,75,1,1.4,1.38
        2012/05/19 05:48:00,48.69,56,58.36,0,75,1,1.4,1.38
        2012/05/19 05:49:00,48.65,56,58.46,0,75,1,1.4,1.38
        2012/05/19 05:50:00,48.65,56,58.56,0,75,1,1.4,1.38
        2012/05/19 05:51:00,48.65,56,58.48,0,75,1,1.4,1.38
        2012/05/19 05:52:00,48.61,56,58.36,0,75,1,1.4,1.38
        2012/05/19 05:53:00,48.59,56,58.21,0,75,1,1.4,1.38
        2012/05/19 05:54:00,48.55,56,58.25,0,75,1,1.4,1.38
        2012/05/19 05:55:00,48.63,56,58.42,0,75,1,1.4,1.38
        2012/05/19 05:56:00,48.76,56,58.56,0,75,1,1.4,1.38
        2012/05/19 05:57:00,48.95,56,58.71,0,75,1,1.4,1.38
        2012/05/19 05:58:00,49.24,56,58.83,0,75,1,1.4,1.38
        2012/05/19 05:59:00,49.54,56,58.93,0,75,1,1.4,1.38
        2012/05/19 06:00:00,49.71,56,58.95,0,75,1,1.4,1.38
        2012/05/19 06:01:00,49.79,56,59.07,0,75,1,1.4,1.38
        2012/05/19 06:02:00,49.94,56,59.17,0,75,1,1.4,1.38
        2012/05/19 06:03:00,50.13,56,59.25,0,75,1,1.4,1.38
        2012/05/19 06:04:00,50.18,56,59.15,0,75,1,1.4,1.38
        2012/05/19 06:05:00,50.15,56,59.04,0,75,1,1.4,1.38
