.. _Agent-Framework:

========================
Agent Framework Overview
========================

Agents in VOLTTRON can be loosely defined as software modules communicating on the platform which perform some function
on behalf of the user.  Agents may perform a huge variety of tasks, but common use cases involve data collection,
control of ICS and IOT devices, and various platform management tasks.  Agents implemented using the VOLTTRON agent
framework inherit a number of capabilities, including message bus connectivity and agent lifecycle.

Agents deployed on VOLTTRON can perform one or more roles which can be broadly classified into the following groups:

-  Platform Agents: Agents which are part of the platform and provide a service to other agents. Examples are the
   Actuator and Master Driver agents which serve as interfaces between control agents and drivers.
-  Control Agents: These agents implement algorithms to control the devices of interest and interact with other
   resources to achieve some goal.
-  Service Agents: These agents perform various data collection or platform management services.  Agents in this
   category include weather service agents which collect weather data from remote sources or operations agents which
   help users maintain situational awareness of their deployment.
-  Cloud Agents: These agents represent a remote application which needs access to the messages and data on the
   platform. This agent would subscribe to topics of interest to the remote application and would also allow it publish
   data to the platform.

The platform includes some valuable services which can be leveraged by agents:

-  Message Bus: All agents and services publish and subscribe to topics on the message bus. This provides a single
   interface that abstracts the details of devices and agents from each other. Components in the platform basically
   produce and consume events.
-  Configuration Store: Using the configuration store, agent operations can be altered ad-hoc without significant
   disruption or downtime.
-  Historian Framework: Historian agents automatically collect data from a subset of topics on the message bus and store
   them in a data store of choice.  Currently SQL, MongoDB, CrateDB and other historians exist, and more can be
   developed to fit the needs of a deployment by inheriting from the base historian.  The base historian has been
   developed to be fast and reliable, and to handle many common pitfalls of data collection over a network.
-  Weather Information: These agents periodically retrieve data from the a remote weather API then format the
   response and publish it to the platform message bus on a weather topic.
-  Device interfaces: Drivers publish device data onto the message bus and send control signals issued from control
   agents to the corresponding device.  Drivers are capable of handling the locking of devices to prevent multiple
   conflicting directives.
-  Application Scheduling: This service allows the scheduling of agents’ access to devices in order to prevent conflicts.
-  Logging service: Agents can publish arbitrary strings to a logging topic and this service will push them to a
   historian for later analysis.
