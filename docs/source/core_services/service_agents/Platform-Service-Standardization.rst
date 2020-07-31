.. _Platform-Service-Standardization:

================================
Platform Service Standardization
================================

Service will interact with the message bus through three topics.

-  Request - The service agent will listen to incoming requests on this
   topic
-  Response - The service agent will respond on this topic
-  Error - The service will "throw" errors on this topic

Agents which are using these services agents should publish to the above
Request topic and listen on the Reponse and Error topics. Response and
Errors will retain the header that was sent into the request.

Headers

-  Request Headers
-  Common Header Formats
-  type - Unique type of request for the service agent to handle (If an
   agent handles more than one request type on a specific topic)
-  requesterID - Name of the requesting agent

Header List
-----------

-  type - Unique type of request for the service agent to handle (If an
   agent handles more than one request type on a specific topic)
-  priority - HIGH, LOW, LOW\_PREEMPT (Found in Scheduler and Activator)
-  taskId - Unique task among scheduled tasks.
-  window - Seconds remaining in timeslot (actuator agent)
-  SourceName - used as name to publish to in smap for archiver agent.
-  FROM - Same as requestor id (volttron.messaging.headers.FROM)
-  CONTENT\_TYPE - volttron.messaging.headers.CONTENT\_TYPE.JSON,
   volttron.messaging.headers.CONTENT\_TYPE.PLAIN\_TEXT
   Datalogger location is specified in the message itself.
-  Multibuilding
-  Cookie

Request Formats (Content-Types)
-------------------------------

-  volttron.messaging.headers.CONTENT\_TYPE.JSON
-  volttron.messaging.headers.CONTENT\_TYPE.PLAIN\_TEXT

Topic List
----------

-  Actuator and Scheduling Agent

   -  devices/actuators/schedule/request (NEW\_SCHEDULE request)
   -  devices/actuators/schedule/request (CANCEL\_SCHEDULE request)
   -  devices/actuators/schedule/response
   -  devices/actuators/schedule/announce/[full device path]
   -  devices/actuators/schedule/response (Response for preempted task)
   -  devices/actuators/get/[full device path]/[ actuation point]
   -  devices/actuators/set/[full device path]/[ actuation point]
   -  devices/actuators/value/[full device path]/[ actuation point]
   -  devices/actuators/error/[full device path]/[ actuation point]

-  Archiver Agent

   -  archiver/request/[path to the value desired/ full device path]

-  Logger Agent

   -  datalogger/log/
   -  datalogger/log/[path in SMAP for the data point]
   -  datalogger/status (Status of the storage request)

-  Mobility Agent

   -  platform/move/request/[agent id]
   -  platform/move/reply/[agent id]

-  Multi-Building Agent

   -  building/recv/[campus]/[building]/[topic]
   -  building/send/[campus]/[building]/[topic]
   -  building/error/[campus]/[building]/[topic]

-  Weather Agent

   -  `Weather agent topic
      list <https://github.com/VOLTTRON/volttron/wiki/WeatherAgentTopics>`__

-  Platform Topics

   -  platform/shutdown
   -  agent/[agent]/shutdown


