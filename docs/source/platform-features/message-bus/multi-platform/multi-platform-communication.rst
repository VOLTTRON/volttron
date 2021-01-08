 .. _Multi-Platform-Communication:

============================
Multi-Platform Communication
============================

To connect to remote VOLTTRON platforms, we would need platform discovery information of the remote platforms. This
information contains the platform name, :term:`VIP` address and `serverkey` of the remote platforms and we need to
provide this as part of multi-platform configuration.


Configuration
*************

The configuration and authentication for multi-platform connection can be setup either manually or by running the
platforms in set up mode.  Both the setups are described below.


Setup Mode For Automatic Authentication
***************************************

.. note::

    It is necessary for each platform to have a web server if running in setup mode.

For ease of use and to support multi-scale deployment, the process of obtaining the platform discovery information and
authenticating the new platform connection is automated.  We can now bypass the manual process of adding auth keys
(i.e., either by using the `volttron-ctl` utility or directly updating the `auth.json` config file).

A config file containing list of web addresses (one for each platform) need to be made available in :term:`VOLTTRON_HOME`
directory.

Name of the file: `external_address.json`

Directory path:   Each platform’s VOLTTRON_HOME directory.

For example: `/home/volttron/.volttron1`

Contents of the file:

::

        [
        "http://<ip1>:<port1>",
        "http://<ip2>:<port2>",
        "http://<ip3>:<port3>",
         ......
        ]


We then start each VOLTTRON platform with setup mode option in this way.

.. code-block:: bash

    volttron -vv -l volttron.log --setup-mode&

Each platform will obtain the platform discovery information of the remote platform that it is trying to connect through
a HTTP discovery request and store the information in a configuration file
(`$VOLTTRON_HOME/external_platform_discovery.json`). It will then use the :term:`VIP address` and `serverkey` to connect
to the remote platform.  The remote platform shall authenticate the new connection and store the auth keys (public key)
of the connecting platform for future use.

The platform discovery information will be stored in `VOLTTRON_HOME` directory and looks like below:

Name of config file: `external_platform_discovery.json`

Contents of the file:

::

    {"<platform1 name>": {"vip-address":"tcp://<ip1>:<vip port1>",
                         "instance-name":"<platform1 name>",
                         "serverkey":"<serverkey1>"
                         },
     "<platform2 name>": {"vip-address":"tcp://<ip2>:<vip port2>",
                         "instance-name":"<platform2 name>",
                         "serverkey":"<serverkey2>"
                         },
     "<platform3 name>": {"vip-address":"tcp://<ip3>:<vip port3>",
                         "instance-name":"<platform3 name>",
                         "serverkey":"<serverkey3>"
                         },
      ......
    }

Each platform will use this information for future connections.

Once the keys have been exchanged and stored in the auth module, we can restart all the VOLTTRON platforms in normal
mode.

.. code-block:: bash

    ./stop-volttron
    ./start-volttron


Manual Configuration of External Platform Information
*****************************************************

Platform discovery configuration file can also be built manually and it needs to be added inside `VOLTTRON_HOME`
directory of each platform.

Name of config file: `external_platform_discovery.json`

Contents of the file:

::

    {"<platform1 name>": {"vip-address":"tcp://<ip1>:<vip port1>",
                         "instance-name":"<platform1 nam>",
                         "serverkey":"<serverkey1>"
                         },
     "<platform2 name>": {"vip-address":"tcp://<ip2>:<vip port2>",
                         "instance-name":"<platform2 name>",
                         "serverkey":"<serverkey2>"
                         },
     "<platform3 name>": {"vip-address":"tcp://<ip3>:<vip port3>",
                         "instance-name":"<platform3 name>",
                         "serverkey":"<serverkey3>"
                         },
     ......
    }

With this configuration, platforms can be started in normal mode.

.. code-block:: bash

    ./start-volttron

For external platform connections to be authenticated, we would need to add the credentials of the connecting platforms
in each platform using the `volttron-ctl auth` utility. For more details
:ref:`Agent authentication walk-through <Agent-Authentication>`.

.. seealso::

    :ref:`Multi-Platform Walk-through <Multi-Platform-Deployment>`


.. toctree::
    :caption: Multi-platform Message Bus Topics

    pubsub-remote-platforms
    multi-platform-rpc
    multi-platform-rabbit/multi-platform-rabbitmq
    multi-platform-rabbit/agent-communication-rabbitmq
