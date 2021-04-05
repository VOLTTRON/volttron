.. _Platform-Configuration:

======================
Platform Configuration
======================

Each instance of the VOLTTRON platform includes a `config` file which is used to configure the platform instance on
startup.  This file is kept in :term:`VOLTTRON_HOME` and is created using the `volttron-cfg` (`vcfg`) command, or will
be created with default values on start up of the platform otherwise.

Following is helpful information about the `config` file and the `vcfg` command.


VOLTTRON_HOME
=============

By default, the VOLTTRON project bases its files out of `VOLTTRON_HOME` which defaults to `~/.volttron`.  This directory
features directories and files used by the platform for important operation and management tasks as well as containing
packaged agents and their individual runtime environments (including data directories, identity files, etc.)

- **$VOLTTRON_HOME/agents** - contains the agents installed on the platform
- **$VOLTTRON_HOME/auth.json** - file containing authentication and authorization rules for agents connecting to the
  VOLTTRON instance.
- **$VOLTTRON_HOME/certificates** - contains the certificates for use with the Licensed VOLTTRON code.
- **$VOLTTRON_HOME/configuration_store** - agent configuration store files are stored in this directory.  Each agent
  may have a file here in which JSON representations of their stored configuration files are stored.
- **$VOLTTRON_HOME/run** - contains files create by the platform during execution.  The main ones are the ZMQ files
  created for publish and subscribe functionality.
- **$VOLTTRON_HOME/ssh** - keys used by agent mobility in the Licensed VOLTTRON code
- **$VOLTTRON_HOME/config** - Default location to place a config file to override any platform settings.
- **$VOLTTRON_HOME/packaged** - agent packages created with `volttron-pkg` are created in this directory
- **$VOLTTRON_HOME/VOLTTRON_PID** - File containing the Unix process ID for the VOLTTRON platform - used for tracking
  platform status.


.. _Platform-Config-File:

VOLTTRON Config File
====================

The `config` file in `VOLTTRON_HOME` is the config file used by the platform.  This configuration file specifies the
behavior of the platform at runtime, including which message bus it uses, the name of the platform instance, and the
address bound to by :term:`VIP`.  The `VOLTTRON Config`_ wizard (explained below) can be used to configure an instance
for the first time.  The user may run the wizard again or edit the config file directly as necessary for operations.
The following is a simple  example `config` for a multi-platform deployment:

::

    [volttron]
    message-bus = zmq
    vip-address = tcp://127.0.0.1:22916
    bind-web-address = <web service bind address>
    web-ssl-cert = <VOLTTRON_HOME>/certificates/certs/platform_web-server.crt
    web-ssl-key = <VOLTTRON_HOME>/certificates/private/platform_web-server.pem
    instance-name = volttron1
    volttron-central-address = <VC address>

The example consists of the following entries:

* **message-bus** - message bus being used for this instance (rmq/zmq)
* **vip-address** - address bound to by VIP for message bus communication
* **bind-web-address** - Optional, needed if platform has to support web feature. Represents address bound to by the
  platform web service for handling HTTP(s) requests.  Typical address would be ``https://<hostname>:8443``
* **web-ssl-cert** - Optional, needed if platform has to support web feature. Represents path to the certificate for the
  instance's web service
* **web-ssl-key** - Optional, needed if platform has to support web feature. Represents secret key or path to secret key
  file used by web service authenticate requests
* **instance-name** - name of this VOLTTRON platform instance, should be unique for the deployment
* **volttron-central-address** - Optional, needed if instance is running Volttron Central.  Represents web address of
  VOLTTRON Central agent managing this platform instance.  Typical address would be ``https://<hostname>:8443``

   
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
        Would you like to install a platform driver? [N]: y
        Configuring /home/user/volttron/services/core/PlatformDriverAgent.
        ['volttron', '-vv', '-l', '/home/user/.volttron/volttron.cfg.log']
        Would you like to**install a fake device on the platform driver? [N]: y
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
------------------

  - **-v, --verbose** - Enables verbose output in standard-output (PIP output, etc.)
  - **--vhome VHOME** - Provide a path to set `VOLTTRON_HOME` for this instance
  - **--instance-name INSTANCE_NAME** - Provide a name for this instance.  Required for running secure agents mode
  - **--list-agents** - Display a list of configurable agents (Listener, Platform Driver, Platform Historian, VOLTTRON
    Central, VOLTTRON Central Platform)
  - **--agent AGENT [AGENT ...]** - Configure listed agents
  - **--secure-agent-users** - Require that agents run as their own Unix users (this requires running
    `scripts/secure_user_permissions.sh` as `sudo`)

RabbitMQ Arguments
------------------
vcfg command to configure a single RabbitMQ instance of VOLTTRON.

        Usage:

        .. code-block:: bash

            vcfg rabbitmq single --config [Optional path to rabbitmq config file]``

vcfg command to configure a federation instance of RabbitMQ VOLTTRON.

        Usage:

        .. code-block:: bash

            vcfg rabbitmq single --config [Optional path to rabbitmq federation config file] --max-retries [Optional maximum CSR retry attempt]``

vcfg command to create shovel to send messages from one RabbitMQ instance of VOLTTRON to another.

        Usage:

        .. code-block:: bash

            vcfg rabbitmq single --config [Optional path to shovel config file] --max-retries [Optional maximum CSR retry attempt]``
