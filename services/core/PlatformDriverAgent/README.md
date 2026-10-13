# Platform Driver Agent

The Platform Driver agent is a special purpose agent a user can install on the platform to manage communication of the 
platform with devices. The Platform driver features a number of endpoints for collecting data and sending control signals 
using the message bus and automatically publishes data to the bus on a specified interval.

## Dependencies

VOLTTRON drivers operated by the platform driver may have additional requirements for installation. Required libraries:
1. BACnet driver - bacpypes
2. Modbus driver - pymodbus
3. Modbus_TK driver - modbus-tk
4. DNP3 and IEEE 2030.5 drivers - pydnp3

The easiest way to install the requirements for drivers included in the VOLTTRON repository is to use bootstrap.py 
```
python3 bootstrap.py --drivers
```

## Permissions

When authentication is enabled, the Platform Driver checks the calling agent's capabilities.

* `driver_write` is required by `set_point`, `set_multiple_points`, `revert_point` and `revert_device`.
* `driver_override` is required by `set_override_on`, `set_override_off` and `clear_overrides`.

An agent installed with `vctl install` gets `driver_write` at install, so it can write to the Platform Driver
directly, without a schedule from the Actuator Agent. (The exception is VolttronCentralPlatform, which does not.)
If you remove `driver_write` from an agent, reinstalling that agent restores it: the install removes the old auth entry
and creates a new one that again includes `driver_write`.
Nothing grants `driver_override`; an operator adds it. Agents that schedule and write through the Actuator Agent
need `actuator_control` instead (see the Actuator Agent README). Platforms running with authentication disabled
do not check these capabilities.

To change an installed agent's capabilities, find its entry and update it:

```bash
vctl auth list
vctl auth update <INDEX>
```

`<INDEX>` is the number of the agent's entry in the `vctl auth list` output. Press Enter to keep each field. At the
`capabilities` prompt, type the agent's whole capability map as JSON, keeping the existing entries and adding or
removing the one you want, for example:

```
{"edit_config_store": {"identity": "my.agent"}, "driver_write": null, "driver_override": null}
```

Use the JSON form with `null`. The prompt shows the current map in Python form (`None`, single quotes), which is
not valid JSON. A comma-separated list such as `edit_config_store,driver_override` is accepted, but it removes the
restrictions on the existing capabilities.

For an agent that connects with its own credentials and has no auth entry yet:

```bash
vctl auth add --credentials <agent public key> --user_id my.agent --capabilities driver_override
```

`vctl auth add` refuses a user id or credentials that already have an entry, so it cannot add a capability to an
installed agent.

## Configuration

### Agent Configuration

The Platform Driver Agent configuration consists of general settings for all devices. The default values of the 
Platform Driver should be sufficient for most users. The user may optionally change the interval between device scrapes 
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
