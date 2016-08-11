.. _Deployment-Walkthrough:

Deployment Walkthrough
~~~~~~~~~~~~~~~~~~~~~~


This page is meant as an overview of setting up a VOLTTRON deployment
which consists of one or more platforms collecting data and being
managed by another platform running the VOLTTRON Central agent. High
level instructions are included but for more details on each step,
please follow links to that section of the wiki.


Assumptions:

- “Data Collector” is the box that has the drivers and is collecting data it needs to forward.
- “Volttron Central/VC” is the box that has the historian which will save data to the database.
- VOLTTRON_HOME is assumed to the default on both boxes which is: /home/<user>/.volttron


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
Using :ref:`scripts <scripts>` will help simplify this project.

:ref:`Install required packages <VOLTTRON-Prerequisites>`
----------------------------------------------------------

-  ``sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git``

:ref:`Build the project <Building-VOLTTRON>`
----------------------------------------------

-  Clone the repository and build using ``python bootstrap.py``


Configuring Platform
----------------------
 

On VC:

- Run :ref:`volttron-cfg<VOLTTRON-Config>`
- Setup as VOLTTRON Central.
- Set appropriate ip, port, etc for this machine 
- Pick to install a platform historian (defaults to sqlite)
- Start up the platform and find the line with the server public key “cat volttron.log|grep “public key”:
2016-05-19 08:42:58,062 () volttron.platform.main INFO: public key: <KEY>
 
 
On the data collector:
=======================
 
Setup :ref:`drivers <VOLTTRON-Drivers>`
-----------------------------------------

For a simple case, follow instructions to install a :ref:`Fake Driver`<Fake-Driver>` 
for testing purposes. For an actual deployment against real devices see the following:

-  Create a :ref:`Master Driver Agent <Master-Driver-Agent>` to coordinate
   drivers for the devices controlled by this platform.
-  For :ref:`MODBUS <Modbus-Driver>` devices, create config files and point
   configuration files.
-  For BACnet devices, create a :ref:`Proxy Agent <BACnet-Proxy-Agent>` for
   :ref:`BACnet drivers <BACnet-Driver>` to communicate through

 
 Setup the Forwarder
 -----------------------
 Now that data is being published to the bus, a :ref:`Forward Historian<Forward-Historian>` can be
 configured to send this data to the VC instance for storage.
 
- Use: volttron-ctl keypair   to generate a keypair
- cat VOLTTRON_HOME/keypair to get the public and secret keys
- Create a config directory in the main project directory
- Setup a :ref:`Forward Historian<ForwardHistorian>`

  - cp services/core/ForwardHistorian/config config/forwarder.config
  - Edit forwarder.config using the VC’s VIP address, the public server key, and the keypair
  
    -"destination-vip": "tcp://<VC_IP>:<VC_PORT>?serverkey=<server_key>&secretkey=<secret_key>&publickey=<public_key>
    
  - For ease of use, you can create a script to install the historian:
  - cp scripts/core/make-listener ./make-forwarder, then edit to look like:
  
make-forwarder::  
  export SOURCE=services/core/ForwardHistorian
  export CONFIG=config/forwarder.config
  export TAG=forward

  ./scripts/core/make-agent.sh enable
 
  - Execute that script and the forward historian should be installed
 
 
To check that things are working:
Start a listener agent on VC, you should see data from the data collector appear
 
In the log for VC, check for credentials success for the ip of data collector.


Registering the collection platform
=====================================

- In a browser, go to the url for your VC instance.
- Click on Register Platforms
- Enter a name for the collection platform and the ip configured http://<ip>:<discovery port>
- Open the tree upper left of the UI and find your platform.




Troubleshooting:
================

-  Check firewall rules
   registering VC on VC:
   ipc:\ //@/home/volttron/.volttron/run/vip.socket
   Change password by putting pw hash in config file
   Add remote ip address to config file

