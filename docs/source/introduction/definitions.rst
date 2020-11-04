.. _Definitions:

===================
Definition of Terms
===================

This page lays out a common terminology for discussing the components and underlying technologies used by the platform.
The first section discusses capabilities and industry standards that VOLTTRON conforms to while the latter is specific
to the VOLTTRON domain.


Industry Terms
==============

.. glossary::

  Agent
    Software which acts on behalf of a user to perform a set of tasks.

  BACNet
    Building Automation and Control network that leverages ASHRAE, ANSI, and IOS 16484-5 standard protocols

  DNP3 (Distributed Network Protocol 3)
    Communications protocol used to coordinate processes in distributed automation systems

  JSON (JavaScript Object Notation)
    JavaScript object notation is a text-based, human-readable, open data interchange format, similar to XML but less verbose

  IEEE 2030.5
    Utilities communication standard for managing energy demand and load (previously Smart Energy Profile version 2, SEP2)

  JSON-RPC (JSON-Remote Procedure Call)
    JSON-encoded Remote Procedure Call

  Modbus
    Communications protocol for talking with industrial electronic devices

  PLC (Programmable Logic Controller)
    Computer used in industrial applications to manage processes of groups of industrial devices

  Python Virtual Environment
    The `Python-VENV` library allows users to create a virtualized copy of the local environment.  A virtual environment allows the user to isolate the dependencies for a project which helps prevent conflicts between dependencies across projects.

  Publish/Subscribe
    A message delivery pattern where senders (publishers) and receivers (subscribers) do not communicate directly nor necessarily have knowledge of each other, but instead exchange messages through an intermediary based on a mutual class or topic.

.. note::

   The Publish/Subscribe paradigm is often notated as ``pub/sub`` in VOLTTRON documentation.

  RabbitMQ
    Open-Source message brokering system used by VOLTTRON for sending messages between services on the platform.

  Remote Procedure Call
    Protocol used to request services of another computer located elsewhere on the network or on a different network.

  SSH (Secure Shell)
    Secure Shell is a network protocol providing encryption and authentication of data using public-key cryptography.

  SSL (Secure Sockets Layer)
    Secure Sockets Layer is a technology for encryption and authentication of network traffic based on a chain of trust.

  TLS (Transport Layer Security)
    Transport Layer Security is the successor to SSL.

  ZeroMQ (also ØMQ)
    A library used for inter-process and inter-computer communication.

VOLTTRON Terms
==============

.. glossary::

.. _Activated-Environment:

  Activated Environment
    An activated environment is the environment a VOLTTRON instance is run in. The bootstrap process creates the environment from the shell.

  AIP (Agent Instantiation and Packaging)
    This is the module responsible for creating agent wheels, the agent execution environment and running agents.  Found in the VOLTTRON repository in the `volttron/platform` directory.

  Agent Framework
    Framework which provides connectivity to the VOLTTRON platform and subsystems for software agents.

.. _Bootstrap-Environment:

  Bootstrap the Environment
    The process by which an operating environment (activated environment) is produced.  From the :ref:`VOLTTRON_ROOT` directory, executing `python bootstrap.py` will start the bootstrap process.

  Config Store
    Agent data store used by the platform for storing configuration files and automating the management of agent configuration

  Driver
    Module that implements communication paradigms of a device to provide an interface to devices for the VOLTTRON platform.

  Driver Framework
    Framework for implementing communication between the VOLTTRON platform and devices on the network (or a remote network)

  Historian
    Historians in VOLTTRON are special purpose agents for automatically collecting data from the platform message bus and storing in a persistent data store.

  VOLTTRON Central
    VOLTTRON Central (VC) is a special purpose agent for managing multiple platforms in a distributed VOLTTRON deployment

.. _VOLTTRON_HOME:

  VOLTTRON_HOME
    The location for a specific :ref:`VOLTTRON_INSTANCE` to store its specific information.  There can be many VOLTTRON_HOMEs on a single computing resource such as a VM, machine, etc. Each `VOLTTRON_HOME` will correspond to a single instance of VOLTTRON.

.. _VOLTTRON_INSTANCE:

  VOLTTRON_INSTANCE
    A single volttron process executing instructions on a computing resource. For each VOLTTRON_INSTANCE, there WILL BE only one :ref:`VOLTTRON_HOME` associated with it.  For a VOLTTRON_INSTANCE to participate outside its computing resource, it must be bound to an external IP address.

.. _VOLTTRON_ROOT:

  VOLTTRON_ROOT
    The cloned directory from Github.  When executing the command:

    .. code-block:: bash

        git clone https://github.com/VOLTTRON/volttron.git

        the top level volttron folder is the VOLTTRON_ROOT.

.. _VIP:

  VIP
    VOLTTRON Interconnect Protocol is a secure routing protocol that facilitates communications between agents, controllers, services, and the supervisory :ref:`VOLTTRON_INSTANCE`.

  Web Framework
    Framework used by VOLTTRON agents to implement web services with HTTP and HTTPS
