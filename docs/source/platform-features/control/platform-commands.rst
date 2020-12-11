.. _Platform-Commands:

=================
Platform Commands
=================

VOLTTRON files for a platform instance are stored under a single directory known as the VOLTTRON home.  This home
directory is set via the :term:`VOLTTRON_HOME` environment variable and defaults to ``~/.volttron``.  Multiple instances
of the platform may exist under the same account on a system by setting the `VOLTTRON_HOME` environment variable
appropriately before executing VOLTTRON commands.

VOLTTRON's configuration file uses a modified INI format where section names are command names for which the settings in
the section apply.  Settings before the first section are considered global and will be used by all commands for which
the settings are valid.  Settings keys are long options (with or without the opening "--") and are followed by a colon
(``:``) or equal (``=``) and then the value.  Boolean options need not include the separator or value, but may specify a
value of ``1``, ``yes``, or ``true`` for `true` or ``0``, ``no``, or ``false`` for `false`.

It is best practice to use the :ref:`vcfg command <VOLTTRON-Config>` prior to starting VOLTTRON for the first time to
populate the configuration file for your deployment.  If VOLTTRON is started without having run `vcfg`, a default config
will be created in `$VOLTTRON_HOME/config`.  The following is an example configuration after running `vcfg`:

.. code-block::

    [volttron]
    message-bus = rmq
    instance-name = volttron1
    vip-address = tcp://127.0.0.1:22916
    bind-web-address = https://<hostname>:8443
    volttron-central-address = https://<hostname>:8443

where:

* **message-bus** - Indicates message bus to be used. Valid values are ``zmq`` and ``rmq``
* **instance-name** - Name of the VOLTTRON instance. This has to be unique if multiple instances need to be connected
  together
* **vip-address** - :term:`VIP address` of the VOLTTRON instance. It contains the IP address and port number (default
  port number is 22916)
* **bind-web-address** - Optional parameter, only needed if VOLTTRON instance needs a web interface
* **volttron-central-address** - Optional parameter. Web address of VOLTTRON Central agent

.. note::



    .. code-block:: bash
    
        env/bin/volttron -c <config> -l volttron.log &

Below is a compendium of commands which can be used to operate the VOLTTRON Platform from the command line interface.


VOLTTRON Platform Command
=========================

The main VOLTTRON platform command is ``volttron``, however this command is seldom run as-is.  In most cases the user
will want to run the platform in the background.  In a limited number of cases, the user will wish to enable verbose
logging.  A typical command to start the platform is:

.. note::

    * All commands and sub-commands have help available with ``-h`` or ``--help``
    * Additional configuration files may be specified with ``-c`` or ``-config``
    * To specify a log file, use ``-l`` or ``--log``
    * The ampersand (``&``) can be added to then end of the command to run the platform in the background, freeing the
      open shell to be used for additional commands.

.. code-block:: bash

    volttron -vv -l volttron.log &


volttron Optional Arguments
---------------------------

- **-c FILE, --config FILE** - Start the platform using the configuration from the provided FILE
- **-l FILE, --log FILE** - send log output to FILE instead of standard output/error
- **-L FILE, --log-config FILE** - Use the configuration from FILE for VOLTTRON platform logging
- **--log-level LOGGER:LEVEL** - override default logger logging level (`INFO`, `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`,
  `NOTSET`)
- **--monitor** - monitor and log connections (implies verbose logging mode ``-v``)
- **-q, --quiet** - decrease logger verboseness; may be used multiple times to further reduce logging (i.e. ``-qq``)
- **-v, --verbose** - increase logger verboseness; may be used multiple times (i.e. ``-vv``)
- **--verboseness LEVEL** - set logger verboseness level
- **-h, --help** - show this help message and exit
- **--version** - show program's version number and exit
- **--message-bus MESSAGE_BUS** - set message bus to be used. valid values are ``zmq`` and ``rmq``

.. note::

    Visit the Python 3 logging documentation for more information about
    `logging and verboseness levels <https://docs.python.org/3/library/logging.html#logging-levels>`_.


Agent Options
-------------

- **--autostart** - automatically start enabled agents and services after platform startup
- **--vip-address ZMQADDR** - ZeroMQ URL to bind for VIP connections
- **--vip-local-address ZMQADDR** - ZeroMQ URL to bind for local agent VIP connections
- **--bind-web-address BINDWEBADDR** - Bind a web server to the specified ip:port passed
- **--web-ca-cert CAFILE** - If using self-signed certificates, this variable will be set globally to allow requests to
  be able to correctly reach the webserver without having to specify verify in all calls.
- **--web-secret-key WEB_SECRET_KEY** - Secret key to be used instead of HTTPS based authentication.
- **--web-ssl-key KEYFILE** - SSL key file for using https with the VOLTTRON server
- **--web-ssl-cert CERTFILE** - SSL certificate file for using https with the VOLTTRON server
- **--volttron-central-address VOLTTRON_CENTRAL_ADDRESS** - The web address of a VOLTTRON Central install instance.
- **--volttron-central-serverkey VOLTTRON_CENTRAL_SERVERKEY** - The server key of the VOLTTRON Central being connected
  to.
