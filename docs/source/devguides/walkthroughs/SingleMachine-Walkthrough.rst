.. _SingleMachine-Walkthrough:

Single Machine Deployment
=========================

The purpose of this page is to provide details for the process of 
setting up an example VOLTTRON setup for use on a single machine.

Install and Build VOLTTRON
--------------------------

First, :ref:`install <VOLTTRON-Prerequisites>` and :ref:`build <Building-VOLTTRON>` VOLTTRON:

.. code-block:: console
        
        sudo apt-get update
        sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git
        git clone https://github.com/VOLTTRON/volttron/
        cd volttron
        python2.7 bootstrap.py


Configuring VOLTTRON
--------------------

After the build is complete, activate the VOLTTRON environment.

.. code-block:: console

        source env/bin/activate

The ``volttron-cfg`` command allows for an easy configuration of the VOLTTRON environment.
An example output is included here:

.. code-block:: console

        (volttron)USER@volttron-pc:~/volttron$ volttron-cfg

        Your VOLTTRON_HOME currently set to: /home/USER/.volttron
        
        Is this the volttron you are attempting to setup?  [Y]: y
        What is the external instance ipv4 address? [tcp://127.0.0.1]: 
        What is the instance port for the vip address? [22916]: 
        Is this instance a volttron central? [N]: y
        Configuring /home/USER/volttron/services/core/VolttronCentral
        
        In order for external clients to connect to volttron central or the instance 
        itself, the instance must bind to a tcp address.  If testing this can be an
        internal address such as 127.0.0.1.

        Please enter the external ipv4 address for this instance?  [http://127.0.0.1]: 
        What is the port for volttron central? [8080]: 
        Enter volttron central admin user name: [USERNAME]
        Enter volttron central admin password: [PASSWORD]
        Retype password: [PASSWORD]
        Installing volttron central
        Should agent autostart? [N]: y
        Will this instance be controlled by volttron central? [Y]: y
        Configuring /home/USER/volttron/services/core/VolttronCentralPlatform
        Enter the name of this instance. [tcp://127.0.0.1:22916]: 
        Enter volttron central's web address [http://127.0.0.1]: 
        What is the port for volttron central? [8080]: 
        Should agent autostart? [N]: y
        Would you like to install a platform historian? [N]: y
        Configuring /home/USER/volttron/services/core/SQLHistorian
        Should agent autostart? [N]: y
        Would you like to install a master driver? [N]: y
        Configuring /home/USER/volttron/services/core/MasterDriverAgent
        Install a fake device on the master driver? [N]: y
        Should agent autostart? [N]: y
        Would you like to install a listener agent? [N]: y                               
        Configuring examples/ListenerAgent
        Should agent autostart? [N]: y
        Finished configuration
        
        You can now start the volttron instance.

        If you need to change the instance configuration you can edit
        the config file at /home/USER/.volttron/config

        (volttron)USER@volttron-pc:~/volttron$



Once this is finished, run VOLTTRON and test the new configuration.

.. note::
        Though many of the defaults will be acceptable, you must choose a username and password for the volttron central admin account.

Testing VOLTTRON
~~~~~~~~~~~~~~~~

Command Line
------------

To test that everything is functional, start up the platform running in the background:

.. code-block:: console

        volttron -vv -l volttron.log >/dev/null 2>&1&

Since the default ``volttron-cfg`` is used, the listener, master_driver, platform_historian, vcp, and vc agents should have all started automatically. This can be checked with using ``volttron-ctl status``. An example output:

.. code-block:: console

        (volttron)USER@volttron-pc:~/volttron$ volttron-ctl status

          AGENT                    IDENTITY            TAG                STATUS          HEALTH
        f listeneragent-3.2        listeneragent-3.2_1 listener           running [7596]  GOOD
        a master_driveragent-3.2   platform.driver     master_driver      running [7599]  GOOD
        e sqlhistorianagent-3.7.0  platform.historian  platform_historian running [7598]  GOOD
        9 vcplatformagent-4.7      platform.agent      vcp                running [7600]  GOOD
        2 volttroncentralagent-4.2 volttron.central    vc                 running [7601]  GOOD

You can further verify functionality with ``tail -f volttron.log``

VOLTTRON Central
----------------

To verify everything is functional, open a web browser and navigate to localhost:8080/vc/index.html.
In this case: ``127.0.0.1:8080/vc/index.html``

|vc-login|

Login using the username and password you created during the ``volttron-ctl`` prompt.

Once you have logged in, click on the Platforms tab in the upper right corner of the window.

|vc-dashboard|

Once in the Platforms screen, click on the name of the platform. If defaults have been left in place, it will be labelled as seen below.

|vc-platform|

You will now see a list of agents. They should all be running.

|vc-agents|

For more information on VOLTTRON Central, please see:
- :ref:`VOLTTRON Central Management <volttron-central-management>`
- :ref:`VOLTTRON Central Demo <volttron-central-demo>`
