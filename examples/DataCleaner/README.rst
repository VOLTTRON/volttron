.. _DataCleaner:

===========
DataCleaner
===========

This is a simple agent that periodically queries platform.historian, cleans the
data based on configuration parameters and republishes it to a configured topic.

This is a good starting point for creating agents that modify and republish data at specific intervals.

Configuration
-------------

::

    {
      "period": 900, # Post cleaned data every 15 minutes.
      # Points to clean.
      "points": {
        # Point to query from the historian.
        "fake0/OutsideAirTemperature1": {
          # Cap republished values to [0,100]
          "min_value": 0,
          "max_value": 100,
          # Publish results to this topic
          "output_topic": "record/cleaned/fake0/OutsideAirTemperature1",
          # If data is stale use this method to create a new value.
          "aggregate_method": "avg"
        },
        "fake0/SampleWritableFloat1": {
          "min_value": 50,
          "max_value": 75,
          "output_topic": "record/cleaned/fake0/SampleWritableFloat1"
        },
        "fake0/SampleLong1": {
          "min_value": 25,
          "max_value": 125,
          "output_topic": "record/cleaned/fake0/SampleLong1"
        }
      }
    }