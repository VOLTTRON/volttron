.. _ActuatorConfig:

ActuatorAgent Configuration
---------------------------

| ``schedule_publish_interval:: Interval between ``\ ```published``
``schedule``
``announcements`` <ActuatorScheduleState>`__\ `` in seconds. Defaults to 30.``
| ``preempt_grace_time:: Minimum time given to Tasks which have been preempted to clean up in seconds. Defaults to 60.``
| ``schedule_state_file:: File used to save and restore Task states if the ActuatorAgent restarts for any reason. File will be created if it does not exist when it is needed.``

Sample configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~

| {
|  "schedule\_publish\_interval": 30,
|  "schedule\_state\_file": "actuator\_state.pickle"
| }
