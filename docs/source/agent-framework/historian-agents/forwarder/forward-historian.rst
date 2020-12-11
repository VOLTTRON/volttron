.. _Forward-Historian:

=================
Forward Historian
=================

The primary use case for the Forward Historian is to send data to another instance of VOLTTRON as if the data were live.
This allows agents running on a more secure and/or more powerful machine to run analysis on data being collected on a
potentially less secure/powerful board.

Given this use case, it is not optimized for batching large amounts of data when "live-ness" is not needed.  For this
use case, please see the :ref:`Data Mover Historian <Data-Mover-Historian>`.

The Forward Historian can be found in the `services/core directory`.


Configuration
=============

The default configuration file is `services/core/ForwardHistorian/config`.  Change the `destination-vip` value to
point towards the foreign VOLTTRON instance.

.. code-block:: json

    {
        "agentid": "forwarder",
        "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
    }

In order to send to a remote platform, you will need its :term:`VIP address` and server key.  The server key can be
found by running:

.. code-block:: bash

    vctl auth serverkey

Put the result into the following example:

.. note::

    The example shown uses the local IP address, the IP address for your configuration should match the intended target

.. code-block:: json

    {
        "agentid": "forwarder",
        "destination-vip": "tcp://127.0.0.1:22916",
        "destination-serverkey": "<SOME_KEY>"
    }


Adding the configuration option below will limit the backup cache to `n` gigabytes.  This will help keep a hard drive
from filling up if the agent is disconnected from its target for a long time.

::

   "backup_storage_limit_gb": n

.. seealso::

    :ref:`Historian Framework <Historian-Framework>`
