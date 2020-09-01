.. _Platform-Configuration:

====================
VOLTTRON Environment
====================

By default, the VOLTTRON projects bases its files out of `VOLTTRON_HOME`
which defaults to `~/.volttron`.

-  ``$VOLTTRON_HOME/agents`` contains the agents installed on the
   platform
-  ``$VOLTTRON_HOME/certificates`` contains the certificates for use
   with the Licensed VOLTTRON code.
-  ``$VOLTTRON_HOME/run`` contains files create by the platform during
   execution. The main ones are the 0MQ files created for publish and
   subcribe.
-  ``$VOLTTRON_HOME/ssh`` keys used by agent mobility in the Licensed
   VOLTTRON code
-  ``$VOLTTRON_HOME/config`` Default location to place a config file to
   override any platform settings.
-  ``$VOLTTRON_HOME/packaged`` is where agent packages created with `volttron-pkg` are created


.. _Platform-Config-File:

VOLTTRON Config File
====================

The VOLTTRON platform config file can contain any of the command line arguments for starting the platform...

.. code-block:: console

       -c FILE, --config FILE
                        read configuration from FILE
       -l FILE, --log FILE   send log output to FILE instead of stderr
       -L FILE, --log-config FILE
                        read logging configuration from FILE
       -q, --quiet           decrease logger verboseness; may be used multiple
                        times
       -v, --verbose         increase logger verboseness; may be used multiple
                        times
       --verboseness LEVEL   set logger verboseness
       --help                show this help message and exit
       --version             show program's version number and exit

agent options:

.. code-block:: console

       --autostart           automatically start enabled agents and services
       --publish-address ZMQADDR
                            ZeroMQ URL for used for agent publishing
       --subscribe-address ZMQADDR
                            ZeroMQ URL for used for agent subscriptions

control options:

.. code-block:: console

       --control-socket FILE
                             path to socket used for control messages
       --allow-root          allow root to connect to control socket
       --allow-users LIST    users allowed to connect to control socket
       --allow-groups LIST   user groups allowed to connect to control socket

Boolean options, which take no argument, may be inverted by prefixing the option with no '-' (e.g. ``--autostart`` may
be inverted using ``--no-autostart``).


.. _VOLTTRON-Config:

VOLTTRON Config
===============

The new volttron-cfg (vcfg) commands allows for the easy configuration of a
VOLTTRON platform. This includes setting up the platform configuration,
historian, VOLTTRON Central UI, and platform agent.

example vcfg output:

.. note::

        - In this example, <user> represents the user's home directory, and <localhost> represents the machine's localhost.
        - If an option was not specified during bootstrapping i.e. "--web", "--rabbitmq", or "--driver", and an option is
          selected during the vcfg wizard that requires that option, the necessary dependencies will be installed automatically.

