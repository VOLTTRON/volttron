.. _VOLTTRON-Driver-Framework:

=========================
VOLTTRON Driver Framework
=========================

VOLTTRON drivers act as an interface between agents on the platform and a device.  While running on the platform,
drivers are special purpose agents which instead of being run as a separate process, are run as a greenlet in the
Master Driver process.

Driver instances are created by the Master Driver when a new driver configuration is added to the configuration store.
Drivers use the following topic pattern `devices/<campus>/<building>/<device id>`.  When a configuration file is added
to the Master Driver's store using this pattern, the Master Driver creates a Driver Agent.  The Driver agent is in turn
instantiated with a instance of the Interface class corresponding to the `driver_type` parameter in the configuration
file.  The Interface class is responsible for implementing the communication paradigms of a device or protocol.  Once
configured, the Master Driver periodically polls the Driver Agent for data which is collected from the interface class.
Additionally, points can be requested ad-hoc via the Master Driver's JSON-RPC method "get_point". Points may be set
by using JSON-RPC with the Actuator agent to set up a schedule and calling the "set_point" method.


Driver Conventions
------------------

-  Drivers are polled by the Master Driver agent and values can be set using the `Actuator Agent`
-  Drivers should have a 1-to-1 relationship with a device
-  Driver modules should be written in Python files in the `services/core/MasterDriverAgent/master_driver/interfaces`
   directory in the VOLTTRON repository.  The master driver will search for a Python file in this directory matching the
   name provided by the `driver_type` value from the driver configuration when creating the Driver agent.
-  Driver code consists of an Interface class (exactly named), supported in most cases by one or more Register classes


Driver Communication Patterns
=============================




.. toctree::
    :maxdepth: 2
