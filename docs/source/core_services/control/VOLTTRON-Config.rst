.. _VOLTTRON-Config:

VOLTTRON Config
===============

The new volttron-cfg commands allows for the easy configuration of a VOLTTRON platform. This includes
setting up the platform configuration, historian, VOLTTRON Central UI, and platform agent.

example volttron-cfg output:

.. note:: 

        - In this example, <user> represents the user's home directory, and <localhost> represents the machine's localhost.
        - The platform has been bootstrapped with rabbitmq enabled e.g. (python bootstrap.py --rabbitmq)

.. code-block:: console 

        Your VOLTTRON_HOME currently set to: /home/<user>/.volttron

        Is this the volttron you are attempting to setup? [Y]: y
        What type of message bus (rmq/zmq)? [zmq]: rmq

        The rmq message bus has a backward compatibility 
        layer with current zmq instances. What is the 
        zmq bus's vip address? [tcp://127.0.0.1]: 
        What is the port for the vip address? [22916]: 
        Is this instance web enabled? [N]: y
        What is the hostname for this instance? (https) [https://<localhost>]: 
        What is the port for this instance? [8443]: 
        Is this an instance of volttron central? [N]: y
        Configuring /home/<user>/volttron/services/core/VolttronCentral.
        Enter volttron central admin user name: admin
        Enter volttron central admin password:
        Retype password:
        Installing volttron central.
        Should the agent autostart? [N]: y
        Will this instance be controlled by volttron central? [Y]: 
        Configuring /home/<user>/volttron/services/core/VolttronCentralPlatform.
        What is the name of this instance? [volttron1]: 
        What is the hostname for volttron central? [https://<localhost>]: 
        What is the port for volttron central? [8443]: 
        Should the agent autostart? [N]: y
        Would you like to install a platform historian? [N]: y
        Configuring /home/<user>/volttron/services/core/SQLHistorian.
        Should the agent autostart? [N]: y
        Would you like to install a master driver? [N]: y
        Configuring /home/<user>/volttron/services/core/MasterDriverAgent.
        Would you like to install a fake device on the master driver? [N]: y
        Should the agent autostart? [N]: y
        Would you like to install a listener agent? [N]: y
        Configuring examples/ListenerAgent.
        Should the agent autostart? [N]: y
        Finished configuration!

        You can now start the volttron instance.

        If you need to change the instance configuration you can edit
        the config file is at /home/<user>/.volttron/config

