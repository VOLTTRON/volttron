.. _Actuator-Agent:

==============
Actuator Agent
==============

This agent is used to manage write access to devices. Agents may request scheduled times, called Tasks, to interact with
one or more devices.


.. _Actuator-Communication:

Actuator Agent Communication
============================


Scheduling a Task
-----------------

An agent can request a task schedule by publishing to the `devices/actuators/schedule/request` topic with the following
header:

.. code-block:: python

    {
        'type': 'NEW_SCHEDULE',
        'requesterID': <Ignored, VIP Identity used internally>
        'taskID': <unique task ID>, #The desired task ID for this task. It must be unique among all other scheduled tasks.
        'priority': <task priority>, #The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
    }

with the following message:

.. code-block:: python

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

   If time zones are not included in schedule requests then the Actuator will interpret them as being in local time.
   This may cause remote interaction with the actuator to malfunction.


Points on Task Scheduling
^^^^^^^^^^^^^^^^^^^^^^^^^

-  Everything in the header is required
-  Task id and requester id (agentid) should be a non empty value of type string
-  A Task schedule must have at least one time slot.
-  The start and end times are parsed with `dateutil's date/time
   parser <http://labix.org/python-dateutil#head-c0e81a473b647dfa787dc11e8c69557ec2c3ecd2>`__.
   **The default string representation of a python datetime object will parse without issue.**
-  Two Tasks are considered conflicted if at least one time slot on a device from one task overlaps the time slot of the
   other on the same device.
-  The end time of one time slot can be the same as the start time of another time slot for the same device. This will
   not be considered a conflict. For example, ``time_slot1(device0, time1, **time2**)`` and
   ``time_slot2(device0, **time2**, time3)`` are not considered a conflict
-  A request must not conflict with itself
-  If something goes wrong see :ref:`this failure string list <Actuator-Failure-Reasons>` for an
   explanation of the error.


Task Priorities
^^^^^^^^^^^^^^^

* `HIGH`:  This Task cannot be preempted under any circumstance.  This task may preempt other conflicting preemptable
  Tasks.

