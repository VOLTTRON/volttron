.. _ActuatorScheduleState:

Schedule State Broadcast
------------------------

Periodically the ActuatorAgent will publish the state of all currently
used devices.

For each device the ActuatorAgent will publish to an associated topic:

::

    #python
    'devices/actuators/schedule/announce/<full device path>'

With the following header:

::

    #python
    {
        'requesterID': <VIP identity of agent with access>,
        'taskID': <Task associated with the time slot>
        'window': <Seconds remaining in the time slot>
    }

The frequency of the updates is configurable with the
"schedule\_publish\_interval" setting.
