.. _Influxdb-Historian:

##################
Influxdb Historian
##################

InfluxDB is an open source time series database with a fast, scalable engine and high availability.
It's often used to build DevOps Monitoring (Infrastructure Monitoring, Application Monitoring,
Cloud Monitoring), IoT Monitoring, and Real-Time Analytics solutions.

More information about InfluxDB is available from `<https://www.influxdata.com/>`_.


Prerequisites
#############

InfluxDB Installation
=====================

To install InfluxDB on an Ubuntu or Debian operating system, run the script:

    ::

        services/core/InfluxdbHistorian/scripts/install-influx.sh

For installation on other operating systems,
see `<https://docs.influxdata.com/influxdb/v1.4/introduction/installation/>`_.

Authentication in InfluxDB
==========================

By default, the InfluxDB *Authentication* option is disabled, and no user authentication is
required to access any InfluxDB database. You can enable authentication by updating the
InfluxDB configuration file. For detailed information on enabling authentication, see:
`<https://docs.influxdata.com/influxdb/v1.4/query_language/authentication_and_authorization/>`_.

If *Authentication* is enabled, authorization privileges are enforced. There must be at least
one defined admin user with access to administrative queries as outlined in the linked document
above. Additionally, you must pre-create the ``user`` and ``database`` that are specified in the
configuration file (the default configuration file for InfluxDB
is ``services/core/InfluxdbHistorian/config``).
If your ``user`` is a non-admin user, they must be granted a full set of privileges on the
desired ``database``.

InfluxDB Driver
===============

In order to connect to an InfluxDb client, the Python library for InfluxDB must be installed
in VOLTTRON's virtual environment. From the command line, after enabling the virtual environment,
install the InfluxDB library as follows:

    ::

        pip install influxdb


Configuration
#############

The default configuration file for VOLTTRON's InfluxDBHistorian agent should be in the format:

.. code-block:: python

    {
      "connection": {
        "params": {
          "host": "localhost",
          "port": 8086,         # Don't change this unless default bind port
                                # in influxdb config is changed
          "database": "historian",
          "user": "historian",  # user is optional if authentication is turned off
          "passwd": "historian" # passwd is optional if authentication is turned off
        }
      },
      "aggregations": {
        "use_calendar_time_periods": true
      }
    }


The InfluxDBHistorian agent can be packaged, installed and started according to the standard
VOLTTRON agent creation procedure. A sample VOLTTRON configuration file has been
provided: ``services/core/InfluxdbHistorian/config``.

.. seealso:: :ref:`Agent Development Walkthrough <Agent-Development>`

Connection
==========

The ``host``, ``database``, ``user`` and ``passwd`` values in the VOLTTRON configuration file
can be modified. ``user`` and ``passwd`` are optional if InfluxDB *Authentication* is disabled.

.. note:: Be sure to initialize or pre-create the ``database`` and ``user`` that you defined in
          the configuration file, and if ``user`` is a non-admin user, be make sure to grant
          privileges for the user on the specified ``database``.
          For more information, see `Authentication in InfluxDB`_.

Aggregations
============

In order to use aggregations, the VOLTTRON configuration file must also specify a value,
either ``true`` or ``false``, for ``use_calendar_time_periods``, indicating whether the
aggregation period should align to calendar time periods. If this value is omitted from the
configuration file, aggregations cannot be used.

For more information on historian aggregations,
see: :ref:`Aggregate Historian Agent Specification <AggregateHistorianSpec>`.

Supported Influxdb aggregation functions:

    Aggregations: COUNT(), DISTINCT(), INTEGRAL(), MEAN(), MEDIAN(), MODE(), SPREAD(), STDDEV(), SUM()

    Selectors: FIRST(), LAST(), MAX(), MIN()

    Transformations: CEILING(),CUMULATIVE_SUM(), DERIVATIVE(), DIFFERENCE(), ELAPSED(), NON_NEGATIVE_DERIVATIVE(), NON_NEGATIVE_DIFFERENCE()

More information how to use those functions: `<https://docs.influxdata.com/influxdb/v1.4/query_language/functions/>`_

