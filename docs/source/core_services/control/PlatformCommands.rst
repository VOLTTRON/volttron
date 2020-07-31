.. _PlatformCommands:

Platform Commands
=================

VOLTTRON files for
a platform instance are stored under a single directory known as the
VOLTTRON home. This home directory is set via the VOLTTRON\_HOME
environment variable and defaults to ~/.volttron. Multiple instances of
the platform may exist under the same account on a system by setting the
VOLTTRON\_HOME environment variable appropriately before executing
VOLTTRON commands.

Configuration files use a modified INI format where section names are
command names for which the settings in the section apply. Settings
before the first section are considered global and will be used by all
commands for which the settings are valid. Settings keys are long
options (with or without the opening --) and are followed by a colon (:)
or equal (=) and then the value. Boolean options need not include the
separator or value, but may specify a value of 1, yes, or true for true
or 0, no, or false for false.

A default configuration file, $VOLTTRON\_HOME/config, may be created to
override default options. If it exists, it will be automatically parsed
before all other command-line options. To skip parsing the default
configuration file, either move the file out of the way or set the
SKIP\_VOLTTRON\_CONFIG environment variable.

All commands and sub-commands have help available with "-h" or "--help".
Additional configuration files may be specified with "-c" or "--config".
To specify a log file, use "-l" or "--log".

.. code-block:: bash

    env/bin/volttron -c config.ini -l volttron.log

Full options:

.. code-block:: console

    VOLTTRON platform service

    optional arguments:
      -c FILE, --config FILE
                            read configuration from FILE
      -l FILE, --log FILE   send log output to FILE instead of stderr
      -L FILE, --log-config FILE
                            read logging configuration from FILE
      --log-level LOGGER:LEVEL
                            override default logger logging level
      --monitor             monitor and log connections (implies -v)
      -q, --quiet           decrease logger verboseness; may be used multiple
                            times
      -v, --verbose         increase logger verboseness; may be used multiple
                            times
      --verboseness LEVEL   set logger verboseness
      -h, --help            show this help message and exit
      --version             show program's version number and exit

    agent options:
      --autostart           automatically start enabled agents and services
      --publish-address ZMQADDR
                            ZeroMQ URL used for pre-3.x agent publishing
                            (deprecated)
      --subscribe-address ZMQADDR
                            ZeroMQ URL used for pre-3.x agent subscriptions
                            (deprecated)
      --vip-address ZMQADDR
                            ZeroMQ URL to bind for VIP connections
      --vip-local-address ZMQADDR
                            ZeroMQ URL to bind for local agent VIP connections
      --bind-web-address BINDWEBADDR
                            Bind a web server to the specified ip:port passed
      --volttron-central-address VOLTTRON_CENTRAL_ADDRESS
                            The web address of a volttron central install
                            instance.
      --volttron-central-serverkey VOLTTRON_CENTRAL_SERVERKEY
                            The serverkey of volttron central.
      --instance-name INSTANCE_NAME
                            The name of the instance that will be reported to
                            VOLTTRON central.

    Boolean options, which take no argument, may be inversed by prefixing the
    option with no- (e.g. --autostart may be inversed using --no-autostart).


volttron-ctl Commands
---------------------
volttron-ctl is used to issue commands to the platform from the command line. Through
volttron-ctl it is possible to install and removed agents, start and stop agents,
manage the configuration store, get the platform status, and shutdown the platform.

In more recent versions of VOLTTRON, the commands 'vctl', 'vpkg', and 'vcfg'
have been added to be used as a stand-in for 'volttron-ctl', 'volttron-pkg', and
'volttron-cfg' in the CLI. The VOLTTRON documentation will often use this convention.

.. warning::
    volttron-ctl creates a special temporary agent ito communicate with the
    platform with a specific VIP IDENTITY, thus multiple instances of volttron-ctl
    cannot run at the same time. Attempting to do so will result in a conflicting
    identity error.

