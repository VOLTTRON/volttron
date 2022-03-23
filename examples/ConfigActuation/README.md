## ConfigActuation Agent

This agent is used to demonstrate scheduling and acutation of devices
when a configstore item is added or updated. The name of a configuration 
file must match the name of the device to be actuated. The configuration 
file is a JSON dictionary of point name and value pairs. Any number of 
points on the device can be listed in the config.

To use this agent as-is, install it as normal with the provided configuration
file ("config" in the agent's directory). For more information on installing and
running agents, see the [Agent Control Commands](https://volttron.readthedocs.io/en/main/platform-features/control/agent-management-control.html).

This agent may be used as an example for scheduling and acutation of devices
when a configstore item is added or updated, and serve as a jumping-off point 
for other simple test agents.
