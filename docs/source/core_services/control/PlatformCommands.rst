.. _PlatformCommands:
Platform Commands
-----------------

With the exception of packaged agent wheel files, all VOLTTRON files for
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

::

    bin/volttron -c config.ini -l volttron.log

Full options:

::

    optional arguments:
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

volttron-ctl commands:

::

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
    shutdown            stop all agents
          with Volttron Restricted package installed and enabled
    send                send mobile agent to and start on a remote platform

| volttron-pkg commands:
|  usage: volttron-pkg [-h] {package,repackage,configure} ...

::

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

volttron-pkg commands (with Volttron Restricted package installed and
enabled):

::

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

