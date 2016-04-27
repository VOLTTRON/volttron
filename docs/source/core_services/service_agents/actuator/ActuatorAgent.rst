ActuatorAgent
==============

This agent is used to access the control points of a controller. Agents
may request scheduled times, called Tasks, to interact with one or more
devices.

The interactions with the ActuatorAgent are handled via pub/sub
interface provided by the message bus. The available points for a
Catalyst 472 are detailed `here <ControllerDataPoints>`__.

Note: VOLTTRON 3.0 adds an RPC communication option which makes
interacting with platform services much simpler. It is recommended RPC
be used for interacting with the ActuatorAgent. The following pages are
being updated but in the meantime, an example of upgrading a 2.0 agent
to a 3.0 agent to interact with the actuator can be found
`here <https://github.com/VOLTTRON/volttron/commit/53b1b40d429ca78789838e365c399a2eb24635de>`__

Actuator Agent Communication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:doc:`Scheduling and canceling a Task. <ActuatorScheduleRequest>`

:doc:`Interacting with a device via the
ActuatorAgent. <ActuatorValueRequest>`

:doc:`AcutatorAgent responses to a schedule or cancel
request. <ActuatorScheduleResponse>`

:doc:`Schedule state announcements. <ActuatorScheduleState>`

:doc:`What happens when a running Task is
preempted. <ActuatorSchedulePreemption>`

:doc:`Setup heartbeat signal for a device. <ActuatorHeartbeat>`

:doc:`ActuatorAgent configuration. <ActuatorConfig>`

:doc:`Notes on programming agents to work with the
ActuatorAgent <ActuatorAgentProgrammingNotes>`
