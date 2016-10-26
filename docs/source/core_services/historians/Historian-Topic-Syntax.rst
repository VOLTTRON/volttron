.. _Historian-Topic-Syntax:

Historian Topic Syntax
======================

Each historian will subscribe to the following message bus topics
(datalogger/*, anaylsis/*, record/\* and devices/\*). For each of these
topics there is a different message syntax that must be adhered to in
order for the correct interpretation of the data being specified.

record/\*
---------
The record topic is the most flexible of all of the topics. This topic allows
any serializable message to be published to any topic under the root topic
'/record'.

**Note: this topic is not recommended to plot, as the structure of the
messages are not necessarily numeric.**

::

    # Example messages that can be published

    # Dictionary data
    {'foo': 'wolrd'}

    # Numerical data
    52

    # Time data (note not a datatime object)
    '2015-12-02T11:06:32.252626'

devices/\*
----------

The devices topic is meant to be data structured from a scraping of a
ModBus or BacNet device. Currently there are drivers for both of these
protocols write data to the message bus in the proper format. VOLTTRON
drivers also publish an aggregation of points in an "all" topic. The all
topic is what is read and published to a historian. Both the all topic and
point topic have the same header information, but the message body for each is
slightly different. For a complete working example of these messages
please see

- :py:mod:`examples.ExampleSubscriber.subscriber.subscriber_agent`

::

    # Header contains the data associated with the message.
    {
        # python code to get this is
        # from datetime import datetime
        # from volttron.platform.messaging import headers as header_mod
        # {
        #     headers_mod.DATE: datetime.utcnow().isoformat() + 'Z'
        # }
        "Date": "2015-11-17T21:24:10.189393Z"
    }

    # Individual Point topic
    # Messages contains a two element list.  The first element contains an
    # individual reading.  The second element contains a list of meta data.
    {
        [52.5, {'units': 'F', 'tz': 'UTC', 'type': 'float'}]
    }

    # ALL TOPIC
    # Messages contains a two element list.  The first element contains a
    # dictionary of all points under a specific parent.  While the second
    # element contains a dictionary of meta data for each of the specified
    # points.  For example devices/pnnl/building/OutsideAirTemperature and
    # devices/pnnl/building/MixedAirTemperature ALL message would be created as:
    {
        [
            {"OutsideAirTemperature ": 52.5, "MixedAirTemperature ": 58.5},
            {
                "OutsideAirTemperature ": {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                "MixedAirTemperature ": {'units': 'F', 'tz': 'UTC', 'type': 'float'}
            }
        ],
        ...
        ...
    ]

analysis/\*
-----------

Data sent to analysis/* topics is result of analysis done by applications.
The format of data sent to analysis/* topics is similar to data sent to
device/* topics.

datalogger/\*
-------------
Messages published to datalogger will be assumed to be timepoint data that
is composed of units and specific types with the assumption that they have
the ability to be graphed easily.

::

    {'MixedAirTemperature': {'Readings': ['2015-12-02T00:00:00',
                                          mixed_reading],
                             'Units': 'F',
                             'tz': 'UTC',
                             'data_type': 'float'}}

If no datetime value is specified as a part of the reading, current time is
used. Message can be published without any header. In the above message
'Readings' and 'Units' are mandatory
