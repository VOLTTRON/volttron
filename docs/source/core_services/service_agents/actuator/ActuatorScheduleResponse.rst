.. _ActuatorScheduleResponse:

ActuatorAgent Response
----------------------

In response to a `Task schedule request <ActuatorScheduleRequest>`__ the
ActuatorAgent will respond on the topic
"devices/actuators/schedule/result" with the header:

::

    #python
    {
        'type': <'NEW_SCHEDULE', 'CANCEL_SCHEDULE'>
        'requesterID': <Agent VIP identity from the request>,
        'taskID': <Task ID from the request>
    }

And the message (after parsing the json):

::

    #python
    {
        'result': <'SUCCESS', 'FAILURE', 'PREEMPTED'>,
        'info': <Failure reason, if any>,
        'data': <Data about the failure or cancellation, if any>
    }

The ActuatorAgent may publish cancellation notices for preempted Tasks
using the "PREEMPTED" result.

Preemption Data
~~~~~~~~~~~~~~~

Preemption data takes the form:

::

    #python
    {
        'agentID': <Agent ID of preempting task>,
        'taskID': <Task ID of preempting task>
    }

Failure Reasons
~~~~~~~~~~~~~~~

In many cases the ActuatorAgent will try to give good feedback as to why
a request failed.

General Failures
^^^^^^^^^^^^^^^^

| ``INVALID_REQUEST_TYPE:: Request type was not "NEW_SCHEDULE" or "CANCEL_SCHEDULE".``
| ``MISSING_TASK_ID:: Failed to supply a taskID.``
| ``MISSING_AGENT_ID:: AgentID not supplied.``

Task Schedule Failures
^^^^^^^^^^^^^^^^^^^^^^

| ``TASK_ID_ALREADY_EXISTS: The supplied taskID already belongs to an existing task.``
| ``MISSING_PRIORITY: Failed to supply a priority for a Task schedule request.``
| ``INVALID_PRIORITY: Priority not one of "HIGH", "LOW", or "LOW_PREEMPT".``
| ``MALFORMED_REQUEST_EMPTY: Request list is missing or empty.``
| ``REQUEST_CONFLICTS_WITH_SELF: Requested time slots on the same device overlap.``
 ``MALFORMED_REQUEST: Reported when the request parser raises an unhandled exception. The exception name and info are appended to this info string.``
 ``CONFLICTS_WITH_EXISTING_SCHEDULES: This schedule conflict with an existing schedules that it cannot preempt. The data item for the results will contain info about the conflicts in this form (after parsing json):``

::

    #python
    {
        '<agentID1>': 
        {
            '<taskID1>':
            [
                ["campus/building/device1", 
                 "2013-12-06 16:00:00",     
                 "2013-12-06 16:20:00"],
                ["campus/building/device1", 
                 "2013-12-06 18:00:00",     
                 "2013-12-06 18:20:00"]     
            ]
            '<taskID2>':[...]
        }
        '<agentID2>': {...}
    }

Task Cancel Failures
^^^^^^^^^^^^^^^^^^^^

``TASK_ID_DOES_NOT_EXIST:: Trying to cancel a Task which does not exist. This error can also occur when trying to cancel a finished Task.``
``AGENT_ID_TASK_ID_MISMATCH:: A different agent ID is being used when trying to cancel a Task.``
