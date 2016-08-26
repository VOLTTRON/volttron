.. _Historian-Topic-Syntax:

Historian Topic Syntax
======================

Each historian will subscribe to the following message bus topics
(actuator/*, anaylsis/*, record/\* and devices/\*). For each of these
topics there is a different message syntax that must be adhered to in
order for the correct interpretation of the data being specified.

record/\*
The record topic is the most flexible of all of the topics. This topic allows any serializable message to be published to any topic under the root topic '/record'.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------

**Note: this topic is not recommended to plot as the structure of the
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
topic is what is read and published to a historian. Both the all topic
have the same header information, but the message body for each is
slightly different. For a complete working example of these messages
please see
https://github.com/VOLTTRON/volttron/blob/develop/examples/ExampleSubscriber/subscriber/subscriber_agent.py

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
    # Messages contains a two element list.  The first element contains an individual reading.  The second
    # element contains a list of meta data.
    {
        [52.5, {'units': 'F', 'tz': 'UTC', 'type': 'float'}]
    }

    # ALL TOPIC
    # Messages contains a two element list.  The first element contains a dictionary of all points 
    # under a #specific parent.  While the second element contains a dictionary of meta data for each of the specified points.  For example devices/pnnl/building/OutsideAirTemperature and 
    # devices/pnnl/building/MixedAirTemperature ALL message would be created like:
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


