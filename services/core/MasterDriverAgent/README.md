# Master Driver Agent

The Master Driver agent is a special purpose agent a user can install on the platform to manage communication of the 
platform with devices. The Master driver features a number of endpoints for collecting data and sending control signals 
using the message bus and automatically publishes data to the bus on a specified interval.

## Dependencies

VOLTTRON drivers operated by the master driver may have additional requirements for installation. Required libraries:
1. BACnet driver - bacpypes
2. Modbus driver - pymodbus
3. Modbus_TK driver - modbus-tk
4. DNP3 and IEEE 2030.5 drivers - pydnp3

The easiest way to install the requirements for drivers included in the VOLTTRON repository is to use bootstrap.py 
```
python3 bootstrap.py --drivers
```

## Configuration

### Agent Configuration

The Master Driver Agent configuration consists of general settings for all devices. The default values of the 
Master Driver should be sufficient for most users. The user may optionally change the interval between device scrapes 
with the driver_scrape_interval.

The following example sets the driver_scrape_interval to 0.05 seconds or 20 devices per second:
```
{
    "driver_scrape_interval": 0.05,
    "publish_breadth_first_all": false,
    "publish_depth_first": false,
    "publish_breadth_first": false,
    "publish_depth_first_all": true,
    "group_offset_interval": 0.0
}
```

1. driver_scrape_interval - Sets the interval between devices scrapes. Defaults to 0.02 or 50 devices per second. 
Useful for when the platform scrapes too many devices at once resulting in failed scrapes.
2. group_offset_interval - Sets the interval between when groups of devices are scraped. Has no effect if all devices 
are in the same group.
In order to improve the scalability of the platform unneeded device state publishes for all devices can be turned off. 
All of the following setting are optional and default to True.
3. publish_depth_first_all - Enable “depth first” publish of all points to a single topic for all devices.
4. publish_breadth_first_all - Enable “breadth first” publish of all points to a single topic for all devices.
5. publish_depth_first - Enable “depth first” device state publishes for each register on the device for all devices.
6. publish_breadth_first - Enable “breadth first” device state publishes for each register on the device for all devices.

### Driver Configuration
Each device configuration has the following form:
```
{
    "driver_config": {"device_address": "10.1.1.5",
                      "device_id": 500},
    "driver_type": "bacnet",
    "registry_config":"config://registry_configs/vav.csv",
    "interval": 60,
    "heart_beat_point": "heartbeat",
    "group": 0
}
```
The following settings are required for all device configurations:
1. driver_config - Driver specific setting go here. See below for driver specific settings.
2. driver_type - Type of driver to use for this device: bacnet, modbus, fake, etc.
3. registry_config - Reference to a configuration file in the configuration store for registers on the device. 

These settings are optional:

1. interval - Period which to scrape the device and publish the results in seconds. Defaults to 60 seconds.
2. heart_beat_point - A Point which to toggle to indicate a heartbeat to the device. A point with this 
Volttron Point Name must exist in the registry. If this setting is missing the driver will not send a heart beat signal 
to the device. Heart beats are triggered by the Actuator Agent which must be running to use this feature.
3. group - Group this device belongs to. Defaults to 0
