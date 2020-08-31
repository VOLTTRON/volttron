.. _Data-Mover-Historian:

====================
Data Mover Historian
====================

The Data Mover sends data from its platform to a remote platform in cases where there are not sufficient resources to
store data locally.  It shares this functionality with the :ref:`Forward Historian <Forward-Historian>`, however the
Data Mover does not have the goal of data appearing "live" on the remote platform.  This allows DataMover to be more
efficient by both batching data and by sending an RPC call to a remote historian instead of publishing data on the
remote message bus.  This allows allows the Data Mover to be more robust by ensuring that the receiving historian is
running.  If the target is unreachable, the Data Mover will cache data until it is available.


Configuration
=============

The default configuration file is `services/core/DataMover/config`. Change the `destination-vip` value to
point towards the foreign Volttron instance.

The following is an example configuration:

::

    {
        "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket",
        "destination-serverkey": null,
        "required_target_agents": [],
        "custom_topic_list": [],
        "services_topic_list": [
            "devices", "analysis", "record", "datalogger", "actuators"
        ],
        "topic_replace_list": [
            #{"from": "FromString", "to": "ToString"}
        ]
    }


The `services_topic_list` allows you to specify which of the main data topics to forward.  If there is no entry, the
historian defaults to sending all.

`topic_replace_list` allows you to replace portions of topics if needed.  This could be used to correct or standardize
topics or to replace building/device names with an anonymous version.  The receiving platform will only see the
replaced values.

Adding the configuration option below will limit the backup cache to `n` gigabytes.  This will keep a hard drive from
filling up if the agent is disconnected from its target for a long time.

::

   "backup_storage_limit_gb": n

.. seealso::

    :ref:`Historian Framework <Historian-Framework>`
