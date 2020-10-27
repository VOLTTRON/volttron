.. _Platform-Configuration:

======================
Platform Configuration
======================

Each instance of the VOLTTRON platform includes a `config` file which is used to configure the platform instance on
startup.  This file is kept in `VOLTTRON_HOME` and is created using the `volttron-cfg` (`vcfg`) command, or will be
created with default values on start up of the platform otherwise.

Following is helpful information about the `config` file and the `vcfg` command.


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

The `volttron-cfg` or `vcfg` command allows for an easy configuration of the VOLTTRON environment.  The command includes
the ability to set up the platform configuration, an instance of the platform historian, VOLTTRON Central UI, and
VOLTTRON Central Platform agent.

Running `vcfg` will create a `config` file in `VOLTTRON_HOME` which will be populated according to the answers to
prompts.  This process should be repeated for each platform instance, and can be re-run to reconfigure a platform
instance.

.. note::

   To create a simple instance of VOLTTRON, leave the default response, or select yes (y) if prompted for a yes or no
   response [Y/N].  You must choose a username and password for the VOLTTRON Central admin account if selected.

A set of example responses are included here (`username` is ``user``, `localhost` is ``volttron-pc``):

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


Optional Arguments
==================

  - **-v, --verbose** - Enables verbose output in standard-output (PIP output, etc.)
  - **--vhome VHOME** - Provide a path to set `VOLTTRON_HOME` for this instance
  - **--instance-name INSTANCE_NAME** - Provide a name for this instance.  Required for running secure agents mode
  - **--list-agents** - Display a list of configurable agents (Listener, Master Driver, Platform Historian, VOLTTRON
    Central, VOLTTRON Central Platform)
  - **--agent AGENT [AGENT ...]** - Configure listed agents
  - **--rabbitmq RABBITMQ [RABBITMQ ...]** - Configure rabbitmq for single instance, federation, or shovel either based
    on configuration file in yml format or providing details when prompted.

        Usage:

        .. code-block:: bash

            vcfg --rabbitmq single|federation|shovel [rabbitmq config file]``

  - **--secure-agent-users** - Require that agents run as their own Unix users (this requires running
    `scripts/secure_user_permissions.sh` as `sudo`)
