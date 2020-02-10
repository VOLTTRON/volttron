.. _ActuatorAgent:

ActuatorAgent
=============

This agent is used to manage write access to devices. Agents
may request scheduled times, called Tasks, to interact with one or more
devices.

Actuator Agent Communication
----------------------------

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




.. toctree::
    :glob:
    :maxdepth: 2

    *
