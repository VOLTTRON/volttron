.. _Forward-Historian:
Forward Historian
===================

The forward historian can be found in the core services directory. Use
it to send information to another Volttron instance.

Configuration
-------------

The default configuration file is
*services/core/ForwardHistorian/config* . Change **destination-vip** to
point towards the foreign Volttron instance.

::

    {
        "agentid": "forwarder"
        "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
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
