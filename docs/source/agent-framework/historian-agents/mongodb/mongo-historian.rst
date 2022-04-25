.. _Mongo-Historian:

===============
Mongo Historian
===============

MongoDB is a NoSQL document database, which allows for great performance for transactional data.  Because MongoDB
documents do not have a schema, it is easy to store and query data which changes over time.  MongoDB also scales
horizontally using sharding.

For more information about MongoDB, read the `MongoDB documentation <https://docs.mongodb.com/>`_


Prerequisites
=============


1. Mongodb
----------

Setup mongodb based on using one of the three installation scripts for the corresponding environment:

1. Install as root on Redhat or Cent OS

    .. code-block:: bash

        sudo scripts/historian-scripts/root_install_mongo_rhel.sh

    The above script will prompt user for os version, db user name, password and database name.  Once installed you can
    start and stop the service using the command:

    .. code-block:: bash

        **sudo service mongod [start|stop|service]**

2. Install as root on Ubuntu

    .. code-block:: bash

        sudo scripts/historian-scripts/root_install_mongo_ubuntu.sh

    The above script will prompt user for os version, db user name, password and database name.  Once installed you can
    start and stop the service using the command:

    .. code-block:: bash

        **sudo service mongod [start|stop|service]**

3. Install as non root user on any Linux machine

    .. code-block:: bash

        scripts/historian-scripts/install_mongodb.sh

    Usage:

    .. code-block:: bash

       install_mongodb.sh [-h] [-d download_url] [-i install_dir] [-c config_file] [-s]

    Optional arguments:

       -s setup admin user and test collection after install and startup

       -d download url. defaults to https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz

       -i install_dir. defaults to current_dir/mongo_install

       -c config file to be used for mongodb startup. Defaults to default_mongodb.conf in the same directory as this
       script.  Any data path mentioned in the config file should already exist and should have write access to the
       current user

       -h print the help message


2. Mongodb connector
--------------------
This historian requires a mongodb connector installed in your activated VOLTTRON virtual environment to talk to MongoDB.
Please execute the following from an activated shell in order to install it:

.. code-block:: bash

    python bootstrap.py --mongo


or

.. code-block:: bash

    python bootstrap.py --databases


or

.. code-block:: bash

    pip install pymongo==3.7.2
    pip install bson
    pip install ujson


3. Configuration Options
------------------------

The historian configuration file can specify

::

    "history_limit_days": <n days>

which will remove entries from the data and rollup collections older than `n` days.  Timestamps passed to the
``manage_db_size`` method are truncated to the day.
