Introduction
------------
The failover agent provides a generic high availability option to volttron.

::

                     _____________
                    |             |
     ________       | Collector 0 |             ________
    |        |----->|_____________|----------->|        |
    | DEVICE |       _____________             | Target |
    |________|----->|             |----------->|________|
                    | Collector 1 |
                    |_____________|

Configuration
-------------

::

    {
        "agent_id": "primary",
        "remote_id": "secondary",
        "remote_vip": "tcp://127.0.0.1:8001",

        "volttron_ctl_tag": "master",

        "heartbeat_period": 10,
        "check_pulse_interval": 10,

        "timeout": 120
    }
