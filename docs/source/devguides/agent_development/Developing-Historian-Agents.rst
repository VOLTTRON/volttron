.. _Developing-Historian-Agents:

Developing Historian Agents
===========================

VOLTTRON provides a convenient base class for developing new historian
agents. The base class automatically subscribes to all pertinent topics,
cache published data to disk until it is successfully recorded to a
historian, create the public facing interface for querying results, and
spells out a simple interface for concrete implementation to meet to
make a working Historian Agent. The VOLTTRON provides support for
several :ref:`historians <VOLTTRON-Historians>` without modification.
Please use one of these if it fits your project criteria, otherwise
continue reading.

The base class also breaks data to publish into reasonably sized chunks
before handing it off to the concrete implementation for publication.
The size of the chunk is configurable.

The base class sets up a separate thread for publication. This way if
publication code needs to block for a long period of time (up to 10s of
seconds) this will no disrupt the collection of data from the bus or the
functioning of the agent itself.

BaseHistorian
-------------

All Historians must inherit from the BaseHistorian class in
volttron.platform.agent.base\_historian and implement the following
methods:

publish\_to\_historian(self, to\_publish\_list)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method is called by the BaseHistorian class when it has received
data from the message bus to be published. to\_publish\_list is a list
of records to publish in the form

::

    [
        {
            '_id': 1,
            'timestamp': timstamp, 
            'source': 'scrape', 
            'topic': 'campus/building/unit/point', 
            'value': 90, 
            'meta': {'units':'F'}  
        }
        {
            ...
        }
    ]

-  \_id - ID of record. All IDs in the list are unique. This is used for
   internal record tracking.
-  timestamp - Python datetime object of the time data was published at
   timezone UTC
-  source - Source of the data. Can be scrape, analysis, log, or
   actuator.
-  topic - Topic data was published on. Prefix's such as "device" are
   dropped.
-  value - Value of the data. Can be any type.
-  meta - Metadata for the value. Some sources will omit this entirely.

For each item in the list the concrete implementation should attempt to
publish (or discard if non-publishable) every item in the list.
Publication should be batched if possible. For every successfully
published record and every record that is to be discarded because it is
non-publishable the agent must call report\_handled on those records.
Records that should be published but were not for whatever reason
require no action. Future calls to publish\_to\_historian will include
these unpublished records. publish\_to\_historian is always called with
the oldest unhandled records. This allows the historian to no lose data
due to lost connections or other problems.

As a convenience report\_all\_handled can be called if all of the items
in published\_list were successfully handled.

query\_topic\_list(self)
~~~~~~~~~~~~~~~~~~~~~~~~

Must return a list of all unique topics published.

query\_historian(self, topic, start=None, end=None, skip=0, count=None, order=None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function must return the results of a query in the form:

::

    {"values": [(timestamp1: value1), (timestamp2: value2), ...],
     "metadata": {"key1": value1, "key2": value2, ...}}

metadata is not required (The caller will normalize this to {} for you
if you leave it out)

-  topic - the topic the user is querying for.
-  start - datetime of the start of the query. None for the beginning of
   time.
-  end - datetime of the end of of the query. None for the end of time.
-  skip - skip this number of results (for pagination)
-  count - return at maximum this number of results (for pagination)
-  order - "FIRST\_TO\_LAST" for ascending time stamps,
   "LAST\_TO\_FIRST" for descending time stamps.

historian\_setup(self)
~~~~~~~~~~~~~~~~~~~~~~

Implementing this is optional. This function is run on the same thread
as the rest of the concrete implementation at startup. It is meant for
connection setup.
