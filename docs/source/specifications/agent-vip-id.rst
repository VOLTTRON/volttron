Agent VIP ID Assignment Specification
=====================================

This document explains how an agent obtains it's VIP ID, how the platform sets an agent's VIP ID at startup, and what mechanisms are available to the user to set the VIP ID for any agent.

Runtime
-------

The primary interface for obtaining a VIP ID *at runtime* is via the runtime environment of the agent. At startup an agent shall check for the environment variable **AGENT_VIP_ID**. If the **AGENT_VIP_ID** environment variable is not set then the agent may set its own VIP ID.

If the **AGENT_VIP_ID** is available the base Agent class provided by the platform will use it. If one is not available the base Agent will use the 'identity' argument to the __init__ function. If an 'identity' argument was not provided or is None the base Agent will generate a uuid using python's uuid.uuid4 function. An agent that inherits from the platform's base Agent class can get it's current VIP ID by retrieving the value of self.core.identity.

The primary use of the 'identity' argument to __init__ is for agent development and platform subsystems that are implemented as agents. For development it allows agents to specify a default VIP ID when run outside the platform. For platform subsystems it is used to provide the VIP ID to the agents created in the platform process. Using this argument to set the VIP ID via agent configuration is no longer supported.

At runtime the platform will set the environment variable **AGENT_VIP_ID** to the value set at installation time.

Agents not based on the platform's base Agent should set their VIP ID by setting the identity of the ZMQ socket before the socket connects to the platform. If the agent fails to set it's VIP ID via the ZMQ socket it will be selected automatically by the platform. This platform chosen ID is currently not discoverable to the agent.

Agent Implementation
--------------------

If an Agent has a preferred VIP ID (for example the MasterDriverAgent prefers to use "platform.driver") it may specify this as a default packed value. This is done by including a file named IDENTITY containing only the desired VIP ID in ASCII plain text in the same directory at the setup.py file for the Agent. This will cause the packaged agent wheel to include an instruction to set the VIP ID at installation time.

This value may be overridden at packaging or installation time.

Packaging
---------

An Agent may have it's VIP ID configured when it is packaged. The packaged value may be used by the platform to set the **AGENT_VIP_ID** environment variable for the agent process.

The packaged VIP ID may be overridden at installation time. This overrides any preferred VIP ID of the agent. This will cause the packaged agent wheel to include an instruction to set the VIP ID at installation time.

To specify the VIP ID when packaging use the *--vip-id* option when running "volttron-pkg package".

Installation
------------

An agent may have it's VIP ID configured when it is installed. This overrides any VIP ID specified when the agent was packaged.

To specify the VIP ID when packaging use the *--vip-id* option when running "volttron-ctl install".

Installation Default VIP ID
***************************

If no VIP ID has been specified by installation time the platform will assign one automatically.

The platform uses the following template to generate a VIP ID:

.. code-block:: python

    "{agent_name} #{n}"

{agent_name} is substituted with the name of the actual agent such as "listeneragent-0.1"

{n} is a number to make VIP ID unique. {n} is set to the first unused number (starting from 1) for all installed instances of an agent. e.g. If there are 2 listener agents installed and the first (VIP ID listeneragent-0.1 #1) is uninstalled leaving the second (VIP ID "listeneragent-0.1 #2") a new listener agent will receive the VIP ID "listeneragent-0.1 #1" when installed. The next installed listener will receive a VIP ID of "listeneragent-0.1 #3".

The # sign is used to prevent confusing the agent version number with the installed instance number.

If an agent is repackaged with a new version number it is treated as a new agent and the number will start again from 1.

VIP ID Conflicts During Installation
************************************

If an agent is assigned a VIP ID besides the default value given to it by the platform it is possible for VIP ID conflicts to exist between installed agents. In this case the platform rejects the installation of an agent with a conflicting VIP ID and reports an error to the user.

VIP ID Conflicts During Runtime
*******************************

In the case where agents are not started through the platform (usually during development or when running standalone agents) it is possible to encounter a VIP ID conflict during runtime. In this case the first agent to use a VIP ID will function as normal. Subsequent agents will still connect to the ZMQ socket but will be silently rejected by the platform router. The router will not route any message to that Agent. Agents using the platforms base Agent class will detect this automatically during the initial handshake with the platform. This condition will shutdown the Agent with an error indicating a VIP ID conflict as the most likely cause of the problem.

Auto Numbering With Non-Default VIP ID's
----------------------------------------

It is possible to use the auto numbering mechanism that the default VIP ID scheme uses. Simply include the string "{n}" somewhere in the requested VIP ID and it will be replaced with a number in the same manner as the default VIP ID is. Python string.format() escaping rules apply. `See this question on StackOverflow. <http://stackoverflow.com/questions/5466451/how-can-i-print-a-literal-characters-in-python-string-and-also-use-format>`__

Security/Privacy
----------------

Currently, much like the TAG file in an installed agent, there is nothing to stop someone from modifying the IDENTITY file in the installed agent.

Constraints and Limitations
---------------------------

Currently there is no way for an agent based on the platform base Agent class to recover from a VIP ID conflict. As that is case only affects developers and a very tiny minority of users and is reported via an error message, there are no plans to fix it.