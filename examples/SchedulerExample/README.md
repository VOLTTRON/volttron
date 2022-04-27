## Scheduler Example Agent

The Scheduler Example Agent demonstrates how to use the scheduling feature of the Actuator Agent
as well as how to send a command. This agent publishes a request for a reservation on a (fake) 
device then takes an action when it’s scheduled time appears. 

The ActuatorAgent must be installed and running first to exercise this example. 

Install the Scheduler Example Agent using this command:
```
vctl install --agent-config examples/SchedulerExample/config examples/SchedulerExample/
```

Once the agent is installed you can start it up using `vctl start ...`