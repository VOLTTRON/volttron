## Scheduler Example Agent

The Scheduler Example Agent demonstrates how to use the scheduling feature of the Actuator Agent
as well as how to send a command. This agent publishes a request for a reservation on a (fake) 
device then takes an action when it’s scheduled time appears. 

The ActuatorAgent must be installed and running first to exercise this example. 

Install the Scheduler Example Agent using this command:
```
vctl install --agent-config examples/SchedulerExample/config examples/SchedulerExample/
```

When authentication is enabled, grant this agent the `actuator_control` capability after installing it, or the
actuator refuses its requests. The steps are in the Actuator Agent README, section "Required capability for
scheduling and writing".

Once the agent is installed you can start it up using `vctl start ...`