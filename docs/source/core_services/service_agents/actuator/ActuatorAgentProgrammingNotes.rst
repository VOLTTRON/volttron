.. _ActuatorAgentProgrammingNotes:

Notes on Working With the ActuatorAgent
---------------------------------------

-  An agent can watch the window value from `device state
   updates <ActuatorScheduleState>`__ to perform scheduled actions
   within a timeslot.

   -  If an Agent's Task is LOW\_PREEMPT priority it can watch for
      `device state updates <ActuatorScheduleState>`__ where the window
      is less than or equal to the grace period (default 60.0).

-  When considering if to schedule long or multiple short time slots on
   a single device:

   -  Do we need to ensure the device state for the duration between
      slots?
   -  Yes. Schedule one long time slot instead.
   -  No. Is it all part of the same Task or can we break it up in case
      there is a conflict with one of our time slots?

-  When considering time slots on multiple devices for a single Task:

   -  Is the Task really dependent on all devices or is it actually
      multiple Tasks?

-  When considering priority:

   -  Does the Task have to happen **on an exact day**?
   -  No. Consider LOW and reschedule if preempted.
   -  Yes. Use HIGH.
   -  Is it problematic to prematurely stop a Task once started?
   -  No. Consider LOW\_PREEMPT and watch the `device state
      updates <ActuatorScheduleState>`__ for a small window value.
   -  Yes. Consider LOW or HIGH.

-  If an agent is only observing but needs to assure that no another
   Task is going on while taking readings it can schedule the time to
   prevent other agents from messing with a devices state. The schedule
   updates can be used as a reminder as to when to start watching.
-  **Any** device, existing or not, can be scheduled. This allows for
   agents to schedule fake devices to create reminders to start working
   later rather then setting up their own internal timers and schedules.


