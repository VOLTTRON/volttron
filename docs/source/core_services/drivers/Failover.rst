Data Collection Failover
========================


Introduction
------------

The failover system is an optional feature that extends the `master
driver <master-driver-agent>`__. Similarly configured Volttron instances
collect from the same device(s) for easy horizontal scaling. Instances
will take turns scraping and publishing data so that each has more free
cycles between scrapes. If one dies, those remaining won't be
interrupted. It can currently be found in the feature/failover branch.

::

                    |             |
     ________       | Collector 0 |             ________
    |        |----->|_____________|----------->|        |
    | DEVICE |       _____________             | Target |
    |________|----->|             |----------->|________|
                    | Collector 1 |
                    |_____________|

Configuration
-------------

Redundant Volttron instances will have almost identical configurations.
The following variables tell the drivers how periodic scrape intervals
should be adjusted:

-  **failover\_array\_size** - The number of collecting instances.
-  **failover\_instance\_id** - Zero is the first instance.

Below is an example of a master driver's config file using the failover
feature. This will be one instance in a pair.

::

    {
        "agentid": "master_driver",
        "failover_array_size": 2,
        "failover_instance_id": 0,
        # "failover_instance_id": 1,

        "driver_config_list": ["driver1.config", "driver2.config"]
    }

To Do
~~~~~

-  Automatically reschedule collection when an instance fails.
-  Dynamically add and remove instances from a collection array. This
   should be available in VC.