.. note:: Historian aggregations in InfluxDB are different from aggregations employed
          by other historian agents in VOLTTRON. InfluxDB doesn't have a separate agent for aggregations.
          Instead, aggregation is supported through the ``query_historian`` function. Other agents can
          execute an aggregation query directly in InfluxDB by calling the *RPC.export* method ``query``.
          For an example, see :ref:`Aggregate Historian Agent Specification <AggregateHistorianSpec>`

Database Schema
###############

Each InfluxDB database has a ``meta`` table as well as other tables for different measurements,
e.g. one table for "power_kw", one table for "energy", one table for "voltage", etc.
(An InfluxDB ``measurement`` is similar to a relational table, so for easier understanding, InfluxDB
measurements will be referred to below as tables.)

Measurement Table
=================

Example: If a topic name is *"CampusA/Building1/Device1/Power_KW"*, the ``power_kw`` table might look as follows:

+-------------------------------+-----------+---------+----------+-------+------+
|time                           |building   |campus   |device    |source |value |
+-------------------------------+-----------+---------+----------+-------+------+
|2017-12-28T20:41:00.004260096Z |building1  |campusa  |device1   |scrape |123.4 |
+-------------------------------+-----------+---------+----------+-------+------+
|2017-12-30T01:05:00.004435616Z |building1  |campusa  |device1   |scrape |567.8 |
+-------------------------------+-----------+---------+----------+-------+------+
|2018-01-15T18:08:00.126345Z    |building1  |campusa  |device1   |scrape |10    |
+-------------------------------+-----------+---------+----------+-------+------+

``building``, ``campus``, ``device``, and ``source`` are InfluxDB *tags*. ``value`` is an InfluxDB *field*.

.. note:: The topic is converted to all lowercase before being stored in the table.
          In other words, a set of *tag* names, as well as a table name, are created by
          splitting ``topic_id`` into substrings (see `meta table`_ below).


So in this example, where the typical format of a topic name is ``<campus>/<building>/<device>/<measurement>``,
``campus``, ``building`` and ``device`` are each stored as tags in the database.

A topic name might not confirm to that convention:

    #. The topic name might contain additional substrings, e.g.
       *CampusA/Building1/LAB/Device/OutsideAirTemperature*. In this case,
       ``campus`` will be *campusa/building*, ``building`` will be *lab*, and ``device`` will be *device*.

    #. The topic name might contain fewer substrings, e.g. *LAB/Device/OutsideAirTemperature*.
       In this case, the ``campus`` tag will be empty, ``building`` will be *lab*,
       and ``device`` will be *device*.

Meta Table
==========

The meta table will be structured as in the following example:

+---------------------+---------------------------------+------------------------------------------------------------------+-------------------------------------+--------------------------------------+
|time                 |last_updated                     |meta_dict                                                         |topic                                |topic_id                              |
+---------------------+---------------------------------+------------------------------------------------------------------+-------------------------------------+--------------------------------------+
|1970-01-01T00:00:00Z |2017-12-28T20:47:00.003051+00:00 |{u'units': u'kw', u'tz': u'US/Pacific', u'type': u'float'}        |CampusA/Building1/Device1/Power_KW   |campusa/building1/device1/power_kw    |
+---------------------+---------------------------------+------------------------------------------------------------------+-------------------------------------+--------------------------------------+
|1970-01-01T00:00:00Z |2017-12-28T20:47:00.003051+00:00 |{u'units': u'kwh', u'tz': u'US/Pacific', u'type': u'float'}       |CampusA/Building1/Device1/Energy_KWH |campusa/building1/device1/energy_kwh  |
+---------------------+---------------------------------+------------------------------------------------------------------+-------------------------------------+--------------------------------------+

In the InfluxDB, ``last_updated``, ``meta_dict`` and ``topic`` are *fields* and ``topic_id`` is a *tag*.

Since InfluxDB is a time series database, the ``time`` column is required, and a dummy value (``time=0``,
which is 1970-01-01T00:00:00Z based on epoch unix time) is assigned to all topics for easier
metadata updating. Hence, if the contents of ``meta_dict`` change for a specific topic, both ``last_updated``
and ``meta_dict`` values for that topic will be replaced in the table.
