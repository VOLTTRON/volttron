Mongo Historian
===============


Prerequisites
~~~~~~~~~~~~~

Mongodb
-------

Setup mongodb based on using one of the three below scripts. The scripts
provide command line options or user prompts to configure user name, password,
and database name.

Install as root on Redhat or Cent OS
::

    sudo scripts/historian_scripts_root_install_mongo_rhel.sh

Install as root on Ubuntu
::

    sudo scripts/historian_scripts_root_install_mongo_ubuntu.sh

Install as non root user on any Linux machine
::

    sudo scripts/historian_scripts_root_install_mongo_ubuntu.sh

Mongodb connector
~~~~~~~~~~~~~~~~~
This historian requires a mongodb connector installed in your activated
volttron environment to talk to mongodb. Please execute the following
from an activated shell in order to install it.

::

    pip install pymongo