* ``LOW`:  This Task cannot be preempted **once it has started**.  A Task is considered started once the earliest time slot
  on any device has been reached.  This Task may **not** preempt other Tasks.

* `LOW_PREEMPT`:  This Task may be preempted at any time.  If the Task is preempted once it has begun running any
  current time slots will be given a grace period (configurable in the ActuatorAgent configuration file, defaults to 60
  seconds) before being revoked.  This Task may **not** preempt other Tasks.


Canceling a Task
----------------

A task may be canceled by publishing to the `devices/actuators/schedule/request` topic with the following header:

.. code-block:: python

    {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': <Ignored, VIP Identity used internally>
        'taskID': <unique task ID>, #The desired task ID for this task. It must be unique among all other scheduled tasks.
    }


Points on Task Canceling
^^^^^^^^^^^^^^^^^^^^^^^^

-  The requesterID and taskID must match the original values from the original request header.
-  After a Tasks time has passed there is no need to cancel it. Doing so will result in a `TASK_ID_DOES_NOT_EXIST`
   error.
-  If something goes wrong see :ref:`this failure string list <Actuator-Failure-Reasons>` for an explanation
   of the error.


Actuator Agent Schedule Response
--------------------------------

In response to a Task schedule request the ActuatorAgent will respond on the topic `devices/actuators/schedule/result`
with the header:

.. code-block:: python

    {
        'type': <'NEW_SCHEDULE', 'CANCEL_SCHEDULE'>
        'requesterID': <Agent VIP identity from the request>,
        'taskID': <Task ID from the request>
    }

And the message (after parsing the json):

.. code-block:: python

    {
        'result': <'SUCCESS', 'FAILURE', 'PREEMPTED'>,
        'info': <Failure reason, if any>,
        'data': <Data about the failure or cancellation, if any>
    }

The Actuator Agent may publish cancellation notices for preempted Tasks using the `PREEMPTED` result.


Preemption Data
^^^^^^^^^^^^^^^

Preemption data takes the form:

.. code-block:: python

    {
        'agentID': <Agent ID of preempting task>,
        'taskID': <Task ID of preempting task>
    }


.. _Actuator-Failure-Reasons:

Failure Reasons
^^^^^^^^^^^^^^^

In many cases the Actuator Agent will try to give good feedback as to why a request failed.


General Failures
""""""""""""""""

* `INVALID_REQUEST_TYPE`:  Request type was not `NEW_SCHEDULE` or `CANCEL_SCHEDULE`.
* `MISSING_TASK_ID`:  Failed to supply a taskID.
* `MISSING_AGENT_ID`:  AgentID not supplied.


Task Schedule Failures
""""""""""""""""""""""

* `TASK_ID_ALREADY_EXISTS`:  The supplied taskID already belongs to an existing task.
* `MISSING_PRIORITY`:  Failed to supply a priority for a Task schedule request.
* `INVALID_PRIORITY`:  Priority not one of `HIGH`, `LOW`, or `LOW_PREEMPT`.
* `MALFORMED_REQUEST_EMPTY`:  Request list is missing or empty.
* `REQUEST_CONFLICTS_WITH_SELF`:  Requested time slots on the same device overlap.
* `MALFORMED_REQUEST`:  Reported when the request parser raises an unhandled exception. The exception name and info are
  appended to this info string.
* `CONFLICTS_WITH_EXISTING_SCHEDULES`:  This schedule conflict with an existing schedules that it cannot preempt. The
  data item for the results will contain info about the conflicts in this form (after parsing json)

.. code-block:: python

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
""""""""""""""""""""

* `TASK_ID_DOES_NOT_EXIST`:  Trying to cancel a Task which does not exist.  This error can also occur when trying to
  cancel a finished Task.
* `AGENT_ID_TASK_ID_MISMATCH`:  A different agent ID is being used when trying to cancel a Task.


.. _Actuator-Value-Request:

Actuator Agent Value Request
----------------------------

Once an Task has been scheduled and the time slot for one or more of the devices has started an agent may interact with
the device using the **get** and **set** topics.

Both **get** and **set** are responded to the same way. See :ref:`Actuator Reply <Actuator-Reply>` below.

Getting values
^^^^^^^^^^^^^^

While a driver for a device should always be setup to periodically broadcast the state of a device you may want an
up-to-the-moment value for an actuation point on a device.

To request a value publish a message to the following topic:

.. code-block:: python

    'devices/actuators/get/<full device path>/<actuation point>'


Setting Values
^^^^^^^^^^^^^^

Value are set in a similar manner:

To set a value publish a message to the following topic:

.. code-block:: python

    'devices/actuators/set/<full device path>/<actuation point>'

With this header:

.. code-block:: python

    #python
    {
        'requesterID': <Ignored, VIP Identity used internally>
    }

And the message contents being the new value of the actuator.

.. warning::

    The actuator agent expects all messages to be JSON and will parse them accordingly. Use `publish_json` to send
    messages where possible.  This is significant for Boolean values especially

.. _Actuator-Reply:

Actuator Reply
^^^^^^^^^^^^^^

The ActuatorAgent will reply to both `get` and `set` on the `value` topic for an actuator:

.. code-block:: python

    'devices/actuators/value/<full device path>/<actuation point>'

With this header:

.. code-block:: python

    {
        'requesterID': <Agent VIP identity>
    }

With the message containing the value encoded in JSON.

Actuator Error Reply
^^^^^^^^^^^^^^^^^^^^

If something goes wrong the Actuator Agent will reply to both `get` and `set` on the `error` topic for an actuator:

.. code-block:: python

    'devices/actuators/error/<full device path>/<actuation point>'

With this header:

.. code-block:: python

    {
        'requesterID': <Agent VIP identity>
    }

The message will be in the following form:

.. code-block:: python

    {
        'type': <Error Type or name of the exception raised by the request>
        'value': <Specific info about the error>
    }

Common Error Types
^^^^^^^^^^^^^^^^^^

* `LockError`:  Returned when a request is made when we do not have permission to use a device.  (Forgot to schedule,
  preempted and we did not handle the preemption message correctly, ran out of time in time slot, etc...)
* `ValueError`:  Message missing or could not be parsed as JSON


.. _Actuator-Schedule-State:

Schedule State Broadcast
------------------------

Periodically the ActuatorAgent will publish the state of all currently scheduled devices.  For each device the
ActuatorAgent will publish to an associated topic:

.. code-block:: python

    'devices/actuators/schedule/announce/<full device path>'

With the following header:

.. code-block:: python

    {
        'requesterID': <VIP identity of agent with access>,
        'taskID': <Task associated with the time slot>
        'window': <Seconds remaining in the time slot>
    }

The frequency of the updates is configurable with the `schedule_publish_interval` setting.


Task Preemption
---------------

Both `LOW` and `LOW_PREEMPT` priority Tasks can be preempted.  `LOW` priority Tasks may be preempted by a conflicting
`HIGH` priority Task before it starts.  `LOW_PREEMPT` priority Tasks can be preempted by `HIGH` priority Tasks even
after they start.

When a Task is preempted the ActuatorAgent will publish to `devices/actuators/schedule/response` with the following
header:

.. code-block:: python

    {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': <Agent VIP identity for the preempted Task>,
        'taskID': <Task ID for the preempted Task>
    }

And the message (after parsing the json):

.. code-block:: python

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
^^^^^^^^^^^^^^^^^^^^^

If a `LOW_PREEMPT` priority Task is preempted while it is running the Task will be given a grace period to clean up
before ending.  For every device which has a current time slot the window of remaining time will be reduced to the grace
time.  At the end of the grace time the Task will finish.  If the Task has no currently open time slots on any devices
it will end immediately.


.. _Actuator-Config:

ActuatorAgent Configuration
---------------------------

* `schedule_publish_interval`:  Interval between current schedules being published to the message bus for all devices
* `preempt_grace_time`:  Minimum time given to Tasks which have been preempted to clean up in seconds.  Defaults to 60
* `schedule_state_file`:  File used to save and restore Task states if the ActuatorAgent restarts for any reason.  File
  will be created if it does not exist when it is needed

Sample configuration file
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
     "schedule_publish_interval": 30,
     "schedule_state_file": "actuator_state.pickle"
    }


Heartbeat Signal
----------------

The ActuatorAgent can be configured to send a heartbeat message to the device to indicate the platform is running.
Ideally, if the heartbeat signal is not sent the device should take over and resume normal operation.

The configuration has two parts, the interval (in seconds) for sending the heartbeat and the specific point that should
be modified each iteration.

The heart beat interval is specified with a global `heartbeat_interval` setting.  The ActuatorAgent will automatically
set the heartbeat point to alternating "1" and "0" values.  Changes to the heartbeat point will be published like any
other value change on a device.

The heartbeat points are specified in the driver configuration file of individual devices.


.. _Actuator-Notes:

Notes on Working With the ActuatorAgent
---------------------------------------

-  An agent can watch the window value from :ref:`device state updates <Actuator-Schedule-State>` to perform scheduled
   actions within a timeslot

   -  If an Agent's Task is `LOW_PREEMPT` priority it can watch for device state updates where the window is less than
      or equal to the grace period (default 60.0)

-  When considering if to schedule long or multiple short time slots on a single device:

   -  Do we need to ensure the device state for the duration between slots?

       -  Yes: Schedule one long time slot instead
       -  No: Is it all part of the same Task or can we break it up in case there is a conflict with one of our time
          slots?

-  When considering time slots on multiple devices for a single Task:

   -  Is the Task really dependent on all devices or is it actually multiple Tasks?

-  When considering priority:

   -  Does the Task have to happen **on an exact day**?

       -  Yes: Use `HIGH`
       -  No: Consider `LOW` and reschedule if preempted

   -  Is it problematic to prematurely stop a Task once started?

       -  Yes: Consider `LOW` or `HIGH`
       -  No: Consider `LOW_PREEMPT` and watch the device state updates for a small window value

-  If an agent is only observing but needs to assure that no another Task is going on while taking readings it can
   schedule the time to prevent other agents from messing with a devices state.  The schedule updates can be used as a
   reminder as to when to start watching
-  **Any** device, existing or not, can be scheduled.  This allows for agents to schedule fake devices to create
   reminders to start working later rather then setting up their own internal timers and schedules