- **--instance-name INSTANCE_NAME** - The name of the instance that will be reported to VOLTTRON Central.
- **--msgdebug** - Route all messages to an instance of the MessageDebug agent while debugging.
- **--setup-mode** - Setup mode flag for setting up authorization of external platforms.
- **--volttron-central-rmq-address VOLTTRON_CENTRAL_RMQ_ADDRESS** - The AMQP address of a VOLTTRON Central install
  instance
- **--agent-monitor-frequency AGENT_MONITOR_FREQUENCY** - How often should the platform check for crashed agents
  and attempt to restart. Units=seconds. Default=600
- **--secure-agent-users SECURE_AGENT_USERS** - Require that agents run with their own users (this requires running
  scripts/secure_user_permissions.sh as sudo)

.. warning::

   Certain options alter some basic behaviors of the platform, such as `--secure-agent-users` which causes the platform
   to run each agent using its own Unix user to spawn the process.  Please view the documentation for each feature to
   understand its implications before choosing to run the platform in that fashion.


volttron-ctl Commands
=====================

`volttron-ctl` is used to issue commands to the platform from the command line.  Through `volttron-ctl` it is possible
to install and removed agents, start and stop agents, manage the configuration store, get the platform status, and
shutdown the platform.

In more recent versions of VOLTTRON, the commands `vctl`, `vpkg`, and `vcfg` have been added to be used as a stand-in
for `volttron-ctl`, `volttron-pkg`, and `volttron-cfg` in the CLI.  The VOLTTRON documentation will often use this
convention.

.. warning::

    `vctl` creates a special temporary agent to communicate with the platform with a specific :term:`VIP Identity`, thus
    multiple instances of `vctl` cannot run at the same time.  Attempting to do so will result in a conflicting
    identity error.

Use `vctl` with one or more of the following arguments, or below sub-commands:


vctl Optional Arguments
-----------------------

- **-c FILE, --config FILE** - Start the platform using the configuration from the provided FILE
- **--debug** - show tracebacks for errors rather than a brief message
- **-t SECS, --timeout SECS** - timeout in seconds for remote calls (default: 60)
- **--msgdebug MSGDEBUG** - route all messages to an agent while debugging
- **--vip-address ZMQADDR** - ZeroMQ URL to bind for VIP connections
- **-l FILE, --log FILE** - send log output to FILE instead of standard output/error
- **-L FILE, --log-config FILE** - Use the configuration from FILE for VOLTTRON platform logging
- **-q, --quiet** - decrease logger verboseness; may be used multiple times to further reduce logging (i.e. ``-qq``)
- **-v, --verbose** - increase logger verboseness; may be used multiple times (i.e. ``-vv``)
- **--verboseness LEVEL** - set logger verboseness level (this level is a numeric level co
- **--json** - format output to json
- **-h, --help** - show this help message and exit


Commands
--------

- **install** - install an agent from wheel

    .. note::

       Does *NOT* package agents similarly to the `scripts/install-agent.py` script; installs agents from wheel files
       only

- **tag AGENT TAG** - set, show, or remove agent tag for a particular agent
- **remove AGENT** - disconnect specified agent from the platform and remove its installed agent package from `VOLTTRON_HOME`
- **peerlist** - list the peers connected to the platform
- **list** - list installed agents
- **status** - show status of installed agents
- **health AGENT** - show agent health as JSON
- **clear** - clear status of defunct agents
- **enable AGENT** - enable agent to start automatically
- **disable AGENT** - prevent agent from start automatically
- **start AGENT** - start installed agent
- **stop AGENT** - stop agent
- **restart AGENT** - restart agent
- **run PATH** - start any agent by path
- **upgrade AGENT WHEEL** - upgrade agent from wheel file

    .. note::

       Does *NOT* upgrade agents from the agent's code directory, requires agent wheel file.

- **rpc** - rpc controls
- **certs OPTIONS** - manage certificate creation
- **auth OPTIONS** - manage authorization entries and encryption keys
- **config OPTIONS** - manage the platform configuration store
- **shutdown** - stop all agents (providing the `--platform` optional argument causes the platform to be shutdown)
- **send WHEEL** - send agent and start on a remote platform
- **stats** - manage router message statistics tracking
- **rabbitmq OPTIONS** - manage rabbitmq

.. note::

   For each command with `OPTIONS` in the description, additional options are required to make use of the command.  For
   each, please visit the corresponding section of documentation.

    * :ref:`Auth <VCTL-Auth-Commands>`
    * :ref:`Certs <VCTL-Certs-Commands>`
    * :ref:`Config <VCTL-Config-Commands>`
    * :ref:`RPC <VCTL-RPC-Commands>`

.. note::

    Visit the Python 3 logging documentation for more information about
    `logging and verboseness levels <https://docs.python.org/3/library/logging.html#logging-levels>`_.


.. _VCTL-Auth-Commands:

vctl auth Subcommands
^^^^^^^^^^^^^^^^^^^^^

- **add** - add new authentication record
- **add-group** - associate a group name with a set of roles
- **add-known-host** - add server public key to known-hosts file
- **add-role** - associate a role name with a set of capabilities
- **keypair** - generate CurveMQ keys for encrypting VIP connections
- **list** - list authentication records
- **list-groups** - show list of group names and their sets of roles
- **list-known-hosts** - list entries from known-hosts file
- **list-roles** - show list of role names and their sets of capabilities
- **publickey** - show public key for each agent
- **remove** - removes one or more authentication records by indices
- **remove-group** - disassociate a group name from a set of roles
- **remove-known-host** - remove entry from known-hosts file
- **remove-role** - disassociate a role name from a set of capabilities
- **serverkey** - show the serverkey for the instance
- **update** - updates one authentication record by index
- **update-group** - update group to include (or remove) given roles
- **update-role** - update role to include (or remove) given capabilities


.. _VCTL-Certs-Commands:

vctl certs Subcommands
^^^^^^^^^^^^^^^^^^^^^^

- **create-ssl-keypair** - create a SSL keypair
- **export-pkcs12** - create a PKCS12 encoded file containing private and public key from an agent.  This function is
  may also be used to create a Java key store using a p12 file.


.. _VCTL-Config-Commands:

vctl config Subcommands
^^^^^^^^^^^^^^^^^^^^^^^

- **store AGENT CONFIG_NAME CONFIG PATH** - store a configuration file in agent's config store (parses JSON by default,
  use `--csv` for CSV files)