.. code-block:: console

    usage: vctl command [OPTIONS] ...

    Manage and control VOLTTRON agents.

    optional arguments:
      -c FILE, --config FILE
                            read configuration from FILE
      --debug               show tracebacks for errors rather than a brief message
      -t SECS, --timeout SECS
                            timeout in seconds for remote calls (default: 60)
      --msgdebug MSGDEBUG   route all messages to an agent while debugging
      --vip-address ZMQADDR
                            ZeroMQ URL to bind for VIP connections
      -l FILE, --log FILE   send log output to FILE instead of stderr
      -L FILE, --log-config FILE
                            read logging configuration from FILE
      -q, --quiet           decrease logger verboseness; may be used multiple
                            times
      -v, --verbose         increase logger verboseness; may be used multiple
                            times
      --verboseness LEVEL   set logger verboseness
      -h, --help            show this help message and exit



    commands:

        install             install agent from wheel
        tag                 set, show, or remove agent tag
        remove              remove agent
        list                list installed agent
        status              show status of agents
        clear               clear status of defunct agents
        enable              enable agent to start automatically
        disable             prevent agent from start automatically
        start               start installed agent
        stop                stop agent
        restart             restart agent
        run                 start any agent by path
        auth                manage authorization entries and encryption keys
        config              manage the platform configuration store
        shutdown            stop all agents
        send                send agent and start on a remote platform
        stats               manage router message statistics tracking

vctl auth subcommands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

    subcommands:

        add                 add new authentication record
        add-known-host      add server public key to known-hosts file
        keypair             generate CurveMQ keys for encrypting VIP connections
        list                list authentication records
        publickey           show public key for each agent
        remove              removes one or more authentication records by indices
        serverkey           show the serverkey for the instance
        update              updates one authentication record by index

vctl config subcommands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

    subcommands:

        store               store a configuration
        delete              delete a configuration
        list                list stores or configurations in a store
        get                 get the contents of a configuration



vpkg Commands
---------------------

.. code-block:: console

    usage: volttron-pkg [-h] [-l FILE] [-L FILE] [-q] [-v] [--verboseness LEVEL]
                        {package,repackage,configure} ...

    optional arguments:
      -h, --help            show this help message and exit

    subcommands:
      valid subcommands

      {package,repackage,configure}
                        additional help
        package             Create agent package (whl) from a directory or
                        installed agent name.
        repackage           Creates agent package from a currently installed
                        agent.
        configure           add a configuration file to an agent package

vpkg commands (with Volttron Restricted package installed and
enabled):

.. code-block:: console

    usage: volttron-pkg [-h] [-l FILE] [-L FILE] [-q] [-v] [--verboseness LEVEL]
                        {package,repackage,configure,create_ca,create_cert,sign,verify}
                        ...

    VOLTTRON packaging and signing utility

    optional arguments:
      -h, --help            show this help message and exit
      -l FILE, --log FILE   send log output to FILE instead of stderr
      -L FILE, --log-config FILE
                            read logging configuration from FILE
      -q, --quiet           decrease logger verboseness; may be used multiple
                            times
      -v, --verbose         increase logger verboseness; may be used multiple
                            times
      --verboseness LEVEL   set logger verboseness

    subcommands:
      valid subcommands

      {package,repackage,configure,create_ca,create_cert,sign,verify}
                            additional help
        package             Create agent package (whl) from a directory or
                            installed agent name.
        repackage           Creates agent package from a currently installed
                            agent.
        configure           add a configuration file to an agent package
        sign                sign a package
        verify              verify an agent package

volttron-cfg Commands
---------------------
volttron-cfg (vcfg) is a tool aimed at making it easier to get up and running with
Volttron and a handful of agents. Running the tool without any arguments
will start a *wizard* with a walk through for setting up instance configuration
options and available agents.If only individual agents need to be configured
they can be listed at the command line.

.. code-block:: console

    usage: vcfg [-h] [--list-agents | --agent AGENT [AGENT ...]]

    optional arguments:
      -h, --help            show this help message and exit
      --list-agents         list configurable agents
                                listener
                                platform_historian
                                vc
                                vcp
      --agent AGENT [AGENT ...]
                            configure listed agents
