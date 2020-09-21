.. _Deployment-Overview:

===================
Deployment Overview
===================

This page is meant as an overview of setting up a VOLTTRON deployment which consists of one or more platforms collecting
data and being managed by another platform running the VOLTTRON Central agent.  High level instructions are included but
for more details on each step, please follow links to that section of the docs.


Assumptions
===========

- `Data Collector` is the box that has the drivers and is collecting data it needs to forward.
- `Volttron Central/VC` is the box that has the historian which will save data to the database.
- ``VOLTTRON_HOME`` is assumed to the default on both boxes which is: `/home/<user>/.volttron`

  .. note::

     ``VOLTTRON_HOME`` is the directory used by the platform for managing state and configuration of the platform and
     agents installed locally on the platform.  Auth keys, certificates, the configuration store, etc. are stored in
     this directory by the platform.


Notes/Tips
==========

-  Aside from installing the required packages with `apt-get`, ``sudo`` is not required and **should not be used**.
   VOLTTRON is designed to be run as a non-root user and running with ``sudo`` is not supported.

   .. warning::

      Running VOLTTRON as the root user using ``sudo`` reduces the effectiveness of the security features built into the
      platform.

-  The convenience :ref:`scripts <Utility-Scripts>` have been developed to simplify many of the repetitive multi-step
   processes.  For instance, ``scripts/core/make-listener`` can be modified for any agent and turn the process into one
   command to stop, remove, build, install, configure, tag, start, and (optionally) enable an agent for autostart.
-  Creating a separate ``config`` directory for agent configuration files used in the deployment can prevent them from
   being committed back to the repository.
-  Double check firewall rules/policies when setting up a multi-node deployment to ensure that platforms can communicate

.. note::

   The following instructions assume default directories are used (for instance, ``/home/<user>/volttron`` for the
   project directory and ``/home/<user>/.volttron`` for the VOLTTRON_HOME directory.)


On all machines
===============

On all machines in the deployment:

- Follow the :ref:`platform installation guide <Platform-Prerequisites>` to setup the platform
- Setup encryption, authentication, and authorization
- Build the basic agents for the deployment.  All platforms will need a PlatformAgent and a Historian.  Using
  :ref:`scripts <Utility-Scripts>` will help simplify this process.


Configuring Platform
====================


On VC
-----

- Run :ref:`vcfg <VOLTTRON-Config>`
- Setup as VOLTTRON Central.
- Set appropriate ip, port, etc for this machine 
- Pick to install a platform historian (defaults to sqlite)
- Start up the platform and find the line with the server public key

  .. code-block:: bash

     cat volttron.log | grep “public key”
     2016-05-19 08:42:58,062 () volttron.platform.main INFO: public key: <KEY>
 
 
On the data collector
---------------------


Driver Setup
============

For a simple case, follow instructions to install a :ref:`Fake Driver <Fake-Driver>` for testing purposes.  For a
production deployment against real devices see the following:

-  Create a :ref:`Master Driver Agent <Master-Driver-Configuration>` to coordinate drivers for the devices controlled by
   this platform.
-  For all devices (such as :ref:`Modbus <Modbus-Driver>`), create config files and point configuration files.

   .. note::

      There are several drivers included with the VOLTTRON core repository.  Each driver will require at least a driver
      configuration and point configuration file.  For more information on drivers and their configuration procedures,
      view the :ref:`Driver Framework <Driver-Framework>` section of the docs.


-  For BACnet devices, create a :ref:`Proxy Agent <BACnet-Proxy-Agent>` for :ref:`BACnet drivers <BACnet-Driver>` to
   communicate through (see :ref:`Driver Communication <Driver_Communication>` for more information)

 
Setup the Forwarder
===================

 Now that data is being published to the bus, a :ref:`Forward Historian<Forward-Historian>` can be
 configured to send this data to the VC instance for storage.
 
- Use: vctl keypair to generate a keypair
- cat VOLTTRON_HOME/keypair to get the public and secret keys
- Create a config directory in the main project directory
- Setup a :ref:`Forward Historian<Forward-Historian>`

  - cp services/core/ForwardHistorian/config config/forwarder.config
  - Edit forwarder.config using the VC’s VIP address, the public server key, and the keypair

    ::

        "destination-vip": "tcp://<VC_IP>:<VC_PORT>?serverkey=<server_key>&secretkey=<secret_key>&publickey=<public_key>
    
  - For ease of use, you can use the install-agent.py in the scripts directory to install the Forward Historian:

    .. code-block:: bash

        python scripts/install-agent.py -s services/core/ForwardHistorian -c config/forwarder.config

  - Use ``vctl status`` in the command line to show installed agents and their respective statuses.
 
Testing
-------

Start a listener agent on VC, you should see data from the data collector appear.

.. code-block:: bash

   vctl start <listener tag>
 
In the log for VC, check for credentials success for the IP of data collector.


Registering the collection platform
-----------------------------------

- In a browser, go to the url for your VC instance.
- Click on Register Platforms
- Enter a name for the collection platform and the ip configured http://<ip>:<discovery_port>
- Open the tree upper left of the UI and find your platform.


Troubleshooting:
================

-  Check firewall rules
-  registering VC on VC: ``ipc:\ //@/home/volttron/.volttron/run/vip.socket``
-  Change password by putting pw hash in config file
-  Add remote ip address to config file


.. toctree::

   deployment-planning-options
   bootstrap-options
