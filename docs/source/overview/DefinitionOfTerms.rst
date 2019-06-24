.. _definitions:

===================
Definition of Terms
===================

This page lays out a common terminology for discussing the components and
underlying technologies used by the platform. The first
section discusses capabilities and industry standards that volttron
conforms to while the latter is specific to the VOLTTRON domain.

Industry Terms
~~~~~~~~~~~~~~

-  **BACNet**: Building Automation and Control network, that leverages ASHRAE, ANSI, and IOS 16484-5 standard protocols.
-  **JSON-RPC**: JSON-encoded remote procedure call
-  **JSON**: JavaScript object notation is a text-based, human-readable, open data interchange format, similar to XML, but less verbose
-  **Publish/subscribe**: A message delivery pattern where senders (publishers) and receivers (subscribers) do not communicate directly nor necessarily have knowledge of each other, but instead exchange messages through an intermediary based on a mutual class or topic
-  **ZeroMQ or ØMQ**: A library used for inter-process and inter-computer communication
-  **Modbus**: Communications protocol for talking with industrial electronic devices
-  **SSH**: Secure shell is a network protocol providing encryption and authentication of data using public-key cryptography
-  **SSL**: Secure sockets layer is a technology for encryption and authentication of network traffic based on a chain of trust
-  **TLS**: Transport layer security is the successor to SSL


VOLTTRON Terms
~~~~~~~~~~~~~~

    .. _activated-environment:

    Activated Environment
        An activated environment is the environment a VOLTTRON instance is run in.
        The bootstrap process creates the environment from the shell and to activate
        it the following command is executed.

        .. code-block:: bash

            user@computer> source env/bin/activate

            # Note once the above command has been run the prompt will have changed
            (volttron)user@computer>

    .. _bootstrap-environment:

    Bootstrap Enviornment
        The process by which an operating environment (activated environment)
        is produced.  From the :ref:`VOLTTRON_ROOT` directory executing
        ``python bootstrap.py`` will start the bootstrap process.

    .. _VOLTTRON_HOME:

    VOLTTRON_HOME
        The location for a specific :ref:`VOLTTRON_INSTANCE` to store its specific
        information.  There can be many VOLTTRON_HOMEs on a single computing
        resource(VM, machine, etc.)

    .. _VOLTTRON_INSTANCE:

    VOLTTRON_INSTANCE
        A single volttron process executing instructions on a computing resource.
        For each VOLTTRON_INSTANCE there WILL BE only one :ref:`VOLTTRON_HOME`
        associated with it.  In order for a VOLTTRON_INSTANCE to be able to
        participate outside its computing resource it must be bound to an
        external ip address.

    .. _VOLTTRON_ROOT:

    VOLTTRON_ROOT
        The cloned directory from github.  When executing the command

        .. code-block:: bash

            git clone http://github.com/VOLTTRON/volttron

        the top volttron folder is the VOLTTRON_ROOT

    .. _VIP:

    VIP
        VOLTTRON Interconnect Protocol is a secure routing protocol that facilitates
        communications between agents, controllers, services and the supervisory
        :ref:`VOLTTRON_INSTANCE`.

