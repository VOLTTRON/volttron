Heartbeat Signal
----------------

The ActuatorAgent can be configured to send a heartbeat message to the
device to indicate the platform is running. Ideally, if the heartbeat
signal is not sent the device should take over and resume normal
operation.

The configuration has two parts, the interval (in seconds) for sending
the heartbeat and the specific point that should be modified each
iteration.

The heart beat interval is specified with a global "heartbeat\_interval"
setting. The ActuatorAgent will automatically set the heartbeat point to
alternating "1" and "0" values. Changes to the heartbeat point will be
published like any other value change on a device.

The heartbeat points are specified under "points" section of the
configuration like so:

::

    "points":
    {
        "<path to a device>": 
        {
            "heartbeat_point":"<heartbeat point>"
        }
        "<path to a device>":
        {
            "heartbeat_point":"<heartbeat point>"
        }
    }

Note: this requires that the device has been setup with a heartbeat
support. For Catalyst controllers check with TWT if you're not sure.
