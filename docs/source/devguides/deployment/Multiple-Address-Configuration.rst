Platform External Address Configuration
=======================================

In the configuration file located in $VOLTTRON\_HOME/config add
vip-address=tcp://ip:port for each address you want to listen on

::

    Example
    vip-address=tcp://127.0.0.102:8182
    vip-address=tcp://127.0.0.103:8083
    vip-address=tcp://127.0.0.103:8183


.. note:: The config file is generated after running the vcfg command. The vip-address is for the local platform, NOT the remote platform.
