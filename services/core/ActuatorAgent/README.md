# Actuator Agent
The Actuator Agent is used to manage write access to devices. Other agents
may request scheduled times, called Tasks, to interact with one or more
devices.

Agents may interact with the ActuatorAgent via either PUB/SUB or RPC, 
but it is recommended agents use RPC to interact with the ActuatorAgent.
For an example of an agent using RPC to interact with the ActuatorAgent, see the 
`SchedulerExample agent <https://github.com/VOLTTRON/volttron/blob/main/examples/SchedulerExample/schedule_example/agent.py>`__ 
from the Volttron repository.

The PUB/SUB interface remains primarily for VOLTTRON 2.0 agents. 

The Actuator Agent also triggers the heart beat on devices whose 
drivers are configured to do so. 

## ActuatorAgent Configuration


1. "schedule_publish_interval"

    Interval between published schedule announcements in seconds. Defaults to 30.
2. "preempt_grace_time"
       
    Minimum time given to Tasks which have been preempted to clean up in seconds. Defaults to 60.
3. "schedule_state_file"

    File used to save and restore Task states if the ActuatorAgent restarts for any reason. File will be
    created if it does not exist when it is needed.
4. "heartbeat_interval"
        
    How often to send a heartbeat signal to all devices in seconds. Defaults to 60.
       

## Sample configuration file

```
    {
        "schedule_publish_interval": 30,
        "schedule_state_file": "actuator_state.pickle"
    }
```

## Required capability for scheduling and writing

When authentication is enabled, the actuator's scheduling and writing methods (`request_new_schedule`,
`request_cancel_schedule`, `set_point`, `set_multiple_points`, `revert_point` and `revert_device`) require the
calling agent to hold the `actuator_control` capability. This applies to RPC calls and to the
`devices/actuators/...` pub/sub topics; on the pub/sub topics the actuator checks the capability of the sender.
Reads (`get_point`, `get_multiple_points`, `scrape_all`) do not require it. Platforms running with authentication
disabled are not affected.

No agent is granted `actuator_control` automatically, `vctl install` included. Holding `driver_write` does not allow
use of the actuator.

An agent installed with `vctl install` gets `driver_write` at install, so today it can write straight to the Platform
Driver, which skips the actuator's scheduling, whether or not it holds `actuator_control`. To make an agent write only
through the actuator, remove `driver_write` from its auth entry with `vctl auth update`, as described under
"Granting the capability" below, and leave it out of the capability map. The actuator itself needs `driver_write` to write to the Platform Driver, so keep that grant on the actuator's
own auth entry. Reinstalling the agent restores the grant: the install removes the old auth entry and creates a new one that again
includes `driver_write`, so repeat the removal after every reinstall. The Platform Driver README lists the methods
each capability covers.

A call without the capability is refused with an `UNAUTHORIZED` RPC error. A pub/sub set or revert without it
receives an `Unauthorized` error reply, and a pub/sub schedule request receives a `FAILURE` schedule result. None of
them reaches the device.

### Granting the capability

For an agent installed with `vctl install`, which already has an auth entry, find the entry and update it:

```bash
vctl auth list
vctl auth update <INDEX>
```

`<INDEX>` is the number of the agent's entry in the `vctl auth list` output. Press Enter to keep each field. At the
`capabilities` prompt, type the agent's whole capability map as JSON. Keep the existing entries and add
`actuator_control`, for example:

```
{"edit_config_store": {"identity": "my.agent"}, "driver_write": null, "actuator_control": null}
```

To make the agent write only through the actuator, leave `driver_write` out of the map:

```
{"edit_config_store": {"identity": "my.agent"}, "actuator_control": null}
```

Use the JSON form with `null`. The prompt shows the current map in Python form (`None`, single quotes), which is not
valid JSON. A comma-separated list such as `edit_config_store,actuator_control` is accepted, but it removes the
restrictions on the existing capabilities, so `edit_config_store` would no longer be limited to the agent's own
identity.

For an agent that connects with its own credentials and has no auth entry yet:

```bash
vctl auth add --credentials <agent public key> --user_id my.control.agent --capabilities actuator_control
```

`vctl auth add` refuses a user id or credentials that already have an entry, so it cannot add a capability to an
installed agent.

### Restricting the grant

A grant can carry parameter restrictions, which follow the same rule as other restricted capabilities: each
restricted parameter must match the call's argument, and a call to a method that has no such parameter is refused.
A grant restricted on `topic` can set and revert single points (`set_point`, `revert_point`, `revert_device`) but
cannot schedule or call `set_multiple_points`, because those methods have no `topic` parameter. Do not restrict on
`requester_id`: the actuator ignores the value an RPC caller supplies for it.
A restriction that cannot be evaluated, such as an invalid `/regex/` pattern, or a non-empty restriction that is not
a map, refuses the call. An empty restriction (`[]`, `""`, `0` or `false`) is treated as no restriction, and the
grant allows any argument.

### Web interface

Writing and reverting device points through the web interface (the VUI device endpoints) is refused while
authentication is enabled, because the web service holds no `actuator_control` grant. Reading device values is
unchanged.
