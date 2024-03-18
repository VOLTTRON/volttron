## Log Statistics Agent

The Log Statistics agent periodically reads the "volttron.log" file based on the configured interval, computes the size 
delta from the previous hour and publishes the difference in bytes with a timestamp.  It also publishes standard 
deviation of the size delta every 24 hours.  This agent can be useful for detecting unexpected changes to the system 
which may be an indication of some sort of failure or breach.


### Configuration

The Log Statistics agent has 4 configuration parameters, all of which are required:

- `file_path`:  The file path to the log file. If left as `null`, defaults to `'volttron.log'` located within your VOLTTRON_HOME environment variable.
- `analysis_interval_secs`: The interval in seconds between publishes of the size delta statistic to the message bus. If left as `null`, defaults to 60 seconds.
- `publish_topic`: Used to specify a topic to publish log statistics to which does not get captured by the
  historian framework (topics not prefixed by any of: "datalogger", "record", "analysis", "devices"). If left as `null`, defaults to `"platform/log_statistics"`.
- `historian_topic`:  Can be used to specify a topic to publish log statistics to which gets captured by the
  historian framework ("datalogger", "record", "analysis", "devices"). If left as `null`, defaults to `record/log_statistics`.

```json
{
  "analysis_interval_sec": 60,
  "file_path": null,
  "historian_topic": "analysis/log_statistics",
  "publish_topic": "platform/log_statistics"
}
```


### Periodic Publish

The Log Statistics agent will run statistics publishes automatically based on the configured intervals.

The following is an example of a periodic size delta publish:

```
Peer: pubsub
Sender: platform.logstatisticsagent1
Bus:
Topic: platform/log_statistics
Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}
Message: {'log_size_delta': 902, 'timestamp': '2021-01-25T22:48:16.924135Z'}
```
