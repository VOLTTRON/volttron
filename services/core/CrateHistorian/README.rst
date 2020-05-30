.. _Crate_Historian:

===============
Crate Historian
===============

Crate is an open source SQL database designed on top of a No-SQL design.  It
allows automatic data replication and self-healing clusters for high
availability, automatic sharding, and fast joins, aggregations and sub-selects.

Find out more about crate from `<https://crate.io/>`_.

Upgrading
~~~~~~~~~

As of version 3 of the CrateHistorian the default topics table is topics instead of topic.  To continue
using the same table name for topics please add a tabledef section to your configuration file

.. code-block:: python

    {
        "connection": {
            "type": "crate",
            # Optional table prefix defaults to historian
            "schema": "testing",
            "params": {
                "host": "localhost:4200"
            }
        },
        "tables_def": {
            "table_prefix": "",
            "data_table": "data",
            "topics_table": "topics",
            "meta_table": "meta"
        }
    }

Note
~~~~

CrateHistorian is still alpha, schemas could change in the future, do not use
this for production data until schema is confirmed as final
Currently the historian supports two schemas for numerical data, the primary
schema closely resembles the SQLHistorian schema but there is an optional
"raw" schema that can be enabled in the config below that utilizes some of
the advanced indexing features of crate


Prerequisites
~~~~~~~~~~~~~

1. Crate Database
-----------------

Install crate version 3.3.3 from https://cdn.crate.io/downloads/releases/crate-3.3.3.tar.gz.
Untar the file and run crate-3.3.3/bin/crate to start crate. After the installation
the service will be available for viewing at http://localhost:4200 by default.

.. note::  Authentication for crate is an enterprise subscription only feature.

2. Crate Driver
---------------

There is a python library for crate that must be installed in the volttron
python environment in order to access crate.  From an activated environment,
in the root of the volttron folder, execute the following command:

    ::

        python bootstrap.py --crate

or

    ::

        pip install crate


Configuration
~~~~~~~~~~~~~
The following is an example of the crate historian's configuration.

.. code-block:: python

    {
        "connection": {
            "type": "crate",
            # Optional table prefix defaults to historian
            "schema": "testing",
            "params": {
                "host": "localhost:4200"
            }
        }
    }

