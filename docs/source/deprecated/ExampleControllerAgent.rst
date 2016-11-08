Exampler Controller Agent
-------------------------

**Note**, this agent is out of date and will not work with the current
actuator/scheduler. Please see [ActuatorAgent documentation]
(ActuatorAgent "wikilink").

This agent listens for outdoor temperature readings then changes the
cool fan speed. It demonstrates pub/sub interaction with the RTU
Controller.

``   ``\ ```Requirements`` <ControllerAccess>`__\ `` for running this agent (or any agent wishing to interact with the RTU:``

-  

   -  Edit the driver.ini file to reflect the sMAP key, uuid, and other
      settings for your installation
   -  Activate the project Python from the project dir: . bin/activate
   -  Launch the smap driver by starting (from the project directory):
      twistd -n smap your\_driver.ini
   -  Launch the ActuatorAgent just as you would launch any other agent

``   With these requirements met, the ``

-  

   -  Subscribe to the outside air temperature topic.
   -  If the new reading is higher than the old reading then

      -  Request the actuator lock for the rtu

   -  If it receives a lock request success it randomly sets the
      coolsupply fan to a new reading.
   -  If it does not get the lock, it will try again the next time the
      temperature rises.
   -  If the set result is a success, it releases the lock.


