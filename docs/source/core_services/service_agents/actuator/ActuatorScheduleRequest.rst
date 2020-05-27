.. _ActuatorScheduleRequest:

Requesting Schedule Changes
---------------------------

For information on responses see `AcutatorAgent responses to a schedule
or cancel requests. <ActuatorScheduleResponse>`__

**For 2.0 Agents using the pubsub interface: The actuator agent expects
all messages to be JSON and will parse them accordingly. Use
publish\_json to send messages where possible.**

3.0 agents using pubsub for scheduling and setting point values should
publish python objects like normal.

Scheduling a Task
~~~~~~~~~~~~~~~~~

An agent can request a task schedule by publishing to the
"devices/actuators/schedule/request" topic with the following header:

::

    #python
    {
        'type': 'NEW_SCHEDULE',
        'requesterID': <Ignored, VIP Identity used internally>
        'taskID': <unique task ID>, #The desired task ID for this task. It must be unique among all other scheduled tasks.
        'priority': <task priority>, #The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
    }

with the following message:

::

    #python
    [
        ["campus/building/device1", #First time slot.
         "2013-12-06 16:00:00",     #Start of time slot.
         "2013-12-06 16:20:00"],    #End of time slot.
        ["campus/building/device1", #Second time slot.
         "2013-12-06 18:00:00",     #Start of time slot.
         "2013-12-06 18:20:00"],    #End of time slot.
        ["campus/building/device2", #Third time slot.
         "2013-12-06 16:00:00",     #Start of time slot.
         "2013-12-06 16:20:00"],    #End of time slot.
        #etc...
    ]

.. warning::

   If time zones are not included in schedule requests then the Actuator will
   interpret them as being in local time. This may cause remote interaction
   with the actuator to malfunction.

Points on Task Scheduling
^^^^^^^^^^^^^^^^^^^^^^^^^

-  Everything in the header is required.
-  Task id and requester id (agentid) should be a non empty value of
   type string
-  A Task schedule must have at least one time slot.
-  The start and end times are parsed with `dateutil's date/time
   parser <http://labix.org/python-dateutil#head-c0e81a473b647dfa787dc11e8c69557ec2c3ecd2>`__.
   **The default string representation of a python datetime object will
   parse without issue.**
-  Two Tasks are considered conflicted if at least one time slot on a
   device from one task overlaps the time slot of the other on the same
   device.
-  The end time of one time slot can be the same as the start time of
   another time slot for the same device. This will not be considered a
   conflict. For example, time\_slot1(device0, time1, **time2**) and
   time\_slot2(device0,\ **time2**, time3) are not considered a conflict
-  A request must not conflict with itself.
-  If something goes wrong see `this failure string
   list <ActuatorScheduleResponse#failure-reasons>`__ for an explanation
   of the error.

Task Priorities
^^^^^^^^^^^^^^^

HIGH: 
 This Task cannot be preempted under any circumstance. 
 This task may preempt other conflicting preemptable Tasks.

LOW: 
 This Task cannot be preempted \ **once it has started**\ . 
 A Task is considered started once the earliest time slot on any device 
 has been reached. This Task may **not** preempt other Tasks.

LOW\_PREEMPT: 
 This Task may be preempted at any time. If the Task is preempted 
 once it has begun running any current time slots will be given a grace period 
 (configurable in the ActuatorAgent configuration file, defaults to 60 seconds) 
 before being revoked. This Task may **not** preempt other Tasks.

Canceling a Task
~~~~~~~~~~~~~~~~

A task may be canceled by publishing to the
"devices/actuators/schedule/request" topic with the following header:

::

    #python
    {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': <Ignored, VIP Identity used internally>
        'taskID': <unique task ID>, #The desired task ID for this task. It must be unique among all other scheduled tasks.
    }

Points on Task Canceling
^^^^^^^^^^^^^^^^^^^^^^^^

-  The requesterID and taskID must match the original values from the
   original request header.
-  After a Tasks time has passed there is no need to cancel it. Doing so
   will result in a "TASK\_ID\_DOES\_NOT\_EXIST" error.
-  If something goes wrong see `this failure string
   list <ActuatorScheduleResponse#FailureReasons>`__ for an explanation
   of the error.

