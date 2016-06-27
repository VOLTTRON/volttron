.. _Platform-Historian:

Platform Historian
==================

A platform historian is a `"friendly named" <VIP-Known-Identities>`__
historian on a VOLTTRON instance. It always has the identity (see
`vip <VIP-Known-Identities>`__) of platform.historian. A platform
historian is made available to a volttron central agent for monitoring
of the VOLTTRON instances health and plotting topics from the platform
historian. In order for one of the (historians)[Historians] to be turned
into a platform historian the identity keyword must be added to it's
configuration with the value of platform.historian. The following
configuration file shows a sqlite based platform historian
configuration.

::

    {
        "agentid": "sqlhistorian-sqlite",
        "identity": "platform.historian",
        "connection": {
            "type": "sqlite",
            "params": {
                "database": "~/.volttron/data/platform.historian.sqlite"
            }
        }
    }

The platform historian will publish data about the current environment
to the following topics. These topics can be pasted into the volttron
central environment and will be able to be graphed appropriately.

+---------+-----------------------------------------------------------------+
| Index   | Topic                                                           |
+=========+=================================================================+
| 1       | datalogger/log/platform/status/cpu/times\_percent/guest\_nice   |
+---------+-----------------------------------------------------------------+
| 2       | datalogger/log/platform/status/cpu/times\_percent/system        |
+---------+-----------------------------------------------------------------+
| 3       | datalogger/log/platform/status/cpu/percent                      |
+---------+-----------------------------------------------------------------+
| 4       | datalogger/log/platform/status/cpu/times\_percent/irq           |
+---------+-----------------------------------------------------------------+
| 5       | datalogger/log/platform/status/cpu/times\_percent/steal         |
+---------+-----------------------------------------------------------------+
| 6       | datalogger/log/platform/status/cpu/times\_percent/user          |
+---------+-----------------------------------------------------------------+
| 7       | datalogger/log/platform/status/cpu/times\_percent/nice          |
+---------+-----------------------------------------------------------------+
| 8       | datalogger/log/platform/status/cpu/times\_percent/iowait        |
+---------+-----------------------------------------------------------------+
| 9       | datalogger/log/platform/status/cpu/times\_percent/idle          |
+---------+-----------------------------------------------------------------+
| 10      | datalogger/log/platform/status/cpu/times\_percent/guest         |
+---------+-----------------------------------------------------------------+
| 11      | datalogger/log/platform/status/cpu/times\_percent/softirq       |
+---------+-----------------------------------------------------------------+