.. code-block:: console

        Your VOLTTRON_HOME currently set to: /home/<user>/.volttron

        Is this the volttron you are attempting to setup? [Y]:
        What type of message bus (rmq/zmq)? [zmq]: rmq
        Name of this volttron instance: [volttron1]:
        RabbitMQ server home: [/home/<user>/rabbitmq_server/rabbitmq_server-3.7.7]:
        Fully qualified domain name of the system: [<localhost>]:
        Would you like to create a new self signed root CAcertificate for this instance: [Y]:

        Please enter the following details for root CA certificate
            Country: [US]:
            State: WA
            Location: Richland
            Organization: PNNL
            Organization Unit: VOLTTRON
        Do you want to use default values for RabbitMQ home, ports, and virtual host: [Y]:
        A rabbitmq conf file /home/<user>/rabbitmq_server/rabbitmq_server-3.7.7/etc/rabbitmq/rabbitmq.conf already exists.
        In order for setup to proceed it must be removed.

        Remove /home/<user>/rabbitmq_server/rabbitmq_server-3.7.7/etc/rabbitmq/rabbitmq.conf?  y
        2020-04-13 13:29:36,347 rmq_setup.py INFO: Starting RabbitMQ server
        2020-04-13 13:29:46,528 rmq_setup.py INFO: Rmq server at /home/<user>/rabbitmq_server/rabbitmq_server-3.7.7 is running at
        2020-04-13 13:29:46,554 volttron.utils.rmq_mgmt DEBUG: Creating new VIRTUAL HOST: volttron
        2020-04-13 13:29:46,582 volttron.utils.rmq_mgmt DEBUG: Create READ, WRITE and CONFIGURE permissions for the user: volttron1-admin
        Create new exchange: volttron, {'durable': True, 'type': 'topic', 'arguments': {'alternate-exchange': 'undeliverable'}}
        Create new exchange: undeliverable, {'durable': True, 'type': 'fanout'}
        2020-04-13 13:29:46,600 rmq_setup.py INFO:
        Checking for CA certificate

        2020-04-13 13:29:46,601 rmq_setup.py INFO:
         Creating root ca for volttron instance: /home/<user>/.volttron/certificates/certs/volttron1-root-ca.crt
        2020-04-13 13:29:46,601 rmq_setup.py INFO: Creating root ca with the following info: {'C': 'US', 'ST': 'WA', 'L': 'Richland', 'O': 'PNNL', 'OU': 'VOLTTRON', 'CN': 'volttron1-root-ca'}
        Created CA cert
        2020-04-13 13:29:49,668 rmq_setup.py INFO: **Stopped rmq server
        2020-04-13 13:30:00,556 rmq_setup.py INFO: Rmq server at /home/<user>/rabbitmq_server/rabbitmq_server-3.7.7 is running at
        2020-04-13 13:30:00,557 rmq_setup.py INFO:

        #######################

        Setup complete for volttron home /home/<user>/.volttron with instance name=volttron1
        Notes:
         - On production environments, restrict write access to /home/<user>/.volttron/certificates/certs/volttron1-root-ca.crt to only admin user. For example: sudo chown root /home/<user>/.volttron/certificates/certs/volttron1-root-ca.crt and /home/<user>/.volttron/certificates/certs/volttron1-trusted-cas.crt
         - A new admin user was created with user name: volttron1-admin and password=default_passwd.
           You could change this user's password by logging into https://<localhost>:15671/ Please update /home/<user>/.volttron/rabbitmq_config.yml if you change password

        #######################

        The rmq message bus has a backward compatibility
        layer with current zmq instances. What is the
        zmq bus's vip address? [tcp://127.0.0.1]:
        What is the port for the vip address? [22916]:
        Is this instance web enabled? [N]: y
        Web address set to: https://<localhost>
        What is the port for this instance? [8443]:
        Is this an instance of volttron central? [N]: y
        Configuring /home/<user>/volttron/services/core/VolttronCentral.
        Installing volttron central.
        ['volttron', '-vv', '-l', '/home/<user>/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        VC admin and password are set up using the admin web interface.
        After starting VOLTTRON, please go to https://<localhost>:8443/admin/login.html to complete the setup.
        Will this instance be controlled by volttron central? [Y]:
        Configuring /home/<user>/volttron/services/core/VolttronCentralPlatform.
        What is the name of this instance? [volttron1]:
        Volttron central address set to https://<localhost>:8443
        ['volttron', '-vv', '-l', '/home/<user>/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Would you like to install a platform historian? [N]: y
        Configuring /home/<user>/volttron/services/core/SQLHistorian.
        ['volttron', '-vv', '-l', '/home/<user>/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Would you like to install a master driver? [N]: y
        Configuring /home/<user>/volttron/services/core/MasterDriverAgent.
        ['volttron', '-vv', '-l', '/home/<user>/.volttron/volttron.cfg.log']
        Would you like to install a fake device on the master driver? [N]: y
        Should the agent autostart? [N]: y
        Would you like to install a listener agent? [N]: y
        Configuring examples/ListenerAgent.
        ['volttron', '-vv', '-l', '/home/<user>/.volttron/volttron.cfg.log']
        Should the agent autostart? [N]: y
        Finished configuration!

        You can now start the volttron instance.

        If you need to change the instance configuration you can edit
        the config file is at /home/<user>/.volttron/config
