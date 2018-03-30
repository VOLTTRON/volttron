.. _SQL_Historian:

============
SQLHistorian
============

This is a historian agent that writes data to a SQLite or Mysql database
based on the connection parameters in the configuration. The sql historian has
been programmed to allow for inconsistent network connectivity
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

2. The mysql user must have READ, WRITE, UPDATE, and DELETE privileges.

3. The tables in the sql database be created as part of the execution of
   the SQLHistorianAgent only if the database user has CREATE privileges.
   If not, use the mysql-create*.sql script to create the tables and then
   start agent.

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
**Not all parameters have been tested, use at your own risk**.

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

SQLite3
~~~~~~~

An Sqlite historian provides a convenient solution for under powered
systems. The database parameter is a location on the file system. By
default it is relative to the agents installation directory, however it
will respect a rooted or relative path to the database.

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


Notes
~~~~~
Do not use the "identity" setting in configuration file. Instead use the
new method provided by the platform to set an agent's identity.
See scripts/core/make-sqlite-historian.sh for an example of how this
is done. Setting a historian's VIP IDENTITY from its configuration file will
not be supported after VOLTTRON 4.0. Using the identity configuration setting
will override the value provided by the platform. This new value will not be
reported correctly by 'volttron-ctl status'