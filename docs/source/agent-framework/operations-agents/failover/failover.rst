.. _Failover-Agent:

Failover Agent
==============

Introduction
------------
The failover agent provides a generic high availability option to VOLTTRON.
When the **primary** platform becomes inactive the **secondary** platform
will start an installed agent.


Standard Failover
-----------------

There are two behavior patterns implemented in the agent. In the default
configuration, the secondary instance will ask Volttron Central to verify
that the primary instance is down. This helps to avoid a split brain scenario.
If neither Volttron Central nor the other failover instance is reachable
then the failover agent will stop the agent it is managing. These states are
shown in the tables below.

**Primary Behavior**

+-----------------+-------+---------+
|                 | VC Up | VC Down |
+-----------------+-------+---------+
| Secondary Up    | start | start   |
+-----------------+-------+---------+
| Secondary Down  | start | stop    |
+-----------------+-------+---------+

**Secondary Behavior**

+--------------+-----------------+---------+
|              | VC Up           | VC Down |
+--------------+-----------------+---------+
| Primary Up   | stop            | stop    |
+--------------+-----------------+---------+
| Primary Down | Verify with VC  | stop    |
|              | before starting |         |
+--------------+-----------------+---------+


Simple Failover
---------------

There is also a *simple* configuration available that does not involve
coordination with Volttron Central. The secondary agent will start its managed
agent if believes the primary to be inactive. The simple primary always has its
managed agent started.


Configuration
-------------
Failover behavior is set in the failover agent's configuration file. Example
primary and secondary configuration files are shown below.

::

    {                                           |    {
        "agent_id": "primary",                  |        "agent_id": "secondary",
        "simple_behavior": true,                |        "simple_behavior": true,
                                                |
        "remote_vip": "tcp://127.0.0.1:8001",   |        "remote_vip": "tcp://127.0.0.1:8000",
        "remote_serverkey": "",                 |        "remote_serverkey": "",
                                                |
        "agent_vip_identity": "platform.driver",|        "agent_vip_identity": "platform.driver",
                                                |
        "heartbeat_period": 10,                 |        "heartbeat_period": 10,
                                                |
        "timeout": 120                          |        "timeout": 120
    }                                           |    }

- **agent_id** - primary **or** secondary
- **simple_behavior** - Switch to turn on or off simple behavior. Both isnstances should match.
- **remote_vip** - Address where *remote_id* can be reached.
- **remote_serverkey** - The public key of the platform where *remote_id* lives.
- **agent_vip_identity** - The :term:`VIP Identity` of the agent that we want to manage.
- **heartbeat_period** - Send a message to *remote_id* with this period. Measured in seconds.
- **timeout** - Consider a platform inactive if a heartbeat has not been received for *timeout* seconds.
