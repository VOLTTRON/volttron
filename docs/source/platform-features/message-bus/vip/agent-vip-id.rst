.. _Agent-Identity-Specification:

===========================================
Agent VIP IDENTITY Assignment Specification
===========================================

This document explains how an agent obtains it's :term:`VIP IDENTITY <VIP Identity>`, how the platform sets an agent's
VIP IDENTITY at startup, and what mechanisms are available to the user to set the VIP IDENTITY for any agent.


What is a VIP IDENTITY
======================

A VIP IDENTITY is a platform instance unique identifier for agents.  The IDENTITY is used to route messages from one
Agent through the VOLTTRON router to the recipient Agent.  The VIP IDENTITY provides a consistent, user defined, and
human readable character set to build a VIP IDENTITY.  VIP IDENTITIES should be composed of both upper and lowercase
letters, numbers and the following special characters.


Runtime
=======

The primary interface for obtaining a VIP IDENTITY *at runtime* is via the runtime environment of the agent.  At startup
the utility function `vip_main` shall check for the environment variable **AGENT_VIP_IDENTITY**.  If the
**AGENT_VIP_IDENTITY** environment variable is not set then the `vip_main` function will fall back to a supplied
identity argument.  `vip_main` will pass the appropriate identity argument to the agent constructor.  If no identity is
set the Agent class will create a random VIP IDENTITY using python's `uuid4` function.

An agent that inherits from the platform's base Agent class can get it's current VIP IDENTITY by retrieving the value of
``self.core.identity``.

The primary use of the 'identity' argument to `vip_main` is for agent development.  For development it allows agents to
specify a default VIP IDENTITY when run outside the platform.  As platform Agents are not started via `vip_main` they
will simply receive their VIP IDENTITY via the identity argument when they are instantiated.  Using the identity
argument of the Agent constructor to set the VIP IDENTITY via agent configuration is no longer supported.

At runtime the platform will set the environment variable **AGENT_VIP_IDENTITY** to the value set at installation time.

Agents not based on the platform's base Agent should set their VIP IDENTITY by setting the identity of the ZMQ socket
before the socket connects to the platform.  If the agent fails to set it's VIP IDENTITY via the ZMQ socket it will be
selected automatically by the platform.  This platform chosen ID is currently not discoverable to the agent.


Agent Implementation
====================

If an Agent has a preferred VIP IDENTITY (for example the Platform Driver Agent prefers to use "platform.driver") it may
specify this as a default packed value.  This is done by including a file named IDENTITY containing only the desired VIP
IDENTITY in ASCII plain text in the same directory at the `setup.py` file for the Agent.  This will cause the packaged
agent wheel to include an instruction to set the VIP IDENTITY at installation time.

This value may be overridden at packaging or installation time.


Packaging
=========

An Agent may have it's VIP IDENTITY configured when it is packaged.  The packaged value may be used by the platform to
set the **AGENT_VIP_IDENTITY** environment variable for the agent process.

The packaged VIP IDENTITY may be overridden at installation time.  This overrides any preferred VIP IDENTITY of the
agent.  This will cause the packaged agent wheel to include an instruction to set the VIP IDENTITY at installation time.

To specify the VIP IDENTITY when packaging use the ``--vip-identity`` option when running `volttron-pkg package`.


Installation
============

An agent may have it's VIP IDENTITY configured when it is installed.  This overrides any VIP IDENTITY specified when the
agent was packaged.

To specify the VIP IDENTITY when packaging use the ``--vip-identity`` option when running `volttron-ctl install`.


Installation Default VIP IDENTITY
---------------------------------

If no VIP IDENTITY has been specified by installation time the platform will assign one automatically.

The platform uses the following template to generate a VIP IDENTITY:

.. code-block:: python

    "{agent_name}_{n}"

``{agent_name}`` is substituted with the name of the actual agent such as ``listeneragent-0.1``

``{n}`` is a number to make VIP IDENTITY unique.  ``{n}`` is set to the first unused number (starting from 1) for all
installed instances of an agent. e.g.  If there are 2 listener agents installed and the first (VIP IDENTITY
listeneragent-0.1_1) is uninstalled leaving the second (VIP IDENTITY "listeneragent-0.1_2"), a new listener agent will
receive the VIP IDENTITY "listeneragent-0.1_1" when installed.  The next installed listener will receive a VIP IDENTITY
of "listeneragent-0.1_3".

The ``#`` sign is used to prevent confusing the agent version number with the installed instance number.

If an agent is repackaged with a new version number it is treated as a new agent and the number will start again from 1.


VIP IDENTITY Conflicts During Installation
------------------------------------------

If an agent is assigned a VIP IDENTITY besides the default value given to it by the platform it is possible for VIP IDENTITY conflicts to exist between installed agents. In this case the platform rejects the installation of an agent with a conflicting VIP IDENTITY and reports an error to the user.


VIP IDENTITY Conflicts During Runtime
-------------------------------------

In the case where agents are not started through the platform (usually during development or when running standalone
agents) it is possible to encounter a VIP IDENTITY conflict during runtime.  In this case the first agent to use a VIP
IDENTITY will function as normal.  Subsequent agents will still connect to the ZMQ socket but will be silently rejected
by the platform router.  The router will not route any message to that Agent.  Agents using the platforms base Agent
will detect this automatically during the initial handshake with the platform.  This condition will shutdown the Agent
with an error indicating a VIP IDENTITY conflict as the most likely cause of the problem.

Auto Numbering With Non-Default VIP IDENTITYs
=============================================

It is possible to use the auto numbering mechanism that the default VIP IDENTITY scheme uses. Simply include the string
``{n}`` somewhere in the requested VIP IDENTITY and it will be replaced with a number in the same manner as the default
VIP IDENTITY is.  Python `string.format()` escaping rules apply. `See this question on StackOverflow.
<http://stackoverflow.com/questions/5466451/how-can-i-print-a-literal-characters-in-python-string-and-also-use-format>`_


Script Features
===============

The `scripts/install-agent.py` script supports specifying the desired VIP IDENTITY using the ``-i`` (or
``--vip-identity``) ``<identity>`` option


Security/Privacy
================

Currently, much like the `TAG` file in an installed agent, there is nothing to stop someone from modifying the
`IDENTITY` file in the installed agent.


Constraints and Limitations
===========================

Currently there is no way for an agent based on the platform base Agent class to recover from a VIP IDENTITY conflict.
This case only affects developers and a very tiny minority of users and is reported via an error message, there
are currently no plans to fix it.
