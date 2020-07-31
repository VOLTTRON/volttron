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


