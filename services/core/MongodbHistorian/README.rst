.. _Mongo_Historian:

===============
Mongo Historian
===============
This is a historian that stores its data in mongodb. Data is store in three
different collection as

    1. raw data
    2. hourly grouped/rolled up data
    3. daily grouped/rolled up data

The hourly_data and daily_data collections store data grouped together by time
to allow for faster queries. It does not aggregate data (point values). Data
gets loaded into hourly and daily collections through a periodic batch process
and hence might be lagging behind when compared to raw data collection. The
lag time would depend on the load on the system and hence needs to be set in
the configuration. Query API of mongo historian is designed to handle this. It
will combine results from rollup data and raw data table as needed.

Prerequisites
~~~~~~~~~~~~~

1. Mongodb
----------

Setup mongodb based on using one of the three below scripts.

1. Install as root on Redhat or Cent OS

    ::

        sudo scripts/historian-scripts/root_install_mongo_rhel.sh

    The above script will prompt user for os version, db user name, password
    and database name. Once installed you can start and stop the service
    using the command:

    **sudo service mongod [start|stop|service]**

2. Install as root on Ubuntu

    ::

        sudo scripts/historian-scripts/root_install_mongo_ubuntu.sh

    The above script will prompt user for os version, db user name, password
    and database name. Once installed you can start and stop the service
    using the command:

    **sudo service mongod [start|stop|service]**

3. Install as non root user on any Linux machine

    ::

        scripts/historian-scripts/install_mongodb.sh

    Usage:
       install_mongodb.sh [-h] [-d download_url] [-i install_dir] [-c config_file] [-s]
    Optional arguments:
       -s setup admin user and test collection after install and startup

       -d download url. defaults to https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz

       -i install_dir. defaults to current_dir/mongo_install

       -c config file to be used for mongodb startup. Defaults to
       default_mongodb.conf in the same directory as this script.Any datapath
       mentioned in the config file should already exist and should have write
       access to the current user

       -h print this help message

2. Create database and user
---------------------------

You also need to pre-create your database in MongoDB before running this
historian. For example, to create a local MongoDB, do the followings in
Mongo shell:

- Switch to the new database "volttron_guide":

    ::

      use volttron_guide

- Create a new user for "volttron_guide":

    ::

      db.createUser({user: "admin", pwd: "admin", roles: ["readWrite"] })

3. Mongodb connector
--------------------
This historian requires a mongodb connector installed in your activated
volttron environment to talk to mongodb. Please execute the following
from an activated shell in order to install it.

::

    pip install pymongo


Configuration
~~~~~~~~~~~~~
::

    {
        #mandatory connection details
        "connection": {
            "type": "mongodb",
            "params": {
                "host": "localhost",
                "port": 27017,
                "database": "test_historian",
                "user": "historian",
                "passwd": "historian"
            }
        },

        #run historian in query/read only mode and not to record any data into the
        database. Default false. optional
        "readonly":false,

        # configuration specific to hourly and daily rollup tables
        # new from version 2.0 of mongo historian. Most of these configurations
        # would become optional once data collected by earlier version of mongo
        # has been batch processed to roll up into hourly and daily
        # collections.

        ## configurations related to rollup data creation

        # From when should historian start rolling up data into hourly and daily
        # collection. Rolling up this way makes queries more efficient
        # datetime in "%Y-%m-%dT%H:%M:%S.%f" format and in UTC. Typically this
        # should be a date close to the initial use of newer(>=2.0) version of
        # mongo historian. Older data should be rolled up using a separate
        # background process(see rollup_data_by_time.py script under
        # MongodbHistorian/scripts. Default value = current time at the time of
        # historian start up

        "initial_rollup_start_time":"2017-01-01T00:00:00.000000",

        # How long should the historian wait after startup to start
        # rolling up raw data into hourly and daily collections. Wait in minutes.
        # Default 15 seconds

        "periodic_rollup_initial_wait":0.1,

        # How often should the function to rollup data be called. The process of
        # rolling up raw data into hourly and daily collections happens in a
        # separate process that is run periodically
        # units - minutes. Default 1 minute

        "periodic_rollup_frequency":1,

        ## configuration related to using rolled up data for queries

        # Start time from which hourly and daily rollup tables can be used for
        # querying. datetime string in UTC. Format "%Y-%m-%dT%H:%M:%S.%f". Default
        # current time (at init of historian)  +  1day

        "rollup_query_start":"2017-01-01T00:00:00.000000",

        # number of days before current time, that can be used as end
        # date for queries from hourly or daily data collections. This is to
        # account for the time it takes the periodic_rollup to process
        # records in data table and insert into daily_data and hourly_data
        # collection. Units days. Default 1 day

        "rollup_query_end":5,

        # topic name patterns for which rollup exists. Set this if rollup was done
        # for only a subset of topics

        "rollup_topic_pattern": "^Economizer_RCx|^Airside_RCx"

    }


