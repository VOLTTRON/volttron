# Actuator Agent
The Actuator Agent is used to manage write access to devices. Other agents
may request scheduled times, called Tasks, to interact with one or more
devices.

Agents may interact with the ActuatorAgent via either PUB/SUB or RPC, 
but it is recommended agents use RPC to interact with the ActuatorAgent.

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
