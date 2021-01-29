## Topic Watcher Agent

The Topic Watcher Agent listens to a set of configured topics and publishes an alert if they are not published within 
some time limit.  In addition to for individual messages or data points, the Topic Watcher Agent supports inspecting 
device "all" topics.  This can be useful when a device contains volatile points that may not be published.


### Configuration

Topics are organized by groups in a JSON structure with the group's identifier as the key. Any alerts raised will 
summarize all missing topics in the group.

There are two configuration options for watching topics.  For single message topics (such as a single 
device point), configuration consists of a key value pair of the topic to its time limit.

```
{
    "groupname: {
        "devices/campus/building/point": 10
    }
}
```

For points published in an "all" style publish, configuration consts of a key mapping to an object as follows:
A `seconds` key for the time limit in seconds, and a `points` key consisting of a list of individual points in the
`all` publish. 

The following is an example "all" publish configuration which configures the Topic Watcher to check for the `temperature`
and `PowerState` points which are expected to be inside the "all" publishes.

```
{
    "groupname": {
            "devices/fakedriver1/all": {
            "seconds": 10,
            "points": ["temperature", "PowerState"]
        }
    }
}
```

It is possible to configure the Topic Watcher to handle both "all" topics and single point topics for the same group:

```
{
    "groupname": {
        "devices/fakedriver0/all": 10,
        "devices/fakedriver1/all": {
            "seconds": 10,
            "points": ["temperature", "PowerState"]
        }
    }
}
```


### Example Publish

The following is an example publish from the Topic Watcher Agent using the above configuration.

```
Peer: pubsub
Sender: platform.topic_watcher
Bus: 
Topic: alerts/AlertAgent/james_platform_topic_watcher
Headers: {'alert_key': 'AlertAgent Timeout for group group1', 'min_compatible_version': '3.0', 'max_compatible_version': ''}
Message: ('{"status": "BAD", "context": "Topic(s) not published within time limit: '
           '[\'devices/fakedriver0/all\']", "last_updated": '
           '"2021-01-25T23:10:07.905633+00:00"}')
```
