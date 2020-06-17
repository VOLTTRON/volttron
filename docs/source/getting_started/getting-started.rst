.. _Getting-Started:

=============================
Getting Started with VOLTTRON
=============================

What is VOLTTRON?
=================

VOLTTRON™, developed at Pacific Northwest National Laboratory as an open-source Python package to enable users to
collect data from devices and send control signals from software modules called Agents.


=======================
How does VOLTTRON work?
=======================

In essence the platform consists of a collection of pre-installed "platform" agents, user-specified agents, and drivers
communicating via a message bus.  An "agent" in VOLTTRON is a Python module connected to the message bus which performs
some arbitrary functionality.  Agents installed by the platform perform the function of managing the platform
communications and security.  Agents installed by a user may have any range of arbitrary functions such as data
collection, sending control signals to devices, simulating power systems, etc.  A number of agents are included in the
VOLTTRON repository for common types of tasks such as collecting device data from the message bus.  Drivers are special
purpose agents for interfacing with devices.  Typically a driver will function as a wrapper around a device protocol
such as BACnet or Modbus.  The message bus facilitates communication between these components using publish/subscribe or
JSON-RPC paradigms.  Multiple platforms can also be interconnected to create a network of platforms controlled by a
central deployment referred to as "VOLTTRON-Central".


Components
**********

An overview of the VOLTTRON platform components is illustrated in the figure below.  The platform comprises several
components and agents that provide services to other agents.  Of these components, the :ref:`Message Bus <messagebus>`
is central to the platform.  All other VOLTTRON components communicate through it using VOLTTRON Interconnect Protocol
(VIP). VIP implements the publish/subscribe paradigm over a variety of topics or more direct communication using Remote
Procedure Calls.

:ref:`Drivers <VOLTTRON-Driver-Framework>` communicate with devices allowing their data to be published on the message
bus.  Agents can control devices by interacting with the :ref:`Actuator Agent <ActuatorAgent>` to schedule and send
commands.  The :ref:`Historian <Historian Index>` framework takes data published on the messages bus and stores it to a
database or file, or sends it to another location.

The agent lifecycle is controlled by the Agent Instantiation and Packaging (AIP) component which launches agents in an
Agent Execution Environment. This isolates agents from the platform while allowing them to interact with the message bus.

|Overview of the VOLTTRON platform|

.. |Overview of the VOLTTRON platform| image:: files/overview.png


===============
Basic Use Cases
===============


.. toctree::
   :caption: Contents
   :maxdepth: 1

   definitions
