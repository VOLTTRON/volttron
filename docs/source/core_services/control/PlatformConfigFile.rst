.. _PlatformConfigFile:
VOLTTRON Config File
====================

The VOLTTRON platform config file can contain any of the command line
arguments for starting the platform...

::

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

::

       --autostart           automatically start enabled agents and services
       --publish-address ZMQADDR
                        ZeroMQ URL for used for agent publishing
       --subscribe-address ZMQADDR
                        ZeroMQ URL for used for agent subscriptions

control options:

::

       --control-socket FILE
                        path to socket used for control messages
       --allow-root          allow root to connect to control socket
       --allow-users LIST    users allowed to connect to control socket
       --allow-groups LIST   user groups allowed to connect to control socket

| Boolean options, which take no argument, may be inversed by prefixing
the
| option with no- (e.g. --autostart may be inversed using
--no-autostart).
