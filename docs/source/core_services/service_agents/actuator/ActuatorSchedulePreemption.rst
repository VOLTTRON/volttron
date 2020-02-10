.. _ActuatorSchedulePreemption:

Task Preemption
---------------

Both LOW and LOW\_PREEMPT priority Tasks can be preempted. LOW priority
Tasks may be preempted by a conflicting HIGH priority Task before it
starts. LOW\_PREEMPT priority Tasks can be preempted by HIGH priority
Tasks even after they start.

When a Task is preempted the ActuatorAgent will publish to
"devices/actuators/schedule/response" with the following header:

::

    #python
    {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': <Agent VIP identity for the preempted Task>,
        'taskID': <Task ID for the preempted Task>
    }

And the message (after parsing the json):

::

    #python
    {
        'result': 'PREEMPTED',
        'info': '',
        'data': 
        {
            'agentID': <Agent VIP identity of preempting task>,
            'taskID': <Task ID of preempting task>
        }
    }

Preemption Grace Time
~~~~~~~~~~~~~~~~~~~~~

If a LOW\_PREEMPT priority Task is preempted while it is running the
Task will be given a grace period to clean up before ending. For every
device which has a current time slot the window of remaining time will
be reduced to the grace time. At the end of the grace time the Task will
finish. If the Task has no currently open time slots on any devices it
will end immediately.
