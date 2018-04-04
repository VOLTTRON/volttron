.. _Historian Index:
============================
VOLTTRON Historian Framework
============================

Historian Agents are the way by which device, actuator, datalogger, and
analysis are captured and stored in some sort of data store. Historians exist for the following storage options:

- A general :ref:`SQL Historian <SQL-Historian>` implemented for MySQL and SQLite
- :ref:`MongoDB Historian <Mongo-Historian>`
- :ref:`Crate Historian <Crate-Historian>`
- :ref:`Forward Historian <Forward-Historian>` for sending data to another VOLTTRON instance
- :ref:`OpenEIS Historian <Analytics-Historian>`
- :ref:`MQTT Historian <MQTT-Historian>` Forwards data to an MQTT broker
- :ref:`InfluxDB Historian <Influxdb-Historian>`

Other implementations of historians can be created by following the
:ref:`developing historian agents <Developing-Historian-Agents>` section of
the wiki.

Historians are all built upon the BaseHistorian which provides general
functionality the specific implementations is built upon.

In most cases the default settings are fine for all deployments.

All historians support the following settings:

.. code-block:: python

    {
        # Maximum amount of time to wait before retrying a failed publish in seconds.
        # Will try more frequently if new data arrives before this timelime expires.
        # Defaults to 300
        "retry_period": 300.0,

        # Maximum number of records to submit to the historian at a time.
        # Defaults to 1000
        "submit_size_limit": 1000,

        # In the case where a historian needs to catch up after a disconnect
        # the maximum amount of time to spend writing to the database before
        # checking for and caching new data.
        # Defaults to 30
        "max_time_publishing": 30.0,

        # Limit how far back the historian will keep data in days.
        # Partial days supported via floating point numbers.
        # A historian must implement this feature for it to be enforced.
        "history_limit_days": 366,

        # Limit the size of the historian data store in gigabytes.
        # A historian must implement this feature for it to be enforced.
        "storage_limit_gb": 2.5

        # Size limit of the backup cache in Gigabytes.
        # Defaults to no limit.
        "backup_storage_limit_gb": 8.0,

        # Do not actually gather any data. Historian is query only.
        "readonly": false,

        # capture_device_data
        #   Defaults to true. Capture data published on the `devices/` topic.
        "capture_device_data": true,

        # capture_analysis_data
        #   Defaults to true. Capture data published on the `analysis/` topic.
        "capture_analysis_data": true,

        # capture_log_data
        #   Defaults to true. Capture data published on the `datalogger/` topic.
        "capture_log_data": true,

        # capture_record_data
        #   Defaults to true. Capture data published on the `record/` topic.
        "capture_record_data": true,

        # Replace a one topic with another before saving to the database.
        # Deprecated in favor of retrieving the list of
        # replacements from the VCP on the current instance.
        "topic_replace_list": [
        #{"from": "FromString", "to": "ToString"}
        ],

        # For historian developers. Adds benchmarking information to gathered data.
        # Defaults to false and should be left that way.
        "gather_timing_data": false,

    }

By default the base historian will listen to 4 separate root topics
`datalogger/*`, `record/*`, `analysis/*`, and `device/*`.

Each of root
topics has a :ref:`specific message syntax <Historian-Topic-Syntax>` that
it is expecting for incoming data.

Messages published to `datalogger`
will be assumed to be timepoint data that is composed of units and
specific types with the assumption that they have the ability to be
graphed easily.

Messages published to `devices` are data that comes
directly from drivers.

Messages published to `analysis` are analysis data published by agnets
in the form of key value pairs.

Finally Messages that are published to `record`
will be handled as string data and can be customized to the user
specific situation.

Please consult the :ref:`Historian Topic
Syntax <Historian-Topic-Syntax>` page for a specific syntax.

This base historian will cache all received messages to a local
database before publishing it to the historian. This allows recovery from
unexpected happenings before the successful writing of data to the historian.


.. toctree::
    :glob:
    :maxdepth: 2

    *
