getting_started.. _agents-overview:

======================
Agents in the Platform
======================

Agents deployed on VOLTTRON can perform one or more roles which can be broadly classified into the following groups:

-  Platform Agents: Agents which are part of the platform and provide a service to other agents. Examples are agents which interface with devices to publish readings and handle control signals from other agents.
-  Cloud Agents: These agents represent a remote application which needs access to the messages and data on the platform. This agent would subscribe to topics of interest to the remote application and would also allow it publish data to the platform.
-  Control Agents: These agents control the devices of interest and interact with other resources to achieve some goal.

Platform Services:

-  Message Bus: All agents and services publish and subscribe to topics on the message bus. This provides a single interface that abstracts the details of devices and agents from each other. Components in the platform basically produce and consume events.
-  Weather Information: This agent periodically retrieves data from the Weather Underground site. It then reformats it and publishes it out to the platform on a weather topic.
-  Modbus-based device interface: The Modbus driver publishes device data onto the message bus. It also handles the locking of devices to prevent multiple conflicting directives.
-  Application Scheduling: This service allows the scheduling of agents’ access to devices in order to prevent conflicts.
-  Logging service: Agents can publish arbitrary strings to a logging topic and this service will push them to a historian for later analysis.

