.. _SingleMachine-Walkthrough:

Single Machine Deployment
=========================

The purpose of this demonstration is to show the process of setting up a simple VOLTTRON instance for use on a single machine.

Install and Build VOLTTRON
--------------------------

First, :ref:`install <VOLTTRON-Prerequisites>` and :ref:`build <Building-VOLTTRON>` VOLTTRON:

For a quick reference: 

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

.. note::
        
        To create a simple instance of VOLTTRON, leave the default response, or select yes (y) if prompted for a yes or no response [Y/N]. You must choose a username and password for the VOLTTRON Central admin account.

A set of example responses are included here:

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


Testing VOLTTRON
----------------

Command Line
~~~~~~~~~~~~

To test that the configuration was successful, start an instance of VOLTTRON in the background:

.. code-block:: console

        volttron -vv -l volttron.log >/dev/null 2>&1&

If the example ``volttron-cfg`` responses were used, the listener, master_driver, platform_historian, vcp, and vc agents should have all started automatically. This can be checked using ``volttron-ctl status``. 

The output should look similar to this:

.. code-block:: console

        (volttron)USER@volttron-pc:~/volttron$ volttron-ctl status

          AGENT                    IDENTITY            TAG                STATUS          HEALTH
        f listeneragent-3.2        listeneragent-3.2_1 listener           running [7596]  GOOD
        a master_driveragent-3.2   platform.driver     master_driver      running [7599]  GOOD
        e sqlhistorianagent-3.7.0  platform.historian  platform_historian running [7598]  GOOD
        9 vcplatformagent-4.7      platform.agent      vcp                running [7600]  GOOD
        2 volttroncentralagent-4.2 volttron.central    vc                 running [7601]  GOOD

You can further verify that the agents are functioning correctly with ``tail -f volttron.log``

VOLTTRON Central
~~~~~~~~~~~~~~~~

To test that the configuration was successful, start an instance of VOLTTRON in the background:

.. code-block:: console

        volttron -vv -l volttron.log >/dev/null 2>&1&

Open a web browser and navigate to localhost:8080/vc/index.html.
In this case: ``127.0.0.1:8080/vc/index.html``

|vc-login|

.. |vc-login| image:: files/vc-login.png

Log in using the username and password you created during the ``volttron-ctl`` prompt.

Once you have logged in, click on the Platforms tab in the upper right corner of the window.

|vc-dashboard|

.. |vc-dashboard| image:: files/vc-dashboard.png

Once in the Platforms screen, click on the name of the platform. If defaults have been left in place, it will be labeled as seen below.

|vc-platform|

.. |vc-platform| image:: files/vc-platform.png

You will now see a list of agents. They should all be running.

|vc-agents|

.. |vc-agents| image:: files/vc-agents.png

For more information on VOLTTRON Central, please see:

* :ref:`VOLTTRON Central Management <VOLTTRON-Central>`
* :ref:`VOLTTRON Central Demo <volttron-central-demo>`
