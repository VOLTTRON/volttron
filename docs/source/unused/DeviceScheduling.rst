The ActuatorAgent can take a schedule for specifying which agents are
eligible to get a lock during the day. Currently, the schedule is
repeated every day. To change the schedule, set a new file and restart
the agent.

The schedule is set in the ActuatorAgent's launch config file:

::

        "points":
        {
            "lbnl/building46/fakecatalyst":
            {
                "heartbeat_point":"ESMMode",
                "schedule":
                {
                    "17:00": ["foo1", "bar1"],
                    "17:03": ["foo2", "bar2"],
                    "17:06": ["foo3", "bar3"],
                    "17:09": ["foo4", "bar4"]
                }
            },
            "campus1/building1/catalyst2":
            {
                "schedule":
                {
                    "03:00": ["foo1", "bar1"],
                    "11:00": ["foo2", "bar2"],
                    "17:00": ["foo3", "bar3"],
                    "18:00": ["foo4", "bar4"]
                }
            }
         }

