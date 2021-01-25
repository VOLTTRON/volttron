## Threshold Detection Agent

The ThresholdDetectionAgent will publish an alert when a value published to a topic exceeds or falls below a configured
value.

The agent subscribes to the topics listed in the configuration file and publishes alerts when the callback receives a 
value for the point above the max (if configured) or below the min (if configured) corresponding to the point in the
configuration file.


### Configuration

The Threshold Detection agent supports observing individual point values from their respective topics or from a device's
all publish.  Points to watch are configured as JSON key-value pairs as follows:

Key:  
    The key is the point topic for the point to watch, or the device's "all" topic if watching points from the all 
    publish (i.e. "devices/campus/building/device/point" or "devices/campus/building/device/all" if using the all topic)
Value:
    Using point topic: JSON object specifying the min ('threshold_min') and max ('threshold_max) threshold values for 
    the point.  Only one of the thresholds are required, but both may be used.

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


### Example Publish

TO BE ADDED IN A FUTURE UPDATE
