.. _What-is-Volttron:

=================
What is VOLTTRON?
=================

VOLTTRON™ is a software platform on which software modules called "agents" and device driver modules to connect to a
message bus to interact. Users may configure included drivers for industry standard device communication protocols such
as BACnet or Modbus, or develop and configure their own. Additionally, agents can be installed or developed to perform
a vast variety of tasks.


Design Philosophy
=================

VOLTTRON was designed by Pacific Northwest National Laboratory to service building efficiency, building-grid integration
and transactive controls systems. These systems are working to improve energy efficiency and resiliency in critical
infrastructure. To this end, VOLTTRON was built with the following pillars in mind:

 * Cost-Effectiveness -  Open source software (free to users) and can be hosted on inexpensive computing resources
 * Scalability - Can be used in one building or a fleet of buildings
 * Interoperability - Enables interaction/connection with various systems and subsystems, in and out of the energy
   sector
 * Security - Underpinned with a robust security foundation to combat today’s cyber vulnerabilities and attacks


Basic Components
================

* :ref:`Message bus <Message-Bus>` - The VOLTTRON message bus uses
  `message queueing software <https://en.wikipedia.org/wiki/Message-oriented_middleware>`_ to exchange messages
  between agents and drivers installed on the platform.  VOLTTRON messages are exchanged using a
  :ref:`publish/suscriber paradigm <VIP-Overview>`, or messages can be routed to specific agents through the bus using
  :ref:`remote procedure calls <Remote-Procedure-Calls>`.

* :ref:`Agents <Agent-Framework>` - Agents are software modules which autonomously perform a set of desired functions on
  behalf of a user.  VOLTTRON agents are often use to collect data, send control signals to devices, implement control
  algorithms or perform simulations.

* :ref:`Drivers <Driver-Framework>` - Drivers can be installed on the platform and configured to communicate with
  industrial or Internet of Things devices.  Drivers provide a set of pre-defined functions which can be mapped to
  device communication methods to read or set values on the device.

* :ref:`Historians <Historian-Framework>` - Historians are special purpose agents which are used to subscribe to sources broadcasting on
the message bus and store their messages for later use.

* :ref:`Web Framework <Web-Framework>` - The VOLTTRON web framework
