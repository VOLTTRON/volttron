VOLTTRON Versions
-----------------

VOLTTRON 1.0 - 1.2
==================

-  VOLTTRON platform based on PNNL research and needs of the RTU Network
   project
-  Open Source Reimplementation omitting patented features
-  Integrates researcher applications, devices, and cloud applications
   and resources
-  1.0 Focused on building up the framework
-  Agent execution environment
-  Basic platform services
-  Modbus driver
-  1.2 Expanded capabilities of platform
-  BACnet support
-  Multi-node communication
-  Released on GitHub

VOLTTRON 2.0
============

-  2.0 Incorporated PNNL IP from the original research
-  Different license: Free for buildings domain
-  Resource monitoring
-  Agents must present an execution contract to the platform stating
   their resource requirements
-  Platform rejects agents which it cannot support
-  Expandable framework for specify additional resources
-  Agent signing and verification
-  Agent package contains multiple layers which can be signed by
   different entities
-  Creator of code
-  Administrator of ‘Scope of Influence’/Deployment
-  Instantiator of agent
-  Most recent platform (for mobile agents)
-  Each level verified before agent is allowed to run
-  Entities cannot change content of other layers

-  Agent Mobility
-  Admin can send an agent to another platform for deployment/updating
-  Agent can request to move
-  Agent can bring along working files as part of ‘mutable luggage’
-  Receiving platform verifies agent package and examines resource
   contract before executing agent

VOLTTRON 3.0
============

-  Modularized Historian
-  Historians can be built for any storage solution

   -  Previous versions did not have option for local storage

-  BaseHistorian

   -  Can be extended for any solution
   -  Handles subscribing to Bus
   -  Local cache

-  Modularized Drivers
-  Standardized creating custom drivers to scrape data and publish to
   the message bus
-  Simplify developing drivers and contributing new capabilities back to
   VOLTTRON
-  Abstracted out driver interfaces allowing Actuator Agent to handle
   controlling devices via any protocol
-  VIP - VOLTTRON Interconnect Protocol
-  Increase security of the message bus and allow direct communication
   where appropriate
-  New communication model underneath VOLTTRON Message Bus
-  Compatibility layer so changes are transparent to existing agents
-  Platform Agent
-  Provides point of contact for the platform
-  Enables VOLTTRON Management Central control of platform
-  VOLTTRON Management Central
-  Web interface for administering VOLTTRON platforms in deployment


