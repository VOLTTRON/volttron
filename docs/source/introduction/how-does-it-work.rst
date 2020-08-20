.. _How-it-Works:

=================
How Does it Work?
=================

The VOLTTRON platform is built around the concept of software agents. Software agents perform autonomous functions on
behalf of a user.  The VOLTTRON platform was created to allow a suite of agents installed by a user to work together to
achieve the user's goals.


Major Components
================

The platform comprises several components that allow agents to operate and connect to the platform.

* The :ref:`Message Bus <Message-Bus>` is central to the platform.  All other VOLTTRON components communicate through it
  using :ref:`VOLTTRON Interconnect Protocol<VIP-Overview>` (VIP). VIP implements the publish/subscribe paradigm over a
  variety of topics or directed communication using :ref:`Remote Procedure Calls <Remote-Procedure-Calls>`.

* :ref:`Agents <Agent-Framework>` on the platform extend the base agent which provides a VIP connection to the message
  bus as well as an agent lifecycle. Agents subscribe to topics which allow it to read The agent lifecycle is controlled
  by the :ref:`Agent Instantiation and Packaging <Agent-Instantiation-and-Packaging>` (AIP) component which launches
  agents in an agent execution environment.

* The :ref:`Master Driver Agent <Master-Driver>` can be configured with a number of driver configurations and will spawn
  corresponding driver instances.  Each driver instance provides functions for collecting device data and setting values
  on the device.  These functions implement device protocol or remote communication endpoint interfaces.  Driver data
  is published to the message bus or if requested by an agent will be delivered in an RPC response.

* Agents can control devices by interacting with the :ref:`Actuator Agent <Actuator-Agent>` to schedule and send
  commands.

* The :ref:`Historian <Historian-Framework>` framework subscribes to data published on the messages bus and stores it to
  a database or file, or sends it to another location.

.. image::


Usability Components
====================

Usability components exist to enhance the base capabilities of the platform for deployments.

* :ref:`VOLTTRON Control <Control>` is the command line interface to controlling a platform instance.  VOLTTRON
  Control can be used to operate agents, configure drivers, get status and health details, etc.

* Data collection, command and control can be achieved in large deployments by
  :ref:`connecting multiple platform instances <Multi-Platform-Communication>`.

* :ref:`VOLTTRON Central <VOLTTRON-Central>` is an agent which can be installed on a platform to provide a single
  management interface to multiple VOLTTRON platform instances.

* JSON, static and websocket endpoints can be registered to agents via the :ref:`Web Framework <Web-Framework-Overview>`
  and platform web server.  This allows remote agent communication as well as for agents to serve web pages.
