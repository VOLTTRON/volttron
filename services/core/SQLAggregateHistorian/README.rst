.. _SQL_Aggregate_Historian:

=======================
SQL Aggregate Historian
=======================

An aggregate historian computes aggregates of data stored in a given volttron
historian's data store. It runs periodically to compute aggregate data
and store it in new tables/collections in the historian's data store. Each
historian implementation would use a corresponding aggregate historian to
compute and store aggregates.

Aggregates can be defined for a specific time interval and can be calculated
for one or more topics. For example, 15 minute average of topic1 or 15 minute
average of values of topic1 and topic2. Current version of this agent only
computes aggregates supported by underlying data store. When aggregation is
done over more than one topic a unique aggregation topic name should be
configured by user. This topic name can be used in historian's query api to
query the collected aggregate data.

Note: This agent doesn't not compute dynamic aggregates. It is only useful when
you know what kind of aggregate you would need before hand and have them be
collected periodically so that retrieval of that data at a later point would be
faster

Data flow between historian and aggregate historian
---------------------------------------------------

  1. Historian collects data from devices and stores it in its data store
  2. Aggregate historian periodically queries historian's data store for data within configured time period.
  3. Aggregate historian computes aggregates and stores it in historian's data store
  4. Historian's query api queries aggregate data when used with additional parameters - agg_type, agg_period

Configuration
-------------

.. code-block:: python

    {
        # configuration from mysql historian - START
        "connection": {
            "type": "mysql",
            "params": {
                "host": "localhost",
                "port": 3306,
                "database": "test_historian",
                "user": "historian",
                "passwd": "historian"
            }
        },
        # configuration from mysql historian - END
        # If you are using a differnt historian(sqlite3, mongo etc.) replace the
        # above with connection details from the corresponding historian.
        # the rest of the configuration would be the same for all aggregate
        # historians

        "aggregations":[
            # list of aggregation groups each with unique aggregation_period and
            # list of points that needs to be collected. value of "aggregations" is
            # a list. you can configure this agent to collect multiple aggregates.
            # aggregation_time_periiod + aggregation topic(s) together uniquely
            # identify an aggregation

            {
                # can be minutes(m), hours(h), weeks(w), or months(M)

                "aggregation_period": "1m",

                # Should aggregation period align to calendar time periods.
                # Default False
                # Example,
                # if "aggregation_period":"1h" and "use_calendar_time_periods": False
                # example periods: 10.15-11.15, 11.15-12.15, 12.15-13.15 etc.
                # if "aggregation_period":"1h" and "use_calendar_time_periods": True
                # example periods: 10.00-11.00, 11.00-12.00, 12.00-13.00 etc.

                "use_calendar_time_periods": "true",

                # topics to be aggregated

                "points": [
                        {
                        # here since aggregation is done over a single topic name
                        # same topic name is used for the aggregation topic
                        "topic_names": ["device1/out_temp"],
                        "aggregation_type": "sum",
                        #minimum required records in the aggregation time period for aggregate to be recorded
                        "min_count": 2
                        },
                        {
                        "topic_names": ["device1/in_temp"],
                        "aggregation_type": "sum",
                        "min_count": 2
                        }
                    ]
            },
            {
                "aggregation_period": "2m",
                "use_calendar_time_periods": "false",
                "points": [
                    {
                     # aggregation over more than one topic so aggregation_topic_name should be specified
                     "topic_names": ["Building/device/point1", "Building/device/point2"],
                     "aggregation_topic_name":"building/device/point1_2/month_sum",
                     "aggregation_type": "avg",
                     "min_count": 2
                    }
                ]
            }
        ]
    }


See Also
--------
 `AggregateHistorianSpec`_