- **edit AGENT CONFIG_NAME** - edit a configuration. (opens nano by default, respects EDITOR env variable)
- **delete AGENT CONFIG_NAME** - delete a configuration from agent's config store (`--all` removes all configs for the
  agent)
- **list AGENT** - list stores or configurations in a store
- **get AGENT CONFIG_NAME** - get the contents of a configuration


.. _VCTL-RPC-Commands:

vctl rpc Subcommands
^^^^^^^^^^^^^^^^^^^^

- **code** - shows how to use RPC call in other agents
- **list** - lists all agents and their RPC methods


vpkg Commands
=============

`vpkg` is the VOLTTRON command used to manage agent packages (code directories and wheel files) including creating
initializing new agent code directories, creating agent wheels, etc.


vpkg Optional Arguments
-----------------------

- **-h, --help** - show this help message and exit
- **-l FILE, --log FILE** - send log output to FILE instead of standard output/error
- **-L FILE, --log-config FILE** - Use the configuration from FILE for VOLTTRON platform logging
- **-q, --quiet** - decrease logger verboseness; may be used multiple times to further reduce logging (i.e. ``-qq``)
- **-v, --verbose** - increase logger verboseness; may be used multiple times (i.e. ``-vv``)
- **--verboseness LEVEL** - set logger verboseness level


Subcommands
-----------

- **package** - Create agent package (whl) from a directory
- **init** - Create new agent code package from a template.  Will prompt for additional metadata.
- **repackage** - Creates agent package from a currently installed agent.
- **configure** - Add a configuration file to an agent package


volttron-cfg Commands
=====================

`volttron-cfg` (`vcfg`) is a tool aimed at making it easier to get up and running with VOLTTRON and a handful of agents.
Running the tool without any arguments will start a *wizard* with a walk through for setting up instance configuration
options and available agents.  If only individual agents need to be configured they can be listed at the command line.

.. note::

    For a detailed description of the VOLTTRON configuration file and `vcfg` wizard, as well as example usage, view the
    :ref:`platform configuration <Platform-Configuration>` docs.

vcfg Optional Arguments
-----------------------

- **-h, --help** - show this help message and exit
- **-v, --verbose** - increase logger verboseness; may be used multiple times (i.e. ``-vv``)
- **--vhome VHOME**         Path to volttron home
- **--instance-name INSTANCE_NAME**
                        Name of this volttron instance
- **--list-agents** - list configurable agents

  .. code-block:: console

     Agents available to configure:
        listener
        master_driver
        platform_historian
        vc
        vcp

- **--agent AGENT [AGENT ...]** - configure listed agents
- **--rabbitmq RABBITMQ [RABBITMQ ...]** - Configure RabbitMQ for single instance, federation, or shovel either based on
  configuration file in YML format or providing details when prompted.  Usage:

  .. code-block:: bash

     vcfg --rabbitmq single|federation|shovel [rabbitmq config file]

- **--secure-agent-users**  Require that agents run with their own users (this requires running
  scripts/secure_user_permissions.sh as sudo)

  .. warning::

     The secure agent users significantly changes the operation of agents on the platform, please read the
     :ref:`secure agent users <Running-Agents-as-Unix-User>` documentation before using this feature.
