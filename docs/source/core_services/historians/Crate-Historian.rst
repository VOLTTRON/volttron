.. _Crate-Historian:

===============
Crate Historian
===============

Crate is an open source SQL database designed on top of a No-SQL design.  It
allows automatic data replication and self-healing clusters for high
availability, automatic sharding, and fast joins, aggregations and sub-selects.

Find out more about crate from `<https://crate.io/>`_.


Prerequisites
~~~~~~~~~~~~~

1. Crate Database
-----------------

For Arch Linux, Debian, RedHat Enterprise Linux and Ubuntu distributions there
is a dead simple installer to get crate up and running on your system.

    ::

        sudo bash -c "$(curl -L https://try.crate.io)"

This command will download and install all of the requirements for running
crate, create a crate user and install a crate service.  After the installation
the service will be available for viewing at http://localhost:4200 by default.

.. note::  There is no authentication support within crate.


2. Crate Driver
---------------

There is a python library for crate that must be installed in the volttron
python environment in order to access crate.  From an activated environment,
in the root of the volttron folder, execute the following command:

    ::

        python bootstrap.py --crate


or

    ::

        python bootstrap.py --crate


or

    ::

        pip install crate


Configuration
~~~~~~~~~~~~~

Because there is no authorization to access a crate database the configuration
for the CrateHistorian is very easy.

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

Finally package, install and start the CrateHistorian agent.

.. seealso::  :ref:`Agent Development Walkthrough <Agent-Development#packaging-agent>`
