Failover Agent
==============

Introduction
------------
The failover agent provides a generic high availability option to volttron.
When the **primary** platform becomes inactive the **secondary** platform
will start an installed agent.

There are two behavior patterns implemented in the agent. In the default
configuration, the secondary instance will ask volttron central to verify
that the primary instance is down. This helps to avoid a split brain scenario.
If neither volttron central nor the other failover instance is reachable
then the failover agent will stop the agent it is managing.

There is also a *simple* configuration available that does not involve
coordination with volttron central. The secondary agent will start its managed
agent if believes the primary to be inactive. The simple primary always has its
managed agent started.


Configuration
-------------
Failover behavior is set in the failover agent's configuration file. Example
primary and secondary configuration files are shown below.

::

    {                                          |    {
        "agent_id": "primary",                 |        "agent_id": "secondary",
        "remote_id": "secondary",              |        "remote_id": "primary",
        "remote_vip": "tcp://127.0.0.1:8001",  |        "remote_vip": "tcp://127.0.0.1:8000",
                                               |
        "volttron_ctl_tag": "master",          |        "volttron_ctl_tag": "master",
                                               |
        "heartbeat_period": 10,                |        "heartbeat_period": 10,
        "check_pulse_interval": 10,            |        "check_pulse_interval": 10,
                                               |
        "timeout": 120                         |        "timeout": 120
    }                                          |    }

- **agent_id** - primary/secondary **or** simple_primary/simple_secondary
- **remote_id** - primary/secondary **or** simple_primary/simple_secondary
- **remove_vip** - Address where *remote_id* can be reached. Don't forget add keys if you are using encryption.
- **volttrol_ctl_tag** - The tag of the agent that we want to manage.
- **heartbeat_period** - Send a message to *remote_id* with this period. Measured in seconds.
- **check_pulse_interval** - Period to check for remote platform timeouts. Measured in seconds.
- **timeout** - Consider a platform inactive if a heartbeat has not been received for *timeout* seconds.
