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
                "database": "data/historian.sqlite",
            }
        }
    }

