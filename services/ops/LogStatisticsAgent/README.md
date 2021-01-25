## Log Statistics Agent

The Log Statistics agent periodically reads the "volttron.log" file, computes the size delta from the previous hour 
and publishes the difference with a timestamp.  It also publishes standard deviation of the size delta every 24 hours.
This agent is useful for ___.

### Configuration

The Log Statistics agent has 4 configuration values:

- "file_path":  This should be the path to the "volttron.log" file, defaults to "$VOLTTRON_HOME/volttron.log"
- "analysis_interval_secs":  The interval in seconds between publishing the size delta statistic to the message bus
- "publish_topic":  Can be used to specify a topic to publish log statistics to which does not get captured by the 
  historian framework
- "historian_topic":  Can be used to specify a topic to publish log statistics to which gets captured by the 
  historian framework ("datalogger", "record", "analysis", "devices")

The following is an example configuration file:

```json
    {
        "file_path" : "~/volttron/volttron.log",
        "analysis_interval_min" : 60,
        "publish_topic" : "platform/log_statistics",
        "historian_topic" : "record/log_statistics"
    }
```

### Usage

The Log Statistics agent will run statistics publishes automatically based on the configured intervals.

The following is an example of a periodic size delta publish:

ADDED IN FUTURE UPDATE
