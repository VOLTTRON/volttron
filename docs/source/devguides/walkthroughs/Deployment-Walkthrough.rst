Deployment Walkthrough
~~~~~~~~~~~~~~~~~~~~~~


This page is meant as an overview of setting up a VOLTTRON deployment
which consists of one or more platforms collecting data and being
managed by another platform running the VOLTTRON Central agent. High
level instructions are included but for more details on each step,
please follow links to that section of the wiki.

Notes/Tips:

-  Aside from installing the required packages with apt-get, ``sudo`` is
   not required and should not be used. VOLTTRON is designed to be run
   as a non-root user and running with sudo is not supported.
-  The convenience `scripts <Scripts>`__ have been developed to simplify
   many of the of the repetitive multi-step processes. For instance,
   ``scripts/core/make-listener`` can be modified for any agent and make
   it one command to stop, remove, build, install, configure, tag,
   start, and (optionally) enable an agent for autostart.
-  These instructions assume default directories are used (for instance,
   ``/home/<user>/volttron`` for the project directory and
   ``/home/<user>/.volttron`` for the VOLTTRON Home directory.
-  Creating a separate ``config`` directory for agent configuration
   files used in the deployment can prevent them from being committed
   back to the repository.
-  Double check firewall rules/policies when setting up a multi-node
   deployment to ensure that platforms can communicate

On all machines:
================

On all machines in the deployment, setup the platform, setup encryption,
authentication, and authorization. Also, build the basic agents for the
deployment. All platforms will need a PlatformAgent and a Historian.
Using `scripts <scripts>`__ will help simplify this project.

`Install required packages <DevelopmentPrerequisites>`__
--------------------------------------------------------

-  ``sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git``

`Build the project <BuildingTheProject>`__
------------------------------------------

-  Clone the repository and build using ``python bootstrap.py``

VIP-Authentication - auth.json

Configuring Platform
--------------------

-  To make the platform available for remote platforms, edit or create a
   `config file <PlatformConfigFile>`__ named ``config`` at the VOLTTRON
   home. By default, this is at: ~/.volttron
-  Add the following:

   ``[volttron]``

   ``vip-address=tcp://<IP-ADDRESS>:<PORT>``

-  | Run the platform once to create default directories and get the
   server key: ``volttron -v``
   | 
   ``2015-09-28 14:01:25,992 () volttron.platform.main INFO: public key: P3Y0rMT6-dH55xUO0mB2voY54pSzB4sIbN0ZyIjkQ1g``

-  For exploring VOLTTRON ONLY
-  Turn off encryption and authorization with: ``--developer-mode``
-  Turn off encryption only:
-  To disable: truncate ~/.volttron/curve.key to a 0 size file:
   ``truncate -s 0 $VOLTTRON_HOME/curve.key``

Remaining instructions assume encryption and authorization are on.

-  Setup `PlatformAgent <PlatformAgent>`__
-  Copy the platform config file from the PlatformAgent directory into
   config.
-  Copy the make-listener script and modify it for PlatformAgent

On client platforms
===================

-  Setup `drivers <VOLTTRON-Drivers>`__
-  Create a `Master Driver Agent <Master-Driver-Agent>`__ to coordinate
   drivers for the devices controlled by this platform.
-  For `MODBUS <Modbus-Driver>`__ devices, create config files and point
   configuration files.
-  For BACnet devices, create a `Proxy Agent <BACnet-Proxy-Agent>`__ for
   `BACnet drivers <BACnet-Driver>`__ to communicate through
-  Setup a `Platform Historian <Platform-Historain>`__ to record data
   from the drivers. A
   `SQLite <https://github.com/VOLTTRON/VOLTTRON3.0-docs/wiki/SQL-Historian>`__
   based historian is recommended for initial exploration.

| edit auth.json to allow VOLTTRON Central to access it
| Add other clients if you want them to communicate directly with it

On VOLTTRON Central platform
============================

-  Setup `VOLTTRON Central <VOLTTRON-Central>`__

-  Register Platform
-  VC and target must have each other in auth.json
-  Edit VC config to make externally facing

Troubleshooting:
================

-  Check firewall rules
   registering VC on VC:
   ipc:\ //@/home/volttron/.volttron/run/vip.socket
   Change password by putting pw hash in config file
   Add remote ip address to config file

