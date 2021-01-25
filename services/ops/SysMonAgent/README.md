## System Monitoring (SysMon) Agent

The System Monitoring Agent (colloquially “SysMon”) can be installed on the platform to monitor system resource metrics,
including percent CPU utilization, percent system memory (RAM) utilization, and percent storage (disk) utilization based
on disk path.

### Configuration

The SysMon agent has 5 configuration values:

- "base_topic":  Topic prefix used to publish all system metric points, is formatted with the metric function name in 
  publishes (i.e. "base/topic/prefix/cpu_percent")
- "cpu_check_interval":  Interval in seconds between publishes of % all core CPU utilization
- "memory_check_interval":  Interval in seconds between publishes of % system memory (RAM) utilization
- "disk_check_interval":  Interval in seconds between publishes of % disk (ROM) utilization for the configured disk
- "disk_path":  Directory path used as the root directory for a mounted disk (Currently, the SysMon agent supports 
  collecting metrics for only 1 disk at a time)

```json
{
   "base_topic": "datalogger/log/platform",
   "cpu_check_interval": 5,
   "memory_check_interval": 5,
   "disk_check_interval": 5,
   "disk_path": "/"
}
```


### Periodic Publish

At the interval specified by the configuration option for each resource, the agent will automatically query the system 
for the resource utilization statistics and publish it to the message bus using the topic as previously described.  The 
message content for each publish will contain only a single numeric value for that specific topic.  Currently, 
“scrape_all” style publishes are not supported.

Example publish:

```
2020-03-10 11:20:33,755 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/cpu_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
4.8
2020-03-10 11:20:33,804 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/memory_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
35.6
2020-03-10 11:20:33,809 (listeneragent-3.3 7993) listener.agent INFO: Peer: pubsub, Sender: platform.sysmon:, Bus: , Topic: datalogger/log/platform/disk_percent, Headers: {'min_compatible_version': '3.0', 'max_compatible_version': ''}, Message:
65.6
```


### JSON RPC Methods

- cpu_percent:  Returns current % all core CPU utilization, takes no parameters
- memory_percent:  Returns current % system memory (RAM) utilization, takes no parameters
- disk_percent:  Returns current % disk (ROM) utilization for the configured disk, takes no parameters
