.. _Single-Machine-Deployment:

==============
Single Machine
==============

The purpose of this demonstration is to show the process of setting up a simple VOLTTRON instance for use on a single
machine.


Install and Build VOLTTRON
==========================

First, :ref:`install <Platform-Installation>` VOLTTRON:

For a quick reference for Ubuntu machines:

.. code-block:: console
        
        sudo apt-get update
        sudo apt-get install build-essential libffi-dev python3-dev python3-venv openssl libssl-dev libevent-dev git
        git clone https://github.com/VOLTTRON/volttron/
        cd volttron
        python3 bootstrap.py

For all others, please see the platform install section.



Activating the  VOLTTRON Environment
====================================

After the build is complete, activate the VOLTTRON environment.

.. code-block:: console

        source env/bin/activate


Configuring VOLTTRON
====================

The ``vcfg`` command allows for an easy configuration of the VOLTTRON environment.

.. note::
        
        To create a simple instance of VOLTTRON, leave the default response, or select yes (y) if
        prompted for a yes or no response [Y/N]. You must choose a username and password for the
        VOLTTRON Central admin account.

A set of example responses are included here (username is user, localhost is volttron-pc):

.. code-block:: console

        (volttron) user@volttron-pc:~/volttron$ vcfg

        Your VOLTTRON_HOME currently set to: /home/user/.volttron

        Is this the volttron you are attempting to setup? [Y]:
        What type of message bus (rmq/zmq)? [zmq]:
        What is the vip address? [tcp://127.0.0.1]:
        What is the port for the vip address? [22916]:
        Is this instance web enabled? [N]: y
        What is the protocol for this instance? [https]:
        Web address set to: https://volttron-pc
        What is the port for this instance? [8443]:
        Would you like to generate a new web certificate? [Y]:
        WARNING! CA certificate does not exist.
        Create new root CA? [Y]:

        Please enter the following details for web server certificate:
            Country: [US]:
            State: WA
            Location: Richland
            Organization: PNNL
            Organization Unit: VOLTTRON
        Created CA cert
        Creating new web server certificate.
        Is this an instance of volttron central? [N]: y
        Configuring /home/user/volttron/services/core/VolttronCentral.
        Installing volttron central.
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        VC admin and password are set up using the admin web interface.
        After starting VOLTTRON, please go to https://volttron-pc:8443/admin/login.html to complete the setup.
        Will this instance be controlled by volttron central? [Y]:
        Configuring /home/user/volttron/services/core/VolttronCentralPlatform.
        What is the name of this instance? [volttron1]:
        Volttron central address set to https://volttron-pc:8443
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Would you like to install a platform historian? [N]: y
        Configuring /home/user/volttron/services/core/SQLHistorian.
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Would you like to install a master driver? [N]: y
        Configuring /home/user/volttron/services/core/MasterDriverAgent.
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Would you like to install a fake device on the master driver? [N]: y
        Should the agent autostart? [N]: y
        Would you like to install a listener agent? [N]: y
        Configuring examples/ListenerAgent.
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Finished configuration!

        You can now start the volttron instance.

        If you need to change the instance configuration you can edit
        the config file is at /home/user/.volttron/config

Once this is finished, run VOLTTRON and test the new configuration.


Testing VOLTTRON
================

To test that the configuration was successful, start an instance of VOLTTRON in the background:

.. code-block:: console

        ./start-volttron

.. note::

        This command must be run from the root VOLTTRON directory.


Command Line
------------

If the example ``vcfg`` responses were used, the listener, master_driver, platform_historian, vcp, and vc agents
should have all started automatically. This can be checked using ``vctl status``.

The output should look similar to this:

.. code-block:: console

        (volttron)user@volttron-pc:~/volttron$ vctl status
          AGENT                    IDENTITY            TAG                STATUS          HEALTH
        8 listeneragent-3.2        listeneragent-3.2_1 listener           running [2810]  GOOD
        0 master_driveragent-3.2   platform.driver     master_driver      running [2813]  GOOD
        3 sqlhistorianagent-3.7.0  platform.historian  platform_historian running [2811]  GOOD
        2 vcplatformagent-4.8      platform.agent      vcp                running [2812]  GOOD
        9 volttroncentralagent-5.0 volttron.central    vc                 running [2808]  GOOD

You can further verify that the agents are functioning correctly with ``tail -f volttron.log``
