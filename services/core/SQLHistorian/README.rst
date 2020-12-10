.. _SQL_Historian:

============
SQLHistorian
============

This is a historian agent that writes data to a SQLite, Mysql, Postgres, TimeScale,
or Redshift database based on the connection parameters in the configuration.
The sql historian has been programmed to allow for inconsistent network connectivity
(automatic re-connection to tcp based databases). All additions to the
historian are batched and wrapped within a transaction with commit and
rollback functions properly implemented. This allows the maximum
throughput of data with the most protection.

MySQL
~~~~~

Installation notes
------------------

1. In order to support timestamp with microseconds you need at least
   MySql 5.6.4. Please see this `MySql documentation
   <http://dev.mysql.com/doc/refman/5.6/en/fractional-seconds.html>`__
   for more details

2. The mysql user must have SELECT INSERT, and DELETE privileges
   to the historian database tables.

3. SQLHistorianAgent can create the database tables the first time it runs if the database
   user has CREATE privileges. But we recommend this only for development/test environments.
   For all other use cases,
   use the mysql-create*.sql script to create the tables and then
   start agent. This way database user used by VOLTTRON historian can work with
   minimum required privileges

Dependencies
------------

In order to use mysql one must install the **mysql-python connector**

    From an activated shell execute

        pip install mysql-connector-python-rf

    On Ubuntu 16.04

        pip install does not work. Please download the connector from
        `<https://launchpad.net/ubuntu/xenial/+package/python-mysql.connector>`__
        and follow instructions on README

Configuration
-------------

The following is a minimal configuration file for using a MySQL based
historian. Other options are available and are documented
http://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html.
**Not all mysql connection parameters have been tested, use at your own risk**.
The configurations can be provided in JSON format or yml format

JSON format
::

    {
        "connection": {
            # type should be "mysql"
            "type": "mysql",
            # additional mysql connection parameters could be added but
            # have not been tested
            "params": {
                "host": "localhost",
                "port": 3306,
                "database": "volttron",
                "user": "user",
                "passwd": "pass"
            }
        }
    }

YML format
::

    connection:
        type: mysql
        params:
            host: localhost
            port: 3306
            database: test_historian
            user: historian
            passwd: historian

SQLite3
~~~~~~~

An Sqlite Historian provides a convenient solution for under powered
systems. The database is a parameter to a location on the file system; 'database' should be a non-empty string.
By default, the location is relative to the agent's installation directory,
however it will respect a rooted or relative path to the database.

If 'database' does not have a rooted or relative path, the location of the database depends on whether the volttron
platform is in secure mode.
In secure mode, the location will be under <install_dir>/<agent name>.agent-data directory because this will be
the only directory in which the agent will have write-access.
In regular mode, the location will be under <install_dir>/data for backward compatibility.

The following is a minimal configuration file that uses a relative path to the database.

Configuration
-------------
::

    {
        "connection": {
            # type should be sqlite
            "type": "sqlite",
            "params": {
                "database": "data/historian.sqlite",
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

Both of the above PostgreSQL connection types can make
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

Notes
~~~~~
Do not use the "identity" setting in configuration file. Instead use the
new method provided by the platform to set an agent's identity.
See scripts/core/make-sqlite-historian.sh for an example of how this
is done. Setting a historian's VIP IDENTITY from its configuration file will
not be supported after VOLTTRON 4.0. Using the identity configuration setting
will override the value provided by the platform. This new value will not be
reported correctly by 'volttron-ctl status'
