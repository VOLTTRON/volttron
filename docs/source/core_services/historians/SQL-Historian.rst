.. _SQL-Historian:

SQL Historian
=============

An SQL Historian is available as a core service. The sql historian has
been programmed to allow for inconsistent network connectivity
(automatic re-connection to tcp based databases). All additions to the
historian are batched and wrapped within a transaction with commit and
rollback functions properly implemented. This allows the maximum
throughput of data with the most protection. The following example
configurations show the different options available for configuring the
SQL Historian Agent.

MySQL Specifics
~~~~~~~~~~~~~~~

MySQL requires a third party driver (mysql-connector) to be installed in
order for it to work. Please execute the following from an activated
shell in order to install it.

::

    pip install --allow-external mysql-connector-python mysql-connector-python

| In addition, the mysql database must be created and permissions
granted for select, insert and update before the agent is started. In
order to support timestamp with microseconds you need at least MySql
5.6.4. Please see this `MySql
documentation <http://dev.mysql.com/doc/refman/5.6/en/fractional-seconds.html>`__
for more details
| The following is a minimal configuration file for using a MySQL based
historian. Other options are available and are documented
http://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html.
**Not all parameters have been tested, use at your own risk**.

::

    {
        "agentid": "sqlhistorian-mysql",
        "connection": {
            "type": "mysql",
            "params": {
                "host": "localhost",
                "port": 3306,
                "database": "volttron",
                "user": "user",
                "passwd": "pass"
            }
        }
    }

Sqlite3 Specifics
~~~~~~~~~~~~~~~~~

An Sqlite Historian provides a convenient solution for under powered
systems. The database is parameter is a location on the file system. By
default it is relative to the agents installation directory, however it
will respect a rooted or relative path to the database.

::

    {
        "agentid": "sqlhistorian-sqlite",
        "connection": {
            "type": "sqlite",
            "params": {
                "database": "data/historian.sqlite"
            }
        }
    }


PostgreSQL and Redshift
~~~~~~~~~~~~~~~~~~~~~~~

Installation notes
------------------

1. The PostgreSQL database driver supports recent PostgreSQL versions.
   It was tested on 10.x, but should work with 9.x and 11.x.

2. The user must have SELECT, INSERT, and UPDATE privileges on historian
   tables.

3. The tables in the database are created as part of the execution of
   the SQLHistorianAgent, but this will fail if the database user does not
   have CREATE privileges.

4. Care must be exercised when using multiple historians with the same
   database. This configuration may be used only if there is no overlap in
   the topics handled by each instance. Otherwise, duplicate topic IDs
   may be created, producing strange results.

5. Redshift databases do not support unique constraints. Therefore, it is
   possible that tables may contain some duplicate data. The Redshift driver
   handles this by using distinct queries. It does not remove duplicates
   from the tables.

Dependencies
------------

The PostgreSQL and Redshift database drivers require the **psycopg2** Python package.

    From an activated shell execute:

        pip install psycopg2-binary

Configuration
-------------

The following are minimal configuration files for using a psycopg2-based
historian. Other options are available and are documented
http://initd.org/psycopg/docs/module.html
**Not all parameters have been tested, use at your own risk**.

Local PostgreSQL Database
+++++++++++++++++++++++++

The following snippet demonstrates how to configure the
SQLHistorianAgent to use a PostgreSQL database on the local system
that is configured to use Unix domain sockets. The user executing
volttron must have appropriate privileges.

::
    {
        "connection": {
            "type": "postgresql",
            "params": {
                "dbname": "volttron"
            }
        }
    }

Remote PostgreSQL Database
++++++++++++++++++++++++++

The following snippet demonstrates how to configure the
SQLHistorianAgent to use a remote PostgreSQL database.

::
    {
        "connection": {
            "type": "postgresql",
            "params": {
                "dbname": "volttron",
                "host": "historian.example.com",
                "port": 5432,
                "user": "volttron",
                "password": "secret"
            }
        }
    }

TimescaleDB Support
++++++++++++++++++++++++++

Both of the above PosgreSQL connection types can make
use of TimescaleDB's high performance Hypertable backend
for the primary timeseries table. The agent assumes you
have completed the TimescaleDB installation and setup
the database by following the instructions here:
https://docs.timescale.com/latest/getting-started/setup
To use, simply add 'timescale_dialect: true' to the 
connection params in the Agent Config as below

::
    {
        "connection": {
            "type": "postgresql",
            "params": {
                "dbname": "volttron",
                "host": "historian.example.com",
                "port": 5432,
                "user": "volttron",
                "password": "secret",
                "timescale_dialect": true
            }
        }
    }

Redshift Database
+++++++++++++++++

The following snippet demonstrates how to configure the
SQLHistorianAgent to use a Redshift database.

::
    {
        "connection": {
            "type": "redshift",
            "params": {
                "dbname": "volttron",
                "host": "historian.example.com",
                "port": 5432,
                "user": "volttron",
                "password": "secret"
            }
        }
    }
