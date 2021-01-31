## Threshold Detection Agent

The ThresholdDetectionAgent will publish an alert when a value published to a topic exceeds or falls below a configured
value.

The agent subscribes to the topics listed in the configuration file and publishes alerts when the callback receives a 
value for the point above the max (if configured) or below the min (if configured) corresponding to the point in the
configuration file.


### Configuration

The Threshold Detection agent supports observing individual point values from their respective topics or from a device's
all publish.  Points to watch are configured as JSON key-value pairs as follows:

* Key:  The key is the point topic for the point to watch, or the device's "all" topic if watching points from the all 
publish (i.e. "devices/campus/building/device/point" or "devices/campus/building/device/all" if using the all topic)

* Value:  Using point topic: JSON object specifying the min ('threshold_min') and max ('threshold_max) threshold values 
for the point.  Only one of the thresholds are required, but both may be used.

Example:

```json
{
    "point0": {
        "threshold_max": 10,
        "threshold_min": 0
    },
    "point1": {
        "threshold_max": 42
    }
}
```

Using device "all" topic:  JSON object with the key as the point name and value being the threshold object described
above

Example

```json
{
    "devices/some/device/all": {
        "point0": {
            "threshold_max": 10,
            "threshold_min": 0
        },
        "point1": {
            "threshold_max": 42
        }
    }
}
```

Example configuration:

```json
{
    "datalogger/log/platform/cpu_percent": {
      "threshold_max": 99
    },
    "datalogger/log/platform/memory_percent": {
      "threshold_max": 99
    },
    "datalogger/log/platform/disk_percent": {
      "threshold_max": 97
    },
    "devices/campus/building/fake/all": {
        "EKG_Sin": {
            "threshold_max": 0.1,
            "threshold_min": -0.1
        }
    }
}
```


### Example Publish

This example publish uses the example config above along with a fake driver running on the platform.

```
Peer: pubsub
Sender: platform.thresholddetection
Bus:
Topic: alerts/ThresholdDetectionAgent/james_platform_thresholddetection
Headers: {'alert_key': 'devices/campus/building/fake/all', 'min_compatible_version': '3.0', 'max_compatible_version': ''}
Message: ('{"status": "BAD", "context": "devices/campus/building/fake/all(EKG_Sin) '
            'value (-0.4999999999999997)is below acceptable limit (-0.1)", '
            '"last_updated": "2021-01-25T22:39:35.035606+00:00"}')
```
