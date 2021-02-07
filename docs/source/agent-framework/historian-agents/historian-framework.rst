.. _Historian-Framework:

===================
Historian Framework
===================

Historian Agents are the way by which `device`, `actuator`, `datalogger`, and `analysis` topics are automatically
captured and stored in some sort of data store.  Historians exist for the following storage options:

- A general :ref:`SQL Historian <SQL-Historian>` implemented for MySQL, SQLite, PostgreSQL, and Amazon Redshift
- :ref:`MongoDB Historian <Mongo-Historian>`
- :ref:`Crate Historian <Crate-Historian>`
- :ref:`Forward Historian <Forward-Historian>` for sending data to another VOLTTRON instance
- :ref:`OpenEIS Historian <OpenEIS-Historian>`
- :ref:`MQTT Historian <MQTT-Historian>` Forwards data to an MQTT broker
- :ref:`InfluxDB Historian <Influxdb-Historian>`

Other implementations of Historians can be created by following the
:ref:`Developing Historian Agents <Developing-Historian-Agents>` guide.


Base Historian
==============

Historians are all built upon the `BaseHistorian` which provides general functionality the specific implementations are
built upon.

This base Historian will cache all received messages to a local database before publishing it to the Historian.  This
allows recovery from unexpected happenings before the successful writing of data to the Historian.


Configuration
=============

In most cases the default configuration settings are fine for all deployments.

All Historians support the following settings:

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

        # How full should the backup storage be for an alert to be raised
        "backup_storage_report" : 0.9,

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

        # After publishing every "message_publish_count" number of records, historian writes
        # INFO level log with total number of records published since start of historian
        "message_publish_count": 10000,

        # If historian should subscribe to the configured topics from all platform (instead of just local platform)
        # by default subscription is only to local topics
        "all_platforms": false,

        # Replace a one topic with another before saving to the database.
        "topic_replace_list": [
        #{"from": "FromString", "to": "ToString"}
        ],

        # For historian developers. Adds benchmarking information to gathered data.
        # Defaults to false and should be left that way.
        "gather_timing_data": false

        # Allow for the custom topics or for limiting topics picked up by a historian instance.
        # the key for each entry in custom topics is the data handler.  The topic and data must
        # conform to the syntax the handler expects (e.g., the capture_device_data handler expects
        # data the driver framework). Handlers that expect specific data format are
        # capture_device_data, capture_log_data, and capture_analysis_data. All other handlers will be  
        # treated as record data. The list associated with the handler is a list of custom
        # topics to be associated with that handler.
        #
        # To restrict collection to only the custom topics, set the following config variables to False
        # capture_device_data
        # capture_analysis_data
        # capture_log_data
        # capture_record_data
        "custom_topics": {
            "capture_device_data": ["devices/campus/building/device/all"],
            "capture_analysis_data": ["analysis/application_data/example"],
            "capture_record_data": ["example"]
        },

        # To restrict the points processed by a historian for a device or set of devices (i.e., this configuration
        # parameter only filters data on topics with base 'devices).  If the 'device' is in the
        # topic (e.g.,'devices/campus/building/device/all') then only points in the list will be passed to the
        # historians capture_data method, and processed by the historian for storage in its database (or forwarded to a
        # remote platform (in the case of the ForwardHistorian).  The key in the device_data_filter dictionary can
        # be made more restrictive (e.g., "device/subdevice") to limit unnecessary searches through topics that may not
        # contain the point(s) of interest.
        "device_data_filter":{
                "device": ["point_name1", "point_name2"]
        },

        # list of topics for which incoming record's timestamp should be compared with current timestamp to see if it
        # within the configured tolerance limit. Default value: "devices"
        "time_tolerance_topics": ["devices"],

        # If this is set, timestamp of incoming records on time_tolerance_topics(by default, "devices" topics) are
        # compared with current timestamp. If the difference between current timestamp and the record's timestamp
        # exceeds the configured time_tolerance (seconds), then those records are added to a separate time_error table
        # in cache and are not sent to concrete historian for publishing. An alert is raised when records are entered
        # into the time_error table. Units: seconds
        "time_tolerance": 5,
    }


Topics
======

By default the base historian will listen to 4 separate root topics:

*  `datalogger/*`
* `record/*`
* `analysis/*`
* `devices/*`

Each root topic has a :ref:`specific message syntax <Historian-Topic-Syntax>` that it is expecting for incoming data.

Messages published to `datalogger` will be assumed to be `timepoint` data that is composed of units and specific types
with the assumption that they have the ability to be plotted easily.

Messages published to `devices` are data that comes directly from drivers.

Messages published to `analysis` are analysis data published by agents in the form of key value pairs.

Finally, messages that are published to `record` will be handled as string data and can be customized to the user
specific situation.


.. _Platform-Historian:

Platform Historian
==================

A platform historian is a :ref:`"friendly named" <VIP-Known-Identities>` historian on a VOLTTRON instance.  It always has
the identity of `platform.historian`.  A platform historian is made available to a VOLTTRON Central agent for monitoring
of the VOLTTRON instances health and plotting topics from the platform historian.  In order for one of the historians to
be turned into a platform historian the `identity` keyword must be added to it's configuration with the value of
`platform.historian`.  The following configuration file shows a SQLite based platform historian configuration:

.. code-block:: json

    {
        "agentid": "sqlhistorian-sqlite",
        "identity": "platform.historian",
        "connection": {
            "type": "sqlite",
            "params": {
                "database": "~/.volttron/data/platform.historian.sqlite"
            }
        }
    }


.. toctree::

    historian-topic-syntax
    crate/crate-historian
    influxdb/influxdb-historian
    mongodb/mongo-historian
    mqtt/mqtt-historian
    openeis/openeis-historian
    sql-historian/sql-historian
    data-mover/data-mover-historian
    forwarder/forward-historian
