.. _Developing-Historian-Agents:

===========================
Developing Historian Agents
===========================

VOLTTRON provides a convenient base class for developing new historian agents. The base class automatically performs
a number of important functions:

* subscribes to all pertinent topics
* caches published data to disk until it is successfully recorded to a historian
* creates the public facing interface for querying results
* spells out a simple interface for concrete implementation to meet to make a working Historian Agent
* breaks data to publish into reasonably sized chunks before handing it off to the concrete implementation for
  publication.  The size of the chunk is configurable
* sets up a separate thread for publication.  If publication code needs to block for a long period of time (up to 10s of
  seconds) this will no disrupt the collection of data from the bus or the functioning of the agent itself

The VOLTTRON repository provides several :ref:`historians <VOLTTRON-Historians>` which can be deployed without
modification.


BaseHistorian
-------------

All Historians must inherit from the BaseHistorian class in volttron.platform.agent.base\_historian and implement the
following methods:


publish_to_historian(self, to_publish_list)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method is called by the BaseHistorian class when it has received data from the message bus to be published.
`to_publish_list` is a list of records to publish in the form:

.. code-block:: json

    [
        {
            '_id': 1,
            'timestamp': timestamp,
            'source': 'scrape', 
            'topic': 'campus/building/unit/point', 
            'value': 90, 
            'meta': {'units':'F'}  
        }
        {
            ...
        }
    ]

-  **_id** - ID of the record used for internal record tracking. All IDs in the list are unique
-  **timestamp** - Python datetime object of the time data was published at timezone UTC
-  **source** - Source of the data: can be scrape, analysis, log, or actuator
-  **topic** - Topic data was published on, topic prefix's such as "device" are dropped
-  **value** - Value of the data, can be any type.
-  **meta** - Metadata for the value, some sources will omit this entirely.

For each item in the list the concrete implementation should attempt to publish (or discard if non-publishable) every
item in the list.  Publication should be batched if possible. For every successfully published record and every record
that is to be discarded because it is non-publishable the agent must call `report_handled` on those records.  Records
that should be published but were not for whatever reason require no action.  Future calls to `publish_to`_historian`
will include these unpublished records.  `publish_to_historian` is always called with the oldest unhandled records. This
allows the historian to no lose data due to lost connections or other problems.

As a convenience `report_all_handled` can be called if all of the items in `published_list` were successfully handled.


query_topic_list(self)
~~~~~~~~~~~~~~~~~~~~~~

Must return a list of all unique topics published.


query_historian(self, topic, start=None, end=None, skip=0, count=None, order=None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


This function must return the results of a query in the form:

.. code-block:: json

    {"values": [(timestamp1: value1), (timestamp2: value2), ...],
     "metadata": {"key1": value1, "key2": value2, ...}}

metadata is not required (The caller will normalize this to {} for you if you leave it out)

-  **topic** - the topic the user is querying for
-  **start** - datetime of the start of the query, `None` for the beginning of time
-  **end** - datetime of the end of of the query, `None` for the end of time
-  **skip** - skip this number of results (for pagination)
-  **count** - return at maximum this number of results (for pagination)
-  **order** - `FIRST_TO_LAST` for ascending time stamps, `LAST_TO_FIRST` for descending time stamps


historian_setup(self)
~~~~~~~~~~~~~~~~~~~~~~

Implementing this is optional. This function is run on the same thread as the rest of the concrete implementation at
startup. It is meant for connection setup.


Example Historian
-----------------

An example historian can be found in the `examples/CSVHistorian` directory in the VOLTTRON repository.  This example
historian uses a CSV file as the persistent data store.  It is recommended to use this agent as a reference for
developing new historian agents.
