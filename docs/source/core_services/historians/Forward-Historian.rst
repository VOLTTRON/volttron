.. _Forward-Historian:
Forward Historian
===================

The primary use case for the ForwardHistorian is to send data to another
instance of VOLTTRON as if the data were live. This allows agents running on a
more secure and/or more powerful machine to run analysis on data being
collected on a potentially less secure/powerful board.

Given this use case, it is not optimized for batching large amounts of data
when liveness is not needed. For this use case, please see the
:ref:`DataMover Historian <DataMover>`.

The forward historian can be found in the services/core directory.

Configuration
-------------

The default configuration file is
*services/core/ForwardHistorian/config* . Change **destination-vip** to
point towards the foreign Volttron instance.

::

    {
        "agentid": "forwarder",
        "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
    }

In order to send to a remote platform, you will need its VIP address and server
key. The server key can be found by running

::

    volttron-ctl auth serverkey

Put the result into the following example
(Note the example uses a local IP address)

::

    {
        "agentid": "forwarder",
        "destination-vip": "tcp://127.0.0.1:22916",
        "destination-serverykey": "<SOME_KEY>"
    }


Adding the configuration option below will limit the backup cache
to *n* gigabytes. This will keep your hard drive from filling up if
the agent is disconnected from its target for a long time.

::

   "backup_storage_limit_gb": n

See Also
~~~~~~~~

`Historians <historians>`_
:ref:`Historians <historians>`
