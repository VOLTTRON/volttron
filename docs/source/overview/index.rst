========
Overview
========


Platform Background
-------------------

| VOLTTRON serves as an integrating platform for the components of the
Transactional Network project. It provides an environment for agent
execution and serves as a single point of contact for interfacing with
devices (RTU HVACs, power meters, etc.), external resources, and
platform services such as data archival and retrieval. The VOLTTRON
platform provides a collection of utility and helper classes which
simplifies agent development.
| In the Transactional Network project, VOLTTRON connects devices (RTU
HVACs, power meters, etc.) to applications implemented in the platform
and in the cloud, a data historian, and signals from the power grid. It
also provides helper classes to ease development and deployment of
agents into the environment.

Platform Components
-------------------

|Overview of the VOLTTRON platform|

| The components of the Transactional Network are illustrated in the
figure above.
| The Device Interface communicates to the HVAC Controller using Modbus.
It periodically scrapes data off the controller and both pushes to the
sMAP historian and publishes it to the Message Bus on a topic for each
device. The Device Interface also responds to lock and control commands
published on the requests topic. Agents must first request and receive a
lock on a device for a certain time period. During this time, they have
exclusive control of the device and may issues commands.
| The sMAP agent in the figure represents the Archiver Agent which
allows agents to request data from sMAP over the Message Bus. The
Archiver Agent isolates agents from the details of the Historian and
would allow the platform to use a different or multiple historian
solutions (sMAP, a database, and a some other site).

Agents in the Platform
----------------------

Agents deployed on VOLTTRON can perform one or more roles which can be
broadly classified into the following groups:

-  Platform Agents: Agents which are part of the platform and provide a
   service to other agents. Examples are agents which interface with
   devices to publish readings and handle control signals from other
   agents.
-  Cloud Agents: These agents represent a remote application which needs
   access to the messages and data on the platform. This agent would
   subscribe to topics of interest to the remote application and would
   also allow it publish data to the platform.
-  Control Agents: These agents control the devices of interest and
   interact with other resources to achieve some goal.

Platform Services:

-  Message Bus: All agents and services publish and subscribe to topics
   on the message bus. This provides a single interface that abstracts
   the details of devices and agents from each other. Components in the
   platform basically produce and consume events.
-  Weather Information: This agent periodically retrieves data from the
   Weather Underground site. It then reformats it and publishes it out
   to the platform on a weather topic.
-  Modbus-based device interface: The Modbus driver publishes device
   data onto the message bus. It also handles the locking of devices to
   prevent multiple conflicting directives.
-  Application Scheduling: This service allows the scheduling of agents’
   access to devices in order to prevent conflicts.
-  Logging service: Agents can publish arbitrary strings to a logging
   topic and this service will push them to the sMAP historian for later
   analysis.

.. |Overview of the VOLTTRON platform| image:: files/overview.png




.. toctree::
    :glob:
    :maxdepth: 2

    *
