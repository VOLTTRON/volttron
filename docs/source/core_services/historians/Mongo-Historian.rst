Mongo Historian
===============
.. sectnum::

Prerequisites
~~~~~~~~~~~~~

Mongodb
-------

Setup mongodb based on using one of the three below scripts. The scripts
provide command line options or user prompts to configure user name, password,
and database name.

Install as root on Redhat or Cent OS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    sudo scripts/historian-scripts/root_install_mongo_rhel.sh

Install as non root user on any Linux machine
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    scripts/historian-scripts/install_mongodb.sh

Usage:
   install_mongodb.sh [-h] [-d download_url] [-i install_dir] [-c config_file] [-s]
Optional arguments:
   -s setup admin user and test collection after install and startup
   -d download url. defaults to https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz
   -i install_dir. defaults to current_dir/mongo_install
   -c config file to be used for mongodb startup. Defaults to default_mongodb.conf in the same directory as this script
      Any datapath mentioned in the config file should already exist and should have write access to the current user
   -h print this help message
Mongodb connector
~~~~~~~~~~~~~~~~~
This historian requires a mongodb connector installed in your activated
volttron environment to talk to mongodb. Please execute the following
from an activated shell in order to install it.

::

    pip install pymongo

